"""多工作区网关映射汇总（B3）：统一读取 Telegram / Discord / Slack / Teams 的 ``.cai/gateway`` JSON。

机读契约：:data:`SUMMARIZE_SCHEMA`。
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SUMMARIZE_SCHEMA = "gateway_maps_summarize_v1"


def parse_workspace_roots(
    *,
    append_roots: list[str] | None,
    workspaces_file: str | None,
    single_workspace: str | None,
    fallback_workspace: Path,
) -> list[Path]:
    """解析 ``--root`` / ``--workspaces-file`` / ``-w``，去重并保持顺序。"""
    raw: list[str] = []
    if append_roots:
        raw.extend(str(x).strip() for x in append_roots if str(x).strip())
    if workspaces_file:
        wf = Path(workspaces_file).expanduser()
        if wf.is_file():
            for line in wf.read_text(encoding="utf-8").splitlines():
                s = line.split("#", 1)[0].strip()
                if s:
                    raw.append(s)
    if not raw and single_workspace and str(single_workspace).strip():
        return [Path(str(single_workspace).strip()).expanduser().resolve()]
    if not raw:
        return [fallback_workspace.resolve()]
    out: list[Path] = []
    seen: set[str] = set()
    for item in raw:
        p = Path(item).expanduser().resolve()
        k = str(p)
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


def _read_map_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        o = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return o if isinstance(o, dict) else {}


def _telegram_map_path(root: Path) -> Path:
    return (root / ".cai" / "gateway" / "telegram-session-map.json").resolve()


def _summarize_telegram(root: Path) -> dict[str, Any]:
    p = _telegram_map_path(root)
    doc = _read_map_json(p)
    bindings = doc.get("bindings") if isinstance(doc.get("bindings"), dict) else {}
    rows: list[dict[str, Any]] = []
    for k, v in sorted(bindings.items(), key=lambda x: x[0]):
        if not isinstance(v, dict):
            continue
        rows.append(
            {
                "binding_key": k,
                "chat_id": v.get("chat_id"),
                "user_id": v.get("user_id"),
                "session_file": v.get("session_file"),
                "label": v.get("label"),
            },
        )
    allow = doc.get("allowed_chat_ids") if isinstance(doc.get("allowed_chat_ids"), list) else []
    return {
        "map_path": str(p),
        "map_exists": p.is_file(),
        "schema_version": str(doc.get("schema_version") or "gateway_telegram_map_v1"),
        "bindings_count": len(rows),
        "bindings": rows,
        "allowed_chat_ids": [str(x) for x in allow if str(x).strip()],
        "allowlist_enabled": bool(allow),
    }


def _summarize_discord(root: Path) -> dict[str, Any]:
    from cai_agent.gateway_discord import discord_list_bindings

    r = discord_list_bindings(root)
    binds = r.get("bindings") if isinstance(r.get("bindings"), dict) else {}
    rows: list[dict[str, Any]] = []
    for cid, v in sorted(binds.items(), key=lambda x: x[0]):
        if not isinstance(v, dict):
            continue
        rows.append(
            {
                "channel_id": cid,
                "session_file": v.get("session_file"),
                "bound_at": v.get("bound_at"),
                "guild_id": v.get("guild_id"),
                "label": v.get("label"),
            },
        )
    al = r.get("allowed_channel_ids") if isinstance(r.get("allowed_channel_ids"), list) else []
    return {
        "map_path": r.get("map_path"),
        "schema_version": r.get("schema_version"),
        "bindings_count": len(rows),
        "bindings": rows,
        "allowed_channel_ids": [str(x) for x in al if str(x).strip()],
        "allowlist_enabled": bool(r.get("allowlist_enabled")),
    }


def _summarize_slack(root: Path) -> dict[str, Any]:
    from cai_agent.gateway_slack import slack_list_bindings

    r = slack_list_bindings(root)
    binds = r.get("bindings") if isinstance(r.get("bindings"), dict) else {}
    rows: list[dict[str, Any]] = []
    for cid, v in sorted(binds.items(), key=lambda x: x[0]):
        if not isinstance(v, dict):
            continue
        rows.append(
            {
                "channel_id": cid,
                "session_file": v.get("session_file"),
                "bound_at": v.get("bound_at"),
                "team_id": v.get("team_id"),
                "label": v.get("label"),
            },
        )
    al = r.get("allowed_channel_ids") if isinstance(r.get("allowed_channel_ids"), list) else []
    return {
        "map_path": r.get("map_path"),
        "schema_version": r.get("schema_version"),
        "bindings_count": len(rows),
        "bindings": rows,
        "allowed_channel_ids": [str(x) for x in al if str(x).strip()],
        "allowlist_enabled": bool(r.get("allowlist_enabled")),
    }


def _summarize_teams(root: Path) -> dict[str, Any]:
    from cai_agent.gateway_teams import teams_list_bindings

    r = teams_list_bindings(root)
    binds = r.get("bindings") if isinstance(r.get("bindings"), dict) else {}
    rows: list[dict[str, Any]] = []
    for cid, v in sorted(binds.items(), key=lambda x: x[0]):
        if not isinstance(v, dict):
            continue
        rows.append(
            {
                "conversation_id": cid,
                "session_file": v.get("session_file"),
                "bound_at": v.get("bound_at"),
                "tenant_id": v.get("tenant_id"),
                "service_url": v.get("service_url"),
                "channel_id": v.get("channel_id"),
                "label": v.get("label"),
            },
        )
    al = r.get("allowed_conversation_ids") if isinstance(r.get("allowed_conversation_ids"), list) else []
    return {
        "map_path": r.get("map_path"),
        "schema_version": r.get("schema_version"),
        "bindings_count": len(rows),
        "bindings": rows,
        "allowed_conversation_ids": [str(x) for x in al if str(x).strip()],
        "allowlist_enabled": bool(r.get("allowlist_enabled")),
    }


def summarize_gateway_maps(roots: list[Path]) -> dict[str, Any]:
    workspaces: list[dict[str, Any]] = []
    for root in roots:
        workspaces.append(
            {
                "workspace": str(root),
                "telegram": _summarize_telegram(root),
                "discord": _summarize_discord(root),
                "slack": _summarize_slack(root),
                "teams": _summarize_teams(root),
            },
        )
    return {
        "schema_version": SUMMARIZE_SCHEMA,
        "generated_at": datetime.now(UTC).isoformat(),
        "workspaces": workspaces,
    }
