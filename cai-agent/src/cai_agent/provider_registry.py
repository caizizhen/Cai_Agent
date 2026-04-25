"""Hermes H1-MP: curated provider presets + registry metadata (Portal / OR / NIM / …)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final


@dataclass(frozen=True)
class ProviderRegistryEntry:
    """Human-facing registry row (not necessarily 1:1 with ``Profile.provider``)."""

    id: str
    canonical: str
    base_url: str
    api_key_env: str
    default_model: str
    auth_style: str  # bearer | custom
    notes: str


# Preset fragments merged into ``profiles.PRESETS`` (provider stays OpenAI-compatible wire).
EXTRA_PRESETS: Final[dict[str, dict[str, Any]]] = {
    "nous_portal": {
        "provider": "openai_compatible",
        "base_url": "https://inference-api.nousresearch.com/v1",
        "api_key_env": "NOUS_API_KEY",
        "model": "Hermes-3-Llama-3.1-8B",
        "temperature": 0.2,
        "timeout_sec": 120.0,
    },
    "nvidia_nim": {
        "provider": "openai_compatible",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "api_key_env": "NVIDIA_API_KEY",
        "model": "meta/llama-3.1-8b-instruct",
        "temperature": 0.2,
        "timeout_sec": 120.0,
    },
    "xiaomi_mimo": {
        "provider": "openai_compatible",
        "base_url": "https://api.xiaomimimo.com/v1",
        "api_key_env": "XIAOMI_MIMO_API_KEY",
        "model": "mimo-v2-flash",
        "temperature": 0.2,
        "timeout_sec": 120.0,
    },
    "zai_glm": {
        "provider": "openai_compatible",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key_env": "ZAI_API_KEY",
        "model": "glm-4.6",
        "temperature": 0.6,
        "timeout_sec": 120.0,
        "context_window": 200_000,
    },
    "kimi_moonshot": {
        "provider": "openai_compatible",
        "base_url": "https://api.moonshot.cn/v1",
        "api_key_env": "MOONSHOT_API_KEY",
        "model": "kimi-k2-turbo-preview",
        "temperature": 0.3,
        "timeout_sec": 120.0,
    },
    "minimax": {
        "provider": "openai_compatible",
        "base_url": "https://api.minimax.chat/v1",
        "api_key_env": "MINIMAX_API_KEY",
        "model": "MiniMax-M2.1",
        "temperature": 0.2,
        "timeout_sec": 120.0,
    },
    "huggingface": {
        "provider": "openai_compatible",
        "base_url": "https://api-inference.huggingface.co/v1",
        "api_key_env": "HF_TOKEN",
        "model": "meta-llama/Meta-Llama-3-8B-Instruct",
        "temperature": 0.2,
        "timeout_sec": 180.0,
    },
}


PROVIDER_REGISTRY: Final[tuple[ProviderRegistryEntry, ...]] = tuple(
    sorted(
        (
            ProviderRegistryEntry(
                id=k,
                canonical="openai_compatible",
                base_url=str(v["base_url"]),
                api_key_env=str(v["api_key_env"]),
                default_model=str(v.get("model") or ""),
                auth_style="bearer",
                notes=f'Preset `{k}` → OpenAI-compatible Chat Completions',
            )
            for k, v in EXTRA_PRESETS.items()
        ),
        key=lambda e: e.id,
    ),
)


def _capabilities_hint_for_preset(preset_id: str) -> dict[str, Any]:
    """Build a non-secret capability hint for a registry preset."""

    from cai_agent.model_gateway import infer_model_capabilities
    from cai_agent.profiles import build_profile

    raw = dict(EXTRA_PRESETS[preset_id])
    raw["id"] = preset_id
    prof = build_profile(raw, hint=f"provider-registry:{preset_id}")
    return infer_model_capabilities(prof).to_public_dict()


def preset_ids() -> tuple[str, ...]:
    """All preset keys including core profiles (``profiles.PRESETS``)."""
    from cai_agent import profiles as _profiles

    return tuple(sorted(set(_profiles.PRESETS.keys())))


def providers_json_payload() -> dict[str, Any]:
    rows = [
        {
            **e.__dict__,
            "capabilities_hint": _capabilities_hint_for_preset(e.id),
        }
        for e in PROVIDER_REGISTRY
    ]
    return {
        "schema_version": "provider_registry_v1",
        "count": len(rows),
        "providers": rows,
    }


def provider_readiness_snapshot() -> dict[str, Any]:
    """For ``doctor`` / CLI: env presence + preset id list."""
    import os

    rows: list[dict[str, Any]] = []
    for e in PROVIDER_REGISTRY:
        env = e.api_key_env
        present = bool(env and (os.getenv(env) or "").strip())
        rows.append(
            {
                "id": e.id,
                "api_key_env": env,
                "env_present": present,
                "base_url": e.base_url,
                "capabilities_hint": _capabilities_hint_for_preset(e.id),
            },
        )
    return {"schema_version": "provider_readiness_v1", "entries": rows}


def build_model_onboarding_flow_v1(
    *,
    profile_id: str,
    preset: str,
    model: str | None = None,
    set_active: bool = True,
) -> dict[str, Any]:
    """Deterministic command chain for adding and validating a model profile."""

    from cai_agent.model_gateway import infer_model_capabilities
    from cai_agent.profiles import PRESETS, ProfilesError, apply_preset, build_profile

    pid = str(profile_id or "").strip() or "new-profile"
    preset_id = str(preset or "").strip() or "openai_compatible"
    model_s = str(model or "").strip()
    if preset_id not in PRESETS:
        known = ", ".join(sorted(PRESETS.keys()))
        raise ProfilesError(f"未知预设 '{preset_id}'（可用：{known}）")
    raw = apply_preset({"id": pid, "model": model_s or None}, preset_id)
    prof = build_profile(raw, hint=f"onboarding:{pid}")
    capabilities_hint = infer_model_capabilities(prof).to_public_dict()
    add_cmd = f"cai-agent models add --id {pid} --preset {preset_id}"
    if model_s:
        add_cmd += f" --model {model_s}"
    if set_active:
        add_cmd += " --set-active"
    commands = [
        {
            "step": "inspect_providers",
            "command": "cai-agent models list --providers --json",
            "why": "查看内置 provider preset 与所需 API key 环境变量。",
        },
        {
            "step": "add_profile",
            "command": add_cmd,
            "why": "新增 profile；只写非敏感配置，优先通过环境变量提供 key。",
        },
        {
            "step": "capabilities",
            "command": f"cai-agent models capabilities {pid} --json",
            "why": "确认 context/tool/vision/json/reasoning/local/cost 等非敏感能力元数据。",
        },
        {
            "step": "ping",
            "command": f"cai-agent models ping {pid} --json",
            "why": "先做不消耗 token 的 /models 或等价健康检查。",
        },
        {
            "step": "chat_smoke",
            "command": f"cai-agent models ping {pid} --chat-smoke --json",
            "why": "显式启用最小真实 chat smoke；会消耗 token，失败返回稳定状态。",
        },
        {
            "step": "use",
            "command": f"cai-agent models use {pid}",
            "why": "把验证过的 profile 设为 active。",
        },
        {
            "step": "routing_test",
            "command": f'cai-agent models routing-test --role active --goal "smoke test" --json',
            "why": "查看 routing explain、capabilities 与 fallback candidates，不会静默切换模型。",
        },
    ]
    return {
        "schema_version": "model_onboarding_flow_v1",
        "profile_id": pid,
        "preset": preset_id,
        "model": model_s or None,
        "set_active": bool(set_active),
        "capabilities_hint": capabilities_hint,
        "commands": commands,
        "boundaries": [
            "不提交 API key；优先设置 preset 对应的环境变量。",
            "chat smoke 必须显式执行，默认 ping 不消耗 token。",
            "routing-test 只解释候选与原因，不会自动切换模型。",
        ],
    }
