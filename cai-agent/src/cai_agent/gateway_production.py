"""Read-side multi-platform gateway production summary (HM-03e)."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cai_agent.gateway_discord import discord_gateway_health
from cai_agent.gateway_lifecycle import build_gateway_summary_payload
from cai_agent.gateway_maps import summarize_gateway_maps
from cai_agent.gateway_platforms import build_gateway_platforms_payload
from cai_agent.gateway_slack import slack_gateway_health
from cai_agent.gateway_teams import teams_gateway_health


def _env_present(*names: str) -> dict[str, bool]:
    return {name: bool(str(os.environ.get(name) or "").strip()) for name in names}


def _map_summary_for(workspace_row: dict[str, Any], platform: str) -> dict[str, Any]:
    value = workspace_row.get(platform)
    return value if isinstance(value, dict) else {}


def _run_state(platform: str, telegram_summary: dict[str, Any]) -> dict[str, Any]:
    if platform == "telegram":
        return {
            "mode": "managed_pid",
            "configured": bool(telegram_summary.get("config_exists")),
            "running": bool(telegram_summary.get("webhook_running")),
            "pid": telegram_summary.get("webhook_pid"),
            "status": telegram_summary.get("status"),
        }
    return {
        "mode": "external_process",
        "configured": False,
        "running": None,
        "pid": None,
        "status": "external_or_not_configured",
    }


def build_gateway_production_summary_payload(workspace: str | Path | None = None) -> dict[str, Any]:
    """Return ``gateway_production_summary_v1`` without contacting vendor APIs."""
    base = Path(workspace or ".").expanduser().resolve()
    platforms_doc = build_gateway_platforms_payload(workspace=base)
    maps_doc = summarize_gateway_maps([base])
    workspace_rows = maps_doc.get("workspaces") if isinstance(maps_doc.get("workspaces"), list) else []
    workspace_row = workspace_rows[0] if workspace_rows and isinstance(workspace_rows[0], dict) else {}
    telegram_summary = build_gateway_summary_payload(base)

    health_by_platform: dict[str, dict[str, Any]] = {
        "telegram": telegram_summary,
        "discord": discord_gateway_health(base),
        "slack": slack_gateway_health(base),
        "teams": teams_gateway_health(
            base,
            app_id=os.environ.get("CAI_TEAMS_APP_ID"),
            app_password=os.environ.get("CAI_TEAMS_APP_PASSWORD"),
            tenant_id=os.environ.get("CAI_TEAMS_TENANT_ID"),
            webhook_secret=os.environ.get("CAI_TEAMS_WEBHOOK_SECRET"),
        ),
    }
    env_by_platform: dict[str, dict[str, bool]] = {
        "telegram": _env_present("CAI_TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN"),
        "discord": _env_present("CAI_GATEWAY_DISCORD_BOT_TOKEN", "CAI_DISCORD_BOT_TOKEN"),
        "slack": _env_present("CAI_SLACK_BOT_TOKEN", "CAI_SLACK_SIGNING_SECRET"),
        "teams": _env_present(
            "CAI_TEAMS_APP_ID",
            "CAI_TEAMS_APP_PASSWORD",
            "CAI_TEAMS_TENANT_ID",
            "CAI_TEAMS_WEBHOOK_SECRET",
        ),
    }

    rows: list[dict[str, Any]] = []
    for meta in platforms_doc.get("platforms") or []:
        if not isinstance(meta, dict):
            continue
        pid = str(meta.get("id") or "").strip()
        if pid not in health_by_platform:
            continue
        m = _map_summary_for(workspace_row, pid)
        h = health_by_platform[pid]
        bindings_count = int(h.get("bindings_count") or m.get("bindings_count") or 0)
        allowlist_enabled = bool(h.get("allowlist_enabled") or m.get("allowlist_enabled"))
        env_present = env_by_platform.get(pid, {})
        configured = bool(bindings_count or allowlist_enabled or any(env_present.values()))
        rs = _run_state(pid, telegram_summary)
        if pid == "telegram":
            configured = configured or bool(rs.get("configured"))
        rows.append(
            {
                "id": pid,
                "label": meta.get("label"),
                "implementation": meta.get("implementation"),
                "cli_prefix": meta.get("cli_prefix") or [],
                "map": m,
                "health": h,
                "env_present": env_present,
                "run_state": rs,
                "production_state": (
                    "running"
                    if rs.get("running") is True
                    else "configured"
                    if configured
                    else "not_configured"
                ),
            },
        )

    return {
        "schema_version": "gateway_production_summary_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(base),
        "platforms": rows,
        "summary": {
            "platforms_count": len(rows),
            "configured_count": sum(1 for r in rows if r.get("production_state") in ("configured", "running")),
            "running_count": sum(1 for r in rows if r.get("production_state") == "running"),
            "bindings_count": sum(
                int((r.get("health") if isinstance(r.get("health"), dict) else {}).get("bindings_count") or 0)
                for r in rows
            ),
        },
    }
