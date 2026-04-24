"""ECC-01a: ecc layout / scaffold CLI 与 ecc_layout 单测。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from cai_agent.ecc_layout import build_ecc_asset_layout_payload, ecc_scaffold_workspace, iter_hooks_json_paths
from cai_agent.config import Settings

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


def test_ecc_scaffold_cli_json(tmp_path: Path) -> None:
    out = _cli(tmp_path, "ecc", "-w", str(tmp_path), "scaffold", "--json")
    assert out.returncode == 0, out.stderr
    r = json.loads((out.stdout or "").strip())
    assert r.get("schema_version") == "ecc_scaffold_result_v1"
