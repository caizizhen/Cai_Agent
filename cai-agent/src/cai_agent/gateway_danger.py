"""Gateway（非 TUI）危险工具确认契约（P4-4）。

聊天网关无法弹出 Textual Modal，因此对 ``execute_on_event`` / ``execute_on_message``
路径约定：用户可在 goal **开头**重复若干行「放行令牌」，语义等价于进程内
``grant_dangerous_approval_once``（与 TUI ``/danger-approve`` 一致）。

令牌可通过环境变量 ``CAI_GATEWAY_DANGER_APPROVE_TOKENS`` 覆盖（逗号分隔整行匹配）。
"""

from __future__ import annotations

import os
from typing import Any, Final

GATEWAY_DANGER_APPROVE_CONTRACT_SCHEMA_VERSION: Final[str] = "danger_gateway_goal_prefix_contract_v1"

_DEFAULT_LINE_TOKENS: Final[tuple[str, ...]] = (
    "[danger-approve]",
    "/danger-approve",
)


def gateway_danger_approve_tokens() -> tuple[str, ...]:
    """返回用于逐行匹配的令牌集合（大小写不敏感比较）。"""
    raw = os.getenv("CAI_GATEWAY_DANGER_APPROVE_TOKENS", "").strip()
    if not raw:
        return _DEFAULT_LINE_TOKENS
    parts = tuple(x.strip() for x in raw.split(",") if x.strip())
    return parts or _DEFAULT_LINE_TOKENS


def strip_gateway_danger_approve_lines(goal: str, *, max_grants: int = 8) -> tuple[str, int]:
    """剥离 goal 开头的放行行；返回 ``(剩余正文, 放行次数)``。

    - 仅匹配**完整一行**（strip 后）；忽略放行之间的空行。
    - ``max_grants`` 防止恶意超长前缀耗尽计数。
    """
    tokens_cf = frozenset(x.casefold() for x in gateway_danger_approve_tokens())
    lines = goal.replace("\r\n", "\n").split("\n")
    grants = 0
    idx = 0
    while idx < len(lines):
        cand = lines[idx].strip()
        if not cand:
            idx += 1
            continue
        if cand.casefold() not in tokens_cf:
            break
        grants += 1
        idx += 1
        if grants >= max_grants:
            break
    remainder = "\n".join(lines[idx:]).strip()
    return remainder, grants


def apply_gateway_danger_grants(settings: Any, count: int, *, audit_via: str = "gateway_goal_prefix") -> None:
    """对剥离得到的次数调用 ``grant_dangerous_approval_once``（写入审计若开启）。"""
    from cai_agent.tools import grant_dangerous_approval_once

    for _ in range(max(0, int(count))):
        grant_dangerous_approval_once(settings=settings, audit_via=audit_via)
