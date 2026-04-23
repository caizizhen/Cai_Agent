"""工作区用户建模占位（Honcho 级能力的增量入口，非完整用户画像引擎）。"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cai_agent.config import Settings
from cai_agent.session import list_session_files

USER_MODEL_OVERLAY_REL = ".cai/user-model.json"


def build_memory_user_model_overview(
    settings: Settings,
    *,
    days: int = 14,
) -> dict[str, Any]:
    """聚合会话文件 mtime 与可选 ``.cai/user-model.json`` 覆盖层，输出 ``memory_user_model_v1``。"""
    root = Path(settings.workspace).expanduser().resolve()
    window_sec = max(1, int(days)) * 86400
    cutoff = time.time() - window_sec
    pattern = ".cai-session*.json"
    paths = list_session_files(cwd=str(root), pattern=pattern, limit=2000)
    total = len(paths)
    recent = 0
    for p in paths:
        try:
            if p.stat().st_mtime >= cutoff:
                recent += 1
        except OSError:
            continue
    overlay_path = root / USER_MODEL_OVERLAY_REL
    user_declared: dict[str, Any] | None = None
    overlay_err: str | None = None
    if overlay_path.is_file():
        try:
            raw = json.loads(overlay_path.read_text(encoding="utf-8"))
            user_declared = raw if isinstance(raw, dict) else None
            if user_declared is None:
                overlay_err = "overlay_not_object"
        except json.JSONDecodeError:
            overlay_err = "overlay_invalid_json"
        except OSError as e:
            overlay_err = f"overlay_read_error:{e.__class__.__name__}"
    return {
        "schema_version": "memory_user_model_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(root),
        "honcho_parity": "stub",
        "notes_zh": (
            "本负载为 Hermes/Honcho 级用户建模的占位入口："
            "仅统计会话文件时间分布并合并可选 `.cai/user-model.json`；"
            "不含跨会话行为图谱或在线学习。"
        ),
        "sessions_total": total,
        "sessions_recent_in_window": recent,
        "window_days": int(days),
        "overlay_path": str(overlay_path),
        "overlay_present": overlay_path.is_file(),
        "user_declared": user_declared,
        "overlay_error": overlay_err,
        "active_profile_id": getattr(settings, "active_profile_id", None),
        "model": getattr(settings, "model", None),
    }
