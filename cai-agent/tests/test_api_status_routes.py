"""HM-N03-D01: ``api serve`` 状态类路由（/v1/health、/v1/ready）与 liveness 契约。"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from cai_agent.api_http_server import AgentApiRequestHandler, AgentApiThreadingServer


def _start(ws: Path, token: str | None, *, config_path: str | None = None) -> AgentApiThreadingServer:
    httpd = AgentApiThreadingServer(("127.0.0.1", 0), AgentApiRequestHandler)
    httpd.workspace = ws
    httpd.api_token = token
    httpd.api_config_path = config_path
    th = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    th.start()
    return httpd


def _url(httpd: AgentApiThreadingServer, path: str) -> str:
    host, port = httpd.server_address
    return f"http://{host}:{port}{path}"


def test_v1_health_requires_bearer_when_token_set(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start(root, "tok")
    try:
        with pytest.raises(urllib.error.HTTPError) as ei:
            urllib.request.urlopen(_url(httpd, "/v1/health"), timeout=5)
        assert ei.value.code == 401
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_v1_health_ok_with_bearer(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start(root, "sec")
    try:
        req = urllib.request.Request(_url(httpd, "/v1/health"))
        req.add_header("Authorization", "Bearer sec")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        assert data.get("schema_version") == "api_health_v1"
        assert data.get("ok") is True
        assert data.get("auth_enforced") is True
        assert data.get("workspace") == str(root)
        assert isinstance(data.get("cai_agent_version"), str)
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_v1_health_no_bearer_when_token_unset(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start(root, None)
    try:
        with urllib.request.urlopen(_url(httpd, "/v1/health"), timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        assert data.get("schema_version") == "api_health_v1"
        assert data.get("auth_enforced") is False
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_v1_ready_ok_with_config(tmp_path: Path) -> None:
    ws = (tmp_path / "w").resolve()
    ws.mkdir()
    cfg = tmp_path / "c.toml"
    cfg.write_text(
        "\n".join(
            [
                "[llm]",
                'provider = "openai_compatible"',
                'base_url = "http://127.0.0.1:9/v1"',
                'model = "m"',
                'api_key = "k"',
                "",
                "[agent]",
                "mock = true",
                "",
                "[models]",
                'active = "p1"',
                "",
                "[[models.profile]]",
                'id = "p1"',
                'provider = "openai_compatible"',
                'base_url = "http://127.0.0.1:9/v1"',
                'model = "m"',
                'api_key = "k"',
                "",
            ],
        ),
        encoding="utf-8",
    )
    httpd = _start(ws, None, config_path=str(cfg))
    try:
        req = urllib.request.Request(_url(httpd, "/v1/ready"))
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        assert data.get("schema_version") == "api_ready_v1"
        assert data.get("ok") is True
        assert data.get("mock") is True
        assert data.get("has_config_file") is True
        assert data.get("active_profile_id") == "p1"
        assert int(data.get("profiles_count") or 0) >= 1
    finally:
        httpd.shutdown()
        httpd.server_close()
