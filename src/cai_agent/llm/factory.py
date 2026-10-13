"""Build the right LLM client from Settings / env."""

from __future__ import annotations

from typing import Any

from cai_agent.config import Settings
from cai_agent.llm.anthropic_messages import AnthropicMessagesLLM, DEFAULT_ANTHROPIC_BASE
from cai_agent.llm.openai_compat import OpenAICompatLLM


LLMClient = OpenAICompatLLM | AnthropicMessagesLLM


def make_llm(settings: Settings | None = None, **overrides: Any) -> LLMClient:
    settings = settings or Settings.from_env()
    provider = str(overrides.get("provider") or settings.provider or "openai").lower()
    mock = bool(overrides.get("mock", settings.mock))
    stream = bool(overrides.get("stream", settings.stream))
    model = str(overrides.get("model") or settings.model)
    api_key = str(overrides.get("api_key") or settings.api_key)
    trust_env = settings.http_trust_env

    if provider in ("anthropic", "anthropic-messages", "claude"):
        base = str(overrides.get("base_url") or settings.base_url or DEFAULT_ANTHROPIC_BASE)
        return AnthropicMessagesLLM(
            base_url=base,
            model=model,
            api_key=api_key,
            trust_env=trust_env,
            mock=mock,
            stream=stream,
        )

    base = str(overrides.get("base_url") or settings.base_url)
    return OpenAICompatLLM(
        base_url=base,
        model=model,
        api_key=api_key,
        trust_env=trust_env,
        mock=mock,
        stream=stream,
    )


def make_llm_from_env(**overrides: Any) -> LLMClient:
    return make_llm(Settings.from_env(), **overrides)
