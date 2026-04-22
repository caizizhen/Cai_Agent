"""Anthropic `/v1/messages` 原生适配器（M10 骨架）。

契约与 ``cai_agent.llm.chat_completion`` 对齐：同签名、**共用** 该模块的 token
usage 计数器（避免多套统计口径），同 retry 表（429/502/503/504）及
``CAI_LLM_MAX_RETRIES``（见 ``cai_agent.llm.llm_max_retries``）。差异处：

- 请求 URL：``{base_url}/v1/messages``；若 ``base_url`` 已含 `/v1` 后缀会自动修剪。
- Headers：``x-api-key``、``anthropic-version``、``content-type``。
- Body 转换：
  * ``system`` 字段来自 ``role == "system"`` 消息的拼接（多条用 ``\\n\\n`` 合并）；
  * ``messages`` 里保留 ``user / assistant``；工具结果等 ``tool`` 角色以
    ``user`` 文本形式保留独立一轮，并加 ``[tool:<name>]`` 前缀方便模型识别；
  * ``max_tokens`` 必填（取 ``settings.anthropic_max_tokens`` 或 ``settings.max_tokens``，
    默认 4096）。
- 响应：``content`` 数组中取 ``type == "text"`` 的 ``text`` 拼接返回。

模块级 ``_DEFAULT_TRANSPORT`` 用于测试注入 ``httpx.MockTransport`` 做离线断言，
业务代码不要依赖该变量；传 ``transport=`` 关键字也可以（优先级更高）。
"""
from __future__ import annotations

import os
import time
from typing import Any

import httpx

from cai_agent import llm as _usage_mod


_RETRYABLE_STATUS = frozenset({429, 502, 503, 504})

# 测试注入点：若非 None 将作为默认 httpx.Client 的 transport。
_DEFAULT_TRANSPORT: httpx.BaseTransport | None = None


def _as_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for it in content:
            if isinstance(it, dict):
                t = it.get("text") or it.get("content")
                if isinstance(t, str):
                    parts.append(t)
            elif isinstance(it, str):
                parts.append(it)
        return "\n".join(parts)
    if content is None:
        return ""
    return str(content)


def _transform_messages(
    messages: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """拆出 system 文本，并把 tool/user/assistant 保留为独立轮次。

    注意：Anthropic 推荐 user/assistant 交替，但 agent 历史中可能连出两条 user
    （user 提问 + tool 结果），这里 **不合并** 相邻同角色消息，保留语义，便于
    模型识别工具调用的边界。
    """
    system_chunks: list[str] = []
    conv: list[dict[str, Any]] = []
    for m in messages:
        role = m.get("role")
        content_text = _as_text(m.get("content"))
        if role == "system":
            if content_text:
                system_chunks.append(content_text)
            continue
        if role == "tool":
            name = str(m.get("name") or "tool").strip() or "tool"
            text = f"[tool:{name}]\n{content_text}" if content_text else f"[tool:{name}]"
            conv.append({"role": "user", "content": text})
            continue
        mapped_role = "assistant" if role == "assistant" else "user"
        conv.append({"role": mapped_role, "content": content_text})

    # 若首条为 assistant，补一个占位 user，避免服务端报 `first message must be user`。
    if conv and conv[0]["role"] != "user":
        conv.insert(0, {"role": "user", "content": "(conversation continues)"})

    system_text = "\n\n".join(s for s in system_chunks if s.strip())
    return system_text, conv


def reset_usage_counters() -> None:
    _usage_mod.reset_usage_counters()


def get_usage_counters() -> dict[str, int]:
    return _usage_mod.get_usage_counters()


def _accumulate_usage(usage: dict[str, Any]) -> None:
    pt = usage.get("input_tokens")
    ct = usage.get("output_tokens")
    if isinstance(pt, int) and pt >= 0:
        _usage_mod._USAGE_PROMPT_TOKENS += pt
    if isinstance(ct, int) and ct >= 0:
        _usage_mod._USAGE_COMPLETION_TOKENS += ct
    total = 0
    if isinstance(pt, int) and isinstance(ct, int) and pt >= 0 and ct >= 0:
        total = int(pt) + int(ct)
        _usage_mod._USAGE_TOTAL_TOKENS += total
    _usage_mod._record_last_usage(
        prompt_tokens=pt if isinstance(pt, int) else 0,
        completion_tokens=ct if isinstance(ct, int) else 0,
        total_tokens=total,
    )


def _max_tokens_from_settings(settings: Any) -> int:
    for name in ("anthropic_max_tokens", "max_tokens"):
        v = getattr(settings, name, None)
        if isinstance(v, int) and v > 0:
            return int(v)
    return 4096


def chat_completion(
    settings: Any,
    messages: list[dict[str, Any]],
    *,
    transport: httpx.BaseTransport | None = None,
) -> str:
    """同步调用 Anthropic `/v1/messages`，返回拼接后的 text 内容。"""
    if getattr(settings, "mock", False):
        fixed = os.getenv("CAI_MOCK_REPLY")
        if fixed:
            return fixed
        return '{"type":"finish","message":"CAI_MOCK=1（未设置 CAI_MOCK_REPLY）"}'

    base = str(getattr(settings, "base_url", "")).rstrip("/")
    if base.endswith("/v1"):
        base = base[: -len("/v1")]
    url = f"{base}/v1/messages"

    system_text, conv = _transform_messages(messages)
    payload: dict[str, Any] = {
        "model": getattr(settings, "model", ""),
        "messages": conv,
        "max_tokens": _max_tokens_from_settings(settings),
        "temperature": float(getattr(settings, "temperature", 0.2)),
    }
    if system_text:
        payload["system"] = system_text

    headers = {
        "x-api-key": str(getattr(settings, "api_key", "") or ""),
        "anthropic-version": str(getattr(settings, "anthropic_version", "2023-06-01")),
        "content-type": "application/json",
    }
    timeout = httpx.Timeout(
        connect=30.0,
        read=float(getattr(settings, "llm_timeout_sec", 120.0)),
        write=30.0,
        pool=30.0,
    )

    effective_transport = transport if transport is not None else _DEFAULT_TRANSPORT
    client_kwargs: dict[str, Any] = {
        "timeout": timeout,
        "trust_env": bool(getattr(settings, "http_trust_env", False)),
    }
    if effective_transport is not None:
        client_kwargs["transport"] = effective_transport

    last: httpx.Response | None = None
    data: dict[str, Any] | None = None
    last_transport_exc: Exception | None = None
    max_retries = _usage_mod.llm_max_retries()
    last_attempt = max_retries - 1
    # Fresh Client per attempt so a broken pooled connection is not reused.
    for attempt in range(max_retries):
        with httpx.Client(**client_kwargs) as client:
            try:
                last = client.post(url, json=payload, headers=headers)
                last_transport_exc = None
            except httpx.TransportError as exc:
                last_transport_exc = exc
                if attempt == last_attempt:
                    raise RuntimeError(
                        f"Anthropic 连接失败（传输层错误，已重试 {max_retries} 次）: {exc}",
                    ) from exc
                delay = min(2.0**attempt, 12.0)
                time.sleep(delay)
                continue
            if last.status_code < 400:
                try:
                    parsed = last.json()
                except (ValueError,) as exc:
                    if attempt == last_attempt:
                        snippet = (last.text or "")[:500]
                        raise RuntimeError(
                            f"Anthropic 返回了非 JSON 响应（已重试 {max_retries} 次）: "
                            f"{exc}; body_snippet={snippet!r}",
                        ) from exc
                    delay = min(2.0**attempt, 12.0)
                    time.sleep(delay)
                    continue
                if not isinstance(parsed, dict):
                    if attempt == last_attempt:
                        raise RuntimeError(
                            f"Anthropic 返回 JSON 根对象不是 dict（已重试 {max_retries} 次）",
                        )
                    delay = min(2.0**attempt, 12.0)
                    time.sleep(delay)
                    continue
                data = parsed
                break
            if last.status_code not in _RETRYABLE_STATUS or attempt == last_attempt:
                hdr = "\n".join(f"  {k}: {v}" for k, v in last.headers.items())
                raise RuntimeError(
                    f"Anthropic HTTP {last.status_code} url={url}\n"
                    f"body={last.text!r}\nheaders:\n{hdr}",
                )
            delay = min(2.0**attempt, 12.0)
            time.sleep(delay)

    if last_transport_exc is not None:
        raise RuntimeError(
            f"Anthropic 连接失败（传输层错误）: {last_transport_exc}",
        ) from last_transport_exc
    if data is None:
        raise RuntimeError("Anthropic 返回体解析失败（未知状态）")
    if last is None or last.status_code >= 400:
        raise RuntimeError("Anthropic 请求失败（未知状态）")

    usage = data.get("usage")
    if isinstance(usage, dict):
        _accumulate_usage(usage)

    content = data.get("content")
    parts: list[str] = []
    if isinstance(content, list):
        for it in content:
            if isinstance(it, dict) and it.get("type") == "text":
                t = it.get("text")
                if isinstance(t, str):
                    parts.append(t)
    joined = "".join(parts).strip()
    if joined:
        return joined

    return _usage_mod.normalize_assistant_text(
        content=joined,
        message={"reasoning_content": ""},
        choice={"finish_reason": data.get("stop_reason")},
        usage=usage if isinstance(usage, dict) else {},
        provider_label="Anthropic",
    )


__all__ = [
    "chat_completion",
    "get_usage_counters",
    "reset_usage_counters",
]
