from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run_cli(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    src = Path(__file__).resolve().parents[1] / "src"
    env["PYTHONPATH"] = str(src)
    return subprocess.run(
        [sys.executable, "-m", "cai_agent", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_gateway_platforms_list_json(tmp_path: Path) -> None:
    p = _run_cli(["gateway", "platforms", "list", "--json"], cwd=tmp_path)
    assert p.returncode == 0, p.stderr
    o = json.loads(p.stdout.strip())
    assert o.get("schema_version") == "gateway_platforms_v1"
    pl = o.get("platforms")
    assert isinstance(pl, list) and len(pl) >= 3
    ids = {x.get("id") for x in pl if isinstance(x, dict)}
    assert "telegram" in ids and "discord" in ids
    assert o.get("adapter_contract_schema_version") == "gateway_platform_adapter_contract_v1"
    tg = next((x for x in pl if isinstance(x, dict) and x.get("id") == "telegram"), {})
    ac = tg.get("adapter_contract") if isinstance(tg.get("adapter_contract"), dict) else {}
    assert ac.get("schema_version") == "gateway_platform_adapter_contract_v1"
    assert (ac.get("health") or {}).get("supported") is True


def test_ops_dashboard_json(tmp_path: Path) -> None:
    p = _run_cli(["ops", "dashboard", "--json"], cwd=tmp_path)
    assert p.returncode == 0, p.stderr
    o = json.loads(p.stdout.strip())
    assert o.get("schema_version") == "ops_dashboard_v1"
    assert isinstance(o.get("board"), dict)
    assert isinstance(o.get("gateway_summary"), dict)
    assert (o.get("gateway_summary") or {}).get("schema_version") == "gateway_summary_v1"
    assert isinstance(o.get("schedule_stats"), dict)
    assert isinstance(o.get("cost_aggregate"), dict)
    sm = o.get("summary")
    assert isinstance(sm, dict)
    assert "failure_rate" in sm
    assert "gateway_status" in sm
    assert isinstance((o.get("board") or {}).get("gateway_summary"), dict)


def test_skills_hub_manifest_json(tmp_path: Path) -> None:
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "demo.md").write_text("# demo\n", encoding="utf-8")
    p = _run_cli(["skills", "hub", "manifest", "--json"], cwd=tmp_path)
    assert p.returncode == 0, p.stderr
    o = json.loads(p.stdout.strip())
    assert o.get("schema_version") == "skills_hub_manifest_v2"
    assert o.get("count") == 1
    ent = (o.get("entries") or [{}])[0]
    assert ent.get("name") == "demo.md"
