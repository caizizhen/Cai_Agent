"""ECC-N02-D04: ecc pack-repair report vs manifest/export."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from cai_agent.config import Settings
from cai_agent.exporter import build_ecc_asset_pack_repair_report_v1

_SRC = Path(__file__).resolve().parents[1] / "src"

_MIN_TOML = """[llm]
provider = "openai_compatible"
base_url = "http://127.0.0.1:9/v1"
model = "m"
api_key = "k"
[agent]
mock = true
"""


def _write_config(root: Path) -> Path:
    p = root / "cai-agent.toml"
    p.write_text(_MIN_TOML, encoding="utf-8")
    return p


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


def _cli_export_ws(root: Path, cfg: Path, *tail: str) -> subprocess.CompletedProcess[str]:
    return _cli(root, "export", "--config", str(cfg), "-w", str(root), *tail)


def _cli_ecc_ws(root: Path, cfg: Path, *tail: str) -> subprocess.CompletedProcess[str]:
    return _cli(root, "ecc", "--config", str(cfg), "-w", str(root), *tail)


def test_build_ecc_asset_pack_repair_report_schema(tmp_path: Path) -> None:
    _write_config(tmp_path)
    s = Settings.from_env(config_path=str(tmp_path / "cai-agent.toml"), workspace_hint=str(tmp_path))
    r = build_ecc_asset_pack_repair_report_v1(s, targets=("cursor",))
    assert r.get("schema_version") == "ecc_asset_pack_repair_report_v1"
    assert "issues" in r
    assert "repair_suggestions" in r
    assert "compat_hints" in r
    kinds = [i.get("kind") for i in (r.get("issues") or []) if isinstance(i, dict)]
    assert "missing_export_file" in kinds


def test_pack_repair_cli_json_after_export(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path)
    (tmp_path / "rules" / "common").mkdir(parents=True)
    (tmp_path / "rules" / "common" / "r.md").write_text("r", encoding="utf-8")
    (tmp_path / "skills").mkdir(parents=True)
    (tmp_path / "skills" / "s.md").write_text("s", encoding="utf-8")
    ex = _cli_export_ws(tmp_path, cfg, "--target", "cursor")
    assert ex.returncode == 0, ex.stderr
    out = _cli_ecc_ws(tmp_path, cfg, "pack-repair", "--target", "cursor", "--json")
    assert out.returncode == 0, out.stderr
    doc = json.loads((out.stdout or "").strip())
    assert doc.get("schema_version") == "ecc_asset_pack_repair_report_v1"
    assert doc.get("ok") is True
    assert doc.get("error_issues") == 0


def test_pack_repair_detects_manifest_schema_drift(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path)
    (tmp_path / "rules" / "common").mkdir(parents=True)
    (tmp_path / "rules" / "common" / "r.md").write_text("r", encoding="utf-8")
    (tmp_path / "skills").mkdir(parents=True)
    (tmp_path / "skills" / "s.md").write_text("s", encoding="utf-8")
    assert _cli_export_ws(tmp_path, cfg, "--target", "cursor").returncode == 0
    man = tmp_path / ".cursor" / "cai-agent-export" / "cai-export-manifest.json"
    data = json.loads(man.read_text(encoding="utf-8"))
    data["local_catalog_schema_version"] = "stale_catalog_schema_x"
    man.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out = _cli_ecc_ws(tmp_path, cfg, "pack-repair", "--target", "cursor", "--json")
    assert out.returncode == 0
    doc = json.loads((out.stdout or "").strip())
    kinds = [i.get("kind") for i in (doc.get("issues") or []) if isinstance(i, dict)]
    assert "export_manifest_schema_drift" in kinds


def test_pack_repair_detects_catalog_hash_drift(tmp_path: Path) -> None:
    cfg = _write_config(tmp_path)
    (tmp_path / "rules" / "common").mkdir(parents=True)
    (tmp_path / "rules" / "common" / "r.md").write_text("r", encoding="utf-8")
    (tmp_path / "skills").mkdir(parents=True)
    (tmp_path / "skills" / "s.md").write_text("s", encoding="utf-8")
    assert _cli_export_ws(tmp_path, cfg, "--target", "cursor").returncode == 0
    cat = tmp_path / ".cursor" / "cai-agent-export" / "cai-local-catalog.json"
    cat.write_text(cat.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    out = _cli_ecc_ws(tmp_path, cfg, "pack-repair", "--target", "cursor", "--json")
    assert out.returncode == 0, out.stderr
    doc = json.loads((out.stdout or "").strip())
    kinds = [i.get("kind") for i in (doc.get("issues") or []) if isinstance(i, dict)]
    assert "export_catalog_drift" in kinds
