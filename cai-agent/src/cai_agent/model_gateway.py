"""Unified model gateway contract for provider/profile-facing model access.

This module intentionally sits beside the existing ``llm.py`` and
``llm_anthropic.py`` adapters instead of replacing them.  The goal is to give
CLI, API, routing and future OpenAI-compatible server work one stable contract
for model capabilities, health checks and normalized responses while keeping
the current execution path intact.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Any, Protocol

from cai_agent import llm as _openai_adapter
from cai_agent import llm_anthropic as _anthropic_adapter
from cai_agent.llm import get_last_usage
from cai_agent.profiles import Profile, project_base_url


KNOWN_MODEL_HEALTH_STATUSES: tuple[str, ...] = (
    "OK",
    "AUTH_FAIL",
    "ENV_MISSING",
    "TIMEOUT",
    "RATE_LIMIT",
    "MODEL_NOT_FOUND",
    "UNSUPPORTED",
    "UNSUPPORTED_FEATURE",
    "CONTEXT_TOO_LARGE",
    "NET_FAIL",
    "CHAT_FAIL",
)


@dataclass(frozen=True)
class ModelCapabilities:
    """Public, non-secret model capability snapshot.

    Capabilities are deliberately conservative.  For OpenAI-compatible local
    servers, many features vary by the server and model; those fields are
    reported as ``"unknown"`` unless the provider/model gives a reliable hint.
    """

    provider: str
    model: str
    profile_id: str | None
    context_window: int | None = None
    max_output_tokens: int | None = None
    chat: str = "yes"
    streaming: str = "adapter_pending"
    tool_calling: str = "unknown"
    vision: str = "unknown"
    json_mode: str = "unknown"
    reasoning: str = "unknown"
    local_private: str = "unknown"
    cost_hint: str = "unknown"

    def to_public_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema_version": "model_capabilities_v1",
            "profile_id": self.profile_id,
            "provider": self.provider,
            "model": self.model,
            "capabilities": {
                "chat": self.chat,
                "streaming": self.streaming,
                "tool_calling": self.tool_calling,
                "vision": self.vision,
                "json_mode": self.json_mode,
                "reasoning": self.reasoning,
                "local_private": self.local_private,
            },
            "cost_hint": self.cost_hint,
        }
        if self.context_window is not None:
            out["context_window"] = int(self.context_window)
        if self.max_output_tokens is not None:
            out["max_output_tokens"] = int(self.max_output_tokens)
        return out


@dataclass(frozen=True)
class ModelResponse:
    """Normalized response envelope returned by gateway helpers."""

    content: str
    provider: str
    model: str
    profile_id: str | None
    usage: dict[str, int]
    latency_ms: int
    finish_reason: str | None = None
    raw_provider: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "model_response_v1",
            "provider": self.provider,
            "model": self.model,
            "profile_id": self.profile_id,
            "content": self.content,
            "usage": dict(self.usage),
            "latency_ms": int(self.latency_ms),
            "finish_reason": self.finish_reason,
            "raw_provider": self.raw_provider or self.provider,
        }


class ModelAdapter(Protocol):
    """Minimal adapter contract for model providers."""

    provider: str

    def capabilities_for_profile(self, profile: Profile) -> ModelCapabilities:
        ...

    def chat_response(
        self,
        settings: Any,
        messages: list[dict[str, Any]],
    ) -> ModelResponse:
        ...


def canonical_provider(value: str | None) -> str:
    s = str(value or "").strip().lower()
    if not s:
        return "openai_compatible"
    if s == "anthropic" or s == "claude" or s.startswith("claude-"):
        return "anthropic"
    if s in {
        "openai",
        "openai_compatible",
        "azure_openai",
        "copilot",
        "ollama",
        "lmstudio",
        "vllm",
    }:
        return s
    return "openai_compatible"


def _provider_from_settings(settings: Any) -> str:
    return canonical_provider(
        getattr(settings, "active_profile_provider", None)
        or getattr(settings, "provider", None),
    )


def _model_from_settings(settings: Any) -> str:
    return str(getattr(settings, "model", "") or "")


def _profile_id_from_settings(settings: Any) -> str | None:
    v = getattr(settings, "active_profile_id", None)
    return str(v) if isinstance(v, str) and v.strip() else None


def _usage_snapshot() -> dict[str, int]:
    snap = get_last_usage()
    return {
        "prompt_tokens": int(snap.get("prompt_tokens") or 0),
        "completion_tokens": int(snap.get("completion_tokens") or 0),
        "total_tokens": int(snap.get("total_tokens") or 0),
    }


def _wrap_response(
    *,
    settings: Any,
    content: str,
    started: float,
    raw_provider: str,
) -> ModelResponse:
    return ModelResponse(
        content=str(content or ""),
        provider=_provider_from_settings(settings),
        model=_model_from_settings(settings),
        profile_id=_profile_id_from_settings(settings),
        usage=_usage_snapshot(),
        latency_ms=max(0, int(round((time.perf_counter() - started) * 1000))),
        raw_provider=raw_provider,
    )


def _boolish_cap(value: bool | None) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "unknown"


def infer_model_capabilities(
    profile: Profile,
    *,
    context_window_fallback: int | None = None,
) -> ModelCapabilities:
    provider = canonical_provider(profile.provider)
    model = str(profile.model or "")
    ml = model.lower()
    context_window = profile.context_window or context_window_fallback
    max_output = profile.max_tokens

    local_private = provider in {"ollama", "lmstudio", "vllm"}
    if provider == "openai_compatible":
        base = project_base_url(profile).lower()
        local_private = (
            base.startswith("http://localhost")
            or base.startswith("http://127.0.0.1")
            or "localhost" in base
        )

    reasoning: bool | None = None
    if any(key in ml for key in ("reason", "deepseek-r1", "qwen3", "o1", "o3", "o4")):
        reasoning = True

    vision: bool | None = None
    if any(key in ml for key in ("vision", "gpt-4o", "gemini", "claude-3", "qwen-vl")):
        vision = True

    tool_calling: bool | None = None
    json_mode: bool | None = None
    if provider in {"openai", "anthropic", "azure_openai"}:
        tool_calling = True
        json_mode = True
    elif provider in {"ollama", "lmstudio", "vllm", "openai_compatible"}:
        tool_calling = None
        json_mode = None

    streaming = "provider_supported"
    if provider in {"ollama", "lmstudio", "vllm", "openai_compatible"}:
        streaming = "provider_dependent"

    cost_hint = "metered"
    if local_private:
        cost_hint = "local"
    elif provider in {"openai_compatible", "copilot"}:
        cost_hint = "provider_dependent"

    return ModelCapabilities(
        profile_id=profile.id,
        provider=provider,
        model=model,
        context_window=context_window,
        max_output_tokens=max_output,
        streaming=streaming,
        tool_calling=_boolish_cap(tool_calling),
        vision=_boolish_cap(vision),
        json_mode=_boolish_cap(json_mode),
        reasoning=_boolish_cap(reasoning),
        local_private=_boolish_cap(local_private),
        cost_hint=cost_hint,
    )


class OpenAICompatibleAdapter:
    provider = "openai_compatible"

    def capabilities_for_profile(self, profile: Profile) -> ModelCapabilities:
        return infer_model_capabilities(profile)

    def chat_response(
        self,
        settings: Any,
        messages: list[dict[str, Any]],
    ) -> ModelResponse:
        started = time.perf_counter()
        content = _openai_adapter.chat_completion(settings, messages)
        return _wrap_response(
            settings=settings,
            content=content,
            started=started,
            raw_provider="openai_compatible",
        )


class AnthropicAdapter:
    provider = "anthropic"

    def capabilities_for_profile(self, profile: Profile) -> ModelCapabilities:
        return infer_model_capabilities(profile)

    def chat_response(
        self,
        settings: Any,
        messages: list[dict[str, Any]],
    ) -> ModelResponse:
        started = time.perf_counter()
        content = _anthropic_adapter.chat_completion(settings, messages)
        return _wrap_response(
            settings=settings,
            content=content,
            started=started,
            raw_provider="anthropic",
        )


_OPENAI_ADAPTER = OpenAICompatibleAdapter()
_ANTHROPIC_ADAPTER = AnthropicAdapter()


def adapter_for_provider(provider: str | None) -> ModelAdapter:
    if canonical_provider(provider) == "anthropic":
        return _ANTHROPIC_ADAPTER
    return _OPENAI_ADAPTER


def chat_response(
    settings: Any,
    messages: list[dict[str, Any]],
) -> ModelResponse:
    """Run chat through the normalized gateway response contract."""

    return adapter_for_provider(_provider_from_settings(settings)).chat_response(
        settings,
        messages,
    )


def build_model_capabilities_payload(
    profiles: tuple[Profile, ...] | list[Profile],
    *,
    active_profile_id: str | None = None,
    context_window_fallback: int | None = None,
) -> dict[str, Any]:
    rows = [
        infer_model_capabilities(
            p,
            context_window_fallback=context_window_fallback,
        ).to_public_dict()
        for p in profiles
    ]
    return {
        "schema_version": "model_capabilities_list_v1",
        "active_profile_id": active_profile_id,
        "count": len(rows),
        "profiles": rows,
    }


def classify_model_exception(exc: BaseException) -> dict[str, Any]:
    text = str(exc)
    low = text.lower()
    status = "CHAT_FAIL"
    if "401" in text or "403" in text or "auth" in low or "api_key" in low:
        status = "AUTH_FAIL"
    elif "429" in text or "rate" in low:
        status = "RATE_LIMIT"
    elif "404" in text or "model_not" in low or "not found" in low:
        status = "MODEL_NOT_FOUND"
    elif "context" in low and ("large" in low or "length" in low or "window" in low):
        status = "CONTEXT_TOO_LARGE"
    elif "timeout" in low or "timed out" in low:
        status = "TIMEOUT"
    elif "unsupported" in low:
        status = "UNSUPPORTED_FEATURE"
    elif "connect" in low or "network" in low or "transport" in low:
        status = "NET_FAIL"
    return {
        "status": status,
        "message": text[:500],
        "error_type": type(exc).__name__,
    }


def smoke_chat_profile(
    settings: Any,
    profile: Profile,
    *,
    prompt: str = "Reply with OK.",
) -> dict[str, Any]:
    """Optional token-spending chat smoke for ``models ping --chat-smoke``."""

    if profile.api_key_env and profile.api_key_env_missing():
        return {
            "profile_id": profile.id,
            "status": "ENV_MISSING",
            "message": f"Environment variable {profile.api_key_env} is not set.",
        }
    try:
        projected = replace(
            settings,
            provider=profile.provider,
            base_url=project_base_url(profile),
            model=profile.model,
            api_key=profile.resolve_api_key() or getattr(settings, "api_key", ""),
            temperature=max(0.0, min(2.0, float(profile.temperature))),
            llm_timeout_sec=max(5.0, min(120.0, float(profile.timeout_sec))),
            active_profile_id=profile.id,
            active_api_key_env=profile.api_key_env,
            llm_max_http_retries=1,
        )
        if profile.provider == "anthropic":
            projected = replace(
                projected,
                anthropic_version=profile.anthropic_version or "2023-06-01",
                anthropic_max_tokens=int(profile.max_tokens or 256),
            )
        resp = chat_response(
            projected,
            [{"role": "user", "content": prompt}],
        )
    except Exception as e:
        out = classify_model_exception(e)
        out["profile_id"] = profile.id
        return out
    return {
        "profile_id": profile.id,
        "status": "OK",
        "latency_ms": resp.latency_ms,
        "usage": resp.usage,
        "message": "chat_smoke_ok",
    }


__all__ = [
    "KNOWN_MODEL_HEALTH_STATUSES",
    "ModelAdapter",
    "ModelCapabilities",
    "ModelResponse",
    "adapter_for_provider",
    "build_model_capabilities_payload",
    "canonical_provider",
    "chat_response",
    "classify_model_exception",
    "infer_model_capabilities",
    "smoke_chat_profile",
]
