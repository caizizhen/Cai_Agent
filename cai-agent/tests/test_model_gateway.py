from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from cai_agent import model_gateway
from cai_agent.profiles import Profile

_SCHEMAS = Path(__file__).resolve().parents[1] / "src" / "cai_agent" / "schemas"


def test_canonical_provider_aliases() -> None:
    assert model_gateway.canonical_provider("claude-3-opus") == "anthropic"
    assert model_gateway.canonical_provider("OpenAI") == "openai"
    assert model_gateway.canonical_provider("unknown-provider") == "openai_compatible"


def test_infer_local_openai_compatible_capabilities() -> None:
    profile = Profile(
        id="local",
        provider="openai_compatible",
        base_url="http://127.0.0.1:1234/v1",
        model="qwen3-coder",
        api_key="local",
        temperature=0.2,
        timeout_sec=60.0,
        context_window=32768,
    )
    caps = model_gateway.infer_model_capabilities(profile).to_public_dict()
    assert caps["schema_version"] == "model_capabilities_v1"
    assert caps["context_window"] == 32768
    assert caps["capabilities"]["local_private"] == "yes"
    assert caps["capabilities"]["reasoning"] == "yes"
    assert caps["cost_hint"] == "local"


def test_build_model_capabilities_payload_uses_fallback_context() -> None:
    profile = Profile(
        id="remote",
        provider="openai",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
        api_key="k",
        temperature=0.2,
        timeout_sec=60.0,
    )
    payload = model_gateway.build_model_capabilities_payload(
        (profile,),
        active_profile_id="remote",
        context_window_fallback=8192,
    )
    assert payload["schema_version"] == "model_capabilities_list_v1"
    assert payload["active_profile_id"] == "remote"
    assert payload["profiles"][0]["context_window"] == 8192
    assert payload["profiles"][0]["capabilities"]["json_mode"] == "yes"


def test_model_capabilities_schema_files() -> None:
    caps_schema = json.loads((_SCHEMAS / "model_capabilities_v1.schema.json").read_text(encoding="utf-8"))
    list_schema = json.loads(
        (_SCHEMAS / "model_capabilities_list_v1.schema.json").read_text(encoding="utf-8"),
    )
    assert caps_schema["properties"]["schema_version"]["const"] == "model_capabilities_v1"
    assert "capabilities" in caps_schema.get("required", [])
    cap_props = caps_schema["properties"]["capabilities"]["properties"]
    for key in ("chat", "streaming", "tool_calling", "vision", "json_mode", "reasoning", "local_private"):
        assert key in cap_props
    assert list_schema["properties"]["schema_version"]["const"] == "model_capabilities_list_v1"
    assert "profiles" in list_schema.get("required", [])


def test_model_response_v1_schema_file() -> None:
    doc = json.loads((_SCHEMAS / "model_response_v1.schema.json").read_text(encoding="utf-8"))
    assert doc["properties"]["schema_version"]["const"] == "model_response_v1"
    assert "usage" in doc.get("required", [])
    assert "latency_ms" in doc.get("required", [])


def test_chat_response_wraps_existing_mock_adapter() -> None:
    settings = SimpleNamespace(
        provider="openai_compatible",
        base_url="http://127.0.0.1:9/v1",
        model="mock-model",
        api_key="k",
        temperature=0.2,
        llm_timeout_sec=5.0,
        http_trust_env=False,
        llm_max_http_retries=1,
        mock=True,
        active_profile_id="p1",
    )
    resp = model_gateway.chat_response(
        settings,
        [{"role": "user", "content": "hello"}],
    )
    doc = resp.to_public_dict()
    assert doc["schema_version"] == "model_response_v1"
    assert doc["provider"] == "openai_compatible"
    assert doc["model"] == "mock-model"
    assert doc["profile_id"] == "p1"
    assert "CAI_MOCK" in doc["content"]


def test_classify_model_exception_common_cases() -> None:
    assert model_gateway.classify_model_exception(RuntimeError("HTTP 429"))["status"] == "RATE_LIMIT"
    assert model_gateway.classify_model_exception(RuntimeError("model not found"))["status"] == "MODEL_NOT_FOUND"
    assert model_gateway.classify_model_exception(RuntimeError("context length exceeded"))["status"] == "CONTEXT_TOO_LARGE"
