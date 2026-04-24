"""Gateway 生命周期 MVP（Hermes S6-01）：setup / start / status / stop。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cai_agent import __version__

CONFIG_NAME = "telegram-config.json"
PID_NAME = "telegram-webhook.pid"
CONFIG_SCHEMA = "gateway_telegram_config_v1"
PID_SCHEMA = "gateway_telegram_pid_v1"
STATUS_SCHEMA = "gateway_lifecycle_status_v1"


def _gateway_dir(root: Path) -> Path:
    d = (root / ".cai" / "gateway").resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read_map_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": "gateway_telegram_map_v1", "bindings": {}, "allowed_chat_ids": []}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"schema_version": "gateway_telegram_map_v1", "bindings": {}, "allowed_chat_ids": []}
    if not isinstance(obj, dict):
        return {"schema_version": "gateway_telegram_map_v1", "bindings": {}, "allowed_chat_ids": []}
    if not isinstance(obj.get("bindings"), dict):
        obj["bindings"] = {}
    if not isinstance(obj.get("allowed_chat_ids"), list):
        obj["allowed_chat_ids"] = []
    obj.setdefault("schema_version", "gateway_telegram_map_v1")
    return obj


def config_path(root: Path | str) -> Path:
    return _gateway_dir(Path(root)) / CONFIG_NAME


def pid_path(root: Path | str) -> Path:
    return _gateway_dir(Path(root)) / PID_NAME


def load_telegram_config(root: Path | str) -> dict[str, Any] | None:
    p = config_path(root)
    if not p.is_file():
        return None
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def save_telegram_config(root: Path | str, doc: dict[str, Any]) -> Path:
    p = config_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def default_serve_block() -> dict[str, Any]:
    return {
        "host": "127.0.0.1",
        "port": 18765,
        "max_events": 0,
        "create_missing": False,
        "execute_on_update": False,
        "reply_on_execution": False,
        "reply_on_deny": False,
        "goal_template": "用户({user_id})在 chat({chat_id}) 发送消息：{text}",
        "reply_template": "执行完成 ok={ok}\n{answer}",
        "deny_message": "此 CAI Agent Bot 未授权本对话。",
    }


def build_setup_payload(
    *,
    root: Path,
    use_env_token: bool,
    bot_token: str | None,
    workspace: str | None,
    serve: dict[str, Any] | None,
    allow_chat_ids: list[str] | None,
) -> dict[str, Any]:
    """写入 ``gateway_telegram_config_v1`` 并可同步 ``allowed_chat_ids`` 到映射文件。"""
    base = root.resolve()
    ws = str(Path(workspace or ".").expanduser().resolve())
    sw = {**default_serve_block(), **(serve or {})}
    token_literal = (str(bot_token).strip() if bot_token else "") or None
    doc: dict[str, Any] = {
        "schema_version": CONFIG_SCHEMA,
        "generated_at": datetime.now(UTC).isoformat(),
        "cai_agent_version": __version__,
        "workspace": ws,
        "use_env_token": bool(use_env_token),
        "bot_token_set_in_file": bool(token_literal),
        "serve_webhook": sw,
    }
    if token_literal:
        doc["bot_token"] = token_literal
    save_telegram_config(base, doc)

    if allow_chat_ids:
        map_p = _gateway_dir(base) / "telegram-session-map.json"
        mdoc = _read_map_file(map_p)
        cur = [str(x).strip() for x in (mdoc.get("allowed_chat_ids") or []) if str(x).strip()]
        for c in allow_chat_ids:
            s = str(c).strip()
            if s and s not in cur:
                cur.append(s)
        mdoc["allowed_chat_ids"] = sorted(set(cur))
        mdoc.setdefault("schema_version", "gateway_telegram_map_v1")
        mdoc.setdefault("bindings", mdoc.get("bindings") if isinstance(mdoc.get("bindings"), dict) else {})
        map_p.parent.mkdir(parents=True, exist_ok=True)
        map_p.write_text(json.dumps(mdoc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "schema_version": CONFIG_SCHEMA,
        "ok": True,
        "config_path": str(config_path(base)),
        "workspace": ws,
        "use_env_token": bool(use_env_token),
        "allow_chat_ids_applied": list(allow_chat_ids or []),
    }


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            r = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            return str(pid) in (r.stdout or "")
        except Exception:
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_pid_doc(root: Path) -> dict[str, Any] | None:
    p = pid_path(root)
    if not p.is_file():
        return None
    try:
        o = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return o if isinstance(o, dict) else None


def build_gateway_summary_payload(root: Path | str) -> dict[str, Any]:
    """Shared read-side gateway summary for board / ops / gateway status."""
    base = Path(root).expanduser().resolve()
    cfg_path = config_path(base)
    map_path = _gateway_dir(base) / "telegram-session-map.json"
    mdoc = _read_map_file(map_path)
    binds = mdoc.get("bindings") if isinstance(mdoc.get("bindings"), dict) else {}
    allowed = [str(x) for x in (mdoc.get("allowed_chat_ids") or []) if str(x).strip()]
    pid_doc = _read_pid_doc(base)
    pid = int(pid_doc.get("pid") or 0) if isinstance(pid_doc, dict) else 0
    alive = _pid_alive(pid) if pid else False
    return {
        "schema_version": "gateway_summary_v1",
        "workspace": str(base),
        "config_path": str(cfg_path),
        "config_exists": cfg_path.is_file(),
        "map_path": str(map_path),
        "bindings_count": len(binds),
        "allowed_chat_ids_count": len(allowed),
        "allowed_chat_ids": allowed,
        "allowlist_enabled": bool(allowed),
        "webhook_pid": pid or None,
        "webhook_running": alive,
        "status": "running" if alive else ("configured" if cfg_path.is_file() else "not_configured"),
    }


def build_status_payload(root: Path | str) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    summary = build_gateway_summary_payload(base)
    return {
        "schema_version": STATUS_SCHEMA,
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(base),
        "config_path": str(config_path(base)),
        "config_exists": config_path(base).is_file(),
        "pid_path": str(pid_path(base)),
        "webhook_pid": summary.get("webhook_pid"),
        "webhook_running": summary.get("webhook_running"),
        "bindings_count": summary.get("bindings_count"),
        "allowed_chat_ids": summary.get("allowed_chat_ids"),
        "allowlist_enabled": summary.get("allowlist_enabled"),
        "gateway_summary": summary,
    }


def start_webhook_subprocess(root: Path | str) -> dict[str, Any]:
    """根据 ``telegram-config.json`` 启动 ``serve-webhook`` 子进程并写入 PID 文件。"""
    base = Path(root).expanduser().resolve()
    cfg = load_telegram_config(base)
    if not cfg:
        return {"schema_version": "gateway_lifecycle_start_v1", "ok": False, "error": "config_missing"}
    sw = cfg.get("serve_webhook") if isinstance(cfg.get("serve_webhook"), dict) else {}
    host = str(sw.get("host") or "127.0.0.1")
    port = int(sw.get("port") or 18765)
    max_ev = int(sw.get("max_events") or 0)
    cmd: list[str] = [
        sys.executable,
        "-m",
        "cai_agent",
        "gateway",
        "telegram",
        "serve-webhook",
        "--host",
        host,
        "--port",
        str(port),
        "--max-events",
        str(max_ev),
    ]
    if bool(sw.get("create_missing")):
        cmd.append("--create-missing")
    if bool(sw.get("execute_on_update")):
        cmd.append("--execute-on-update")
    if bool(sw.get("reply_on_execution")):
        cmd.append("--reply-on-execution")
    if bool(sw.get("reply_on_deny")):
        cmd.append("--reply-on-deny")
    gt = str(sw.get("goal_template") or "").strip()
    if gt:
        cmd.extend(["--goal-template", gt])
    rt = str(sw.get("reply_template") or "").strip()
    if rt:
        cmd.extend(["--reply-template", rt])
    dm = str(sw.get("deny_message") or "").strip()
    if dm:
        cmd.extend(["--deny-message", dm])
    tok = str(cfg.get("bot_token") or "").strip()
    if tok:
        cmd.extend(["--telegram-bot-token", tok])

    gdir = _gateway_dir(base)
    out_log = gdir / "telegram-webhook.stdout.log"
    err_log = gdir / "telegram-webhook.stderr.log"
    out_log.parent.mkdir(parents=True, exist_ok=True)
    with out_log.open("ab") as fo, err_log.open("ab") as fe:
        kwargs: dict[str, Any] = {
            "cwd": str(base),
            "stdout": fo,
            "stderr": fe,
        }
        if os.name == "nt":
            cf = getattr(subprocess, "DETACHED_PROCESS", 0)
            cf |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            kwargs["creationflags"] = cf
        else:
            kwargs["start_new_session"] = True
        proc = subprocess.Popen(cmd, **kwargs)  # noqa: S603
    pid_doc = {
        "schema_version": PID_SCHEMA,
        "pid": proc.pid,
        "started_at": datetime.now(UTC).isoformat(),
        "cmd": cmd,
        "workspace": str(base),
    }
    pid_path(base).write_text(json.dumps(pid_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "schema_version": "gateway_lifecycle_start_v1",
        "ok": True,
        "pid": proc.pid,
        "pid_file": str(pid_path(base)),
        "stdout_log": str(out_log),
        "stderr_log": str(err_log),
    }


def stop_webhook_subprocess(root: Path | str) -> dict[str, Any]:
    base = Path(root).expanduser().resolve()
    doc = _read_pid_doc(base)
    pid = int(doc.get("pid") or 0) if isinstance(doc, dict) else 0
    if pid <= 0:
        return {"schema_version": "gateway_lifecycle_stop_v1", "ok": False, "error": "no_pid_file"}
    if not _pid_alive(pid):
        pid_path(base).unlink(missing_ok=True)
        return {"schema_version": "gateway_lifecycle_stop_v1", "ok": True, "stopped": False, "reason": "not_running"}
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        else:
            os.kill(pid, 15)
    except Exception as e:
        return {"schema_version": "gateway_lifecycle_stop_v1", "ok": False, "error": "stop_failed", "message": str(e)}
    pid_path(base).unlink(missing_ok=True)
    return {"schema_version": "gateway_lifecycle_stop_v1", "ok": True, "stopped": True, "pid": pid}
