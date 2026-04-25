"""多平台 Gateway 目录（与 `gateway telegram` 生产路径并列的元数据出口）。"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cai_agent.gateway_lifecycle import pid_path


def _env_presence(keys: list[str]) -> dict[str, bool]:
    out: dict[str, bool] = {}
    for k in keys:
        out[str(k)] = bool(str(os.environ.get(str(k)) or "").strip())
    return out


def _adapter_contract_for(platform_id: str, implementation: str) -> dict[str, Any]:
    impl = str(implementation or "").strip().lower()
    pid = str(platform_id or "").strip().lower()
    if impl not in ("full", "mvp"):
        return {
            "schema_version": "gateway_platform_adapter_contract_v1",
            "send": {"supported": False, "surface": []},
            "receive": {"supported": False, "surface": []},
            "health": {"supported": False, "surface": []},
            "map": {"supported": False, "surface": []},
            "lifecycle": {"supported": False, "surface": []},
        }
    mapping: dict[str, dict[str, list[str]]] = {
        "telegram": {
            "send": ["gateway telegram serve-webhook --reply-on-execution"],
            "receive": ["gateway telegram serve-webhook", "gateway telegram resolve-update"],
            "health": ["gateway status --json", "gateway prod-status --json"],
            "map": ["gateway telegram bind|get|list|unbind", "gateway telegram allow add|list|rm"],
            "lifecycle": ["gateway start", "gateway stop", "gateway status"],
        },
        "discord": {
            "send": ["gateway discord serve-polling --execute-on-message"],
            "receive": ["gateway discord serve-polling"],
            "health": ["gateway discord health --json", "gateway prod-status --json"],
            "map": ["gateway discord bind|get|list|unbind", "gateway discord allow add|list|rm"],
            "lifecycle": ["gateway discord serve-polling"],
        },
        "slack": {
            "send": ["gateway slack serve-webhook --execute-on-message|--execute-on-slash"],
            "receive": ["gateway slack serve-webhook"],
            "health": ["gateway slack health --json", "gateway prod-status --json"],
            "map": ["gateway slack bind|get|list|unbind", "gateway slack allow add|list|rm"],
            "lifecycle": ["gateway slack serve-webhook"],
        },
        "teams": {
            "send": ["gateway teams serve-webhook --execute-on-message"],
            "receive": ["gateway teams serve-webhook"],
            "health": ["gateway teams health --json", "gateway prod-status --json"],
            "map": ["gateway teams bind|get|list|unbind", "gateway teams allow add|list|rm"],
            "lifecycle": ["gateway teams serve-webhook"],
        },
        "signal": {
            "send": [],
            "receive": [],
            "health": ["gateway signal health --json", "gateway platforms list --json"],
            "map": ["gateway signal bind|get|list|unbind", "gateway signal allow add|list|rm"],
            "lifecycle": [],
        },
        "email": {
            "send": ["gateway email send --json"],
            "receive": ["gateway email receive --json"],
            "health": ["gateway email health --json", "gateway platforms list --json"],
            "map": ["gateway email bind|get|list|unbind", "gateway email allow add|list|rm"],
            "lifecycle": [],
        },
        "matrix": {
            "send": ["gateway matrix send --json"],
            "receive": ["gateway matrix receive --json"],
            "health": ["gateway matrix health --json", "gateway platforms list --json"],
            "map": ["gateway matrix bind|get|list|unbind", "gateway matrix allow add|list|rm"],
            "lifecycle": [],
        },
    }
    use = mapping.get(pid, {})
    out: dict[str, Any] = {"schema_version": "gateway_platform_adapter_contract_v1"}
    for sec in ("send", "receive", "health", "map", "lifecycle"):
        surf = list(use.get(sec) or [])
        out[sec] = {"supported": bool(surf), "surface": surf}
    return out


def build_gateway_platforms_payload(*, workspace: str | Path | None = None) -> dict[str, Any]:
    """返回 ``gateway_platforms_v1``：Telegram 已实现；其它平台为 stub/规划位。"""
    base = Path(workspace or ".").expanduser().resolve()
    tg_map = base / ".cai" / "gateway" / "telegram-session-map.json"
    tg_pid = pid_path(base)
    raw_rows: list[dict[str, Any]] = [
        {
            "id": "telegram",
            "label": "Telegram",
            "implementation": "full",
            "cli_prefix": ["gateway", "telegram"],
            "notes": "Webhook MVP：`serve-webhook`、会话映射 `list|bind|get|unbind|resolve-update`。",
        },
        {
            "id": "discord",
            "label": "Discord",
            "implementation": "mvp",
            "cli_prefix": ["gateway", "discord"],
            "env": ["CAI_GATEWAY_DISCORD_BOT_TOKEN", "CAI_DISCORD_BOT_TOKEN"],
            "notes": "MVP（§24）：Bot Polling 接入，`serve-polling`、会话映射 `bind|get|list|unbind`、白名单 `allow`。",
        },
        {
            "id": "slack",
            "label": "Slack",
            "implementation": "mvp",
            "cli_prefix": ["gateway", "slack"],
            "env": ["CAI_SLACK_BOT_TOKEN", "CAI_SLACK_SIGNING_SECRET"],
            "notes": "MVP（§24）：Events API Webhook 接入，`serve-webhook`、会话映射 `bind|get|list|unbind`、白名单 `allow`。",
        },
        {
            "id": "teams",
            "label": "Microsoft Teams",
            "implementation": "mvp",
            "cli_prefix": ["gateway", "teams"],
            "env": [
                "CAI_TEAMS_APP_ID",
                "CAI_TEAMS_APP_PASSWORD",
                "CAI_TEAMS_TENANT_ID",
                "CAI_TEAMS_WEBHOOK_SECRET",
            ],
            "notes": "MVP（HM-03d）：Bot Framework Activity Webhook 接入、manifest 模板、会话映射 `bind|get|list|unbind`、白名单 `allow`。",
        },
        {
            "id": "whatsapp",
            "label": "WhatsApp",
            "implementation": "planned",
            "cli_prefix": [],
            "env": [],
            "notes": "规划中。",
        },
        {
            "id": "signal",
            "label": "Signal",
            "implementation": "mvp",
            "cli_prefix": ["gateway", "signal"],
            "env": [
                "CAI_SIGNAL_SERVICE_URL",
                "CAI_SIGNAL_ACCOUNT",
                "CAI_SIGNAL_PHONE_NUMBER",
            ],
            "notes": "Skeleton（HM-N05-D02）：本地 map/allow/health 契约已接入，send/receive 后续补齐。",
        },
        {
            "id": "email",
            "label": "Email",
            "implementation": "mvp",
            "cli_prefix": ["gateway", "email"],
            "env": [
                "CAI_EMAIL_SMTP_HOST",
                "CAI_EMAIL_SMTP_PORT",
                "CAI_EMAIL_SMTP_USER",
                "CAI_EMAIL_IMAP_HOST",
                "CAI_EMAIL_IMAP_PORT",
                "CAI_EMAIL_IMAP_USER",
            ],
            "notes": "MVP（HM-N05-D03）：SMTP/IMAP 配置面 + 本地 send/receive 最小链路（spool）。",
        },
        {
            "id": "matrix",
            "label": "Matrix",
            "implementation": "mvp",
            "cli_prefix": ["gateway", "matrix"],
            "env": [
                "CAI_MATRIX_HOMESERVER",
                "CAI_MATRIX_ACCESS_TOKEN",
                "CAI_MATRIX_USER_ID",
            ],
            "notes": "MVP（HM-N05-D04）：room map + send/receive + health 最小链路。",
        },
    ]
    platforms: list[dict[str, Any]] = []
    for row in raw_rows:
        d = dict(row)
        env_keys = d.get("env")
        if isinstance(env_keys, list) and env_keys:
            d["env_present"] = _env_presence([str(x) for x in env_keys])
        else:
            d["env_present"] = {}
        d["adapter_contract"] = _adapter_contract_for(
            str(d.get("id") or ""),
            str(d.get("implementation") or ""),
        )
        platforms.append(d)
    tok_cli = str(os.environ.get("CAI_TELEGRAM_BOT_TOKEN") or "").strip()
    tok_env = str(os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    return {
        "schema_version": "gateway_platforms_v1",
        "adapter_contract_schema_version": "gateway_platform_adapter_contract_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(base),
        "telegram_session_map_path": str(tg_map),
        "telegram_map_exists": tg_map.is_file(),
        "telegram_webhook_pid_path": str(tg_pid),
        "telegram_webhook_pid_exists": tg_pid.is_file(),
        "telegram_bot_token_env_present": bool(tok_cli or tok_env),
        "platforms": platforms,
    }
