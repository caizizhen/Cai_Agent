from __future__ import annotations

import os

from cai_agent.config import Settings
from cai_agent.sandbox import SandboxError


def _auto_approved() -> bool:
    v = os.getenv("CAI_AUTO_APPROVE", "")
    return v.lower() in ("1", "true", "yes", "on")


def enforce_tool_permission(settings: Settings, tool_name: str) -> None:
    """在 dispatch 前校验 write_file / run_command 策略。"""
    if tool_name == "write_file":
        mode = settings.permission_write_file
    elif tool_name == "run_command":
        mode = settings.permission_run_command
    elif tool_name == "fetch_url":
        mode = settings.permission_fetch_url
    else:
        return
    if mode == "allow":
        return
    if mode == "deny":
        msg = (
            f"工具 {tool_name} 已被配置为 deny（[permissions]）。"
            "若确需执行，请改为 allow/ask 或调整策略。"
        )
        raise SandboxError(msg)
    if mode == "ask":
        if _auto_approved():
            return
        msg = (
            f"工具 {tool_name} 需要确认（permissions=ask）。"
            "非交互模式下请设置环境变量 CAI_AUTO_APPROVE=1，"
            "或使用 CLI --auto-approve。"
        )
        raise SandboxError(msg)
