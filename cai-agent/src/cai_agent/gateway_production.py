"""Read-side multi-platform gateway production summary (HM-03e)."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cai_agent.gateway_discord import discord_gateway_health
from cai_agent.gateway_email import email_gateway_health
from cai_agent.gateway_lifecycle import build_gateway_summary_payload
from cai_agent.gateway_maps import summarize_gateway_maps
from cai_agent.gateway_matrix import matrix_gateway_health
from cai_agent.gateway_platforms import build_gateway_platforms_payload
from cai_agent.gateway_signal import signal_gateway_health
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


def _monitoring_owner(platform: str, binding: dict[str, Any]) -> str | None:
    if not isinstance(binding, dict):
        return None
    for key in ("label", "owner", "tenant_id", "guild_id", "team_id", "user_id", "chat_id", "channel_id"):
        value = binding.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    if platform == "email":
        addr = binding.get("address")
        if addr is not None and str(addr).strip():
            return str(addr).strip()
    return None


def _channel_id_for(platform: str, binding: dict[str, Any]) -> str:
    key_map = {
        "telegram": "binding_key",
        "discord": "channel_id",
        "slack": "channel_id",
        "teams": "conversation_id",
        "signal": "sender_id",
        "email": "address",
        "matrix": "room_id",
    }
    key = key_map.get(platform, "binding_key")
    raw = binding.get(key)
    if raw is not None and str(raw).strip():
        return str(raw).strip()
    fallback = (
        binding.get("chat_id")
        or binding.get("user_id")
        or binding.get("session_file")
        or binding.get("label")
        or "unknown"
    )
    return str(fallback).strip()


def _channel_monitoring(
    platform: str,
    map_doc: dict[str, Any],
    health_doc: dict[str, Any],
) -> dict[str, Any]:
    bindings = map_doc.get("bindings") if isinstance(map_doc.get("bindings"), list) else []
    token_check = health_doc.get("token_check") if isinstance(health_doc.get("token_check"), dict) else {}
    token_err = 1 if token_check.get("performed") and token_check.get("ok") is False else 0
    channels: list[dict[str, Any]] = []
    for row in bindings:
        if not isinstance(row, dict):
            continue
        channels.append(
            {
                "channel_id": _channel_id_for(platform, row),
                "last_seen": row.get("bound_at"),
                "latency_ms": None,
                "error_count": token_err,
                "owner": _monitoring_owner(platform, row),
            },
        )
    return {
        "schema_version": "gateway_channel_monitoring_v1",
        "channels_count": len(channels),
        "channels": channels,
        "summary": {
            "error_count_total": sum(int(c.get("error_count") or 0) for c in channels),
            "has_latency_data": any(c.get("latency_ms") is not None for c in channels),
        },
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
        "signal": signal_gateway_health(
            base,
            service_url=os.environ.get("CAI_SIGNAL_SERVICE_URL"),
            account=os.environ.get("CAI_SIGNAL_ACCOUNT"),
            phone_number=os.environ.get("CAI_SIGNAL_PHONE_NUMBER"),
        ),
        "email": email_gateway_health(
            base,
            smtp_host=os.environ.get("CAI_EMAIL_SMTP_HOST"),
            smtp_port=int(os.environ.get("CAI_EMAIL_SMTP_PORT", "0") or "0") or None,
            smtp_user=os.environ.get("CAI_EMAIL_SMTP_USER"),
            imap_host=os.environ.get("CAI_EMAIL_IMAP_HOST"),
            imap_port=int(os.environ.get("CAI_EMAIL_IMAP_PORT", "0") or "0") or None,
            imap_user=os.environ.get("CAI_EMAIL_IMAP_USER"),
        ),
        "matrix": matrix_gateway_health(
            base,
            homeserver=os.environ.get("CAI_MATRIX_HOMESERVER"),
            access_token=os.environ.get("CAI_MATRIX_ACCESS_TOKEN"),
            user_id=os.environ.get("CAI_MATRIX_USER_ID"),
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
        "signal": _env_present(
            "CAI_SIGNAL_SERVICE_URL",
            "CAI_SIGNAL_ACCOUNT",
            "CAI_SIGNAL_PHONE_NUMBER",
        ),
        "email": _env_present(
            "CAI_EMAIL_SMTP_HOST",
            "CAI_EMAIL_SMTP_PORT",
            "CAI_EMAIL_SMTP_USER",
            "CAI_EMAIL_IMAP_HOST",
            "CAI_EMAIL_IMAP_PORT",
            "CAI_EMAIL_IMAP_USER",
        ),
        "matrix": _env_present(
            "CAI_MATRIX_HOMESERVER",
            "CAI_MATRIX_ACCESS_TOKEN",
            "CAI_MATRIX_USER_ID",
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
                "adapter_contract": meta.get("adapter_contract") if isinstance(meta.get("adapter_contract"), dict) else {},
                "map": m,
                "health": h,
                "env_present": env_present,
                "run_state": rs,
                "channel_monitoring": _channel_monitoring(pid, m, h),
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
        "federation": maps_doc.get("federation") if isinstance(maps_doc.get("federation"), dict) else {},
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


def build_gateway_federation_summary_payload(workspace: str | Path | None = None) -> dict[str, Any]:
    """HM-N07-D04: unified CLI/API federation summary payload."""
    prod = build_gateway_production_summary_payload(workspace=workspace)
    platforms = prod.get("platforms") if isinstance(prod.get("platforms"), list) else []
    rows: list[dict[str, Any]] = []
    for row in platforms:
        if not isinstance(row, dict):
            continue
        mon = row.get("channel_monitoring") if isinstance(row.get("channel_monitoring"), dict) else {}
        rows.append(
            {
                "id": row.get("id"),
                "production_state": row.get("production_state"),
                "bindings_count": int((row.get("health") if isinstance(row.get("health"), dict) else {}).get("bindings_count") or 0),
                "channels_count": int(mon.get("channels_count") or 0),
                "error_count_total": int((mon.get("summary") if isinstance(mon.get("summary"), dict) else {}).get("error_count_total") or 0),
            },
        )
    return {
        "schema_version": "gateway_federation_summary_v1",
        "generated_at": prod.get("generated_at"),
        "workspace": prod.get("workspace"),
        "federation": prod.get("federation") if isinstance(prod.get("federation"), dict) else {},
        "platforms": rows,
        "summary": {
            "platforms_count": len(rows),
            "configured_count": sum(1 for r in rows if r.get("production_state") in ("configured", "running")),
            "running_count": sum(1 for r in rows if r.get("production_state") == "running"),
            "channels_count": sum(int(r.get("channels_count") or 0) for r in rows),
            "error_count_total": sum(int(r.get("error_count_total") or 0) for r in rows),
        },
    }
