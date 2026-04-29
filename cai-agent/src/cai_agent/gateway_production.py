"""Read-side multi-platform gateway production summary (HM-03e)."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cai_agent.gateway_discord import discord_gateway_health
from cai_agent.gateway_discord import discord_default_slash_command_specs
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


def _check(
    *,
    check_id: str,
    label: str,
    ok: bool,
    severity: str,
    message: str,
    next_step: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": check_id,
        "label": label,
        "ok": ok,
        "severity": severity,
        "message": message,
    }
    if next_step:
        row["next_step"] = next_step
    return row


def _readiness_state(checks: list[dict[str, Any]]) -> str:
    if any((not c.get("ok")) and c.get("severity") == "blocker" for c in checks):
        return "blocked"
    if any(not c.get("ok") for c in checks):
        return "warn"
    return "ready"


def _diagnostics_from_checks(platform: str, checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for check in checks:
        if check.get("ok"):
            continue
        diagnostics.append(
            {
                "schema_version": "gateway_platform_diagnostic_v1",
                "platform": platform,
                "check_id": check.get("id"),
                "severity": check.get("severity"),
                "message": check.get("message"),
                "next_step": check.get("next_step"),
            },
        )
    return diagnostics


def _platform_readiness(
    platform: str,
    *,
    env_present: dict[str, bool],
    bindings_count: int,
    allowlist_enabled: bool,
    health_doc: dict[str, Any],
    run_state: dict[str, Any],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    route_ready = bool(bindings_count or allowlist_enabled)
    route_label = "binding_or_allowlist"
    route_message = "At least one bound channel or allowlist entry is configured."
    route_next_step = f"cai-agent gateway {platform} bind <channel_id> <session_file> --json"
    if platform == "teams":
        route_next_step = "cai-agent gateway teams bind <conversation_id> <session_file> --json"
    if platform == "telegram":
        route_next_step = "cai-agent gateway setup --allow-chat-id <chat_id> --json"
    checks.append(
        _check(
            check_id=route_label,
            label="Route map",
            ok=route_ready,
            severity="blocker",
            message=route_message if route_ready else "No routable channel is configured yet.",
            next_step=None if route_ready else route_next_step,
        ),
    )

    token_check = health_doc.get("token_check") if isinstance(health_doc.get("token_check"), dict) else {}
    if platform == "discord":
        has_token = bool(env_present.get("CAI_GATEWAY_DISCORD_BOT_TOKEN") or env_present.get("CAI_DISCORD_BOT_TOKEN"))
        token_ok = has_token and token_check.get("ok") is not False
        checks.append(
            _check(
                check_id="discord_bot_token",
                label="Discord bot token",
                ok=token_ok,
                severity="blocker",
                message="Discord bot token is configured." if token_ok else "Discord bot token is missing or failed validation.",
                next_step=None
                if token_ok
                else "set CAI_DISCORD_BOT_TOKEN, then run: cai-agent gateway discord health --json",
            ),
        )
    elif platform == "slack":
        has_token = bool(env_present.get("CAI_SLACK_BOT_TOKEN"))
        has_secret = bool(env_present.get("CAI_SLACK_SIGNING_SECRET")) or bool(health_doc.get("signing_secret_configured"))
        checks.append(
            _check(
                check_id="slack_bot_token",
                label="Slack bot token",
                ok=has_token and token_check.get("ok") is not False,
                severity="blocker",
                message="Slack bot token is configured."
                if has_token
                else "Slack bot token is required before serving events.",
                next_step=None if has_token else "set CAI_SLACK_BOT_TOKEN, then run: cai-agent gateway slack health --json",
            ),
        )
        checks.append(
            _check(
                check_id="slack_signing_secret",
                label="Slack signing secret",
                ok=has_secret,
                severity="blocker",
                message="Slack signing secret is configured."
                if has_secret
                else "Slack signing secret is required to verify Events API requests.",
                next_step=None
                if has_secret
                else "set CAI_SLACK_SIGNING_SECRET, then run: cai-agent gateway slack health --json",
            ),
        )
    elif platform == "teams":
        for env_name, field_name, label in (
            ("CAI_TEAMS_APP_ID", "app_id_configured", "Teams app id"),
            ("CAI_TEAMS_APP_PASSWORD", "app_password_configured", "Teams app password"),
            ("CAI_TEAMS_TENANT_ID", "tenant_id_configured", "Teams tenant id"),
            ("CAI_TEAMS_WEBHOOK_SECRET", "webhook_secret_configured", "Teams webhook secret"),
        ):
            ok = bool(env_present.get(env_name)) or bool(health_doc.get(field_name))
            checks.append(
                _check(
                    check_id=env_name.lower(),
                    label=label,
                    ok=ok,
                    severity="blocker" if env_name != "CAI_TEAMS_TENANT_ID" else "warning",
                    message=f"{label} is configured." if ok else f"{label} is not configured.",
                    next_step=None
                    if ok
                    else "cai-agent gateway teams manifest --app-id <APP_ID> --valid-domain <DOMAIN> --json",
                ),
            )
    elif platform == "telegram":
        configured = bool(run_state.get("configured"))
        checks.append(
            _check(
                check_id="telegram_lifecycle_config",
                label="Telegram lifecycle config",
                ok=configured,
                severity="warning",
                message="Telegram lifecycle config exists." if configured else "Telegram lifecycle config is missing.",
                next_step=None if configured else "cai-agent gateway setup --json",
            ),
        )

    state = _readiness_state(checks)
    diagnostics = _diagnostics_from_checks(platform, checks)
    return {
        "schema_version": "gateway_platform_readiness_v1",
        "ready": state == "ready",
        "state": state,
        "checks_total": len(checks),
        "checks_passed": sum(1 for c in checks if c.get("ok")),
        "blocking_count": sum(1 for c in checks if (not c.get("ok")) and c.get("severity") == "blocker"),
        "checks": checks,
        "diagnostics": diagnostics,
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
        readiness = _platform_readiness(
            pid,
            env_present=env_present,
            bindings_count=bindings_count,
            allowlist_enabled=allowlist_enabled,
            health_doc=h,
            run_state=rs,
        )
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
                "readiness": readiness,
                "readiness_checklist": readiness.get("checks") or [],
                "diagnostics": readiness.get("diagnostics") or [],
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
            "ready_count": sum(
                1
                for r in rows
                if (r.get("readiness") if isinstance(r.get("readiness"), dict) else {}).get("state") == "ready"
            ),
            "warn_count": sum(
                1
                for r in rows
                if (r.get("readiness") if isinstance(r.get("readiness"), dict) else {}).get("state") == "warn"
            ),
            "blocked_count": sum(
                1
                for r in rows
                if (r.get("readiness") if isinstance(r.get("readiness"), dict) else {}).get("state") == "blocked"
            ),
            "diagnostics_count": sum(
                len(r.get("diagnostics") if isinstance(r.get("diagnostics"), list) else []) for r in rows
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


def build_gateway_channel_monitor_payload(
    workspace: str | Path | None = None,
    *,
    platform: str | None = None,
    only_errors: bool = False,
) -> dict[str, Any]:
    """Return a compact, script-friendly channel monitoring view."""
    platform_filter = str(platform or "").strip().lower()
    prod = build_gateway_production_summary_payload(workspace=workspace)
    rows: list[dict[str, Any]] = []
    channels_total = 0
    error_count_total = 0
    for row in prod.get("platforms") or []:
        if not isinstance(row, dict):
            continue
        pid = str(row.get("id") or "").strip()
        if platform_filter and pid != platform_filter:
            continue
        monitoring = row.get("channel_monitoring") if isinstance(row.get("channel_monitoring"), dict) else {}
        channels = monitoring.get("channels") if isinstance(monitoring.get("channels"), list) else []
        filtered_channels: list[dict[str, Any]] = []
        for ch in channels:
            if not isinstance(ch, dict):
                continue
            error_count = int(ch.get("error_count") or 0)
            if only_errors and error_count <= 0:
                continue
            filtered_channels.append(dict(ch))
            error_count_total += error_count
        channels_total += len(filtered_channels)
        summary = monitoring.get("summary") if isinstance(monitoring.get("summary"), dict) else {}
        rows.append(
            {
                "id": pid,
                "production_state": row.get("production_state"),
                "channels_count": len(filtered_channels),
                "error_count_total": sum(int(ch.get("error_count") or 0) for ch in filtered_channels),
                "has_latency_data": bool(summary.get("has_latency_data")),
                "channels": filtered_channels,
            },
        )
    return {
        "schema_version": "gateway_channel_monitor_v1",
        "generated_at": prod.get("generated_at"),
        "workspace": prod.get("workspace"),
        "platform_filter": platform_filter or None,
        "only_errors": bool(only_errors),
        "platforms_count": len(rows),
        "channels_count": channels_total,
        "error_count_total": error_count_total,
        "platforms": rows,
    }


def build_gateway_slash_catalog_payload(workspace: str | Path | None = None) -> dict[str, Any]:
    """Return offline slash-command / command-list capabilities by platform."""
    base = Path(workspace or ".").expanduser().resolve()
    discord_commands = [
        {
            "name": str(c.get("name") or ""),
            "description": str(c.get("description") or ""),
            "kind": "application_command",
            "execute_capable": False,
        }
        for c in discord_default_slash_command_specs()
        if isinstance(c, dict)
    ]
    platforms = [
        {
            "id": "discord",
            "platform": "discord",
            "surface": "application_commands",
            "registration": "gateway discord commands register",
            "commands": discord_commands,
        },
        {
            "id": "slack",
            "platform": "slack",
            "surface": "slash_command",
            "registration": "Slack App slash command /cai",
            "commands": [
                {"name": "/cai help", "description": "Show CAI Slack help", "kind": "slash_subcommand", "execute_capable": False},
                {"name": "/cai ping", "description": "Check gateway reachability", "kind": "slash_subcommand", "execute_capable": False},
                {"name": "/cai <goal>", "description": "Execute a goal when --execute-on-slash is enabled", "kind": "slash_goal", "execute_capable": True},
            ],
        },
        {
            "id": "teams",
            "platform": "teams",
            "surface": "bot_command_list",
            "registration": "gateway teams manifest",
            "commands": [
                {"name": "help", "description": "Show CAI Agent help", "kind": "message_command", "execute_capable": False},
                {"name": "ping", "description": "Check gateway reachability", "kind": "message_command", "execute_capable": False},
                {"name": "status", "description": "Show local gateway status", "kind": "message_command", "execute_capable": False},
                {"name": "new", "description": "Start or bind a new session", "kind": "message_command", "execute_capable": False},
            ],
        },
    ]
    commands_count = sum(len(p.get("commands") or []) for p in platforms)
    return {
        "schema_version": "gateway_slash_catalog_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(base),
        "platforms_count": len(platforms),
        "commands_count": commands_count,
        "platforms": platforms,
        "summary": {
            "execute_capable_count": sum(
                1
                for p in platforms
                for c in (p.get("commands") if isinstance(p.get("commands"), list) else [])
                if isinstance(c, dict) and bool(c.get("execute_capable"))
            ),
        },
    }
