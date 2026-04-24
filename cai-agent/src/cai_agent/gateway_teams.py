"""Microsoft Teams Gateway minimum production path (HM-03d).

This module deliberately avoids a Bot Framework SDK dependency. It provides the
same local production surface as the Slack/Discord gateways: workspace mapping,
allowlist, health payload, app-manifest scaffold, and a small Activity webhook
receiver that deployment layers can protect with a shared secret.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

_MAP_SCHEMA = "gateway_teams_map_v1"
_MAP_NAME = "teams-session-map.json"
_HEALTH_SCHEMA = "gateway_teams_health_v1"
_WEBHOOK_SCHEMA = "gateway_teams_webhook_v1"
_MANIFEST_SCHEMA = "gateway_teams_manifest_v1"


def _gateway_dir(root: Path) -> Path:
    d = (root / ".cai" / "gateway").resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _map_path(root: Path) -> Path:
    return _gateway_dir(root) / _MAP_NAME


def _empty_map() -> dict[str, Any]:
    return {
        "schema_version": _MAP_SCHEMA,
        "bindings": {},
        "allowed_conversation_ids": [],
    }


def _read_map(root: Path) -> dict[str, Any]:
    p = _map_path(root)
    if not p.is_file():
        return _empty_map()
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return _empty_map()
    if not isinstance(obj, dict):
        return _empty_map()
    obj.setdefault("schema_version", _MAP_SCHEMA)
    obj.setdefault("bindings", {})
    obj.setdefault("allowed_conversation_ids", [])
    if not isinstance(obj.get("bindings"), dict):
        obj["bindings"] = {}
    if not isinstance(obj.get("allowed_conversation_ids"), list):
        obj["allowed_conversation_ids"] = []
    return obj


def _write_map(root: Path, obj: dict[str, Any]) -> None:
    p = _map_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def teams_bind(
    root: Path,
    conversation_id: str,
    session_file: str,
    *,
    tenant_id: str | None = None,
    service_url: str | None = None,
    channel_id: str | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    m = _read_map(root)
    cid = str(conversation_id).strip()
    row: dict[str, Any] = {
        "session_file": str(session_file),
        "bound_at": datetime.now(UTC).isoformat(),
    }
    for key, value in (
        ("tenant_id", tenant_id),
        ("service_url", service_url),
        ("channel_id", channel_id),
        ("label", label),
    ):
        if value is not None and str(value).strip():
            row[key] = str(value).strip()
    m["bindings"][cid] = row
    _write_map(root, m)
    return {
        "ok": True,
        "schema_version": _MAP_SCHEMA,
        "conversation_id": cid,
        "session_file": str(session_file),
        "binding": row,
    }


def teams_unbind(root: Path, conversation_id: str) -> dict[str, Any]:
    m = _read_map(root)
    cid = str(conversation_id).strip()
    existed = cid in m["bindings"]
    if existed:
        del m["bindings"][cid]
        _write_map(root, m)
    return {"ok": True, "conversation_id": cid, "was_bound": existed}


def teams_get_binding(root: Path, conversation_id: str) -> dict[str, Any]:
    m = _read_map(root)
    cid = str(conversation_id).strip()
    binding = m["bindings"].get(cid)
    return {"conversation_id": cid, "binding": binding, "found": binding is not None}


def teams_list_bindings(root: Path) -> dict[str, Any]:
    m = _read_map(root)
    allowed = m.get("allowed_conversation_ids", [])
    return {
        "schema_version": _MAP_SCHEMA,
        "map_path": str(_map_path(root)),
        "bindings": m.get("bindings", {}),
        "allowed_conversation_ids": allowed,
        "allowlist_enabled": bool(allowed),
    }


def teams_allow_add(root: Path, conversation_id: str) -> dict[str, Any]:
    m = _read_map(root)
    cid = str(conversation_id).strip()
    if cid not in m["allowed_conversation_ids"]:
        m["allowed_conversation_ids"].append(cid)
        _write_map(root, m)
    return {
        "ok": True,
        "conversation_id": cid,
        "allowed_conversation_ids": m["allowed_conversation_ids"],
    }


def teams_allow_rm(root: Path, conversation_id: str) -> dict[str, Any]:
    m = _read_map(root)
    cid = str(conversation_id).strip()
    before = list(m["allowed_conversation_ids"])
    m["allowed_conversation_ids"] = [x for x in before if x != cid]
    _write_map(root, m)
    return {"ok": True, "conversation_id": cid, "removed": cid in before}


def teams_allow_list(root: Path) -> dict[str, Any]:
    m = _read_map(root)
    allowed = m.get("allowed_conversation_ids", [])
    return {"allowed_conversation_ids": allowed, "allowlist_enabled": bool(allowed)}


def teams_gateway_health(
    root: Path,
    *,
    app_id: str | None = None,
    app_password: str | None = None,
    tenant_id: str | None = None,
    webhook_secret: str | None = None,
) -> dict[str, Any]:
    local = teams_list_bindings(root)
    binds = local.get("bindings") if isinstance(local.get("bindings"), dict) else {}
    allow = local.get("allowed_conversation_ids") if isinstance(local.get("allowed_conversation_ids"), list) else []
    app_id_s = str(app_id or "").strip()
    app_pw_s = str(app_password or "").strip()
    return {
        "schema_version": _HEALTH_SCHEMA,
        "workspace": str(root.resolve()),
        "map_path": local.get("map_path"),
        "map_schema_version": local.get("schema_version"),
        "bindings_count": len(binds),
        "allowlist_enabled": bool(local.get("allowlist_enabled")),
        "allowed_conversation_ids_count": len(allow),
        "app_id_configured": bool(app_id_s),
        "app_password_configured": bool(app_pw_s),
        "tenant_id_configured": bool(str(tenant_id or "").strip()),
        "webhook_secret_configured": bool(str(webhook_secret or "").strip()),
        "token_check": {
            "performed": False,
            "ok": None,
            "hint": (
                "Teams Bot Framework token validation is delegated to deployment "
                "middleware; use --webhook-secret for this lightweight local receiver."
            ),
        },
    }


def build_teams_manifest_payload(
    *,
    app_id: str,
    bot_id: str | None = None,
    name: str = "CAI Agent",
    valid_domains: list[str] | None = None,
) -> dict[str, Any]:
    """Return a Teams app manifest scaffold without writing files."""
    aid = str(app_id or "").strip()
    bid = str(bot_id or "").strip() or aid
    domains = [str(x).strip() for x in (valid_domains or []) if str(x).strip()]
    manifest = {
        "$schema": "https://developer.microsoft.com/json-schemas/teams/v1.17/MicrosoftTeams.schema.json",
        "manifestVersion": "1.17",
        "version": "1.0.0",
        "id": aid,
        "developer": {
            "name": "Cai Agent",
            "websiteUrl": "https://github.com/caizizhen/Cai_Agent",
            "privacyUrl": "https://github.com/caizizhen/Cai_Agent",
            "termsOfUseUrl": "https://github.com/caizizhen/Cai_Agent",
        },
        "name": {"short": name[:30], "full": name[:100]},
        "description": {
            "short": "CAI Agent Teams gateway",
            "full": "Routes Microsoft Teams conversations into Cai Agent sessions.",
        },
        "bots": [
            {
                "botId": bid,
                "scopes": ["personal", "team", "groupchat"],
                "supportsFiles": False,
                "isNotificationOnly": False,
                "commandLists": [
                    {
                        "scopes": ["personal", "team", "groupchat"],
                        "commands": [
                            {"title": "help", "description": "Show CAI Agent help"},
                            {"title": "ping", "description": "Check gateway reachability"},
                            {"title": "status", "description": "Show local gateway status"},
                            {"title": "new", "description": "Start or bind a new session"},
                        ],
                    },
                ],
            },
        ],
        "validDomains": domains,
    }
    return {"schema_version": _MANIFEST_SCHEMA, "ok": bool(aid), "manifest": manifest}


def extract_teams_activity(activity: dict[str, Any]) -> dict[str, str]:
    conversation = activity.get("conversation") if isinstance(activity.get("conversation"), dict) else {}
    from_user = activity.get("from") if isinstance(activity.get("from"), dict) else {}
    channel_data = activity.get("channelData") if isinstance(activity.get("channelData"), dict) else {}
    tenant = channel_data.get("tenant") if isinstance(channel_data.get("tenant"), dict) else {}
    return {
        "type": str(activity.get("type") or ""),
        "conversation_id": str(conversation.get("id") or ""),
        "user_id": str(from_user.get("id") or ""),
        "text": str(activity.get("text") or "").strip(),
        "service_url": str(activity.get("serviceUrl") or ""),
        "channel_id": str(activity.get("channelId") or ""),
        "tenant_id": str(tenant.get("id") or ""),
    }


def teams_activity_response(
    *,
    root: Path,
    activity: dict[str, Any],
    execute_on_message: bool = False,
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    """Build the synchronous local response for a Teams Bot Framework Activity."""
    if not isinstance(activity, dict):
        return 400, {"error": "invalid_activity"}, {"ok": False, "error": "invalid_activity"}
    data = extract_teams_activity(activity)
    cid = data["conversation_id"]
    text = data["text"]
    if not cid:
        return 400, {"error": "missing_conversation_id"}, {"ok": False, "error": "missing_conversation_id"}
    m = _read_map(root)
    allowed = [str(x) for x in m.get("allowed_conversation_ids", []) if str(x).strip()]
    if allowed and cid not in allowed:
        return 200, {"type": "message", "text": "此 Teams conversation 未在白名单内。"}, {"ok": True, "blocked": True}

    low = text.lower()
    if low in ("help", "/help", "?"):
        return (
            200,
            {"type": "message", "text": "CAI Teams gateway: help, ping, status, new, or bound-session text."},
            {"ok": True, "command": "help"},
        )
    if low in ("ping", "/ping"):
        return 200, {"type": "message", "text": "pong"}, {"ok": True, "command": "ping"}
    if low in ("status", "/status"):
        bindings = m.get("bindings") if isinstance(m.get("bindings"), dict) else {}
        return (
            200,
            {"type": "message", "text": f"ok bindings={len(bindings)} allowlist={bool(allowed)}"},
            {"ok": True, "command": "status"},
        )
    if low.startswith("new") or low.startswith("/new"):
        return (
            200,
            {"type": "message", "text": "请先运行 gateway teams bind <conversation_id> <session_file> 绑定会话。"},
            {"ok": True, "command": "new"},
        )
    if execute_on_message and text:
        binding = m.get("bindings", {}).get(cid, {})
        return (
            200,
            {"type": "message", "text": "Teams 执行入口已接收；当前本地最小实现仅记录事件。"},
            {"ok": True, "executed": False, "binding_found": isinstance(binding, dict) and bool(binding)},
        )
    return 200, {"type": "message", "text": "发送 help 查看用法，或 ping 测试。"}, {"ok": True}


class _TeamsWebhookHandler(BaseHTTPRequestHandler):
    root: Path = Path(".")
    webhook_secret: str = ""
    execute_on_message: bool = False
    log_path: Path | None = None
    events_handled: list[dict[str, Any]] = []
    max_events: int = 0

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass

    def do_GET(self) -> None:  # noqa: N802
        self._send_json(200, {"ok": True, "service": "cai-agent teams gateway"})

    def do_POST(self) -> None:  # noqa: N802
        if self.webhook_secret:
            got = str(self.headers.get("X-CAI-Teams-Secret", "") or "")
            if got != self.webhook_secret:
                self._send_json(403, {"error": "invalid_secret"})
                return
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        try:
            activity = json.loads(body.decode("utf-8"))
        except Exception:
            self._send_json(400, {"error": "invalid_json"})
            return
        status, response, meta = teams_activity_response(
            root=self.root,
            activity=activity,
            execute_on_message=self.execute_on_message,
        )
        ev = {
            "ts": datetime.now(UTC).isoformat(),
            "event": "teams.activity",
            **extract_teams_activity(activity if isinstance(activity, dict) else {}),
            "meta": meta,
        }
        if self.log_path:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        self.events_handled.append(ev)
        self._send_json(status, response)
        if self.max_events > 0 and len(self.events_handled) >= self.max_events:
            import threading

            threading.Thread(target=self.server.shutdown, daemon=True).start()

    def _send_json(self, code: int, obj: dict[str, Any]) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve_teams_webhook(
    *,
    root: Path,
    webhook_secret: str = "",
    host: str = "0.0.0.0",
    port: int = 7893,
    execute_on_message: bool = False,
    log_file: str | None = None,
    max_events: int = 0,
) -> dict[str, Any]:
    started_at = datetime.now(UTC).isoformat()
    log_path = Path(log_file) if log_file else None
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    shared_events: list[dict[str, Any]] = []

    class _Handler(_TeamsWebhookHandler):
        pass

    _Handler.root = root
    _Handler.webhook_secret = webhook_secret
    _Handler.execute_on_message = execute_on_message
    _Handler.log_path = log_path
    _Handler.events_handled = shared_events
    _Handler.max_events = max_events
    server = HTTPServer((host, port), _Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return {
        "schema_version": _WEBHOOK_SCHEMA,
        "ok": True,
        "started_at": started_at,
        "stopped_at": datetime.now(UTC).isoformat(),
        "host": host,
        "port": port,
        "events_handled": len(shared_events),
        "execute_on_message": bool(execute_on_message),
        "webhook_secret_configured": bool(str(webhook_secret or "").strip()),
        "log_file": str(log_path) if log_path else None,
    }
