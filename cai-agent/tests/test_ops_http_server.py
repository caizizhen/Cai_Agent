"""``ops_http_server``：只读 dashboard / dashboard.html HTTP 契约（Phase B）。"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

from cai_agent.ops_http_server import OpsApiRequestHandler, OpsApiThreadingServer


def _start_server(allow: frozenset[Path], token: str | None) -> OpsApiThreadingServer:
    httpd = OpsApiThreadingServer(("127.0.0.1", 0), OpsApiRequestHandler)
    httpd.allow_roots = allow
    httpd.api_token = token
    th = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    th.start()
    return httpd


def _url(httpd: OpsApiThreadingServer, path: str, query: dict[str, str]) -> str:
    host, port = httpd.server_address
    qs = urllib.parse.urlencode(query)
    return f"http://{host}:{port}{path}?{qs}"


def test_ops_dashboard_missing_workspace(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start_server(frozenset({root}), None)
    try:
        url = _url(httpd, "/v1/ops/dashboard", {})
        with pytest.raises(urllib.error.HTTPError) as ei:
            urllib.request.urlopen(url, timeout=5)
        assert ei.value.code == 400
        body = json.loads(ei.value.read().decode("utf-8"))
        assert body.get("error") == "missing_workspace"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_ops_dashboard_workspace_forbidden(tmp_path: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
    root = tmp_path.resolve()
    other = tmp_path_factory.mktemp("other").resolve()
    httpd = _start_server(frozenset({root}), None)
    try:
        url = _url(httpd, "/v1/ops/dashboard", {"workspace": str(other)})
        with pytest.raises(urllib.error.HTTPError) as ei:
            urllib.request.urlopen(url, timeout=5)
        assert ei.value.code == 403
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_ops_dashboard_ok_json(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start_server(frozenset({root}), None)
    try:
        url = _url(
            httpd,
            "/v1/ops/dashboard",
            {"workspace": str(root), "observe_pattern": ".cai-session*.json", "observe_limit": "5"},
        )
        with urllib.request.urlopen(url, timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
        assert data.get("schema_version") == "ops_dashboard_v1"
        assert data.get("workspace") == str(root)
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_ops_dashboard_html(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start_server(frozenset({root}), None)
    try:
        url = _url(httpd, "/v1/ops/dashboard.html", {"workspace": str(root)})
        with urllib.request.urlopen(url, timeout=5) as resp:
            assert resp.status == 200
            ctype = resp.headers.get("Content-Type") or ""
            assert "text/html" in ctype
            assert (resp.headers.get("Cache-Control") or "") == "no-store"
            html = resp.read().decode("utf-8")
        assert "ops_dashboard" in html or "CAI" in html or "cai-agent" in html.lower()
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_ops_dashboard_bad_pattern(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start_server(frozenset({root}), None)
    try:
        url = _url(httpd, "/v1/ops/dashboard", {"workspace": str(root), "observe_pattern": "x/y"})
        with pytest.raises(urllib.error.HTTPError) as ei:
            urllib.request.urlopen(url, timeout=5)
        assert ei.value.code == 400
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_ops_dashboard_unauthorized(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = OpsApiThreadingServer(("127.0.0.1", 0), OpsApiRequestHandler)
    httpd.allow_roots = frozenset({root})
    httpd.api_token = "secret-test-token"
    th = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    th.start()
    try:
        url = _url(httpd, "/v1/ops/dashboard", {"workspace": str(root)})
        with pytest.raises(urllib.error.HTTPError) as ei:
            urllib.request.urlopen(url, timeout=5)
        assert ei.value.code == 401
        req = urllib.request.Request(url, headers={"Authorization": "Bearer secret-test-token"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 200
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_ops_dashboard_html_refresh_query(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start_server(frozenset({root}), None)
    try:
        url = _url(
            httpd,
            "/v1/ops/dashboard.html",
            {"workspace": str(root), "html_refresh_seconds": "20"},
        )
        with urllib.request.urlopen(url, timeout=5) as resp:
            html = resp.read().decode("utf-8")
        assert 'http-equiv="refresh"' in html
        assert 'content="20"' in html
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_ops_not_found(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start_server(frozenset({root}), None)
    try:
        url = _url(httpd, "/v1/other", {"workspace": str(root)})
        with pytest.raises(urllib.error.HTTPError) as ei:
            urllib.request.urlopen(url, timeout=5)
        assert ei.value.code == 404
    finally:
        httpd.shutdown()
        httpd.server_close()
