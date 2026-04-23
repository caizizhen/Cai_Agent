"""Slack Gateway MVP（§24 补齐）。

实现策略：使用 Slack Bot Token 通过 Events API Webhook 接收事件（HTTP POST），
与 Telegram serve-webhook 实现路径对齐（无外部依赖，仅 urllib + http.server）。

Bot Token 需要以下 OAuth Scopes：
  chat:write, channels:history, im:history, app_mentions:read

端点：
  gateway slack serve-webhook  —— 启动 Slack Events API 接收服务
  gateway slack bind/get/list/unbind  —— 会话映射管理
  gateway slack allow add/list/rm     —— 白名单管理
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

_SLACK_API = "https://slack.com/api"
_MAP_SCHEMA = "gateway_slack_map_v1"
_MAP_NAME = "slack-session-map.json"


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _gateway_dir(root: Path) -> Path:
    d = (root / ".cai" / "gateway").resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _map_path(root: Path) -> Path:
    return _gateway_dir(root) / _MAP_NAME


def _read_map(root: Path) -> dict[str, Any]:
    p = _map_path(root)
    if not p.is_file():
        return {"schema_version": _MAP_SCHEMA, "bindings": {}, "allowed_channel_ids": []}
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"schema_version": _MAP_SCHEMA, "bindings": {}, "allowed_channel_ids": []}
    if not isinstance(obj, dict):
        return {"schema_version": _MAP_SCHEMA, "bindings": {}, "allowed_channel_ids": []}
    obj.setdefault("bindings", {})
    obj.setdefault("allowed_channel_ids", [])
    obj.setdefault("schema_version", _MAP_SCHEMA)
    return obj


def _write_map(root: Path, obj: dict[str, Any]) -> None:
    p = _map_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def _slack_post(
    method_path: str,
    bot_token: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{_SLACK_API}/{method_path}"
    data = json.dumps(payload or {}).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {bot_token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return {"ok": False, "_http_error": e.code, **json.loads(body)}
        except Exception:
            return {"ok": False, "_http_error": e.code, "body": body[:400]}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 会话映射管理
# ---------------------------------------------------------------------------

def slack_bind(root: Path, channel_id: str, session_file: str) -> dict[str, Any]:
    m = _read_map(root)
    m["bindings"][channel_id] = {
        "session_file": session_file,
        "bound_at": datetime.now(UTC).isoformat(),
    }
    _write_map(root, m)
    return {"ok": True, "channel_id": channel_id, "session_file": session_file}


def slack_unbind(root: Path, channel_id: str) -> dict[str, Any]:
    m = _read_map(root)
    existed = channel_id in m["bindings"]
    if existed:
        del m["bindings"][channel_id]
        _write_map(root, m)
    return {"ok": True, "channel_id": channel_id, "was_bound": existed}


def slack_get_binding(root: Path, channel_id: str) -> dict[str, Any]:
    m = _read_map(root)
    b = m["bindings"].get(channel_id)
    return {"channel_id": channel_id, "binding": b, "found": b is not None}


def slack_list_bindings(root: Path) -> dict[str, Any]:
    m = _read_map(root)
    return {
        "schema_version": _MAP_SCHEMA,
        "map_path": str(_map_path(root)),
        "bindings": m.get("bindings", {}),
        "allowed_channel_ids": m.get("allowed_channel_ids", []),
        "allowlist_enabled": bool(m.get("allowed_channel_ids")),
    }


# ---------------------------------------------------------------------------
# 白名单
# ---------------------------------------------------------------------------

def slack_allow_add(root: Path, channel_id: str) -> dict[str, Any]:
    m = _read_map(root)
    if channel_id not in m["allowed_channel_ids"]:
        m["allowed_channel_ids"].append(channel_id)
        _write_map(root, m)
    return {"ok": True, "channel_id": channel_id}


def slack_allow_rm(root: Path, channel_id: str) -> dict[str, Any]:
    m = _read_map(root)
    before = list(m["allowed_channel_ids"])
    m["allowed_channel_ids"] = [c for c in before if c != channel_id]
    _write_map(root, m)
    return {"ok": True, "channel_id": channel_id, "removed": channel_id in before}


def slack_allow_list(root: Path) -> dict[str, Any]:
    m = _read_map(root)
    return {"allowed_channel_ids": m.get("allowed_channel_ids", []), "allowlist_enabled": bool(m.get("allowed_channel_ids"))}


# ---------------------------------------------------------------------------
# 消息发送（Slack chat.postMessage）
# ---------------------------------------------------------------------------

_MAX_SLACK_LEN = 3500


def _send_slack_message(channel: str, text: str, bot_token: str) -> dict[str, Any]:
    chunks = [text[i : i + _MAX_SLACK_LEN] for i in range(0, max(1, len(text)), _MAX_SLACK_LEN)]
    last: dict[str, Any] = {}
    for chunk in chunks:
        last = _slack_post("chat.postMessage", bot_token, {"channel": channel, "text": chunk})
    return last


# ---------------------------------------------------------------------------
# Slack 签名验证
# ---------------------------------------------------------------------------

def _verify_slack_signature(
    signing_secret: str,
    timestamp: str,
    body: bytes,
    received_sig: str,
) -> bool:
    """验证 Slack Events API 的 X-Slack-Signature 签名。"""
    try:
        ts = int(timestamp)
        if abs(time.time() - ts) > 300:
            return False
    except (ValueError, TypeError):
        return False
    base = f"v0:{timestamp}:".encode("utf-8") + body
    expected = "v0=" + hmac.new(
        signing_secret.encode("utf-8"), base, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, received_sig)


# ---------------------------------------------------------------------------
# Webhook 服务（Events API）
# ---------------------------------------------------------------------------

class _SlackWebhookHandler(BaseHTTPRequestHandler):
    """处理 Slack Events API 的 POST 请求。"""

    root: Path = Path(".")
    bot_token: str = ""
    signing_secret: str = ""
    execute_on_event: bool = False
    reply_on_execution: bool = False
    log_path: Path | None = None
    events_handled: list = []  # 共享计数器（list 可变）
    max_events: int = 0

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        pass

    def do_GET(self) -> None:  # noqa: N802
        self._send_json(200, {"ok": True, "service": "cai-agent slack gateway"})

    def do_POST(self) -> None:  # noqa: N802
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length)

        if self.signing_secret:
            ts = self.headers.get("X-Slack-Request-Timestamp", "")
            sig = self.headers.get("X-Slack-Signature", "")
            if not _verify_slack_signature(self.signing_secret, ts, body_bytes, sig):
                self._send_json(403, {"error": "invalid_signature"})
                return

        try:
            payload = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            self._send_json(400, {"error": "invalid_json"})
            return

        # URL Verification challenge
        if payload.get("type") == "url_verification":
            self._send_json(200, {"challenge": payload.get("challenge", "")})
            return

        # Events API callback
        if payload.get("type") == "event_callback":
            event = payload.get("event") or {}
            event_type = str(event.get("type") or "")
            channel_id = str(event.get("channel") or "")
            text = str(event.get("text") or "").strip()
            bot_id = event.get("bot_id")
            user_id = str(event.get("user") or "")

            self._send_json(200, {"ok": True})

            if bot_id:
                return

            m = _read_map(self.root)
            al = m.get("allowed_channel_ids", [])
            if al and channel_id not in al:
                return

            ev: dict[str, Any] = {
                "ts": datetime.now(UTC).isoformat(),
                "event": f"slack.{event_type}",
                "channel_id": channel_id,
                "user_id": user_id,
                "content_preview": text[:120],
                "not_allowed": bool(al and channel_id not in al),
            }

            if self.execute_on_event and text and event_type in ("message", "app_mention"):
                binding = m.get("bindings", {}).get(channel_id, {})
                session_file = str(binding.get("session_file") or "") if isinstance(binding, dict) else ""
                try:
                    from cai_agent.config import Settings
                    from cai_agent.graph import build_app, initial_state
                    s = Settings.from_env(workspace_hint=str(self.root))
                    if session_file and Path(session_file).is_file():
                        from cai_agent.session import load_session, save_session
                        from cai_agent.graph import continue_state
                        sess = load_session(Path(session_file))
                        app = build_app(s)
                        state = continue_state(s, text, sess)
                        final = app.invoke(state)
                        save_session(Path(session_file), final)
                    else:
                        app = build_app(s)
                        state = initial_state(s, text)
                        final = app.invoke(state)
                        if session_file:
                            from cai_agent.session import save_session
                            save_session(Path(session_file), final)
                    answer = str(final.get("answer") or "")[:600]
                    ev["executed"] = True
                    ev["answer_preview"] = answer
                    if self.reply_on_execution and answer and channel_id and self.bot_token:
                        _send_slack_message(channel_id, answer, self.bot_token)
                        ev["replied"] = True
                except Exception as exc:
                    ev["executed"] = False
                    ev["execute_error"] = str(exc)[:200]

            if self.log_path:
                with self.log_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(ev, ensure_ascii=False) + "\n")
            self.events_handled.append(ev)
            if self.max_events > 0 and len(self.events_handled) >= self.max_events:
                import threading
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        self._send_json(200, {"ok": True})

    def _send_json(self, code: int, obj: dict[str, Any]) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve_slack_webhook(
    *,
    root: Path,
    bot_token: str,
    signing_secret: str = "",
    host: str = "0.0.0.0",
    port: int = 7892,
    execute_on_event: bool = False,
    reply_on_execution: bool = False,
    log_file: str | None = None,
    max_events: int = 0,
) -> dict[str, Any]:
    """启动 Slack Events API Webhook 接收服务。

    Args:
        root: 工作区根目录。
        bot_token: Slack Bot Token（xoxb-...）。
        signing_secret: Slack 签名密钥（用于验证请求合法性）。
        host: 监听主机。
        port: 监听端口（默认 7892）。
        execute_on_event: 是否对收到的消息触发执行。
        reply_on_execution: 是否将执行结果回发到频道。
        log_file: 事件 JSONL 日志路径。
        max_events: 最大处理事件数（0 = 无限）。

    Returns:
        ``gateway_slack_webhook_v1`` 结构。
    """
    started_at = datetime.now(UTC).isoformat()
    log_path = Path(log_file) if log_file else None
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    shared_events: list = []

    class _Handler(_SlackWebhookHandler):
        pass

    _Handler.root = root
    _Handler.bot_token = bot_token
    _Handler.signing_secret = signing_secret
    _Handler.execute_on_event = execute_on_event
    _Handler.reply_on_execution = reply_on_execution
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
        "schema_version": "gateway_slack_webhook_v1",
        "started_at": started_at,
        "stopped_at": datetime.now(UTC).isoformat(),
        "host": host,
        "port": port,
        "events_handled": len(shared_events),
        "log_file": str(log_path) if log_path else None,
        "ok": True,
    }
