"""Signal Gateway adapter skeleton (HM-N05-D02).

This module intentionally stays local/read-safe for now:
- mapping CRUD for `signal-session-map.json`
- allowlist CRUD for sender IDs
- health contract with config presence checks only
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_MAP_SCHEMA = "gateway_signal_map_v1"
_HEALTH_SCHEMA = "gateway_signal_health_v1"
_MAP_NAME = "signal-session-map.json"


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
        "allowed_sender_ids": [],
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
    if not isinstance(obj.get("bindings"), dict):
        obj["bindings"] = {}
    if not isinstance(obj.get("allowed_sender_ids"), list):
        obj["allowed_sender_ids"] = []
    return obj


def _write_map(root: Path, obj: dict[str, Any]) -> None:
    p = _map_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def signal_bind(root: Path, sender_id: str, session_file: str, *, label: str | None = None) -> dict[str, Any]:
    m = _read_map(root)
    sid = str(sender_id).strip()
    row: dict[str, Any] = {
        "session_file": str(session_file),
        "bound_at": datetime.now(UTC).isoformat(),
    }
    if label is not None and str(label).strip():
        row["label"] = str(label).strip()
    m["bindings"][sid] = row
    _write_map(root, m)
    return {"ok": True, "schema_version": _MAP_SCHEMA, "sender_id": sid, "binding": row}


def signal_unbind(root: Path, sender_id: str) -> dict[str, Any]:
    m = _read_map(root)
    sid = str(sender_id).strip()
    existed = sid in m["bindings"]
    if existed:
        del m["bindings"][sid]
        _write_map(root, m)
    return {"ok": True, "sender_id": sid, "was_bound": existed}


def signal_get_binding(root: Path, sender_id: str) -> dict[str, Any]:
    m = _read_map(root)
    sid = str(sender_id).strip()
    binding = m["bindings"].get(sid)
    return {"sender_id": sid, "binding": binding, "found": binding is not None}


def signal_list_bindings(root: Path) -> dict[str, Any]:
    m = _read_map(root)
    allowed = m.get("allowed_sender_ids", [])
    return {
        "schema_version": _MAP_SCHEMA,
        "map_path": str(_map_path(root)),
        "bindings": m.get("bindings", {}),
        "allowed_sender_ids": allowed,
        "allowlist_enabled": bool(allowed),
    }


def signal_allow_add(root: Path, sender_id: str) -> dict[str, Any]:
    m = _read_map(root)
    sid = str(sender_id).strip()
    if sid not in m["allowed_sender_ids"]:
        m["allowed_sender_ids"].append(sid)
        _write_map(root, m)
    return {"ok": True, "sender_id": sid, "allowed_sender_ids": m["allowed_sender_ids"]}


def signal_allow_rm(root: Path, sender_id: str) -> dict[str, Any]:
    m = _read_map(root)
    sid = str(sender_id).strip()
    before = list(m["allowed_sender_ids"])
    m["allowed_sender_ids"] = [x for x in before if x != sid]
    _write_map(root, m)
    return {"ok": True, "sender_id": sid, "removed": sid in before}


def signal_allow_list(root: Path) -> dict[str, Any]:
    m = _read_map(root)
    allowed = m.get("allowed_sender_ids", [])
    return {"allowed_sender_ids": allowed, "allowlist_enabled": bool(allowed)}


def signal_gateway_health(
    root: Path,
    *,
    service_url: str | None = None,
    account: str | None = None,
    phone_number: str | None = None,
) -> dict[str, Any]:
    local = signal_list_bindings(root)
    binds = local.get("bindings") if isinstance(local.get("bindings"), dict) else {}
    allow = local.get("allowed_sender_ids") if isinstance(local.get("allowed_sender_ids"), list) else []
    return {
        "schema_version": _HEALTH_SCHEMA,
        "workspace": str(root.resolve()),
        "map_path": local.get("map_path"),
        "map_schema_version": local.get("schema_version"),
        "bindings_count": len(binds),
        "allowlist_enabled": bool(local.get("allowlist_enabled")),
        "allowed_sender_ids_count": len(allow),
        "service_url_configured": bool(str(service_url or "").strip()),
        "account_configured": bool(str(account or "").strip()),
        "phone_number_configured": bool(str(phone_number or "").strip()),
        "token_check": {
            "performed": False,
            "ok": None,
            "hint": "Signal skeleton does local config checks only; runtime send/receive will be added in HM-N05-D03+.",
        },
    }


__all__ = [
    "signal_bind",
    "signal_unbind",
    "signal_get_binding",
    "signal_list_bindings",
    "signal_allow_add",
    "signal_allow_rm",
    "signal_allow_list",
    "signal_gateway_health",
]
