"""工作区用户建模（Honcho 级能力增量入口）。

从近期会话文件中提取工具频率、错误率与 goal 摘要，升级
原先的 stub 版本为有意义的行为偏好输出。
"""

from __future__ import annotations

import json
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cai_agent.config import Settings
from cai_agent.session import list_session_files, load_session

USER_MODEL_OVERLAY_REL = ".cai/user-model.json"


def _extract_tool_and_error_stats(
    sessions: list[dict[str, Any]],
) -> tuple[dict[str, int], int, int]:
    """从会话列表中统计工具调用频率与错误计数。"""
    tool_counts: Counter[str] = Counter()
    total_tool_calls = 0
    total_errors = 0
    for sess in sessions:
        msgs = sess.get("messages")
        if not isinstance(msgs, list):
            continue
        for msg in msgs:
            if not isinstance(msg, dict) or msg.get("role") != "user":
                continue
            content = msg.get("content")
            if not isinstance(content, str):
                continue
            try:
                obj = json.loads(content)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            tn = obj.get("tool")
            if not isinstance(tn, str) or not tn.strip():
                continue
            name = tn.strip()
            tool_counts[name] += 1
            total_tool_calls += 1
            result = obj.get("result")
            if isinstance(result, str):
                r = result.lower()
                if "失败" in result or "error" in r or "exception" in r or "traceback" in r:
                    total_errors += 1
    return dict(tool_counts), total_tool_calls, total_errors


def _recent_goal_previews(sessions: list[dict[str, Any]], limit: int = 5) -> list[str]:
    """提取最近会话的 goal 字段（截断到 120 字符）。"""
    out: list[str] = []
    for sess in sessions:
        g = str(sess.get("goal") or "").strip()
        if g:
            out.append(g[:120])
        if len(out) >= limit:
            break
    return out


def build_memory_user_model_overview(
    settings: Settings,
    *,
    days: int = 14,
) -> dict[str, Any]:
    """聚合会话行为偏好并合并可选 ``.cai/user-model.json`` 覆盖层，输出 ``memory_user_model_v1``。"""
    root = Path(settings.workspace).expanduser().resolve()
    window_sec = max(1, int(days)) * 86400
    cutoff = time.time() - window_sec
    pattern = ".cai-session*.json"
    paths = list_session_files(cwd=str(root), pattern=pattern, limit=2000)
    total = len(paths)
    recent_paths = [p for p in paths if p.stat().st_mtime >= cutoff]

    recent_sessions: list[dict[str, Any]] = []
    parse_errors = 0
    for p in recent_paths[:100]:
        try:
            recent_sessions.append(load_session(str(p)))
        except Exception:
            parse_errors += 1

    tool_freq, total_calls, total_errors = _extract_tool_and_error_stats(recent_sessions)
    top_tools = sorted(tool_freq.items(), key=lambda x: -x[1])[:8]
    error_rate = (float(total_errors) / total_calls) if total_calls else 0.0
    goal_previews = _recent_goal_previews(recent_sessions)

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

    behavior: dict[str, Any] = {
        "top_tools": [{"tool": t, "count": c} for t, c in top_tools],
        "tool_calls_total": total_calls,
        "tool_error_rate": round(error_rate, 4),
        "recent_goal_previews": goal_previews,
        "sessions_parsed": len(recent_sessions),
        "parse_errors": parse_errors,
    }

    return {
        "schema_version": "memory_user_model_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(root),
        "honcho_parity": "behavior_extract",
        "notes_zh": (
            "本轮已从近期会话提取工具频率、错误率与 goal 摘要；"
            "尚不含跨会话行为图谱或在线学习（Honcho 完整能力）。"
        ),
        "sessions_total": total,
        "sessions_recent_in_window": len(recent_paths),
        "window_days": int(days),
        "overlay_path": str(overlay_path),
        "overlay_present": overlay_path.is_file(),
        "user_declared": user_declared,
        "overlay_error": overlay_err,
        "active_profile_id": getattr(settings, "active_profile_id", None),
        "model": getattr(settings, "model", None),
        "behavior": behavior,
    }


def build_user_model_bundle_v1(
    settings: Settings,
    *,
    days: int = 14,
) -> dict[str, Any]:
    """RFC：可归档的导出包，嵌套当前 ``memory_user_model_v1`` 概览。"""
    overview = build_memory_user_model_overview(settings, days=days)
    return {
        "schema_version": "user_model_bundle_v1",
        "exported_at": datetime.now(UTC).isoformat(),
        "bundle_kind": "behavior_overview",
        "overview": overview,
    }
