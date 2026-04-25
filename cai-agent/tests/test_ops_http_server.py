"""``ops_http_server``：只读 dashboard / dashboard.html HTTP 契约（Phase B）。"""

from __future__ import annotations

import json
import threading
import tomllib
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


def test_ops_dashboard_interactions_schedule_reorder_apply(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    sched = root / ".cai-schedule.json"
    sched.write_text(
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
                "mode": "apply",
                "action": "schedule_reorder_preview",
                "task_id": "task-c",
                "before_task_id": "task-a",
            },
        )
        with urllib.request.urlopen(url, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        assert payload["ok"] is True
        assert payload["applied"] is True
        doc = json.loads(sched.read_text(encoding="utf-8"))
        ids = [str(t.get("id")) for t in (doc.get("tasks") or [])]
        assert ids == ["task-c", "task-a", "task-b"]
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


def test_ops_dashboard_interactions_gateway_bind_edit_apply_and_audit(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    gdir = root / ".cai" / "gateway"
    gdir.mkdir(parents=True)
    mpath = gdir / "slack-session-map.json"
    mpath.write_text(
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
        apply_url = _url(
            httpd,
            "/v1/ops/dashboard/interactions",
            {
                "workspace": str(root),
                "mode": "apply",
                "action": "gateway_bind_edit_preview",
                "platform": "slack",
                "binding_id": "C1",
                "session_file": "new.json",
                "label": "new",
            },
        )
        with urllib.request.urlopen(apply_url, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        assert payload["ok"] is True
        assert payload["applied"] is True
        doc = json.loads(mpath.read_text(encoding="utf-8"))
        row = ((doc.get("bindings") or {}).get("C1") or {})
        assert row.get("session_file") == "new.json"
        assert row.get("label") == "new"

        audit_url = _url(
            httpd,
            "/v1/ops/dashboard/interactions",
            {"workspace": str(root), "mode": "audit", "action": "gateway_bind_edit_preview"},
        )
        with urllib.request.urlopen(audit_url, timeout=5) as resp:
            audit = json.loads(resp.read().decode("utf-8"))
        assert audit["ok"] is True
        assert audit["audit_schema_version"] == "ops_dashboard_action_audit_v1"
        assert int(audit.get("records_count") or 0) >= 1
        assert isinstance(audit.get("records"), list)
        assert (audit.get("records") or [])[0].get("schema_version") == "ops_dashboard_action_audit_v1"
        assert "actor" in (audit.get("records") or [])[0]

        audit_filtered_url = _url(
            httpd,
            "/v1/ops/dashboard/interactions",
            {
                "workspace": str(root),
                "mode": "audit",
                "action": "gateway_bind_edit_preview",
                "filter_action": "gateway_bind_edit_preview",
                "filter_mode": "apply",
                "ok": "true",
            },
        )
        with urllib.request.urlopen(audit_filtered_url, timeout=5) as resp:
            af = json.loads(resp.read().decode("utf-8"))
        assert af["ok"] is True
        assert af.get("filter", {}).get("action") == "gateway_bind_edit_preview"
        assert af.get("filter", {}).get("mode") == "apply"
        assert af.get("filter", {}).get("ok") is True
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


def test_ops_dashboard_interactions_profile_switch_preview_and_apply(tmp_path: Path) -> None:
    import os

    root = tmp_path.resolve()
    (root / "cai-agent.toml").write_text(
        "\n".join(
            [
                "[llm]",
                'provider = "openai_compatible"',
                'base_url = "http://127.0.0.1:9/v1"',
                'model = "m"',
                'api_key = "k"',
                "",
                "[models]",
                'active = "p1"',
                "",
                "[[models.profile]]",
                'id = "p1"',
                'provider = "openai_compatible"',
                'base_url = "http://127.0.0.1:9/v1"',
                'model = "m1"',
                "",
                "[[models.profile]]",
                'id = "p2"',
                'provider = "openai_compatible"',
                'base_url = "http://127.0.0.1:9/v1"',
                'model = "m2"',
                "",
            ],
        ),
        encoding="utf-8",
    )
    prev_cfg = os.environ.pop("CAI_CONFIG", None)
    prev_ws = os.environ.pop("CAI_WORKSPACE", None)
    httpd = _start_server(frozenset({root}), None)
    try:
        preview_url = _url(
            httpd,
            "/v1/ops/dashboard/interactions",
            {
                "workspace": str(root),
                "mode": "preview",
                "action": "profile_switch_preview",
                "target_profile_id": "p2",
            },
        )
        with urllib.request.urlopen(preview_url, timeout=5) as resp:
            preview = json.loads(resp.read().decode("utf-8"))
        assert preview["ok"] is True
        assert preview["active_profile_id"] == "p1"
        assert preview["target_profile_id"] == "p2"
        assert preview["dry_run"] is True

        apply_url = _url(
            httpd,
            "/v1/ops/dashboard/interactions",
            {
                "workspace": str(root),
                "mode": "apply",
                "action": "profile_switch_preview",
                "target_profile_id": "p2",
            },
        )
        with urllib.request.urlopen(apply_url, timeout=5) as resp:
            applied = json.loads(resp.read().decode("utf-8"))
        assert applied["ok"] is True
        assert applied["applied"] is True
        cfg = tomllib.loads((root / "cai-agent.toml").read_text(encoding="utf-8"))
        assert cfg.get("models", {}).get("active") == "p2"
    finally:
        httpd.shutdown()
        httpd.server_close()
        if prev_cfg is None:
            os.environ.pop("CAI_CONFIG", None)
        else:
            os.environ["CAI_CONFIG"] = prev_cfg
        if prev_ws is None:
            os.environ.pop("CAI_WORKSPACE", None)
        else:
            os.environ["CAI_WORKSPACE"] = prev_ws


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
