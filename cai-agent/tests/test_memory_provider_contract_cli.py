from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
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


def test_memory_provider_contract_empty_workspace_does_not_create_store(tmp_path: Path) -> None:
    result = _run_cli(tmp_path, "memory", "provider", "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == "memory_provider_contract_v1"
    assert payload["default_provider"] == "local_entries_jsonl"
    assert payload["ok"] is True
    assert (tmp_path / ".cai" / "user_model_store.sqlite3").exists() is False
    providers = {row["id"]: row for row in payload["providers"]}
    assert providers["local_entries_jsonl"]["exists"] is False
    assert providers["local_user_model_sqlite"]["status"] == "available"
    assert payload["user_model_provider_coverage"]["external_graph"] is None
    assert payload["external_adapters"][0]["status"] == "future_adapter"


def test_memory_provider_contract_reports_entries_and_user_model_store(tmp_path: Path) -> None:
    mem = tmp_path / "memory"
    mem.mkdir()
    ts = datetime.now(UTC).isoformat()
    (mem / "entries.jsonl").write_text(
        json.dumps(
            {
                "id": "m1",
                "category": "preference",
                "text": "prefers compact summaries",
                "confidence": 0.8,
                "expires_at": None,
                "created_at": ts,
            },
        )
        + "\n",
        encoding="utf-8",
    )
    learn = _run_cli(
        tmp_path,
        "memory",
        "user-model",
        "learn",
        "--belief",
        "likes provider-neutral contracts",
        "--json",
    )
    assert learn.returncode == 0, learn.stderr
    result = _run_cli(tmp_path, "memory", "provider", "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    providers = {row["id"]: row for row in payload["providers"]}
    assert providers["local_entries_jsonl"]["counts"]["valid_entries"] == 1
    assert providers["local_user_model_sqlite"]["exists"] is True
    assert providers["local_user_model_sqlite"]["counts"]["beliefs"] == 1
