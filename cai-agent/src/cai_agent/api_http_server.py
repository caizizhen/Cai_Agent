"""最小只读 HTTP API（HM-02b）：``cai-agent api serve``。

契约见仓库 ``docs/rfc/HM_02_MINIMAL_SERVER_CONTRACT.zh-CN.md``。与 ``ops serve`` 端口分离；
鉴权环境变量 ``CAI_API_TOKEN``（非空则除 ``/healthz`` 外要求 ``Authorization: Bearer``）。
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, TextIO
from urllib.parse import urlparse

from cai_agent.config import Settings
from cai_agent.doctor import build_api_doctor_summary_v1
from cai_agent.gateway_lifecycle import build_gateway_summary_payload, build_status_payload
from cai_agent.schedule import compute_due_tasks


class AgentApiThreadingServer(ThreadingHTTPServer):
    workspace: Path
    api_token: str | None


class AgentApiRequestHandler(BaseHTTPRequestHandler):
    server_version = "cai-agent-api/0"

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Cai-Agent-Api-Version", "0")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, obj: object) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(code, raw, "application/json; charset=utf-8")

    def _auth_ok(self, *, path: str) -> bool:
        if path == "/healthz":
            return True
        token = getattr(self.server, "api_token", None)
        if not token:
            return True
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return False
        got = auth[7:].strip()
        return bool(got) and got == token

    def _read_json_body(self, *, max_bytes: int = 65536) -> dict[str, Any] | None:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        if n > max_bytes:
            raise ValueError("body_too_large")
        raw = self.rfile.read(n)
        if len(raw) != n:
            raise ValueError("short_read")
        try:
            obj = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise ValueError(f"invalid_json:{e}") from e
        return obj if isinstance(obj, dict) else {}

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or ""
        if not self._auth_ok(path=path):
            self._send_json(401, {"ok": False, "error": "unauthorized", "message": "Bearer token required"})
            return
        ws: Path = getattr(self.server, "workspace")
        try:
            if path == "/healthz":
                self._send_json(200, {"ok": True})
                return
            if path == "/v1/status":
                st = build_status_payload(ws)
                summary = st.get("gateway_summary") if isinstance(st.get("gateway_summary"), dict) else {}
                payload = {
                    "schema_version": "api_status_v1",
                    "generated_at": datetime.now(UTC).isoformat(),
                    "workspace": str(ws),
                    "gateway_summary": summary or build_gateway_summary_payload(ws),
                    "gateway_lifecycle": {
                        "schema_version": st.get("schema_version"),
                        "config_exists": st.get("config_exists"),
                        "webhook_running": st.get("webhook_running"),
                        "webhook_pid": st.get("webhook_pid"),
                        "bindings_count": st.get("bindings_count"),
                        "allowlist_enabled": st.get("allowlist_enabled"),
                    },
                }
                self._send_json(200, payload)
                return
            if path == "/v1/doctor/summary":
                settings = Settings.from_env(config_path=None, workspace_hint=str(ws))
                doc = build_api_doctor_summary_v1(settings)
                self._send_json(200, doc)
                return
        except Exception as e:
            self._send_json(500, {"ok": False, "error": "internal_error", "message": str(e)[:500]})
            return
        self._send_json(404, {"ok": False, "error": "not_found", "message": path})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or ""
        if not self._auth_ok(path=path):
            self._send_json(401, {"ok": False, "error": "unauthorized", "message": "Bearer token required"})
            return
        ws: Path = getattr(self.server, "workspace")
        if path != "/v1/tasks/run-due":
            self._send_json(404, {"ok": False, "error": "not_found", "message": path})
            return
        try:
            body = self._read_json_body()
        except ValueError as e:
            self._send_json(400, {"ok": False, "error": "bad_request", "message": str(e)})
            return
        dry = body.get("dry_run")
        if dry is None:
            dry_run = True
        else:
            dry_run = bool(dry)
        if not dry_run:
            self._send_json(
                403,
                {
                    "ok": False,
                    "error": "execute_forbidden",
                    "message": "HTTP API only supports dry_run; use: cai-agent schedule run-due --execute",
                },
            )
            return
        try:
            due = compute_due_tasks(cwd=str(ws))
        except Exception as e:
            self._send_json(500, {"ok": False, "error": "internal_error", "message": str(e)[:500]})
            return
        self._send_json(
            200,
            {
                "schema_version": "api_tasks_run_due_v1",
                "mode": "dry-run",
                "workspace": str(ws),
                "due_jobs": due,
                "executed": [],
            },
        )


def run_agent_api_server(
    *,
    host: str,
    port: int,
    workspace: Path,
    stderr: TextIO | None = None,
) -> int:
    """阻塞运行直到 ``KeyboardInterrupt``。"""
    err = stderr if stderr is not None else sys.stderr
    root = workspace.expanduser().resolve()
    if not root.is_dir():
        err.write(f"api serve: not a directory: {root}\n")
        return 2
    token_raw = (os.environ.get("CAI_API_TOKEN") or "").strip()
    api_token = token_raw or None

    httpd = AgentApiThreadingServer((host, port), AgentApiRequestHandler)
    httpd.workspace = root
    httpd.api_token = api_token

    err.write(
        f"api serve: listening http://{host}:{port}\n"
        f"  workspace: {root}\n"
        f"  CAI_API_TOKEN: {'set' if api_token else 'unset'}\n"
        "  GET /healthz | GET /v1/status | GET /v1/doctor/summary | POST /v1/tasks/run-due\n",
    )
    try:
        httpd.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        err.write("api serve: stopped\n")
        return 0
    finally:
        httpd.server_close()
    return 0
