from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"


def _run_cli(cwd: Path, *args: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_SRC)
    if env_extra:
        env.update(env_extra)
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
    assert payload["builtin_registry"]["schema_version"] == "memory_provider_builtin_registry_v1"
    assert payload["builtin_registry"]["provider_ids"] == ["local_entries_jsonl", "local_user_model_sqlite"]
    assert payload["user_model_provider_coverage"]["external_graph"] is None
    assert payload["external_adapters"][0]["status"] == "mock_http_available"


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


def test_memory_provider_use_and_test_flow(tmp_path: Path) -> None:
    use_r = _run_cli(tmp_path, "memory", "provider", "use", "--id", "local_user_model_sqlite", "--json")
    assert use_r.returncode == 0, use_r.stderr
    use_p = json.loads(use_r.stdout)
    assert use_p["schema_version"] == "memory_provider_use_v1"
    assert use_p["active_provider"] == "local_user_model_sqlite"
    state_file = Path(str(use_p["state_file"]))
    assert state_file.is_file()

    list_r = _run_cli(tmp_path, "memory", "provider", "list", "--json")
    assert list_r.returncode == 0, list_r.stderr
    list_p = json.loads(list_r.stdout)
    assert list_p["active_provider"] == "local_user_model_sqlite"
    assert list_p["active_provider_source"] == "config"
    assert list_p["builtin_registry"]["schema_version"] == "memory_provider_builtin_registry_v1"

    test_r = _run_cli(tmp_path, "memory", "provider", "test", "--json")
    assert test_r.returncode == 0, test_r.stderr
    test_p = json.loads(test_r.stdout)
    assert test_p["schema_version"] == "memory_provider_test_v1"
    assert test_p["provider_id"] == "local_user_model_sqlite"
    assert test_p["ok"] is True


def test_memory_provider_use_rejects_unknown_provider(tmp_path: Path) -> None:
    r = _run_cli(tmp_path, "memory", "provider", "use", "--id", "unknown-provider", "--json")
    assert r.returncode == 2, r.stderr
    p = json.loads(r.stdout)
    assert p["schema_version"] == "memory_provider_use_v1"
    assert p["error"] == "provider_not_found"


def test_memory_provider_test_external_mock_http(tmp_path: Path) -> None:
    class _H(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path != "/health":
                self.send_response(404)
                self.end_headers()
                return
            body = json.dumps({"ok": True, "schema_version": "memory_external_provider_health_v1"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):  # type: ignore[override]
            return

    srv = ThreadingHTTPServer(("127.0.0.1", 0), _H)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        url = f"http://127.0.0.1:{srv.server_address[1]}"
        r = _run_cli(
            tmp_path,
            "memory",
            "provider",
            "test",
            "--id",
            "honcho_external",
            "--json",
            env_extra={"CAI_MEMORY_EXTERNAL_MOCK_URL": url},
        )
    finally:
        srv.shutdown()
        srv.server_close()
        th.join(timeout=2.0)
    assert r.returncode == 0, r.stderr
    p = json.loads(r.stdout)
    assert p["schema_version"] == "memory_provider_test_v1"
    assert p["provider_id"] == "honcho_external"
    assert p["ok"] is True
    checks = p.get("checks") or {}
    assert checks.get("remote_schema_version") == "memory_external_provider_health_v1"
