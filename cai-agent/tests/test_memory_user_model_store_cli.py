"""HM-05a: ``memory user-model store`` / ``learn`` / ``query`` / ``export --with-store`` CLI 闭环。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"


def _run_cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
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


def test_user_model_store_learn_query_export_with_store_roundtrip(tmp_path: Path) -> None:
    ini = _run_cli(tmp_path, "memory", "user-model", "store", "init", "--json")
    assert ini.returncode == 0, ini.stderr
    o0 = json.loads((ini.stdout or "").strip())
    assert o0.get("schema_version") == "memory_user_model_store_init_v1"
    assert o0.get("ok") is True

    lr = _run_cli(
        tmp_path,
        "memory",
        "user-model",
        "learn",
        "--belief",
        "prefers small PRs for review",
        "--confidence",
        "0.62",
        "--tag",
        "workflow",
        "--json",
    )
    assert lr.returncode == 0, lr.stderr
    ol = json.loads((lr.stdout or "").strip())
    assert ol.get("schema_version") == "memory_user_model_learn_v1"
    assert ol.get("ok") is True
    assert ol.get("store_path")
    assert isinstance(ol.get("belief"), dict)

    qy = _run_cli(tmp_path, "memory", "user-model", "query", "--text", "PRs", "--json")
    assert qy.returncode == 0, qy.stderr
    oq = json.loads((qy.stdout or "").strip())
    assert oq.get("schema_version") == "memory_user_model_query_v1"
    assert oq.get("needle") == "PRs"
    assert isinstance(oq.get("hits"), list)
    assert len(oq["hits"]) >= 1

    ls = _run_cli(tmp_path, "memory", "user-model", "store", "list", "--limit", "10", "--json")
    assert ls.returncode == 0, ls.stderr
    osnap = json.loads((ls.stdout or "").strip())
    assert osnap.get("schema_version") == "memory_user_model_store_list_v1"
    assert len(osnap.get("beliefs") or []) >= 1

    ex = _run_cli(tmp_path, "memory", "user-model", "export", "--days", "3", "--with-store")
    assert ex.returncode == 0, ex.stderr
    bundle = json.loads((ex.stdout or "").strip())
    assert bundle.get("schema_version") == "user_model_bundle_v1"
    ust = bundle.get("user_model_store")
    assert isinstance(ust, dict)
    assert ust.get("schema_version") == "user_model_store_snapshot_v1"
    assert ust.get("store_exists") is True


def test_user_model_learn_empty_belief_exit_2(tmp_path: Path) -> None:
    _run_cli(tmp_path, "memory", "user-model", "store", "init", "--json")
    bad = _run_cli(tmp_path, "memory", "user-model", "learn", "--belief", "   ", "--json")
    assert bad.returncode == 2, bad.stderr
    ob = json.loads((bad.stdout or "").strip())
    assert ob.get("ok") is False
    assert ob.get("error") == "belief_invalid"


def test_build_user_model_bundle_v1_with_store_inprocess(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.chdir(tmp_path)
    toml = """[llm]
provider = "openai_compatible"
base_url = "http://127.0.0.1:9/v1"
model = "t"
api_key = ""

[agent]
mock = true
"""
    (tmp_path / "cai-agent.toml").write_text(toml, encoding="utf-8")
    from cai_agent.config import Settings
    from cai_agent.user_model import build_user_model_bundle_v1
    from cai_agent.user_model_store import init_user_model_store, upsert_belief

    init_user_model_store(tmp_path)
    upsert_belief(tmp_path, text="bundle store smoke", confidence=0.4)
    s = Settings.from_env(config_path=str(tmp_path / "cai-agent.toml"))
    b = build_user_model_bundle_v1(s, days=3, with_store=True)
    assert b.get("schema_version") == "user_model_bundle_v1"
    ust = b.get("user_model_store")
    assert isinstance(ust, dict)
    assert ust.get("store_exists") is True
    assert any((x.get("text") or "").startswith("bundle store") for x in (ust.get("beliefs") or []))
