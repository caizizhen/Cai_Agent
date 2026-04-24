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


def test_ops_dashboard_events_sse(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start_server(frozenset({root}), None)
    try:
        url = _url(
            httpd,
            "/v1/ops/dashboard/events",
            {"workspace": str(root), "max_events": "1", "live_interval_seconds": "1"},
        )
        with urllib.request.urlopen(url, timeout=5) as resp:
            body = resp.read().decode("utf-8")
            ctype = resp.headers.get("Content-Type") or ""
        assert "text/event-stream" in ctype
        assert "event: ops_dashboard" in body
        assert '"schema_version": "ops_dashboard_v1"' in body
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_ops_dashboard_html_live_mode_sse_injects_script(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start_server(frozenset({root}), None)
    try:
        url = _url(
            httpd,
            "/v1/ops/dashboard.html",
            {"workspace": str(root), "live_mode": "sse", "live_interval_seconds": "4"},
        )
        with urllib.request.urlopen(url, timeout=5) as resp:
            html = resp.read().decode("utf-8")
        assert "EventSource" in html
        assert "/v1/ops/dashboard/events?" in html
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_ops_dashboard_interactions_schedule_reorder_preview(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    (root / ".cai-schedule.json").write_text(
        json.dumps(
            {
                "schema_version": "1.1",
                "tasks": [
                    {"id": "task-a", "goal": "a"},
                    {"id": "task-b", "goal": "b"},
                    {"id": "task-c", "goal": "c"},
                ],
            },
        ),
        encoding="utf-8",
    )
    httpd = _start_server(frozenset({root}), None)
    try:
        url = _url(
            httpd,
            "/v1/ops/dashboard/interactions",
            {
                "workspace": str(root),
                "action": "schedule_reorder_preview",
                "task_id": "task-c",
                "before_task_id": "task-a",
            },
        )
        with urllib.request.urlopen(url, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        assert payload["schema_version"] == "ops_dashboard_interactions_v1"
        assert payload["dry_run"] is True
        assert payload["applied"] is False
        assert payload["preview_order"] == ["task-c", "task-a", "task-b"]
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_ops_dashboard_interactions_gateway_bind_edit_preview(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    gdir = root / ".cai" / "gateway"
    gdir.mkdir(parents=True)
    (gdir / "slack-session-map.json").write_text(
        json.dumps(
            {
                "schema_version": "gateway_slack_map_v1",
                "bindings": {"C1": {"session_file": "old.json", "label": "old"}},
                "allowed_channel_ids": [],
            },
        ),
        encoding="utf-8",
    )
    httpd = _start_server(frozenset({root}), None)
    try:
        url = _url(
            httpd,
            "/v1/ops/dashboard/interactions",
            {
                "workspace": str(root),
                "action": "gateway_bind_edit_preview",
                "platform": "slack",
                "binding_id": "C1",
                "session_file": "new.json",
                "label": "new",
            },
        )
        with urllib.request.urlopen(url, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        assert payload["ok"] is True
        assert payload["binding_found"] is True
        assert payload["preview_binding"]["session_file"] == "new.json"
        assert payload["summary"]["changed_fields"] == ["label", "session_file"]
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_ops_dashboard_interactions_rejects_unknown_action(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    httpd = _start_server(frozenset({root}), None)
    try:
        url = _url(
            httpd,
            "/v1/ops/dashboard/interactions",
            {"workspace": str(root), "action": "write_everything"},
        )
        with pytest.raises(urllib.error.HTTPError) as ei:
            urllib.request.urlopen(url, timeout=5)
        assert ei.value.code == 400
        payload = json.loads(ei.value.read().decode("utf-8"))
        assert payload["error"] == "unsupported_action"
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
