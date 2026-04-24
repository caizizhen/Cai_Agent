"""最小只读 HTTP API（HM-02b / HM-02c）：``cai-agent api serve``。

契约见仓库 ``docs/rfc/HM_02_MINIMAL_SERVER_CONTRACT.zh-CN.md``。与 ``ops serve`` 端口分离；
鉴权环境变量 ``CAI_API_TOKEN``（非空则除 ``/healthz`` 外要求 ``Authorization: Bearer``）。

``HM-02c`` 在 ``HM-02b`` 基础上增加三条只读扩展：
``GET /v1/models/summary``（``api_models_summary_v1``，仅暴露 ``profile_contract_v1`` 白名单字段），
``GET /v1/plugins/surface``（``api_plugins_surface_v1``，复用 ``list_plugin_surface``，可选 ``?compat=1`` 附加
``plugin_compat_matrix_v1``），以及 ``GET /v1/release/runbook``（``api_release_runbook_v1``，复用 release
runbook 摘要，不含仓库绝对路径）。均不扩大写操作面、不改默认鉴权策略。
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, TextIO
from urllib.parse import parse_qs, urlparse

from cai_agent.config import Settings
from cai_agent.doctor import build_api_doctor_summary_v1
from cai_agent.gateway_lifecycle import build_gateway_summary_payload, build_status_payload
from cai_agent.plugin_registry import build_plugin_compat_matrix, list_plugin_surface
from cai_agent.profiles import build_profile_contract_payload
from cai_agent.release_runbook import build_release_runbook_payload, resolve_release_repo_root
from cai_agent.schedule import compute_due_tasks


def build_api_models_summary_v1(settings: Settings) -> dict[str, Any]:
    """HTTP ``GET /v1/models/summary`` 白名单视图：仅包含 ``profile_contract_v1`` 与 ID 列表。"""
    contract = build_profile_contract_payload(
        settings.profiles,
        profiles_explicit=bool(getattr(settings, "profiles_explicit", False)),
        active_profile_id=settings.active_profile_id,
        subagent_profile_id=getattr(settings, "subagent_profile_id", None),
        planner_profile_id=getattr(settings, "planner_profile_id", None),
        env_active_override=os.getenv("CAI_ACTIVE_MODEL"),
    )
    return {
        "schema_version": "api_models_summary_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "active_profile_id": settings.active_profile_id,
        "subagent_profile_id": getattr(settings, "subagent_profile_id", None),
        "planner_profile_id": getattr(settings, "planner_profile_id", None),
        "profiles_count": len(settings.profiles),
        "profile_ids": [p.id for p in settings.profiles],
        "profile_contract": contract,
    }


def _plugins_surface_whitelist(surface: dict[str, Any]) -> dict[str, Any]:
    comps = surface.get("components") if isinstance(surface.get("components"), dict) else {}
    safe_components: dict[str, dict[str, Any]] = {}
    for name, meta in comps.items():
        if not isinstance(meta, dict):
            continue
        safe_components[str(name)] = {
            "exists": bool(meta.get("exists")),
            "files_count": int(meta.get("files_count", 0) or 0),
        }
    return {
        "plugin_version": surface.get("plugin_version"),
        "health_score": int(surface.get("health_score") or 0),
        "compatibility": surface.get("compatibility"),
        "components": safe_components,
    }


def build_api_plugins_surface_v1(
    settings: Settings,
    *,
    include_compat_matrix: bool,
) -> dict[str, Any]:
    """HTTP ``GET /v1/plugins/surface`` 白名单视图；不暴露 ``project_root`` 绝对路径。"""
    surface = list_plugin_surface(settings)
    safe = _plugins_surface_whitelist(surface)
    payload: dict[str, Any] = {
        "schema_version": "api_plugins_surface_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        **safe,
    }
    if include_compat_matrix:
        payload["compat_matrix"] = build_plugin_compat_matrix()
    return payload


def _release_runbook_whitelist(payload: dict[str, Any]) -> dict[str, Any]:
    """裁剪 release runbook 供 HTTP 暴露：去掉仓库绝对路径字段。"""
    out: dict[str, Any] = {}
    for key in (
        "schema_version",
        "changelog",
        "feedback",
        "runbook_steps",
        "writeback_targets",
        "docs",
    ):
        if key in payload:
            out[key] = payload[key]
    return out


def build_api_release_runbook_v1(workspace: Path) -> dict[str, Any]:
    """HTTP ``GET /v1/release/runbook`` 视图；包裹 ``release_runbook_v1`` 白名单字段。"""
    root = workspace
    rb = build_release_runbook_payload(
        repo_root=resolve_release_repo_root(root),
        workspace=root,
    )
    safe = _release_runbook_whitelist(rb if isinstance(rb, dict) else {})
    return {
        "schema_version": "api_release_runbook_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "release_runbook": safe,
    }


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
            if path == "/v1/models/summary":
                settings = Settings.from_env(config_path=None, workspace_hint=str(ws))
                self._send_json(200, build_api_models_summary_v1(settings))
                return
            if path == "/v1/plugins/surface":
                settings = Settings.from_env(config_path=None, workspace_hint=str(ws))
                qs = parse_qs(parsed.query or "", keep_blank_values=False)
                compat_raw = (qs.get("compat") or [""])[0].strip().lower()
                include_compat = compat_raw in ("1", "true", "yes", "on")
                self._send_json(
                    200,
                    build_api_plugins_surface_v1(
                        settings,
                        include_compat_matrix=include_compat,
                    ),
                )
                return
            if path == "/v1/release/runbook":
                self._send_json(200, build_api_release_runbook_v1(ws))
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
        "  GET /healthz | GET /v1/status | GET /v1/doctor/summary\n"
        "  GET /v1/models/summary | GET /v1/plugins/surface[?compat=1] | GET /v1/release/runbook\n"
        "  POST /v1/tasks/run-due (dry_run only)\n",
    )
    try:
        httpd.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        err.write("api serve: stopped\n")
        return 0
    finally:
        httpd.server_close()
    return 0
