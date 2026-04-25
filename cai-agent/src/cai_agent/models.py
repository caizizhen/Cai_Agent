"""Provider 的 `/models` 列表拉取 + profile 健康检查（M6）。

`ping_profile` 对 profile 发起一次**非敏感**请求：
- 非 anthropic：GET `{base_url}/models`（OpenAI 兼容约定）
- anthropic：GET `{base_url}/v1/models`，使用 `x-api-key` + `anthropic-version`

返回结构化字典：`{profile_id, status, http_status, message}`，
`status ∈ {OK, AUTH_FAIL, TIMEOUT, RATE_LIMIT, NET_FAIL, ENV_MISSING, UNSUPPORTED}`。
"""
from __future__ import annotations

from typing import Any

import httpx

from cai_agent.config import Settings
from cai_agent.http_trust import effective_http_trust_env
from cai_agent.profiles import Profile, project_base_url


def fetch_models(
    settings: Settings,
    *,
    transport: httpx.BaseTransport | None = None,
) -> list[str]:
    """按当前激活 profile 的 provider 拉取模型 id 列表。

    - ``anthropic`` → ``GET {base}/v1/models``，使用 ``x-api-key`` + ``anthropic-version``；
    - 其余兼容 provider（openai / openai_compatible / azure_openai / copilot /
      ollama / lmstudio / vllm） → ``GET {base}/models``，使用 ``Authorization: Bearer``；

    未识别的 provider 回退走 OpenAI 兼容路径，以保持 S1 之前单一 ``[llm]`` 的行为。
    """
    active_id = getattr(settings, "active_profile_id", None)
    active_profile: Profile | None = None
    for p in getattr(settings, "profiles", ()) or ():
        if getattr(p, "id", None) == active_id:
            active_profile = p
            break

    provider = (
        (active_profile.provider if active_profile else None)
        or getattr(settings, "provider", None)
        or ""
    )
    provider = str(provider).strip().lower()

    base = str(getattr(settings, "base_url", "") or "").rstrip("/")
    api_key = getattr(settings, "api_key", "") or ""

    if provider == "anthropic":
        url = f"{base}/v1/models"
        anth_ver = (
            getattr(settings, "anthropic_version", None)
            or (active_profile.anthropic_version if active_profile else None)
            or "2023-06-01"
        )
        headers = {
            "x-api-key": api_key,
            "anthropic-version": anth_ver,
            "content-type": "application/json",
        }
    else:
        url = f"{base}/models"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    timeout = httpx.Timeout(connect=15.0, read=30.0, write=15.0, pool=15.0)
    client_kwargs: dict[str, Any] = {
        "timeout": timeout,
        "trust_env": effective_http_trust_env(
            trust_env=bool(getattr(settings, "http_trust_env", False)),
            request_url=url,
        ),
    }
    if transport is not None:
        client_kwargs["transport"] = transport
    with httpx.Client(**client_kwargs) as client:
        r = client.get(url, headers=headers)
    if r.status_code >= 400:
        raise RuntimeError(f"/models 请求失败: HTTP {r.status_code} body={r.text!r}")
    data: Any = r.json()
    rows = data.get("data")
    if not isinstance(rows, list):
        raise RuntimeError("/models 返回格式异常：缺少 data 数组")
    ids: list[str] = []
    for item in rows:
        if isinstance(item, dict):
            mid = item.get("id")
            if isinstance(mid, str) and mid.strip():
                ids.append(mid.strip())
    return sorted(set(ids))


def _ping_result(
    profile_id: str, status: str, message: str = "", http_status: int | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {"profile_id": profile_id, "status": status}
    if http_status is not None:
        out["http_status"] = http_status
    if message:
        out["message"] = message
    return out


def ping_profile(
    profile: Profile,
    *,
    trust_env: bool = False,
    timeout_sec: float = 10.0,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    """对单个 profile 做最小健康检查；不消耗 chat token。

    - `api_key_env` 已声明但环境未导出 → ``ENV_MISSING``（提示变量名，不泄漏值）；
    - 连接超时 / 读超时 → ``TIMEOUT``；
    - 其它网络错误 → ``NET_FAIL``；
    - HTTP 401/403 → ``AUTH_FAIL``；429 → ``RATE_LIMIT``；404 → ``UNSUPPORTED``；
      HTTP < 400 → ``OK``；其余视为 ``NET_FAIL``。
    """
    pid = profile.id
    if profile.api_key_env and profile.api_key_env_missing():
        return _ping_result(
            pid, "ENV_MISSING", f"环境变量 {profile.api_key_env} 未设置",
        )

    api_key = profile.resolve_api_key()
    base = project_base_url(profile)
    if profile.provider == "anthropic":
        url = f"{base.rstrip('/')}/v1/models"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": profile.anthropic_version or "2023-06-01",
            "content-type": "application/json",
        }
    elif profile.provider in (
        "openai",
        "openai_compatible",
        "azure_openai",
        "copilot",
        "ollama",
        "lmstudio",
        "vllm",
    ):
        url = f"{base.rstrip('/')}/models"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    else:
        return _ping_result(pid, "UNSUPPORTED", f"provider={profile.provider}")

    timeout = httpx.Timeout(
        connect=min(15.0, timeout_sec),
        read=timeout_sec,
        write=min(15.0, timeout_sec),
        pool=min(15.0, timeout_sec),
    )
    client_kwargs: dict[str, Any] = {
        "timeout": timeout,
        "trust_env": effective_http_trust_env(trust_env=trust_env, request_url=url),
    }
    if transport is not None:
        client_kwargs["transport"] = transport
    try:
        with httpx.Client(**client_kwargs) as client:
            r = client.get(url, headers=headers)
    except httpx.TimeoutException as e:
        return _ping_result(pid, "TIMEOUT", str(e))
    except httpx.HTTPError as e:
        return _ping_result(pid, "NET_FAIL", str(e))

    if r.status_code in (401, 403):
        return _ping_result(
            pid, "AUTH_FAIL", "HTTP 鉴权失败（检查 api_key 或 api_key_env）",
            http_status=r.status_code,
        )
    if r.status_code == 429:
        return _ping_result(
            pid, "RATE_LIMIT", "HTTP 429 rate limited",
            http_status=r.status_code,
        )
    if r.status_code == 404:
        return _ping_result(
            pid, "UNSUPPORTED", "HTTP 404：provider 不支持 /models 或 base_url 不正确",
            http_status=r.status_code,
        )
    if r.status_code >= 400:
        return _ping_result(
            pid, "NET_FAIL", f"HTTP {r.status_code}",
            http_status=r.status_code,
        )
    return _ping_result(pid, "OK", http_status=r.status_code)
