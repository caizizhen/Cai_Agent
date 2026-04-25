"""Email Gateway minimal adapter (HM-N05-D03).

This adapter provides a local minimal message chain:
- map/allow contract (`gateway_email_map_v1`)
- health contract (`gateway_email_health_v1`)
- local send/receive spool (`gateway_email_messages_v1`)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

_MAP_SCHEMA = "gateway_email_map_v1"
_HEALTH_SCHEMA = "gateway_email_health_v1"
_MESSAGES_SCHEMA = "gateway_email_messages_v1"
_MAP_NAME = "email-session-map.json"
_SPOOL_NAME = "email-messages.jsonl"


def _gateway_dir(root: Path) -> Path:
    d = (root / ".cai" / "gateway").resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _map_path(root: Path) -> Path:
    return _gateway_dir(root) / _MAP_NAME


def _spool_path(root: Path) -> Path:
    return _gateway_dir(root) / _SPOOL_NAME


def _empty_map() -> dict[str, Any]:
    return {"schema_version": _MAP_SCHEMA, "bindings": {}, "allowed_senders": []}


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
    if not isinstance(obj.get("bindings"), dict):
        obj["bindings"] = {}
    if not isinstance(obj.get("allowed_senders"), list):
        obj["allowed_senders"] = []
    return obj


def _write_map(root: Path, obj: dict[str, Any]) -> None:
    p = _map_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _append_spool(root: Path, event: dict[str, Any]) -> None:
    p = _spool_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def _read_spool(root: Path) -> list[dict[str, Any]]:
    p = _spool_path(root)
    if not p.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def email_bind(root: Path, address: str, session_file: str, *, label: str | None = None) -> dict[str, Any]:
    m = _read_map(root)
    addr = str(address).strip().lower()
    row: dict[str, Any] = {"session_file": str(session_file), "bound_at": datetime.now(UTC).isoformat()}
    if label is not None and str(label).strip():
        row["label"] = str(label).strip()
    m["bindings"][addr] = row
    _write_map(root, m)
    return {"ok": True, "schema_version": _MAP_SCHEMA, "address": addr, "binding": row}


def email_unbind(root: Path, address: str) -> dict[str, Any]:
    m = _read_map(root)
    addr = str(address).strip().lower()
    existed = addr in m["bindings"]
    if existed:
        del m["bindings"][addr]
        _write_map(root, m)
    return {"ok": True, "address": addr, "was_bound": existed}


def email_get_binding(root: Path, address: str) -> dict[str, Any]:
    m = _read_map(root)
    addr = str(address).strip().lower()
    binding = m["bindings"].get(addr)
    return {"address": addr, "binding": binding, "found": binding is not None}


def email_list_bindings(root: Path) -> dict[str, Any]:
    m = _read_map(root)
    allowed = m.get("allowed_senders", [])
    return {
        "schema_version": _MAP_SCHEMA,
        "map_path": str(_map_path(root)),
        "bindings": m.get("bindings", {}),
        "allowed_senders": allowed,
        "allowlist_enabled": bool(allowed),
    }


def email_allow_add(root: Path, sender: str) -> dict[str, Any]:
    m = _read_map(root)
    s = str(sender).strip().lower()
    if s not in m["allowed_senders"]:
        m["allowed_senders"].append(s)
        _write_map(root, m)
    return {"ok": True, "sender": s, "allowed_senders": m["allowed_senders"]}


def email_allow_rm(root: Path, sender: str) -> dict[str, Any]:
    m = _read_map(root)
    s = str(sender).strip().lower()
    before = list(m["allowed_senders"])
    m["allowed_senders"] = [x for x in before if x != s]
    _write_map(root, m)
    return {"ok": True, "sender": s, "removed": s in before}


def email_allow_list(root: Path) -> dict[str, Any]:
    m = _read_map(root)
    allowed = m.get("allowed_senders", [])
    return {"allowed_senders": allowed, "allowlist_enabled": bool(allowed)}


def email_send(
    root: Path,
    *,
    from_address: str,
    to_address: str,
    subject: str,
    text: str,
    mirror_inbox: bool = False,
) -> dict[str, Any]:
    msg_id = f"eml-{uuid4().hex[:12]}"
    ev = {
        "schema_version": _MESSAGES_SCHEMA,
        "event": "email.send",
        "message_id": msg_id,
        "ts": datetime.now(UTC).isoformat(),
        "from": str(from_address).strip().lower(),
        "to": str(to_address).strip().lower(),
        "subject": str(subject),
        "text": str(text),
        "status": "queued_local",
    }
    _append_spool(root, ev)
    mirrored = False
    if mirror_inbox:
        inbound = dict(ev)
        inbound["event"] = "email.inbound"
        inbound["status"] = "received_local"
        _append_spool(root, inbound)
        mirrored = True
    return {"ok": True, "schema_version": _MESSAGES_SCHEMA, "message": ev, "mirrored_to_inbox": mirrored}


def email_receive(root: Path, *, inbox_address: str, limit: int = 20) -> dict[str, Any]:
    inbox = str(inbox_address).strip().lower()
    rows = _read_spool(root)
    out: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("schema_version") or "") != _MESSAGES_SCHEMA:
            continue
        if str(row.get("event") or "") != "email.inbound":
            continue
        if str(row.get("to") or "").strip().lower() != inbox:
            continue
        out.append(row)
    m = _read_map(root)
    allow = [str(x).strip().lower() for x in (m.get("allowed_senders") or []) if str(x).strip()]
    if allow:
        out = [x for x in out if str(x.get("from") or "").strip().lower() in allow]
    lim = max(1, int(limit))
    view = out[-lim:]
    return {
        "ok": True,
        "schema_version": _MESSAGES_SCHEMA,
        "inbox_address": inbox,
        "messages_count": len(view),
        "messages": view,
        "spool_path": str(_spool_path(root)),
    }


def email_gateway_health(
    root: Path,
    *,
    smtp_host: str | None = None,
    smtp_port: int | None = None,
    smtp_user: str | None = None,
    imap_host: str | None = None,
    imap_port: int | None = None,
    imap_user: str | None = None,
) -> dict[str, Any]:
    local = email_list_bindings(root)
    binds = local.get("bindings") if isinstance(local.get("bindings"), dict) else {}
    allow = local.get("allowed_senders") if isinstance(local.get("allowed_senders"), list) else []
    return {
        "schema_version": _HEALTH_SCHEMA,
        "workspace": str(root.resolve()),
        "map_path": local.get("map_path"),
        "map_schema_version": local.get("schema_version"),
        "spool_path": str(_spool_path(root)),
        "spool_exists": _spool_path(root).is_file(),
        "bindings_count": len(binds),
        "allowlist_enabled": bool(local.get("allowlist_enabled")),
        "allowed_senders_count": len(allow),
        "smtp": {
            "host_configured": bool(str(smtp_host or "").strip()),
            "port_configured": bool(smtp_port),
            "user_configured": bool(str(smtp_user or "").strip()),
        },
        "imap": {
            "host_configured": bool(str(imap_host or "").strip()),
            "port_configured": bool(imap_port),
            "user_configured": bool(str(imap_user or "").strip()),
        },
        "token_check": {
            "performed": False,
            "ok": None,
            "hint": "Email MVP checks local config and spool only; real SMTP/IMAP connectivity comes in later slices.",
        },
    }


__all__ = [
    "email_bind",
    "email_unbind",
    "email_get_binding",
    "email_list_bindings",
    "email_allow_add",
    "email_allow_rm",
    "email_allow_list",
    "email_send",
    "email_receive",
    "email_gateway_health",
]
