"""ECC-N03-D04: structured home diff (add/update/skip/conflict) vs harness export roots."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from cai_agent.config import Settings
from cai_agent.exporter import (
    build_ecc_structured_home_diff_bundle_v1,
    build_export_ecc_structured_home_diff_v1,
)

_SRC = Path(__file__).resolve().parents[1] / "src"

_MIN_TOML = """[llm]
provider = "openai_compatible"
base_url = "http://127.0.0.1:9/v1"
model = "m"
api_key = "k"

[agent]
mock = true
"""


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


def test_structured_home_diff_counts_add_update_skip_conflict(tmp_path: Path) -> None:
    root = tmp_path
    (root / "cai-agent.toml").write_text(_MIN_TOML, encoding="utf-8")
    src_rules = root / "rules" / "x"
    src_rules.mkdir(parents=True)
    (src_rules / "only_src.md").write_text("a", encoding="utf-8")
    (src_rules / "both_same.md").write_text("same", encoding="utf-8")
    (src_rules / "both_diff.md").write_text("src", encoding="utf-8")

    ecc = root / ".cursor" / "cai-agent-export" / "rules" / "x"
    ecc.mkdir(parents=True)
    (ecc / "both_same.md").write_text("same", encoding="utf-8")
    (ecc / "both_diff.md").write_text("dst", encoding="utf-8")
    (ecc / "only_dst.md").write_text("orphan", encoding="utf-8")

    s = Settings.from_env(config_path=str(root / "cai-agent.toml"), workspace_hint=str(root))
    rep = build_export_ecc_structured_home_diff_v1(s, target="cursor")
    assert rep.get("schema_version") == "ecc_structured_home_diff_v1"
    dirs = {d.get("name"): d for d in (rep.get("directories") or []) if isinstance(d, dict)}
    assert "rules" in dirs
    c = dirs["rules"].get("counts") or {}
    assert c.get("add") == 1
    assert c.get("update") == 1
    assert c.get("skip") == 1
    assert c.get("conflict") == 1
    tot = rep.get("totals") or {}
    assert tot.get("add") >= 1
    assert tot.get("update") >= 1


def test_structured_home_diff_bundle_pending_targets(tmp_path: Path) -> None:
    root = tmp_path
    (root / "cai-agent.toml").write_text(_MIN_TOML, encoding="utf-8")
    (root / "skills" / "s").mkdir(parents=True)
    (root / "skills" / "s" / "a.md").write_text("x", encoding="utf-8")
    s = Settings.from_env(config_path=str(root / "cai-agent.toml"), workspace_hint=str(root))
    b = build_ecc_structured_home_diff_bundle_v1(s)
    assert b.get("schema_version") == "ecc_structured_home_diff_bundle_v1"
    pending = b.get("targets_with_pending_actions") or []
    assert isinstance(pending, list)
    assert "cursor" in pending or "opencode" in pending


def test_ecc_home_diff_cli_bundle_json(tmp_path: Path) -> None:
    (tmp_path / "cai-agent.toml").write_text(_MIN_TOML, encoding="utf-8")
    out = _cli(tmp_path, "ecc", "--config", str(tmp_path / "cai-agent.toml"), "-w", str(tmp_path), "home-diff", "--json")
    assert out.returncode == 0, out.stderr
    doc = json.loads((out.stdout or "").strip())
    assert doc.get("schema_version") == "ecc_structured_home_diff_bundle_v1"


def test_ecc_home_diff_cli_single_target_json(tmp_path: Path) -> None:
    (tmp_path / "cai-agent.toml").write_text(_MIN_TOML, encoding="utf-8")
    out = _cli(
        tmp_path,
        "ecc",
        "--config",
        str(tmp_path / "cai-agent.toml"),
        "-w",
        str(tmp_path),
        "home-diff",
        "--target",
        "codex",
        "--json",
    )
    assert out.returncode == 0, out.stderr
    doc = json.loads((out.stdout or "").strip())
    assert doc.get("schema_version") == "ecc_structured_home_diff_v1"
    assert doc.get("target") == "codex"
