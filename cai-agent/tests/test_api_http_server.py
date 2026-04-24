"""HM-02b：``api_http_server`` 最小只读 HTTP API。"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from cai_agent.api_http_server import AgentApiRequestHandler, AgentApiThreadingServer


def _start(ws: Path, token: str | None) -> AgentApiThreadingServer:
    httpd = AgentApiThreadingServer(("127.0.0.1", 0), AgentApiRequestHandler)
    httpd.workspace = ws
    httpd.api_token = token
    th = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    th.start()
    return httpd


def _url(httpd: AgentApiThreadingServer, path: str) -> str:
    host, port = httpd.server_address
    return f"http://{host}:{port}{path}"


def test_api_healthz_without_bearer_when_token_set(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start(root, "tok")
    try:
        url = _url(httpd, "/healthz")
        with urllib.request.urlopen(url, timeout=5) as resp:
            assert resp.status == 200
            assert (resp.headers.get("X-Cai-Agent-Api-Version") or "") == "0"
            body = json.loads(resp.read().decode("utf-8"))
        assert body.get("ok") is True
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_api_status_unauthorized_without_bearer(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start(root, "secret")
    try:
        url = _url(httpd, "/v1/status")
        with pytest.raises(urllib.error.HTTPError) as ei:
            urllib.request.urlopen(url, timeout=5)
        assert ei.value.code == 401
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_api_status_ok_with_bearer(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start(root, "abc")
    try:
        req = urllib.request.Request(_url(httpd, "/v1/status"))
        req.add_header("Authorization", "Bearer abc")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        assert data.get("schema_version") == "api_status_v1"
        assert data.get("workspace") == str(root)
        gs = data.get("gateway_summary") or {}
        assert gs.get("schema_version") == "gateway_summary_v1"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_api_doctor_summary_no_base_url(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    cfg = root / "cai-agent.toml"
    cfg.write_text(
        '[llm]\nprovider = "openai_compatible"\nbase_url = "http://127.0.0.1:9/v1"\n'
        'model = "m"\napi_key = "k"\n\n[agent]\nmock = true\n\n[models]\nactive = "default"\n',
        encoding="utf-8",
    )
    prev = __import__("os").environ.get("CAI_CONFIG")
    try:
        __import__("os").environ["CAI_CONFIG"] = str(cfg)
        httpd = _start(root, None)
        try:
            with urllib.request.urlopen(_url(httpd, "/v1/doctor/summary"), timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            assert data.get("schema_version") == "api_doctor_summary_v1"
            assert "base_url" not in data
            assert "model" not in data
            assert data.get("mock") is True
        finally:
            httpd.shutdown()
            httpd.server_close()
    finally:
        import os

        if prev is None:
            os.environ.pop("CAI_CONFIG", None)
        else:
            os.environ["CAI_CONFIG"] = prev


def test_api_run_due_dry_run_and_execute_forbidden(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start(root, None)
    try:
        base = _url(httpd, "/v1/tasks/run-due")
        req = urllib.request.Request(base, data=json.dumps({}).encode("utf-8"), method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=5) as resp:
            d1 = json.loads(resp.read().decode("utf-8"))
        assert d1.get("schema_version") == "api_tasks_run_due_v1"
        assert d1.get("mode") == "dry-run"

        req2 = urllib.request.Request(
            base,
            data=json.dumps({"dry_run": False}).encode("utf-8"),
            method="POST",
        )
        req2.add_header("Content-Type", "application/json")
        with pytest.raises(urllib.error.HTTPError) as ei:
            urllib.request.urlopen(req2, timeout=5)
        assert ei.value.code == 403
    finally:
        httpd.shutdown()
        httpd.server_close()
