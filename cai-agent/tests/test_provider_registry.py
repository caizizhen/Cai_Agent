"""Hermes H1-MP: provider registry presets."""

from __future__ import annotations

import json
from pathlib import Path

from cai_agent.provider_registry import EXTRA_PRESETS, provider_readiness_snapshot, providers_json_payload

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "cai_agent"
    / "schemas"
    / "provider_registry_v1.schema.json"
)


def test_extra_presets_merged_into_profiles() -> None:
    from cai_agent.profiles import PRESETS

    for k in ("openrouter", "kimi_moonshot", "nvidia_nim"):
        assert k in PRESETS


def test_providers_json_payload_schema() -> None:
    doc = providers_json_payload()
    assert doc["schema_version"] == "provider_registry_v1"
    assert doc["count"] == len(EXTRA_PRESETS)
    row = next(r for r in doc["providers"] if r["id"] == "zai_glm")
    hint = row.get("capabilities_hint")
    assert hint["schema_version"] == "model_capabilities_v1"
    assert hint["profile_id"] == "zai_glm"
    assert hint["provider"] == "openai_compatible"
    assert hint["context_window"] == 200_000
    assert hint["cost_hint"] == "provider_dependent"
    assert "api_key" not in hint
    assert "base_url" not in hint
    caps = hint["capabilities"]
    assert "streaming" in caps
    assert "local_private" in caps
    expectations = {
        "nous_portal": 128_000,
        "nvidia_nim": 128_000,
        "xiaomi_mimo": 1_000_000,
        "kimi_moonshot": 256_000,
        "minimax": 204_800,
        "huggingface": 8_192,
    }
    for preset_id, expected_ctx in expectations.items():
        preset_row = next(r for r in doc["providers"] if r["id"] == preset_id)
        preset_hint = preset_row.get("capabilities_hint") or {}
        assert preset_hint.get("context_window") == expected_ctx


def test_provider_registry_v1_schema_file() -> None:
    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert schema["properties"]["schema_version"]["const"] == "provider_registry_v1"
    assert "providers" in schema.get("required", [])
    provider_props = schema["properties"]["providers"]["items"]["properties"]
    assert "capabilities_hint" in provider_props
    hint = provider_props["capabilities_hint"]
    assert hint["properties"]["schema_version"]["const"] == "model_capabilities_v1"


def test_provider_readiness_snapshot() -> None:
    snap = provider_readiness_snapshot()
    assert snap["schema_version"] == "provider_readiness_v1"
    assert len(snap["entries"]) >= 1
    first = snap["entries"][0]
    assert (first.get("capabilities_hint") or {}).get("schema_version") == "model_capabilities_v1"
