"""模型 Profile：解析 `[[models.profile]]`、兼容 `[llm]`、TOML 原子写入与供应商预设。

设计目标（见 docs/MODEL_SWITCHER_BACKLOG.zh-CN.md）：

1. 把 `[llm]` 单一模型扩展为 **多 profile 并列** + **主/子代理路由**；
2. 密钥默认用 `api_key_env = "..."` 引用环境变量，`api_key` 明文仅为回退兼容；
3. 写入 TOML 时对 `[models]` / `[[models.profile]]` 做 **原子替换**（`.bak` 备份）
   并 **保留** 用户其它手写内容（以非 `models` 表头分段）。
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Sequence


KNOWN_PROVIDERS: tuple[str, ...] = (
    "openai",
    "anthropic",
    "openai_compatible",
    "azure_openai",
    "copilot",
    "ollama",
    "lmstudio",
    "vllm",
)

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-.]{0,63}$")


_LOCAL_BASE_MARKERS = (
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "[::1]",
)


def _is_local_base_url(base_url: str | None) -> bool:
    base = str(base_url or "").strip().lower()
    return base.startswith("http://") and any(marker in base for marker in _LOCAL_BASE_MARKERS)


def infer_default_context_window(
    *,
    provider: str | None,
    base_url: str | None,
    model: str | None,
) -> int | None:
    """Best-effort non-local provider context-window defaults.

    Local/self-hosted OpenAI-compatible servers can expose arbitrary models, so
    this helper intentionally returns ``None`` for localhost/127.0.0.1.  For
    hosted providers, values are conservative public API limits used only when
    the user has not explicitly set ``context_window``.
    """

    provider_s = str(provider or "").strip().lower()
    base = str(base_url or "").strip().lower()
    model_l = str(model or "").strip().lower()
    if not model_l or _is_local_base_url(base):
        return None

    # Explicit model-level defaults for built-in hosted third-party presets.
    if "mimo-v2.5-pro" in model_l:
        return 1_000_000
    if model_l.startswith(("kimi-k2", "moonshot/kimi-k2")):
        return 256_000
    if model_l.startswith("minimax-m2.1"):
        return 204_800
    if "hermes-3-llama-3.1-8b" in model_l:
        return 128_000
    if model_l.startswith("meta/llama-3.1-8b-instruct"):
        return 128_000
    if model_l.endswith("meta-llama-3-8b-instruct"):
        return 8_192

    # Provider/protocol-wide defaults first.
    if provider_s == "anthropic" or "api.anthropic.com" in base or model_l.startswith("claude-"):
        return 200_000
    if "open.bigmodel.cn" in base or model_l.startswith(("glm-5", "glm-4.6")):
        return 200_000
    if "api.deepseek.com" in base or model_l.startswith("deepseek-"):
        return 128_000
    if "generativelanguage.googleapis.com" in base or model_l.startswith("gemini-"):
        return 1_048_576

    # OpenAI family.
    if model_l.startswith(("gpt-4.1", "gpt-4.5")):
        return 1_047_576
    if model_l.startswith(("gpt-4o", "chatgpt-4o")):
        return 128_000
    if model_l.startswith(("o1", "o3", "o4")):
        return 200_000
    if model_l.startswith("gpt-5"):
        return 400_000

    # xAI / Grok.
    if "api.x.ai" in base or model_l.startswith("grok-"):
        if "fast" in model_l or "4.1" in model_l or "4.20" in model_l:
            return 2_000_000
        if "4" in model_l:
            return 256_000
        return 131_072

    # Common OpenAI-compatible hosted providers and open-model routers.
    if "api.moonshot" in base or model_l.startswith("kimi-"):
        return 128_000
    if "api.minimax" in base or model_l.startswith("minimax-"):
        return 1_000_000
    if "api.perplexity.ai" in base or model_l.startswith("sonar"):
        return 128_000
    if "api.groq.com" in base:
        if "llama-3.3" in model_l or "llama-4" in model_l:
            return 131_072
        return 32_768
    if "mistral" in base or model_l.startswith(("mistral-", "codestral", "ministral")):
        return 128_000
    if "dashscope" in base or "aliyuncs.com" in base or model_l.startswith(("qwen-", "qwen2", "qwen3")):
        return 131_072
    if "ark.cn-" in base or "volces.com" in base or model_l.startswith(("doubao-", "seed-")):
        return 128_000
    if "siliconflow" in base or "together.xyz" in base or "fireworks.ai" in base:
        if "deepseek" in model_l:
            return 128_000
        if "qwen" in model_l:
            return 131_072
        if "llama-4" in model_l or "llama-3.3" in model_l:
            return 131_072
        return None

    # OpenRouter model ids often look like "vendor/model".
    if "openrouter.ai" in base:
        if model_l.startswith("openai/"):
            return infer_default_context_window(provider="openai", base_url="https://api.openai.com/v1", model=model_l.split("/", 1)[1])
        if model_l.startswith("anthropic/"):
            return 200_000
        if model_l.startswith("google/"):
            return 1_048_576 if "gemini" in model_l else None
        if model_l.startswith("deepseek/"):
            return 128_000
        if model_l.startswith("x-ai/") or model_l.startswith("xai/"):
            return infer_default_context_window(provider="openai_compatible", base_url="https://api.x.ai/v1", model=model_l.split("/", 1)[1])
        return None

    return None


class ProfilesError(ValueError):
    """Profile 解析 / 校验错误（向 CLI 报可读消息时使用）。"""


@dataclass(frozen=True)
class Profile:
    id: str
    provider: str
    base_url: str
    model: str
    api_key_env: str | None = None
    api_key: str | None = None
    temperature: float = 0.2
    timeout_sec: float = 120.0
    anthropic_version: str | None = None
    max_tokens: int | None = None
    # 模型的上下文窗口大小（tokens）。仅用于 UI 显示上下文占用进度条，
    # 不会作为请求参数发给服务端；None 表示"未知 / 交给上层使用默认值"。
    context_window: int | None = None
    notes: str | None = None

    def resolve_api_key(self) -> str:
        """按 env → literal 顺序解析；均缺失时返回空串（调用方决定是否报错）。"""
        if self.api_key_env:
            return (os.getenv(self.api_key_env, "") or "").strip()
        return (self.api_key or "").strip()

    def api_key_env_missing(self) -> bool:
        return bool(self.api_key_env) and not (os.getenv(self.api_key_env) or "").strip()


PRESETS: dict[str, dict[str, Any]] = {
    "openai": {
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "temperature": 0.2,
        "timeout_sec": 120.0,
    },
    "anthropic": {
        "provider": "anthropic",
        "base_url": "https://api.anthropic.com",
        "api_key_env": "ANTHROPIC_API_KEY",
        "anthropic_version": "2023-06-01",
        "max_tokens": 4096,
        "temperature": 0.2,
        "timeout_sec": 120.0,
    },
    "openrouter": {
        "provider": "openai_compatible",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "temperature": 0.2,
        "timeout_sec": 120.0,
    },
    "lmstudio": {
        "provider": "openai_compatible",
        "base_url": "http://localhost:1234/v1",
        "api_key_env": "LM_API_KEY",
        "temperature": 0.2,
        "timeout_sec": 120.0,
    },
    "ollama": {
        "provider": "openai_compatible",
        "base_url": "http://localhost:11434/v1",
        "api_key_env": "OLLAMA_API_KEY",
        "temperature": 0.2,
        "timeout_sec": 120.0,
    },
    # vLLM OpenAI server: `vllm serve ... --port 8000` exposes /v1/chat/completions
    "vllm": {
        "provider": "openai_compatible",
        "base_url": "http://localhost:8000/v1",
        "model": "replace-with-served-model-id",
        "api_key_env": "VLLM_API_KEY",
        "temperature": 0.2,
        "timeout_sec": 120.0,
    },
    # One API / LiteLLM / 自建网关等：改 base_url 与 model 即可；密钥常用 OPENAI_API_KEY
    "gateway": {
        "provider": "openai_compatible",
        "base_url": "http://127.0.0.1:8080/v1",
        "model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
        "temperature": 0.2,
        "timeout_sec": 120.0,
    },
    # 智谱 AI OpenAI 兼容（见 https://docs.bigmodel.cn/cn/guide/develop/openai/introduction ）
    "zhipu": {
        "provider": "openai_compatible",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-5.1",
        "api_key_env": "ZAI_API_KEY",
        "temperature": 0.6,
        "timeout_sec": 120.0,
        "context_window": 200_000,
    },
}

from cai_agent.provider_registry import EXTRA_PRESETS as _EXTRA_PRESETS
from cai_agent.memory import resolve_active_memory_provider

PRESETS.update(_EXTRA_PRESETS)


def apply_preset(raw: dict[str, Any], preset_name: str) -> dict[str, Any]:
    """以预设为底 + 用户输入覆盖，返回可交给 `build_profile` 的 dict。"""
    key = str(preset_name or "").strip().lower()
    if key not in PRESETS:
        known = ", ".join(sorted(PRESETS.keys()))
        raise ProfilesError(f"未知预设 '{preset_name}'（可用：{known}）")
    merged: dict[str, Any] = dict(PRESETS[key])
    for k, v in raw.items():
        if v is None:
            continue
        merged[k] = v
    return merged


def _as_float(v: Any, default: float | None) -> float | None:
    if isinstance(v, bool):
        return float(int(v))
    if isinstance(v, int | float):
        return float(v)
    if isinstance(v, str) and v.strip():
        try:
            return float(v.strip())
        except ValueError:
            return default
    return default


def _as_int(v: Any, default: int | None) -> int | None:
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return int(v)
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str) and v.strip():
        try:
            return int(v.strip())
        except ValueError:
            return default
    return default


def _as_str(v: Any) -> str | None:
    if isinstance(v, str) and v.strip():
        return v.strip()
    return None


def build_profile(raw: dict[str, Any], *, hint: str = "") -> Profile:
    """从 dict 构造 Profile，做必填 / 类型 / 冲突校验。"""
    if not isinstance(raw, dict):
        raise ProfilesError(f"profile 必须是表（table）：{hint}")

    pid = _as_str(raw.get("id"))
    if not pid or not _ID_RE.match(pid):
        raise ProfilesError(
            f"profile id 非法：{raw.get('id')!r}（须为字母数字开头，长度 1-64）",
        )

    provider = _as_str(raw.get("provider")) or ""
    provider = provider.lower()
    if provider not in KNOWN_PROVIDERS:
        known = ", ".join(KNOWN_PROVIDERS)
        raise ProfilesError(
            f"profile[{pid}] provider='{provider}' 非法（可选：{known}）",
        )

    base_url = _as_str(raw.get("base_url"))
    if not base_url:
        raise ProfilesError(f"profile[{pid}] 缺少 base_url")

    model = _as_str(raw.get("model"))
    if not model:
        raise ProfilesError(f"profile[{pid}] 缺少 model")

    api_key = _as_str(raw.get("api_key"))
    api_key_env = _as_str(raw.get("api_key_env"))
    if api_key and api_key_env:
        raise ProfilesError(
            f"profile[{pid}] 不能同时设置 api_key 与 api_key_env；推荐只写 api_key_env",
        )

    temperature = _as_float(raw.get("temperature"), 0.2) or 0.2
    temperature = max(0.0, min(2.0, float(temperature)))
    timeout_sec = _as_float(raw.get("timeout_sec"), 120.0) or 120.0
    timeout_sec = max(5.0, min(3600.0, float(timeout_sec)))

    anthropic_version = _as_str(raw.get("anthropic_version"))
    max_tokens = _as_int(raw.get("max_tokens"), None)
    if max_tokens is not None:
        max_tokens = max(1, min(1_000_000, int(max_tokens)))
    context_window = _as_int(raw.get("context_window"), None)
    if context_window is None:
        context_window = infer_default_context_window(
            provider=provider,
            base_url=base_url,
            model=model,
        )
    if context_window is not None:
        context_window = max(256, min(10_000_000, int(context_window)))

    if provider == "anthropic":
        # Anthropic 需要这两项；给个合理默认，避免调用时报错。
        anthropic_version = anthropic_version or "2023-06-01"
        if max_tokens is None:
            max_tokens = 4096

    notes = _as_str(raw.get("notes"))

    return Profile(
        id=pid,
        provider=provider,
        base_url=base_url,
        model=model,
        api_key_env=api_key_env,
        api_key=api_key,
        temperature=temperature,
        timeout_sec=timeout_sec,
        anthropic_version=anthropic_version,
        max_tokens=max_tokens,
        context_window=context_window,
        notes=notes,
    )


def parse_models_section(
    file_data: dict[str, Any],
) -> tuple[tuple[Profile, ...], str | None, str | None, str | None]:
    """解析顶层 `[models]` 与 `[[models.profile]]`。

    - 未配置 models 段 → 返回 `((), None, None, None)`；
    - 路由字段 `active / subagent / planner` 可缺省；
    - profile id 必须唯一，否则抛 ``ProfilesError``。
    """
    models_sec = file_data.get("models")
    if not isinstance(models_sec, dict):
        return ((), None, None, None)

    raw_list = models_sec.get("profile")
    if raw_list is None:
        raw_list = []
    if not isinstance(raw_list, list):
        raise ProfilesError("[models].profile 必须是数组（[[models.profile]]）")

    profiles: list[Profile] = []
    seen: set[str] = set()
    for idx, raw in enumerate(raw_list):
        p = build_profile(raw, hint=f"[[models.profile]][{idx}]")
        if p.id in seen:
            raise ProfilesError(f"profile id 重复: {p.id!r}")
        seen.add(p.id)
        profiles.append(p)

    def _route(name: str) -> str | None:
        v = _as_str(models_sec.get(name))
        if v is None:
            return None
        if profiles and v not in seen:
            raise ProfilesError(f"[models].{name}={v!r} 不存在于已定义 profile 中")
        return v

    active = _route("active")
    subagent = _route("subagent")
    planner = _route("planner")
    return tuple(profiles), active, subagent, planner


def synthesize_default_profile(
    *,
    provider: str,
    base_url: str,
    model: str,
    api_key: str,
    temperature: float,
    timeout_sec: float,
) -> Profile:
    """基于旧 `[llm]` 段构造隐式 default profile，保证零迁移启动。"""
    prov = (provider or "").lower()
    if prov not in KNOWN_PROVIDERS:
        prov = "openai_compatible"
    inferred_context_window = infer_default_context_window(
        provider=prov,
        base_url=base_url,
        model=model,
    )
    return Profile(
        id="default",
        provider=prov,
        base_url=base_url,
        model=model,
        api_key_env=None,
        api_key=api_key if api_key else None,
        temperature=temperature,
        timeout_sec=timeout_sec,
        anthropic_version=None,
        max_tokens=None,
        context_window=inferred_context_window,
        notes=None,
    )


def normalize_openai_chat_base_url(base: str) -> str:
    """Strip and normalize base URL used as ``{base}/chat/completions``.

    Most OpenAI-compatible servers use ``…/v1/chat/completions``. 智谱 OpenAI
    兼容网关根路径为 ``…/api/paas/v4``（文档：
    https://docs.bigmodel.cn/cn/guide/develop/openai/introduction ），不能再拼
    ``/v1``，否则请求会落到错误路径。
    """
    raw = (base or "").strip().rstrip("/")
    if not raw:
        return raw
    low = raw.lower()
    if "open.bigmodel.cn" in low and "/api/paas/" in low:
        return raw
    if raw.endswith("/v1"):
        return raw
    return raw + "/v1"


def pick_active(
    profiles: Sequence[Profile],
    active_id: str | None,
    *,
    env_override: str | None = None,
) -> Profile:
    """按优先级返回激活 profile。

    优先级：`CAI_ACTIVE_MODEL`（env_override）> `[models].active` > 列表首个。
    若 `env_override` 指向未定义 id：**不抛异常**，退回 `active` 或首个；
    否则 UX 上一切配置来源切换都会踩到这个坑。
    """
    if not profiles:
        raise ProfilesError("profiles 列表为空，无法选中激活 profile")
    ids = {p.id: p for p in profiles}
    if env_override and env_override in ids:
        return ids[env_override]
    if active_id and active_id in ids:
        return ids[active_id]
    return profiles[0]


def ensure_profile_id_legal(pid: str, *, context: str = "") -> str:
    """校验 profile id 符合 ``_ID_RE``；非法时抛出 :class:`ProfilesError`。"""
    s = str(pid or "").strip()
    if not s or not _ID_RE.match(s):
        tail = f"（{context}）" if context else ""
        raise ProfilesError(
            f"profile id 非法：{pid!r}{tail}（须为字母数字开头，长度 1-64）",
        )
    return s


def get_profile_by_id(
    profiles: Sequence[Profile],
    profile_id: str | None,
) -> Profile | None:
    pid = str(profile_id or "").strip()
    if not pid:
        return None
    for p in profiles:
        if p.id == pid:
            return p
    return None


def resolve_role_profile_id(
    *,
    role: str,
    active_profile_id: str | None,
    subagent_profile_id: str | None = None,
    planner_profile_id: str | None = None,
) -> str | None:
    role_l = (role or "active").strip().lower()
    if role_l == "subagent":
        return subagent_profile_id or active_profile_id
    if role_l == "planner":
        return planner_profile_id or active_profile_id
    return active_profile_id


def project_base_url(profile: Profile) -> str:
    """按 provider 规则把 base_url 规整为「call-site 直接拼路径」的形式。

    - `anthropic`: 返回 **不含 /v1** 的根（llm_anthropic 拼 `/v1/messages`）；
    - 其它 provider：多数补齐 ``/v1``；智谱 ``open.bigmodel.cn/api/paas/…`` 除外
      （见 :func:`normalize_openai_chat_base_url`）。
    """
    raw = (profile.base_url or "").strip().rstrip("/")
    if profile.provider == "anthropic":
        if raw.endswith("/v1"):
            raw = raw[: -len("/v1")]
        return raw
    return normalize_openai_chat_base_url(profile.base_url or "")


# ---------------------------------------------------------------------------
# TOML 序列化 / 原子写入
# ---------------------------------------------------------------------------

def _toml_str(val: str) -> str:
    escaped = val.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + escaped + '"'


def _format_float(v: float) -> str:
    # 用 repr 避免 1.0 写成 "1"；TOML 要求 float 必须带小数点。
    s = repr(float(v))
    if "." not in s and "e" not in s and "E" not in s:
        s += ".0"
    return s


def _serialize_profile(p: Profile) -> str:
    lines: list[str] = ["[[models.profile]]"]
    lines.append(f"id = {_toml_str(p.id)}")
    lines.append(f"provider = {_toml_str(p.provider)}")
    lines.append(f"base_url = {_toml_str(p.base_url)}")
    lines.append(f"model = {_toml_str(p.model)}")
    if p.api_key_env:
        lines.append(f"api_key_env = {_toml_str(p.api_key_env)}")
    if p.api_key:
        lines.append(f"api_key = {_toml_str(p.api_key)}")
    lines.append(f"temperature = {_format_float(p.temperature)}")
    lines.append(f"timeout_sec = {_format_float(p.timeout_sec)}")
    if p.anthropic_version:
        lines.append(f"anthropic_version = {_toml_str(p.anthropic_version)}")
    if p.max_tokens is not None:
        lines.append(f"max_tokens = {int(p.max_tokens)}")
    if p.context_window is not None:
        lines.append(f"context_window = {int(p.context_window)}")
    if p.notes:
        lines.append(f"notes = {_toml_str(p.notes)}")
    return "\n".join(lines) + "\n"


def serialize_models_block(
    profiles: Sequence[Profile],
    *,
    active: str | None,
    subagent: str | None = None,
    planner: str | None = None,
) -> str:
    """生成 `[models] + [[models.profile]] ...` 块（末尾不带多余空行）。"""
    out: list[str] = ["[models]"]
    if active:
        out.append(f"active = {_toml_str(active)}")
    if subagent:
        out.append(f"subagent = {_toml_str(subagent)}")
    if planner:
        out.append(f"planner = {_toml_str(planner)}")
    out.append("")
    for p in profiles:
        out.append(_serialize_profile(p))
    return "\n".join(out).rstrip() + "\n"


# 识别「未被注释」的 TOML 顶层表/数组表表头
_HEADER_RE = re.compile(r"^\s*(\[\[([^\]]+)\]\]|\[([^\]]+)\])\s*(#.*)?$")


def _is_models_header(line: str) -> bool:
    m = _HEADER_RE.match(line)
    if not m:
        return False
    name = (m.group(2) or m.group(3) or "").strip()
    return name == "models" or name.startswith("models.")


def _is_section_header(line: str) -> bool:
    return bool(_HEADER_RE.match(line))


def strip_models_blocks(text: str) -> str:
    """删除 text 中未被注释的 `[models]` / `[models.*]` / `[[models.*]]` 整段。

    以「下一段顶层表头」为边界；注释行（# 开头）不会被当作表头。
    """
    lines = text.splitlines()
    out: list[str] = []
    skipping = False
    for raw in lines:
        stripped = raw.lstrip()
        if stripped.startswith("#"):
            if not skipping:
                out.append(raw)
            continue
        if _is_section_header(raw):
            if _is_models_header(raw):
                skipping = True
                continue
            skipping = False
            out.append(raw)
            continue
        if not skipping:
            out.append(raw)
    # 收尾：去掉连续空行，保证末尾单一换行。
    cleaned: list[str] = []
    for ln in out:
        if ln.strip() == "" and cleaned and cleaned[-1].strip() == "":
            continue
        cleaned.append(ln)
    txt = "\n".join(cleaned).rstrip() + "\n"
    return txt


def _atomic_write_text(path: Path, text: str, *, backup: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmpname = tempfile.mkstemp(prefix=".tmp-cai-", dir=str(path.parent))
    tmp_path = Path(tmpname)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        if backup and path.is_file():
            bak = path.with_name(path.name + ".bak")
            try:
                if bak.exists():
                    bak.unlink()
            except OSError:
                pass
            try:
                os.replace(str(path), str(bak))
            except OSError:
                # Windows 某些路径下 replace 失败时退回 copy
                bak.write_bytes(path.read_bytes())
        os.replace(str(tmp_path), str(path))
    except Exception:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
        raise


def write_models_to_toml(
    config_path: Path,
    profiles: Sequence[Profile],
    *,
    active: str | None,
    subagent: str | None = None,
    planner: str | None = None,
) -> None:
    """把 profiles 写回 TOML 文件：保留非 models 段 + 原子替换 + `.bak` 备份。

    若目标文件不存在则新建，仅写 `[models]` + `[[models.profile]]` 块。
    """
    new_block = serialize_models_block(
        profiles, active=active, subagent=subagent, planner=planner,
    )
    if config_path.is_file():
        original = config_path.read_text(encoding="utf-8")
        head = strip_models_blocks(original)
        if not head.endswith("\n\n"):
            head = head.rstrip() + "\n\n"
        new_text = head + new_block
    else:
        new_text = new_block
    _atomic_write_text(config_path, new_text, backup=True)


# ---------------------------------------------------------------------------
# 小工具：新增 / 编辑 / 删除 / 切换（只负责集合运算，不管 IO）
# ---------------------------------------------------------------------------

def add_profile(
    profiles: Sequence[Profile], new_p: Profile, *, allow_replace: bool = False,
) -> tuple[Profile, ...]:
    for p in profiles:
        if p.id == new_p.id and not allow_replace:
            raise ProfilesError(f"profile id 已存在：{new_p.id!r}（如需覆盖请用 edit）")
    return tuple(p for p in profiles if p.id != new_p.id) + (new_p,)


def remove_profile(profiles: Sequence[Profile], pid: str) -> tuple[Profile, ...]:
    if not any(p.id == pid for p in profiles):
        raise ProfilesError(f"profile 不存在：{pid!r}")
    return tuple(p for p in profiles if p.id != pid)


def edit_profile(
    profiles: Sequence[Profile], pid: str, updates: dict[str, Any],
) -> tuple[Profile, ...]:
    found: Profile | None = None
    for p in profiles:
        if p.id == pid:
            found = p
            break
    if found is None:
        raise ProfilesError(f"profile 不存在：{pid!r}")
    merged: dict[str, Any] = {
        "id": found.id,
        "provider": found.provider,
        "base_url": found.base_url,
        "model": found.model,
        "api_key_env": found.api_key_env,
        "api_key": found.api_key,
        "temperature": found.temperature,
        "timeout_sec": found.timeout_sec,
        "anthropic_version": found.anthropic_version,
        "max_tokens": found.max_tokens,
        "context_window": found.context_window,
        "notes": found.notes,
    }
    for k, v in updates.items():
        if v is None:
            continue
        merged[k] = v
    new_p = build_profile(merged, hint=f"edit {pid}")
    return tuple(new_p if p.id == pid else p for p in profiles)


def profile_to_public_dict(p: Profile, *, include_resolved_key: bool = False) -> dict[str, Any]:
    """面向 `models list --json` / `status` 的 **脱敏** 表示。"""
    out: dict[str, Any] = {
        "id": p.id,
        "provider": p.provider,
        "base_url": p.base_url,
        "model": p.model,
        "temperature": p.temperature,
        "timeout_sec": p.timeout_sec,
    }
    if p.api_key_env:
        out["api_key_env"] = p.api_key_env
        out["api_key_env_present"] = not p.api_key_env_missing()
    if p.api_key:
        out["api_key_literal"] = True  # 不回显密钥值
    if p.anthropic_version:
        out["anthropic_version"] = p.anthropic_version
    if p.max_tokens is not None:
        out["max_tokens"] = p.max_tokens
    if p.context_window is not None:
        out["context_window"] = p.context_window
    if p.notes:
        out["notes"] = p.notes
    if include_resolved_key:
        out["api_key_present"] = bool(p.resolve_api_key())
    return out


def _build_profile_home_layout(workspace_root: str | Path, profile_id: str) -> dict[str, str]:
    root = Path(workspace_root).expanduser().resolve()
    pid = ensure_profile_id_legal(profile_id, context="profile home layout")
    home = root / ".cai" / "profiles" / pid
    return {
        "root": str(home),
        "config_dir": str(home / "config"),
        "sessions_dir": str(home / "sessions"),
        "memory_dir": str(home / "memory"),
        "gateway_dir": str(home / "gateway"),
        "state_dir": str(home / "state"),
    }


PROFILE_HOME_SUBDIR_NAMES: tuple[str, ...] = ("config", "sessions", "memory", "gateway", "state")


def profile_home_root_path(workspace_root: str | Path, profile_id: str) -> Path:
    """``.cai/profiles/<id>/`` 根路径（目录未必已存在）。"""
    return Path(_build_profile_home_layout(workspace_root, profile_id)["root"])


def _profile_home_dir_nonempty(home_root: Path) -> bool:
    if not home_root.is_dir():
        return False
    try:
        return any(home_root.iterdir())
    except OSError:
        return True


def clone_profile_home_tree(
    workspace_root: str | Path,
    src_profile_id: str,
    dst_profile_id: str,
    *,
    dry_run: bool = False,
    no_copy: bool = False,
    force_home: bool = False,
) -> dict[str, Any]:
    """将 ``.cai/profiles/<src>`` 整树复制到 ``<dst>``（用于 HM-N01 profile home 隔离）。

    - ``no_copy``：跳过文件系统操作。
    - ``src`` 家目录不存在：跳过（非错误），便于仅有 TOML 而无本地状态的 profile。
    - ``dst`` 已存在且非空：除非 ``force_home``，否则返回 ``reason=dst_profile_home_nonempty``。
    """
    ws = Path(workspace_root).expanduser().resolve()
    src_pid = ensure_profile_id_legal(src_profile_id, context="clone source")
    dst_pid = ensure_profile_id_legal(dst_profile_id, context="clone destination")
    src_root = profile_home_root_path(ws, src_pid)
    dst_root = profile_home_root_path(ws, dst_pid)
    out: dict[str, Any] = {
        "schema_version": "profile_home_clone_result_v1",
        "workspace": str(ws),
        "src_profile_id": src_pid,
        "dst_profile_id": dst_pid,
        "dry_run": dry_run,
        "skipped": False,
        "reason": None,
        "src_home_existed": src_root.is_dir(),
        "dst_home_nonempty": _profile_home_dir_nonempty(dst_root),
        "copied": False,
    }
    if no_copy:
        out["skipped"] = True
        out["reason"] = "no_copy_home"
        return out
    if not src_root.is_dir():
        out["skipped"] = True
        out["reason"] = "src_profile_home_missing"
        return out
    if _profile_home_dir_nonempty(dst_root):
        if not force_home:
            out["skipped"] = True
            out["reason"] = "dst_profile_home_nonempty"
            return out
        if dry_run:
            out["would_remove_dst_home"] = True
        else:
            shutil.rmtree(dst_root)
    if dry_run:
        out["would_copytree"] = str(src_root)
        return out
    dst_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src_root, dst_root, symlinks=True)
    out["copied"] = True
    return out


def build_models_alias_v1(
    *,
    profile_id: str,
    workspace_root: str | Path,
    config_path: str | Path | None,
    cai_agent_executable: str = "cai-agent",
) -> dict[str, Any]:
    """生成固定工作区 + 配置下切换到某 profile 的可复制命令（HM-N01 alias）。"""
    ws = Path(workspace_root).expanduser().resolve()
    cfg_abs = Path(config_path).expanduser().resolve() if config_path else None
    ws_q = shlex.quote(str(ws))
    exe = cai_agent_executable.strip() or "cai-agent"
    exe_tokens = shlex.split(exe)
    exe_q = shlex.join(exe_tokens) if len(exe_tokens) > 1 else shlex.quote(exe)
    pid_q = shlex.quote(str(profile_id))
    mid: list[str] = [exe_q]
    if cfg_abs is not None:
        mid.extend(["--config", shlex.quote(str(cfg_abs))])
    mid.extend(["models", "use", pid_q])
    posix_use = f"cd {ws_q} && {' '.join(mid)}"
    ws_ps = str(ws).replace("'", "''")
    pid_ps = str(profile_id).replace("'", "''")
    cfg_ps = str(cfg_abs).replace("'", "''") if cfg_abs is not None else ""
    if cfg_abs is not None:
        ps_use = f"Set-Location '{ws_ps}'; {exe} --config '{cfg_ps}' models use '{pid_ps}'"
    else:
        ps_use = f"Set-Location '{ws_ps}'; {exe} models use '{pid_ps}'"
    mid_run = [exe_q]
    if cfg_abs is not None:
        mid_run.extend(["--config", shlex.quote(str(cfg_abs))])
    mid_run.extend(["-w", shlex.quote(str(ws)), "run", shlex.quote("你的目标")])
    posix_run = f"cd {ws_q} && {' '.join(mid_run)}"
    return {
        "schema_version": "models_alias_v1",
        "profile_id": str(profile_id),
        "workspace": str(ws),
        "config_path": str(cfg_abs) if cfg_abs is not None else None,
        "posix_shell": {
            "cd_models_use": posix_use,
            "cd_run_example": posix_run,
        },
        "powershell": {
            "set_location_models_use": ps_use,
        },
        "hint_zh": (
            "在同一工作区下使用下列命令可切换到该 profile（含 cd，确保 .cai/profiles 相对路径正确）。"
            "若使用 api_key 字面量，注意副本配置同样敏感。"
        ),
    }


def build_profile_home_migration_diag_v1(
    profiles: Sequence[Profile],
    *,
    profiles_explicit: bool,
    workspace_root: str | Path,
) -> dict[str, Any]:
    """对比 profile 列表与 ``.cai/profiles/*`` 目录，辅助 legacy → explicit 与家目录迁移诊断。"""
    ws = Path(workspace_root).expanduser().resolve()
    prof_root = ws / ".cai" / "profiles"
    ids = {p.id for p in profiles}
    orphan_dirs: list[str] = []
    if prof_root.is_dir():
        for child in prof_root.iterdir():
            if child.is_dir() and child.name not in ids:
                orphan_dirs.append(child.name)
    rows: list[dict[str, Any]] = []
    hints: list[str] = []
    if not profiles_explicit:
        hints.append(
            "当前为 [llm] 隐式 default profile；建议运行 "
            "`cai-agent models add …` 写入显式 [[models.profile]] 后再使用 route/subagent/planner。",
        )
    for p in profiles:
        home = prof_root / p.id
        missing_subdirs = [
            name for name in PROFILE_HOME_SUBDIR_NAMES
            if not (home / name).is_dir()
        ]
        rows.append(
            {
                "profile_id": p.id,
                "home_root": str(home),
                "home_root_exists": home.is_dir(),
                "missing_subdirs": missing_subdirs,
            },
        )
    if orphan_dirs:
        hints.append(
            f"`.cai/profiles` 下存在未绑定到任何 profile 的子目录: {', '.join(orphan_dirs)}；"
            "可用 `cai-agent models clone <旧id> <新id>` 或手工整理。",
        )
    any_missing = any(bool(r.get("missing_subdirs")) for r in rows)
    if any_missing and profiles_explicit:
        hints.append(
            "部分 profile 家目录缺少标准子目录（sessions/memory/gateway/state）；"
            "运行相关功能时会按需创建，也可用 repair / 手工 mkdir 预建。",
        )
    return {
        "schema_version": "profile_home_migration_diag_v1",
        "workspace": str(ws),
        "profiles_explicit": bool(profiles_explicit),
        "profile_contract_migration_state": (
            "ready" if profiles_explicit else "needs_explicit_profiles"
        ),
        "profiles": rows,
        "orphan_profile_dirs": orphan_dirs,
        "hints_zh": hints,
    }


def build_profile_contract_payload(
    profiles: Sequence[Profile],
    *,
    profiles_explicit: bool,
    active_profile_id: str,
    subagent_profile_id: str | None = None,
    planner_profile_id: str | None = None,
    env_active_override: str | None = None,
    workspace_root: str | Path | None = None,
) -> dict[str, Any]:
    """Shared profile contract summary used by HM-01a-facing surfaces."""
    ids = [p.id for p in profiles]
    source_kind = "explicit_models_profile" if profiles_explicit else "legacy_llm_default_profile"
    persistence_mode = "explicit_profiles" if profiles_explicit else "implicit_default_profile"
    migration_state = "ready" if profiles_explicit else "needs_explicit_profiles"
    migration_hint = (
        "Add explicit [[models.profile]] entries before configuring route/subagent/planner features."
        if not profiles_explicit
        else "Profile contract is explicit; future HM-01 work can build on this persisted structure."
    )
    profile_homes: dict[str, dict[str, str]] = {}
    active_profile_home: dict[str, str] | None = None
    if workspace_root is not None:
        for pid in ids:
            profile_homes[pid] = _build_profile_home_layout(workspace_root, pid)
        active_profile_home = profile_homes.get(active_profile_id)
    payload: dict[str, Any] = {
        "schema_version": "profile_contract_v1",
        "source_kind": source_kind,
        "persistence_mode": persistence_mode,
        "profiles_explicit": bool(profiles_explicit),
        "legacy_llm_compatible": not profiles_explicit,
        "profiles_count": len(ids),
        "profile_ids": ids,
        "active_profile_id": active_profile_id,
        "subagent_profile_id": subagent_profile_id,
        "planner_profile_id": planner_profile_id,
        "selection_order": ["CAI_ACTIVE_MODEL", "[models].active", "first_profile"],
        "env_active_override": env_active_override,
        "fallback_behavior": {
            "active_profile": "configured_or_first_profile",
            "subagent_profile": subagent_profile_id or active_profile_id,
            "planner_profile": planner_profile_id or active_profile_id,
        },
        "migration_state": migration_state,
        "migration_hint": migration_hint,
        "docs": {
            "backlog_doc": "docs/ISSUE_BACKLOG.zh-CN.md",
            "routing_doc": "docs/MODEL_ROUTING_RULES.zh-CN.md",
        },
    }
    if workspace_root is not None:
        payload["profile_home_schema_version"] = "profile_home_layout_v1"
        payload["workspace_root"] = str(Path(workspace_root).expanduser().resolve())
        payload["profile_homes"] = profile_homes
        payload["active_profile_home"] = active_profile_home
        payload["memory_provider"] = resolve_active_memory_provider(workspace_root)
    return payload


__all__ = [
    "KNOWN_PROVIDERS",
    "PRESETS",
    "PROFILE_HOME_SUBDIR_NAMES",
    "Profile",
    "ProfilesError",
    "add_profile",
    "apply_preset",
    "build_profile",
    "build_profile_contract_payload",
    "build_models_alias_v1",
    "build_profile_home_migration_diag_v1",
    "clone_profile_home_tree",
    "edit_profile",
    "ensure_profile_id_legal",
    "get_profile_by_id",
    "normalize_openai_chat_base_url",
    "parse_models_section",
    "pick_active",
    "profile_home_root_path",
    "profile_to_public_dict",
    "resolve_role_profile_id",
    "project_base_url",
    "remove_profile",
    "serialize_models_block",
    "strip_models_blocks",
    "synthesize_default_profile",
    "write_models_to_toml",
]
