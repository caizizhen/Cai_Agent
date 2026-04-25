"""Matrix Gateway minimal adapter (HM-N05-D04)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

_MAP_SCHEMA = "gateway_matrix_map_v1"
_HEALTH_SCHEMA = "gateway_matrix_health_v1"
_MESSAGES_SCHEMA = "gateway_matrix_messages_v1"
_MAP_NAME = "matrix-room-map.json"
_SPOOL_NAME = "matrix-messages.jsonl"


def _gateway_dir(root: Path) -> Path:
    d = (root / ".cai" / "gateway").resolve()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _map_path(root: Path) -> Path:
    return _gateway_dir(root) / _MAP_NAME


def _spool_path(root: Path) -> Path:
    return _gateway_dir(root) / _SPOOL_NAME


def _empty_map() -> dict[str, Any]:
    return {"schema_version": _MAP_SCHEMA, "bindings": {}, "allowed_room_ids": []}


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
    if not isinstance(obj.get("allowed_room_ids"), list):
        obj["allowed_room_ids"] = []
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


def matrix_bind(root: Path, room_id: str, session_file: str, *, label: str | None = None) -> dict[str, Any]:
    m = _read_map(root)
    rid = str(room_id).strip()
    row: dict[str, Any] = {"session_file": str(session_file), "bound_at": datetime.now(UTC).isoformat()}
    if label is not None and str(label).strip():
        row["label"] = str(label).strip()
    m["bindings"][rid] = row
    _write_map(root, m)
    return {"ok": True, "schema_version": _MAP_SCHEMA, "room_id": rid, "binding": row}


def matrix_unbind(root: Path, room_id: str) -> dict[str, Any]:
    m = _read_map(root)
    rid = str(room_id).strip()
    existed = rid in m["bindings"]
    if existed:
        del m["bindings"][rid]
        _write_map(root, m)
    return {"ok": True, "room_id": rid, "was_bound": existed}


def matrix_get_binding(root: Path, room_id: str) -> dict[str, Any]:
    m = _read_map(root)
    rid = str(room_id).strip()
    binding = m["bindings"].get(rid)
    return {"room_id": rid, "binding": binding, "found": binding is not None}


def matrix_list_bindings(root: Path) -> dict[str, Any]:
    m = _read_map(root)
    allowed = m.get("allowed_room_ids", [])
    return {
        "schema_version": _MAP_SCHEMA,
        "map_path": str(_map_path(root)),
        "bindings": m.get("bindings", {}),
        "allowed_room_ids": allowed,
        "allowlist_enabled": bool(allowed),
    }


def matrix_allow_add(root: Path, room_id: str) -> dict[str, Any]:
    m = _read_map(root)
    rid = str(room_id).strip()
    if rid not in m["allowed_room_ids"]:
        m["allowed_room_ids"].append(rid)
        _write_map(root, m)
    return {"ok": True, "room_id": rid, "allowed_room_ids": m["allowed_room_ids"]}


def matrix_allow_rm(root: Path, room_id: str) -> dict[str, Any]:
    m = _read_map(root)
    rid = str(room_id).strip()
    before = list(m["allowed_room_ids"])
    m["allowed_room_ids"] = [x for x in before if x != rid]
    _write_map(root, m)
    return {"ok": True, "room_id": rid, "removed": rid in before}


def matrix_allow_list(root: Path) -> dict[str, Any]:
    m = _read_map(root)
    allowed = m.get("allowed_room_ids", [])
    return {"allowed_room_ids": allowed, "allowlist_enabled": bool(allowed)}


def matrix_send(
    root: Path,
    *,
    room_id: str,
    sender: str,
    text: str,
    mirror_inbound: bool = False,
) -> dict[str, Any]:
    msg_id = f"mx-{uuid4().hex[:12]}"
    ev = {
        "schema_version": _MESSAGES_SCHEMA,
        "event": "matrix.send",
        "message_id": msg_id,
        "ts": datetime.now(UTC).isoformat(),
        "room_id": str(room_id).strip(),
        "sender": str(sender).strip(),
        "text": str(text),
        "status": "queued_local",
    }
    _append_spool(root, ev)
    mirrored = False
    if mirror_inbound:
        inbound = dict(ev)
        inbound["event"] = "matrix.inbound"
        inbound["status"] = "received_local"
        _append_spool(root, inbound)
        mirrored = True
    return {"ok": True, "schema_version": _MESSAGES_SCHEMA, "message": ev, "mirrored_to_inbound": mirrored}


def matrix_receive(root: Path, *, room_id: str, limit: int = 20) -> dict[str, Any]:
    rid = str(room_id).strip()
    rows = _read_spool(root)
    out = [
        x
        for x in rows
        if str(x.get("schema_version") or "") == _MESSAGES_SCHEMA
        and str(x.get("event") or "") == "matrix.inbound"
        and str(x.get("room_id") or "").strip() == rid
    ]
    m = _read_map(root)
    allow = [str(x).strip() for x in (m.get("allowed_room_ids") or []) if str(x).strip()]
    if allow and rid not in allow:
        out = []
    lim = max(1, int(limit))
    view = out[-lim:]
    return {
        "ok": True,
        "schema_version": _MESSAGES_SCHEMA,
        "room_id": rid,
        "messages_count": len(view),
        "messages": view,
        "spool_path": str(_spool_path(root)),
    }


def matrix_gateway_health(
    root: Path,
    *,
    homeserver: str | None = None,
    access_token: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    local = matrix_list_bindings(root)
    binds = local.get("bindings") if isinstance(local.get("bindings"), dict) else {}
    allow = local.get("allowed_room_ids") if isinstance(local.get("allowed_room_ids"), list) else []
    return {
        "schema_version": _HEALTH_SCHEMA,
        "workspace": str(root.resolve()),
        "map_path": local.get("map_path"),
        "map_schema_version": local.get("schema_version"),
        "spool_path": str(_spool_path(root)),
        "spool_exists": _spool_path(root).is_file(),
        "bindings_count": len(binds),
        "allowlist_enabled": bool(local.get("allowlist_enabled")),
        "allowed_room_ids_count": len(allow),
        "homeserver_configured": bool(str(homeserver or "").strip()),
        "access_token_configured": bool(str(access_token or "").strip()),
        "user_id_configured": bool(str(user_id or "").strip()),
        "token_check": {
            "performed": False,
            "ok": None,
            "hint": "Matrix MVP checks local map/spool/config only; remote homeserver checks come later.",
        },
    }


__all__ = [
    "matrix_bind",
    "matrix_unbind",
    "matrix_get_binding",
    "matrix_list_bindings",
    "matrix_allow_add",
    "matrix_allow_rm",
    "matrix_allow_list",
    "matrix_send",
    "matrix_receive",
    "matrix_gateway_health",
]
