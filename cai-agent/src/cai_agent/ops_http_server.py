"""只读运营 HTTP 侧车（Phase B）：``GET /v1/ops/dashboard`` / ``dashboard.html``。

与 ``build_ops_dashboard_payload`` / ``build_ops_dashboard_html`` 同源；契约见仓库
``docs/OPS_DYNAMIC_WEB_API.zh-CN.md`` §3。
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import sys
from pathlib import Path
from typing import TextIO
from urllib.parse import parse_qs, unquote, urlencode, urlparse

from cai_agent.ops_dashboard import (
    _append_ops_action_audit,
    build_ops_dashboard_html,
    build_ops_dashboard_interactions_payload,
    build_ops_dashboard_payload,
)
from cai_agent.server_auth import resolve_bearer_token


class OpsApiThreadingServer(ThreadingHTTPServer):
    """携带 allowlist 与可选 Bearer 校验配置。"""

    allow_roots: frozenset[Path]
    api_token: str | None
    default_role: str


_OPS_ROLE_LEVELS = {
    "viewer": 0,
    "operator": 1,
    "admin": 2,
}


_OPS_APPLY_REQUIRED_ROLES = {
    "schedule_reorder_preview": "operator",
    "gateway_bind_edit_preview": "operator",
    "profile_switch_preview": "admin",
}


class OpsApiRequestHandler(BaseHTTPRequestHandler):
    server_version = "cai-agent-ops-api/1.0"

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, code: int, obj: object) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._send(code, raw, "application/json; charset=utf-8")

    def _read_json_body(self, *, max_bytes: int = 262_144) -> dict[str, str]:
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
        if not isinstance(obj, dict):
            raise ValueError("invalid_json_object")
        out: dict[str, str] = {}
        for k, v in obj.items():
            if isinstance(k, str):
                out[k] = "" if v is None else str(v)
        return out

    def _auth_ok(self) -> bool:
        token = getattr(self.server, "api_token", None)
        if not token:
            return True
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return False
        got = auth[7:].strip()
        return bool(got) and got == token

    def _role_error(self, role: str) -> dict[str, object] | None:
        if role in _OPS_ROLE_LEVELS:
            return None
        return {
            "ok": False,
            "error": "invalid_role",
            "role": role,
            "supported_roles": sorted(_OPS_ROLE_LEVELS),
        }

    def _request_role(self) -> str:
        configured = str(getattr(self.server, "default_role", "admin") or "admin").strip().lower()
        if configured not in _OPS_ROLE_LEVELS:
            configured = "admin"
        requested = str(self.headers.get("X-CAI-Role") or "").strip().lower()
        if not requested:
            return configured
        if requested not in _OPS_ROLE_LEVELS:
            return requested
        if _OPS_ROLE_LEVELS[requested] > _OPS_ROLE_LEVELS[configured]:
            return configured
        return requested

    def _operator_context(self, workspace: Path, role: str) -> dict[str, object]:
        actor = str(
            self.headers.get("X-CAI-Actor")
            or os.environ.get("CAI_OPERATOR")
            or os.environ.get("USERNAME")
            or os.environ.get("USER")
            or "unknown"
        ).strip() or "unknown"
        roots: frozenset[Path] = getattr(self.server, "allow_roots", frozenset())
        return {
            "actor": actor,
            "role": role,
            "workspace_scope": {
                "workspace": str(workspace),
                "allowed": self._workspace_allowed(workspace),
                "allow_roots_count": len(roots),
            },
        }

    def _rbac_apply_denial(
        self,
        *,
        action: str,
        mode: str,
        role: str,
        workspace: Path,
    ) -> dict[str, object] | None:
        if mode != "apply":
            return None
        if action not in _OPS_APPLY_REQUIRED_ROLES:
            return None
        required = _OPS_APPLY_REQUIRED_ROLES.get(action, "operator")
        if _OPS_ROLE_LEVELS.get(role, -1) >= _OPS_ROLE_LEVELS[required]:
            return None
        ctx = self._operator_context(workspace, role)
        audit = _append_ops_action_audit(
            workspace,
            action=action,
            mode=mode,
            ok=False,
            summary={"required_role": required, "denied_role": role},
            params={"error": "rbac_forbidden"},
            actor=str(ctx.get("actor") or "unknown"),
            role=role,
            workspace_scope=ctx.get("workspace_scope") if isinstance(ctx.get("workspace_scope"), dict) else {},
        )
        return {
            "schema_version": "ops_dashboard_interactions_v1",
            "ok": False,
            "error": "rbac_forbidden",
            "workspace": str(workspace),
            "action": action,
            "mode": mode,
            "dry_run": False,
            "applied": False,
            "required_role": required,
            "role": role,
            "supported_roles": sorted(_OPS_ROLE_LEVELS),
            "rbac": {
                "schema_version": "ops_dashboard_rbac_v1",
                **ctx,
            },
            "audit_event": audit,
        }

    def _workspace_allowed(self, root: Path) -> bool:
        roots: frozenset[Path] = getattr(self.server, "allow_roots", frozenset())
        return root in roots

    def _parse_positive_int(self, raw: str | None, default: int, *, name: str, max_v: int) -> int:
        if raw is None or raw == "":
            return default
        try:
            v = int(str(raw).strip(), 10)
        except ValueError as e:
            raise ValueError(f"invalid_int:{name}") from e
        if v < 1 or v > max_v:
            raise ValueError(f"out_of_range:{name}")
        return v

    def _safe_observe_pattern(self, raw: str | None, default: str) -> str:
        s = (raw if raw is not None else default) or default
        s = str(s).strip()
        if not s or ".." in s or "\x00" in s:
            raise ValueError("invalid_observe_pattern")
        if re.search(r"[/\\]", s):
            raise ValueError("invalid_observe_pattern")
        return s

    def _parse_bool(self, raw: str | None, default: bool = False) -> bool:
        if raw is None or str(raw).strip() == "":
            return bool(default)
        s = str(raw).strip().lower()
        if s in ("1", "true", "yes", "on"):
            return True
        if s in ("0", "false", "no", "off"):
            return False
        raise ValueError("invalid_bool")

    def _build_workspaces_payload(
        self,
        *,
        include_summary: bool,
        observe_pattern: str,
        observe_limit: int,
        schedule_days: int,
        cost_session_limit: int,
    ) -> dict[str, object]:
        roots: frozenset[Path] = getattr(self.server, "allow_roots", frozenset())
        rows: list[dict[str, object]] = []
        for root in sorted(roots):
            row: dict[str, object] = {
                "workspace": str(root),
                "exists": root.is_dir(),
                "allowed": True,
                "dashboard_url": "/v1/ops/dashboard?" + urlencode({"workspace": str(root)}),
                "dashboard_html_url": "/v1/ops/dashboard.html?" + urlencode({"workspace": str(root)}),
                "interactions_url": "/v1/ops/dashboard/interactions?" + urlencode({"workspace": str(root)}),
            }
            if include_summary and root.is_dir():
                try:
                    payload = build_ops_dashboard_payload(
                        cwd=str(root),
                        observe_pattern=observe_pattern,
                        observe_limit=observe_limit,
                        schedule_days=schedule_days,
                        audit_path=None,
                        cost_session_limit=cost_session_limit,
                    )
                    row["summary"] = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
                    row["generated_at"] = payload.get("generated_at")
                except OSError as e:
                    row["summary_error"] = str(e)
            rows.append(row)
        return {
            "schema_version": "ops_workspaces_v1",
            "generated_at": datetime.now(UTC).isoformat(),
            "workspaces_count": len(rows),
            "include_summary": bool(include_summary),
            "workspaces": rows,
        }

    def _resolve_audit_path(self, workspace: Path, raw: str | None) -> Path | None:
        if raw is None or str(raw).strip() == "":
            return None
        p = Path(unquote(str(raw).strip())).expanduser()
        if not p.is_absolute():
            p = (workspace / p).resolve()
        else:
            p = p.resolve()
        try:
            p.relative_to(workspace)
        except ValueError as e:
            raise PermissionError("audit_file outside workspace") from e
        return p

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or ""
        if path not in (
            "/v1/ops/dashboard",
            "/v1/ops/dashboard.html",
            "/v1/ops/dashboard/events",
            "/v1/ops/dashboard/interactions",
            "/v1/ops/workspaces",
        ):
            self._send_json(404, {"error": "not_found", "path": path})
            return
        if not self._auth_ok():
            self._send_json(401, {"error": "unauthorized"})
            return
        role = self._request_role()
        role_error = self._role_error(role)
        if role_error is not None:
            self._send_json(400, role_error)
            return
        try:
            q = parse_qs(parsed.query, keep_blank_values=False)
        except ValueError:
            self._send_json(400, {"error": "bad_query"})
            return

        def one(key: str) -> str | None:
            xs = q.get(key)
            if not xs:
                return None
            return xs[0]

        if path == "/v1/ops/workspaces":
            try:
                include_summary = self._parse_bool(one("include_summary"), default=False)
                observe_pattern = self._safe_observe_pattern(one("observe_pattern"), ".cai-session*.json")
                observe_limit = self._parse_positive_int(
                    one("observe_limit"), 100, name="observe_limit", max_v=50_000
                )
                schedule_days = self._parse_positive_int(
                    one("schedule_days"), 30, name="schedule_days", max_v=3660
                )
                cost_session_limit = self._parse_positive_int(
                    one("cost_session_limit"), 200, name="cost_session_limit", max_v=50_000
                )
            except ValueError as e:
                self._send_json(400, {"error": "bad_request", "detail": str(e)})
                return
            self._send_json(
                200,
                self._build_workspaces_payload(
                    include_summary=include_summary,
                    observe_pattern=observe_pattern,
                    observe_limit=observe_limit,
                    schedule_days=schedule_days,
                    cost_session_limit=cost_session_limit,
                ),
            )
            return

        ws_raw = one("workspace")
        if not ws_raw or not str(ws_raw).strip():
            self._send_json(400, {"error": "missing_workspace"})
            return
        try:
            workspace = Path(unquote(str(ws_raw).strip())).expanduser().resolve()
        except OSError:
            self._send_json(400, {"error": "invalid_workspace"})
            return
        if not workspace.is_dir():
            self._send_json(400, {"error": "workspace_not_a_directory"})
            return
        if not self._workspace_allowed(workspace):
            self._send_json(403, {"error": "workspace_not_allowed"})
            return

        try:
            observe_pattern = self._safe_observe_pattern(one("observe_pattern"), ".cai-session*.json")
            observe_limit = self._parse_positive_int(
                one("observe_limit"), 100, name="observe_limit", max_v=50_000
            )
            schedule_days = self._parse_positive_int(
                one("schedule_days"), 30, name="schedule_days", max_v=3660
            )
            cost_session_limit = self._parse_positive_int(
                one("cost_session_limit"), 200, name="cost_session_limit", max_v=50_000
            )
            audit_path = self._resolve_audit_path(workspace, one("audit_file"))
        except ValueError as e:
            self._send_json(400, {"error": "bad_request", "detail": str(e)})
            return
        except PermissionError as e:
            self._send_json(400, {"error": "bad_request", "detail": str(e)})
            return

        try:
            payload = build_ops_dashboard_payload(
                cwd=str(workspace),
                observe_pattern=observe_pattern,
                observe_limit=observe_limit,
                schedule_days=schedule_days,
                audit_path=audit_path,
                cost_session_limit=cost_session_limit,
            )
        except OSError as e:
            self._send_json(400, {"error": "io_error", "detail": str(e)})
            return

        if path == "/v1/ops/dashboard/interactions":
            action = str(one("action") or "").strip()
            mode = str(one("mode") or "preview").strip().lower()
            if mode == "apply":
                self._send_json(
                    403,
                    {
                        "ok": False,
                        "error": "execute_forbidden",
                        "message": "GET /v1/ops/dashboard/interactions supports preview|audit only; use POST for apply",
                    },
                )
                return
            params = {k: v[0] for k, v in q.items() if v and k not in {"workspace", "action", "mode"}}
            interaction = build_ops_dashboard_interactions_payload(
                cwd=str(workspace),
                action=action,
                mode=mode,
                params=params,
                operator_context=self._operator_context(workspace, role),
            )
            self._send_json(200 if interaction.get("ok") else 400, interaction)
            return
        if path == "/v1/ops/dashboard":
            self._send_json(200, payload)
            return
        if path == "/v1/ops/dashboard/events":
            raw_interval = one("live_interval_seconds")
            try:
                live_interval = float(str(raw_interval).strip()) if raw_interval is not None and str(raw_interval).strip() != "" else 5.0
            except ValueError:
                self._send_json(400, {"error": "bad_request", "detail": "invalid_float:live_interval_seconds"})
                return
            if live_interval <= 0 or live_interval > 3600:
                self._send_json(400, {"error": "bad_request", "detail": "out_of_range:live_interval_seconds"})
                return
            raw_max = one("max_events")
            try:
                max_events = int(str(raw_max).strip(), 10) if raw_max is not None and str(raw_max).strip() != "" else 0
            except ValueError:
                self._send_json(400, {"error": "bad_request", "detail": "invalid_int:max_events"})
                return
            if max_events < 0 or max_events > 10_000:
                self._send_json(400, {"error": "bad_request", "detail": "out_of_range:max_events"})
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close" if max_events > 0 else "keep-alive")
            self.end_headers()
            sent = 0
            while True:
                raw = json.dumps(payload, ensure_ascii=False)
                body = f"event: ops_dashboard\ndata: {raw}\n\n".encode("utf-8")
                self.wfile.write(body)
                self.wfile.flush()
                sent += 1
                if max_events > 0 and sent >= max_events:
                    self.close_connection = True
                    return
                time.sleep(live_interval)
                payload = build_ops_dashboard_payload(
                    cwd=str(workspace),
                    observe_pattern=observe_pattern,
                    observe_limit=observe_limit,
                    schedule_days=schedule_days,
                    audit_path=audit_path,
                    cost_session_limit=cost_session_limit,
                )
        html_refresh: int | None = None
        raw_rf = one("html_refresh_seconds")
        if raw_rf is not None and str(raw_rf).strip() != "":
            try:
                v_rf = int(str(raw_rf).strip(), 10)
            except ValueError:
                self._send_json(400, {"error": "bad_request", "detail": "invalid_int:html_refresh_seconds"})
                return
            if v_rf < 0 or v_rf > 86_400:
                self._send_json(
                    400,
                    {"error": "bad_request", "detail": "out_of_range:html_refresh_seconds"},
                )
                return
            html_refresh = v_rf if v_rf > 0 else None
        live_mode = str(one("live_mode") or "").strip().lower()
        raw_live_interval = one("live_interval_seconds")
        live_interval_for_html = 0
        if raw_live_interval is not None and str(raw_live_interval).strip() != "":
            try:
                live_interval_for_html = int(float(str(raw_live_interval).strip()))
            except ValueError:
                self._send_json(400, {"error": "bad_request", "detail": "invalid_float:live_interval_seconds"})
                return
            if live_interval_for_html <= 0 or live_interval_for_html > 3600:
                self._send_json(400, {"error": "bad_request", "detail": "out_of_range:live_interval_seconds"})
                return
        html = build_ops_dashboard_html(payload, html_refresh_seconds=html_refresh)
        if live_mode in ("sse", "poll"):
            live_query = {
                "workspace": str(workspace),
                "observe_pattern": observe_pattern,
                "observe_limit": str(observe_limit),
                "schedule_days": str(schedule_days),
                "cost_session_limit": str(cost_session_limit),
            }
            if audit_path is not None:
                live_query["audit_file"] = str(audit_path)
            if live_interval_for_html > 0:
                live_query["live_interval_seconds"] = str(live_interval_for_html)
            if live_mode == "sse":
                live_path = "/v1/ops/dashboard/events?" + urlencode(live_query)
                live_script = (
                    "<script>"
                    f"(()=>{{if(!window.EventSource)return;const es=new EventSource({json.dumps(live_path, ensure_ascii=False)});"
                    "es.onmessage=()=>window.location.reload();es.onerror=()=>es.close();}})();"
                    "</script>"
                )
            else:
                if live_interval_for_html <= 0:
                    live_interval_for_html = 5
                live_script = (
                    "<script>"
                    f"(()=>{{window.setInterval(()=>window.location.reload(), {live_interval_for_html * 1000});}})();"
                    "</script>"
                )
            html = html.replace("</body>", f"{live_script}</body>", 1)
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or ""
        if path != "/v1/ops/dashboard/interactions":
            self._send_json(404, {"error": "not_found", "path": path})
            return
        if not self._auth_ok():
            self._send_json(401, {"error": "unauthorized"})
            return
        role = self._request_role()
        role_error = self._role_error(role)
        if role_error is not None:
            self._send_json(400, role_error)
            return
        try:
            body = self._read_json_body()
        except ValueError as e:
            self._send_json(400, {"error": "bad_request", "detail": str(e)})
            return
        ws_raw = str(body.get("workspace") or "").strip()
        if not ws_raw:
            self._send_json(400, {"error": "missing_workspace"})
            return
        try:
            workspace = Path(unquote(ws_raw)).expanduser().resolve()
        except OSError:
            self._send_json(400, {"error": "invalid_workspace"})
            return
        if not workspace.is_dir():
            self._send_json(400, {"error": "workspace_not_a_directory"})
            return
        if not self._workspace_allowed(workspace):
            self._send_json(403, {"error": "workspace_not_allowed"})
            return

        action = str(body.get("action") or "").strip()
        mode = str(body.get("mode") or "apply").strip().lower()
        denial = self._rbac_apply_denial(action=action, mode=mode, role=role, workspace=workspace)
        if denial is not None:
            self._send_json(403, denial)
            return
        params = {
            k: v
            for k, v in body.items()
            if k not in {"workspace", "action", "mode"} and str(v).strip() != ""
        }
        interaction = build_ops_dashboard_interactions_payload(
            cwd=str(workspace),
            action=action,
            mode=mode,
            params=params,
            operator_context=self._operator_context(workspace, role),
        )
        self._send_json(200 if interaction.get("ok") else 400, interaction)


def run_ops_api_server(
    *,
    host: str,
    port: int,
    allow_workspaces: list[str],
    role: str = "admin",
    stderr: TextIO | None = None,
) -> int:
    """阻塞运行 HTTP 服务直到 ``KeyboardInterrupt``。成功启动返回 ``0``。"""
    err = stderr if stderr is not None else sys.stderr
    if not allow_workspaces:
        err.write("ops serve: allow_workspaces is empty\n")
        return 2
    roots: list[Path] = []
    for raw in allow_workspaces:
        p = Path(raw).expanduser().resolve()
        if not p.is_dir():
            err.write(f"ops serve: not a directory: {p}\n")
            return 2
        roots.append(p)
    allow = frozenset(roots)
    api_token = resolve_bearer_token("CAI_OPS_API_TOKEN", "CAI_API_TOKEN")
    role_norm = str(role or "admin").strip().lower()
    if role_norm not in _OPS_ROLE_LEVELS:
        err.write(f"ops serve: invalid role: {role_norm}\n")
        return 2

    httpd = OpsApiThreadingServer((host, port), OpsApiRequestHandler)
    httpd.allow_roots = allow
    httpd.api_token = api_token
    httpd.default_role = role_norm

    err.write(
        f"ops serve: listening http://{host}:{port}\n"
        f"  allow workspaces ({len(allow)}): {', '.join(str(x) for x in sorted(allow))}\n"
        "  CAI_OPS_API_TOKEN/CAI_API_TOKEN: "
        f"{'set' if api_token else 'unset'}\n"
        f"  role: {role_norm}\n"
        "  GET /v1/ops/workspaces?include_summary=0|1\n"
        "  GET /v1/ops/dashboard?workspace=...&observe_pattern=...\n"
        "  GET /v1/ops/dashboard/interactions?workspace=...&action=...&mode=preview|audit\n"
        "  POST /v1/ops/dashboard/interactions  (mode=apply|preview|audit)\n",
    )
    try:
        httpd.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        err.write("ops serve: stopped\n")
        return 0
    finally:
        httpd.server_close()
    return 0
