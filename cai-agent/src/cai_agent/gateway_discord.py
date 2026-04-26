"""Discord Gateway MVP（§24 补齐）。

实现策略：使用 Discord Bot Token 通过 REST Polling（GET /channels/{id}/messages）
轮询消息，与 Telegram 实现路径对齐（无外部依赖，仅 urllib）。

端点：
  gateway discord serve-polling  —— 启动轮询服务
  gateway discord bind/get/list/unbind  —— 会话映射管理
  gateway discord allow add/list/rm     —— 白名单管理
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DISCORD_API = "https://discord.com/api/v10"
_MAP_SCHEMA = "gateway_discord_map_v1"
_MAP_NAME = "discord-session-map.json"


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


def _discord_request(
    method: str,
    path: str,
    bot_token: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{_DISCORD_API}{path}"
    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json",
        "User-Agent": "CaiAgent/1 (https://github.com)",
    }
    data = json.dumps(payload or {}).encode("utf-8") if payload else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            if body:
                return json.loads(body)
            return {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            return {"_error": True, "status": e.code, **json.loads(body)}
        except Exception:
            return {"_error": True, "status": e.code, "body": body[:500]}
    except Exception as e:
        return {"_error": True, "message": str(e)}


def _discord_exchange(
    method: str,
    path: str,
    bot_token: str,
    *,
    json_data: list[dict[str, Any]] | dict[str, Any] | None = None,
) -> Any:
    """底层 REST 交换（可 mock）；``json_data`` 为 list 时原样 JSON 编码（注册 Slash 命令）。"""
    url = f"{_DISCORD_API}{path}"
    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json",
        "User-Agent": "CaiAgent/1 (https://github.com)",
    }
    raw = json.dumps(json_data, ensure_ascii=False).encode("utf-8") if json_data is not None else None
    req = urllib.request.Request(url, data=raw, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            if not body.strip():
                return [] if method.upper() == "PUT" else {}
            return json.loads(body)
    except urllib.error.HTTPError as e:
        b = e.read().decode("utf-8", errors="replace")
        try:
            return {"_error": True, "status": e.code, **json.loads(b)}
        except Exception:
            return {"_error": True, "status": e.code, "body": b[:500]}
    except Exception as e:
        return {"_error": True, "message": str(e)}


def discord_default_slash_command_specs() -> list[dict[str, Any]]:
    """与 Telegram 表面对齐的 Application Command 草案（name + type=1 CHAT_INPUT）。"""
    return [
        {"name": "ping", "description": "Ping CAI", "type": 1},
        {"name": "help", "description": "Help", "type": 1},
        {"name": "status", "description": "Status", "type": 1},
        {"name": "new", "description": "New session", "type": 1},
    ]


def discord_resolve_application(bot_token: str) -> dict[str, Any]:
    data = _discord_exchange("GET", "/oauth2/applications/@me", bot_token)
    if isinstance(data, dict) and data.get("_error"):
        return {"ok": False, "error": data}
    if isinstance(data, dict) and data.get("id") is not None:
        return {"ok": True, "application_id": str(data["id"])}
    return {"ok": False, "error": {"message": "unexpected_resolve_payload", "raw": data}}


def discord_list_application_commands(
    bot_token: str,
    *,
    guild_id: str | None = None,
) -> dict[str, Any]:
    app = discord_resolve_application(bot_token)
    if not app.get("ok"):
        return {**app, "commands": [], "guild_id": guild_id}
    aid = str(app.get("application_id") or "")
    path = (
        f"/applications/{aid}/guilds/{guild_id}/commands"
        if guild_id
        else f"/applications/{aid}/commands"
    )
    data = _discord_exchange("GET", path, bot_token)
    if isinstance(data, dict) and data.get("_error"):
        return {"ok": False, "error": data, "commands": [], "guild_id": guild_id}
    if isinstance(data, list):
        return {"ok": True, "commands": data, "guild_id": guild_id}
    return {"ok": False, "error": {"message": "unexpected_list_payload"}, "commands": [], "guild_id": guild_id}


def discord_register_application_commands(
    bot_token: str,
    *,
    guild_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    specs = discord_default_slash_command_specs()
    app = discord_resolve_application(bot_token)
    if not app.get("ok"):
        return {
            "ok": False,
            "dry_run": dry_run,
            "registered": False,
            "commands": [],
            "error": app.get("error"),
        }
    aid = str(app.get("application_id") or "")
    if dry_run:
        return {"ok": True, "dry_run": True, "registered": False, "commands": specs}
    path = (
        f"/applications/{aid}/guilds/{guild_id}/commands"
        if guild_id
        else f"/applications/{aid}/commands"
    )
    data = _discord_exchange("PUT", path, bot_token, json_data=specs)
    if isinstance(data, dict) and data.get("_error"):
        return {"ok": False, "dry_run": False, "registered": False, "commands": [], "error": data}
    if isinstance(data, list):
        return {"ok": True, "dry_run": False, "registered": True, "commands": data}
    return {"ok": False, "dry_run": False, "registered": False, "commands": [], "error": {"message": "unexpected_put"}}


# ---------------------------------------------------------------------------
# 会话映射管理
# ---------------------------------------------------------------------------

def discord_bind(
    root: Path,
    channel_id: str,
    session_file: str,
    *,
    guild_id: str | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    m = _read_map(root)
    row: dict[str, Any] = {
        "session_file": session_file,
        "bound_at": datetime.now(UTC).isoformat(),
    }
    if guild_id is not None and str(guild_id).strip():
        row["guild_id"] = str(guild_id).strip()
    if label is not None and str(label).strip():
        row["label"] = str(label).strip()
    m["bindings"][channel_id] = row
    _write_map(root, m)
    return {"ok": True, "channel_id": channel_id, "session_file": session_file, "binding": row}


def discord_unbind(root: Path, channel_id: str) -> dict[str, Any]:
    m = _read_map(root)
    existed = channel_id in m["bindings"]
    if existed:
        del m["bindings"][channel_id]
        _write_map(root, m)
    return {"ok": True, "channel_id": channel_id, "was_bound": existed}


def discord_get_binding(root: Path, channel_id: str) -> dict[str, Any]:
    m = _read_map(root)
    b = m["bindings"].get(channel_id)
    return {"channel_id": channel_id, "binding": b, "found": b is not None}


def discord_list_bindings(root: Path) -> dict[str, Any]:
    m = _read_map(root)
    return {
        "schema_version": _MAP_SCHEMA,
        "map_path": str(_map_path(root)),
        "bindings": m.get("bindings", {}),
        "allowed_channel_ids": m.get("allowed_channel_ids", []),
        "allowlist_enabled": bool(m.get("allowed_channel_ids")),
    }


def discord_gateway_health(
    root: Path,
    *,
    bot_token: str | None = None,
) -> dict[str, Any]:
    """运维自检：本地 ``discord-session-map`` + 可选 ``GET /users/@me`` 校验 Token。

    机读契约：``gateway_discord_health_v1``。
    """
    local = discord_list_bindings(root)
    binds = local.get("bindings") if isinstance(local.get("bindings"), dict) else {}
    allow = local.get("allowed_channel_ids") if isinstance(local.get("allowed_channel_ids"), list) else []
    base: dict[str, Any] = {
        "schema_version": "gateway_discord_health_v1",
        "workspace": str(root.resolve()),
        "map_path": local.get("map_path"),
        "map_schema_version": local.get("schema_version"),
        "bindings_count": len(binds),
        "allowlist_enabled": bool(local.get("allowlist_enabled")),
        "allowed_channel_ids_count": len(allow),
    }
    tok = (bot_token or "").strip()
    if not tok:
        base["token_check"] = {
            "performed": False,
            "ok": None,
            "hint": "提供 --bot-token 或环境变量 CAI_DISCORD_BOT_TOKEN 以调用 Discord API 校验 Token。",
        }
        return base
    me = _discord_request("GET", "/users/@me", tok)
    if isinstance(me, dict) and me.get("_error"):
        base["token_check"] = {
            "performed": True,
            "ok": False,
            "http_status": me.get("status"),
            "message": str(me.get("message") or me.get("body") or "")[:400],
        }
        return base
    if isinstance(me, dict) and me.get("id") is not None:
        base["token_check"] = {
            "performed": True,
            "ok": True,
            "username": me.get("username"),
            "user_id": str(me.get("id")),
            "discriminator": str(me.get("discriminator") or ""),
            "bot": bool(me.get("bot")),
        }
        return base
    base["token_check"] = {
        "performed": True,
        "ok": False,
        "message": "unexpected_users_me_payload",
    }
    return base


# ---------------------------------------------------------------------------
# 白名单
# ---------------------------------------------------------------------------

def discord_allow_add(root: Path, channel_id: str) -> dict[str, Any]:
    m = _read_map(root)
    if channel_id not in m["allowed_channel_ids"]:
        m["allowed_channel_ids"].append(channel_id)
        _write_map(root, m)
    return {"ok": True, "channel_id": channel_id, "allowed_channel_ids": m["allowed_channel_ids"]}


def discord_allow_rm(root: Path, channel_id: str) -> dict[str, Any]:
    m = _read_map(root)
    before = list(m["allowed_channel_ids"])
    m["allowed_channel_ids"] = [c for c in before if c != channel_id]
    _write_map(root, m)
    return {"ok": True, "channel_id": channel_id, "removed": channel_id in before}


def discord_allow_list(root: Path) -> dict[str, Any]:
    m = _read_map(root)
    return {"allowed_channel_ids": m.get("allowed_channel_ids", []), "allowlist_enabled": bool(m.get("allowed_channel_ids"))}


# ---------------------------------------------------------------------------
# 消息发送（分段，Discord 消息上限 2000 字符）
# ---------------------------------------------------------------------------

_MAX_MSG_LEN = 1990


def _send_discord_message(channel_id: str, text: str, bot_token: str) -> dict[str, Any]:
    chunks = [text[i : i + _MAX_MSG_LEN] for i in range(0, max(1, len(text)), _MAX_MSG_LEN)]
    last: dict[str, Any] = {}
    for chunk in chunks:
        last = _discord_request(
            "POST",
            f"/channels/{channel_id}/messages",
            bot_token,
            {"content": chunk},
        )
    return last


# ---------------------------------------------------------------------------
# Bot Polling 服务（serve-polling）
# ---------------------------------------------------------------------------

def serve_discord_polling(
    *,
    root: Path,
    bot_token: str,
    poll_interval: float = 2.0,
    max_events: int = 0,
    execute_on_message: bool = False,
    reply_on_execution: bool = False,
    log_file: str | None = None,
    agent_config_path: str | None = None,
) -> dict[str, Any]:
    """轮询指定频道（已绑定会话的频道）的新消息并可选执行。

    Args:
        root: 工作区根目录。
        bot_token: Discord Bot Token。
        poll_interval: 轮询间隔秒数。
        max_events: 最大处理消息数（0 = 无限，直到 KeyboardInterrupt）。
        execute_on_message: 是否对每条消息触发 `run`/`continue` 执行。
        reply_on_execution: 是否将执行结果回发到频道。
        log_file: 事件 JSONL 日志路径（None = 不落盘）。
        agent_config_path: 可选 ``cai-agent.toml``，与 ``api serve --config`` 对齐以固定 profile 解析。

    Returns:
        ``gateway_discord_polling_v1`` 结构。
    """
    started_at = datetime.now(UTC).isoformat()
    events_log: list[dict[str, Any]] = []
    events_handled = 0
    last_message_ids: dict[str, str] = {}

    log_path: Path | None = Path(log_file) if log_file else None
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)

    def _log(ev: dict[str, Any]) -> None:
        if log_path:
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        events_log.append(ev)

    def _get_bindings() -> dict[str, Any]:
        m = _read_map(root)
        return m.get("bindings", {})

    def _is_allowed(channel_id: str) -> bool:
        m = _read_map(root)
        al = m.get("allowed_channel_ids", [])
        if not al:
            return True
        return channel_id in al

    try:
        while True:
            bindings = _get_bindings()
            for channel_id, binding in bindings.items():
                if not _is_allowed(channel_id):
                    continue
                last_id = last_message_ids.get(channel_id)
                params = "?limit=10"
                if last_id:
                    params += f"&after={last_id}"
                msgs = _discord_request("GET", f"/channels/{channel_id}/messages{params}", bot_token)
                if isinstance(msgs, list):
                    for msg in reversed(msgs):
                        msg_id = str(msg.get("id") or "")
                        author = msg.get("author") or {}
                        if author.get("bot"):
                            last_message_ids[channel_id] = msg_id
                            continue
                        content = str(msg.get("content") or "").strip()
                        if not content:
                            last_message_ids[channel_id] = msg_id
                            continue
                        ev: dict[str, Any] = {
                            "ts": datetime.now(UTC).isoformat(),
                            "event": "discord.message",
                            "channel_id": channel_id,
                            "message_id": msg_id,
                            "author_id": str(author.get("id") or ""),
                            "content_preview": content[:120],
                        }
                        answer_preview = ""
                        if execute_on_message:
                            session_file = str(binding.get("session_file") or "")
                            try:
                                from cai_agent.config import load_agent_settings_for_workspace
                                from cai_agent.graph import build_app, initial_state
                                s = load_agent_settings_for_workspace(
                                    workspace=root,
                                    config_path=agent_config_path,
                                )
                                if session_file and Path(session_file).is_file():
                                    from cai_agent.session import load_session, save_session
                                    sess = load_session(Path(session_file))
                                    from cai_agent.graph import build_app, continue_state
                                    app = build_app(s)
                                    state = continue_state(s, content, sess)
                                    final = app.invoke(state)
                                    save_session(Path(session_file), final)
                                else:
                                    app = build_app(s)
                                    state = initial_state(s, content)
                                    final = app.invoke(state)
                                    if session_file:
                                        from cai_agent.session import save_session
                                        save_session(Path(session_file), final)
                                answer_preview = str(final.get("answer") or "")[:300]
                                ev["executed"] = True
                                ev["answer_preview"] = answer_preview
                            except Exception as exc:
                                ev["executed"] = False
                                ev["execute_error"] = str(exc)[:200]
                            if reply_on_execution and answer_preview:
                                reply = answer_preview or "(no answer)"
                                _send_discord_message(channel_id, reply, bot_token)
                                ev["replied"] = True
                        _log(ev)
                        events_handled += 1
                        last_message_ids[channel_id] = msg_id
                        if max_events > 0 and events_handled >= max_events:
                            raise KeyboardInterrupt
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        pass

    return {
        "schema_version": "gateway_discord_polling_v1",
        "started_at": started_at,
        "stopped_at": datetime.now(UTC).isoformat(),
        "events_handled": events_handled,
        "ok": True,
        "log_file": str(log_path) if log_path else None,
    }
