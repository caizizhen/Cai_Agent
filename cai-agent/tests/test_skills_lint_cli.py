"""CLI skills lint + hub fetch."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_SRC)
    return subprocess.run(
        [sys.executable, "-m", "cai_agent", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=30,
    )


def test_skills_lint_json(tmp_path: Path) -> None:
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "bad.md").write_text("# no frontmatter\n", encoding="utf-8")
    good = """---
name: Good Skill
description: This is a compliant enough description for lint.
---

""" + ("content line\n" * 10)
    (tmp_path / "skills" / "good.md").write_text(good, encoding="utf-8")
    cfg = tmp_path / "cai-agent.toml"
    cfg.write_text(
        '[llm]\nbase_url = "http://127.0.0.1:9/v1"\nmodel = "m"\napi_key = "k"\n',
        encoding="utf-8",
    )
    p = _run(
        ["skills", "--config", str(cfg), "lint", "--json"],
        cwd=tmp_path,
    )
    assert p.returncode == 2, p.stderr
    doc = json.loads(p.stdout)
    assert doc["schema_version"] == "skills_lint_v1"
    assert doc["violation_count"] >= 1


def test_skills_hub_fetch_local_http(tmp_path: Path) -> None:
    manifest = {
        "schema_version": "skills_hub_manifest_v2",
        "entries": [],
        "count": 0,
    }

    class H(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(manifest).encode("utf-8"))

        def log_message(self, *args: object) -> None:
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    try:
        url = f"http://127.0.0.1:{port}/m.json"
        p = _run(["skills", "hub", "fetch", url, "--json"], cwd=tmp_path)
        assert p.returncode == 0, p.stderr
        out = json.loads(p.stdout)
        assert out.get("schema_version") == "skills_hub_fetch_v1"
        assert out.get("manifest", {}).get("schema_version") == "skills_hub_manifest_v2"
    finally:
        srv.shutdown()
        th.join(timeout=2)
