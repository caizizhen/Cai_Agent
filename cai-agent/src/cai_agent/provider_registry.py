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


def preset_ids() -> tuple[str, ...]:
    """All preset keys including core profiles (``profiles.PRESETS``)."""
    from cai_agent import profiles as _profiles

    return tuple(sorted(set(_profiles.PRESETS.keys())))


def providers_json_payload() -> dict[str, Any]:
    rows = [e.__dict__ for e in PROVIDER_REGISTRY]
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
            },
        )
    return {"schema_version": "provider_readiness_v1", "entries": rows}
