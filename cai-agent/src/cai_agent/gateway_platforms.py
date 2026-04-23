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
            "implementation": "stub",
            "cli_prefix": [],
            "env": ["CAI_GATEWAY_DISCORD_BOT_TOKEN", "CAI_GATEWAY_DISCORD_APPLICATION_ID"],
            "notes": "占位：事件网关与 Hermes 矩阵对齐前，仅文档化环境变量与后续 Sprint 接口。",
        },
        {
            "id": "slack",
            "label": "Slack",
            "implementation": "stub",
            "cli_prefix": [],
            "env": ["CAI_GATEWAY_SLACK_BOT_TOKEN", "CAI_GATEWAY_SLACK_APP_TOKEN"],
            "notes": "占位：Socket Mode / Events API 接入仍为后续 Story。",
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
            "implementation": "planned",
            "cli_prefix": [],
            "env": [],
            "notes": "规划中。",
        },
        {
            "id": "email",
            "label": "Email",
            "implementation": "planned",
            "cli_prefix": [],
            "env": [],
            "notes": "规划中。",
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
        platforms.append(d)
    tok_cli = str(os.environ.get("CAI_TELEGRAM_BOT_TOKEN") or "").strip()
    tok_env = str(os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    return {
        "schema_version": "gateway_platforms_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(base),
        "telegram_session_map_path": str(tg_map),
        "telegram_map_exists": tg_map.is_file(),
        "telegram_webhook_pid_path": str(tg_pid),
        "telegram_webhook_pid_exists": tg_pid.is_file(),
        "telegram_bot_token_env_present": bool(tok_cli or tok_env),
        "platforms": platforms,
    }
