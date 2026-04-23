"""OpenClaw / Claw migration stub (Hermes H8-MIG-01)."""

from __future__ import annotations

import sys


def run_claw_migrate(*, dry_run: bool = True) -> int:
    print(
        "[claw-migrate] MVP 占位：尚未实现自动迁移；"
        "请手动对照 OpenClaw 文档导出 skills/commands 到本仓库结构。",
        file=sys.stderr,
    )
    if dry_run:
        return 0
    return 3
