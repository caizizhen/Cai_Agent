"""ECC-N04 ingest draft snapshots under docs/schema remain valid JSON."""

from __future__ import annotations

import json
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_snapshot(name: str) -> dict:
    path = _repo_root() / "docs" / "schema" / name
    return json.loads(path.read_text(encoding="utf-8"))


def test_ecc_asset_registry_snapshot_shape() -> None:
    data = _load_snapshot("ecc_asset_registry_v1.snapshot.json")
    assert data.get("schema_version") == "ecc_asset_registry_v1"
    b = data.get("boundaries") or {}
    assert b.get("provenance_policy_included") is True


def test_ecc_ingest_sanitizer_policy_snapshot_shape() -> None:
    data = _load_snapshot("ecc_ingest_sanitizer_policy_v1.snapshot.json")
    assert data.get("schema_version") == "ecc_ingest_sanitizer_policy_v1"
    assert data.get("decision") in {"reject", "review", "allow_metadata_only"}


def test_ecc_ingest_provenance_trust_snapshot_shape() -> None:
    data = _load_snapshot("ecc_ingest_provenance_trust_v1.snapshot.json")
    assert data.get("schema_version") == "ecc_ingest_provenance_trust_v1"
    assert isinstance(data.get("trust_levels"), list)
    assert data.get("sample_evaluation", {}).get("combined_decision")
