"""Hermes H1-MP: provider registry presets."""

from __future__ import annotations

from cai_agent.provider_registry import EXTRA_PRESETS, provider_readiness_snapshot, providers_json_payload


def test_extra_presets_merged_into_profiles() -> None:
    from cai_agent.profiles import PRESETS

    for k in ("openrouter", "kimi_moonshot", "nvidia_nim"):
        assert k in PRESETS


def test_providers_json_payload_schema() -> None:
    doc = providers_json_payload()
    assert doc["schema_version"] == "provider_registry_v1"
    assert doc["count"] == len(EXTRA_PRESETS)


def test_provider_readiness_snapshot() -> None:
    snap = provider_readiness_snapshot()
    assert snap["schema_version"] == "provider_readiness_v1"
    assert len(snap["entries"]) >= 1
