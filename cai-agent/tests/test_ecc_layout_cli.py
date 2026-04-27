"""ECC-01a: ecc layout / scaffold CLI 与 ecc_layout 单测。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from cai_agent.ecc_layout import (
    build_ecc_asset_layout_payload,
    build_ecc_harness_target_inventory_v1,
    ecc_scaffold_workspace,
    iter_hooks_json_paths,
)
from cai_agent.config import Settings
from cai_agent.exporter import build_export_ecc_dir_diff_report, build_ecc_home_sync_drift_v1
from cai_agent.plugin_registry import build_local_catalog_payload

_SRC = Path(__file__).resolve().parents[1] / "src"


def _cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_SRC)
    return subprocess.run(
        [sys.executable, "-m", "cai_agent", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_iter_hooks_json_paths_order(tmp_path: Path) -> None:
    p1 = tmp_path / "hooks" / "hooks.json"
    p1.parent.mkdir(parents=True, exist_ok=True)
    p1.write_text('{"hooks":[]}', encoding="utf-8")
    paths = list(iter_hooks_json_paths(tmp_path))
    assert paths[0] == p1.resolve()


def test_build_ecc_asset_layout_root_override(tmp_path: Path) -> None:
    s = Settings.from_env(config_path=None, workspace_hint=str(tmp_path))
    pl = build_ecc_asset_layout_payload(s, root_override=tmp_path)
    assert pl.get("schema_version") == "ecc_asset_layout_v1"
    assert pl.get("workspace") == str(tmp_path.resolve())
    assert isinstance(pl.get("entries"), list)


def test_ecc_scaffold_creates_files(tmp_path: Path) -> None:
    r = ecc_scaffold_workspace(tmp_path, dry_run=False)
    assert r.get("schema_version") == "ecc_scaffold_result_v1"
    assert (tmp_path / "rules" / "common" / "README.md").is_file()
    assert (tmp_path / "skills" / "README.md").is_file()
    assert (tmp_path / "hooks" / "hooks.json").is_file()
    r2 = ecc_scaffold_workspace(tmp_path, dry_run=False)
    assert not (r2.get("created") or [])


def test_ecc_layout_cli_json(tmp_path: Path) -> None:
    out = _cli(tmp_path, "ecc", "-w", str(tmp_path), "layout", "--json")
    assert out.returncode == 0, out.stderr
    pl = json.loads((out.stdout or "").strip())
    assert pl.get("schema_version") == "ecc_asset_layout_v1"


def test_build_ecc_harness_target_inventory_v1_schema(tmp_path: Path) -> None:
    s = Settings.from_env(config_path=None, workspace_hint=str(tmp_path))
    inv = build_ecc_harness_target_inventory_v1(s, root_override=tmp_path)
    assert inv.get("schema_version") == "ecc_harness_target_inventory_v1"
    assert inv.get("workspace") == str(tmp_path.resolve())
    targets = inv.get("targets")
    assert isinstance(targets, list) and len(targets) == 3
    assert {t.get("target") for t in targets if isinstance(t, dict)} == {"cursor", "codex", "opencode"}
    ws = inv.get("workspace_sources")
    assert isinstance(ws, list) and len(ws) == 4


def test_ecc_inventory_cli_json(tmp_path: Path) -> None:
    out = _cli(tmp_path, "ecc", "-w", str(tmp_path), "inventory", "--json")
    assert out.returncode == 0, out.stderr
    inv = json.loads((out.stdout or "").strip())
    assert inv.get("schema_version") == "ecc_harness_target_inventory_v1"


def test_ecc_scaffold_cli_json(tmp_path: Path) -> None:
    out = _cli(tmp_path, "ecc", "-w", str(tmp_path), "scaffold", "--json")
    assert out.returncode == 0, out.stderr
    r = json.loads((out.stdout or "").strip())
    assert r.get("schema_version") == "ecc_scaffold_result_v1"


def test_local_catalog_payload_schema(tmp_path: Path) -> None:
    s = Settings.from_env(config_path=None, workspace_hint=str(tmp_path))
    pl = build_local_catalog_payload(s, root_override=tmp_path)
    assert pl.get("schema_version") == "local_catalog_v1"
    assert pl.get("workspace") == str(tmp_path.resolve())
    assets = pl.get("assets")
    assert isinstance(assets, list)
    ids = {a.get("id") for a in assets if isinstance(a, dict)}
    assert {"rules", "skills", "hooks", "plugins"}.issubset(ids)


def test_ecc_catalog_cli_json(tmp_path: Path) -> None:
    out = _cli(tmp_path, "ecc", "-w", str(tmp_path), "catalog", "--json")
    assert out.returncode == 0, out.stderr
    pl = json.loads((out.stdout or "").strip())
    assert pl.get("schema_version") == "local_catalog_v1"
    assert isinstance(pl.get("assets"), list)


def test_ecc_sync_home_dry_run_json(tmp_path: Path) -> None:
    out = _cli(
        tmp_path,
        "ecc",
        "-w",
        str(tmp_path),
        "sync-home",
        "--all-targets",
        "--dry-run",
        "--json",
    )
    assert out.returncode == 0, out.stderr
    doc = json.loads((out.stdout or "").strip())
    assert doc.get("schema_version") == "ecc_home_sync_result_v1"
    assert doc.get("dry_run") is True
    plans = doc.get("plans") or []
    assert len(plans) == 3
    assert {p.get("schema_version") for p in plans if isinstance(p, dict)} == {"ecc_home_sync_plan_v1"}


def test_ecc_pack_manifest_cli_json(tmp_path: Path) -> None:
    out = _cli(tmp_path, "ecc", "-w", str(tmp_path), "pack-manifest", "--json")
    assert out.returncode == 0, out.stderr
    doc = json.loads((out.stdout or "").strip())
    assert doc.get("schema_version") == "ecc_asset_pack_manifest_v1"
    targets = doc.get("targets") or []
    assert len(targets) == 3
    assert all(isinstance(t.get("pack_sha256"), str) and len(t["pack_sha256"]) == 64 for t in targets)


def test_ecc_pack_import_dry_run_json(tmp_path: Path) -> None:
    src = tmp_path / "src-pack"
    (src / "rules" / "common").mkdir(parents=True)
    (src / "rules" / "common" / "a.md").write_text("x", encoding="utf-8")
    out = _cli(
        tmp_path,
        "ecc",
        "-w",
        str(tmp_path),
        "pack-import",
        "--from-workspace",
        str(src),
        "--json",
    )
    assert out.returncode == 0, out.stderr
    doc = json.loads((out.stdout or "").strip())
    assert doc.get("schema_version") == "ecc_asset_pack_import_plan_v1"
    comps = doc.get("components") or []
    rules = next((x for x in comps if isinstance(x, dict) and x.get("component") == "rules"), None)
    assert isinstance(rules, dict)
    assert rules.get("action") == "add"


def test_ecc_pack_import_apply_force_backs_up_conflict(tmp_path: Path) -> None:
    src = tmp_path / "src-pack"
    (src / "skills").mkdir(parents=True)
    (src / "skills" / "a.md").write_text("source", encoding="utf-8")
    dst = tmp_path / "skills"
    dst.mkdir()
    (dst / "a.md").write_text("old", encoding="utf-8")
    out = _cli(
        tmp_path,
        "ecc",
        "-w",
        str(tmp_path),
        "pack-import",
        "--from-workspace",
        str(src),
        "--apply",
        "--force",
        "--json",
    )
    assert out.returncode == 0, out.stderr
    doc = json.loads((out.stdout or "").strip())
    assert doc.get("schema_version") == "ecc_asset_pack_import_result_v1"
    assert doc.get("ok") is True
    assert (tmp_path / "skills" / "a.md").read_text(encoding="utf-8") == "source"
    backups = doc.get("backups") or []
    assert backups
    bpath = Path(str(backups[0].get("backup_path")))
    assert (bpath / "a.md").read_text(encoding="utf-8") == "old"


def test_ecc_pack_import_no_backup_requires_apply_force(tmp_path: Path) -> None:
    src = tmp_path / "src-pack"
    src.mkdir(parents=True)
    out = _cli(
        tmp_path,
        "ecc",
        "-w",
        str(tmp_path),
        "pack-import",
        "--from-workspace",
        str(src),
        "--no-backup",
    )
    assert out.returncode == 2
    assert "--no-backup 仅可与 --apply --force 联用" in (out.stderr or "")


def test_export_dry_run_json(tmp_path: Path) -> None:
    out = _cli(tmp_path, "export", "-w", str(tmp_path), "--target", "codex", "--dry-run")
    assert out.returncode == 0, out.stderr
    doc = json.loads((out.stdout or "").strip())
    assert doc.get("schema_version") == "ecc_home_sync_plan_v1"
    assert doc.get("target") == "codex"


def test_export_ecc_dir_diff_opencode_and_drift(tmp_path: Path) -> None:
    (tmp_path / "rules" / "common").mkdir(parents=True)
    (tmp_path / "rules" / "common" / "a.md").write_text("x", encoding="utf-8")
    s = Settings.from_env(config_path=None, workspace_hint=str(tmp_path))
    rep = build_export_ecc_dir_diff_report(s, target="opencode")
    assert rep.get("schema_version") == "export_ecc_dir_diff_v1"
    assert rep.get("target") == "opencode"
    drift = build_ecc_home_sync_drift_v1(s)
    assert drift.get("schema_version") == "ecc_home_sync_drift_v1"
    assert len(drift.get("diffs") or []) == 3
