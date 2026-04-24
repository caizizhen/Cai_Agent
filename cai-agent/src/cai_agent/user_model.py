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


def _load_recent_sessions_for_user_model(
    settings: Settings,
    *,
    days: int,
) -> tuple[Path, list[Path], list[Path], list[dict[str, Any]], int]:
    """返回 ``(root, recent_all_paths, session_paths_sample, sessions_sample, parse_errors)``。"""
    root = Path(settings.workspace).expanduser().resolve()
    window_sec = max(1, int(days)) * 86400
    cutoff = time.time() - window_sec
    pattern = ".cai-session*.json"
    paths = list_session_files(cwd=str(root), pattern=pattern, limit=2000)
    recent_all = [p for p in paths if p.stat().st_mtime >= cutoff]
    sample_paths = recent_all[:100]
    recent_sessions: list[dict[str, Any]] = []
    parse_errors = 0
    loaded_paths: list[Path] = []
    for p in sample_paths:
        try:
            recent_sessions.append(load_session(str(p)))
            loaded_paths.append(p)
        except Exception:
            parse_errors += 1
    return root, recent_all, loaded_paths, recent_sessions, parse_errors


def _heuristic_dialectic_block(
    recent_sessions: list[dict[str, Any]],
    recent_paths: list[Path],
) -> dict[str, Any]:
    """无 LLM 时的辩证块：从 goal 与 user 文本消息抽取弱主张 / 反主张 / 时间轴。"""
    beliefs: list[dict[str, Any]] = []
    counter_beliefs: list[dict[str, Any]] = []
    uncertainty: list[dict[str, Any]] = []
    traits: list[dict[str, Any]] = []
    timeline: list[dict[str, Any]] = []

    seen: set[str] = set()
    for sess in recent_sessions[:30]:
        g = str(sess.get("goal") or "").strip()
        if 24 <= len(g) <= 220:
            key = g[:100]
            if key not in seen:
                seen.add(key)
                beliefs.append({"text": g[:200], "confidence": 0.35, "kind": "goal_derived"})
        msgs = sess.get("messages")
        if not isinstance(msgs, list):
            continue
        for msg in msgs:
            if not isinstance(msg, dict) or msg.get("role") != "user":
                continue
            c = msg.get("content")
            if not isinstance(c, str) or len(c.strip()) < 8:
                continue
            if c.strip().startswith("{"):
                continue
            low = c.lower()
            if any(x in c for x in ("但是", "不过", "担心", "不要", "避免", "风险")) or any(
                x in low for x in ("don't", "avoid", "risk", "however")
            ):
                counter_beliefs.append({"text": c.strip()[:200], "confidence": 0.3, "kind": "user_caveat"})
            elif any(x in c for x in ("?", "？", "是否", "怎么", "如何")):
                uncertainty.append({"text": c.strip()[:200], "confidence": 0.25, "kind": "question"})

    beliefs = beliefs[:8]
    counter_beliefs = counter_beliefs[:8]
    uncertainty = uncertainty[:8]

    for p, sess in zip(recent_paths[:15], recent_sessions[:15], strict=False):
        g = str(sess.get("goal") or "").strip()[:80]
        try:
            mt = datetime.fromtimestamp(p.stat().st_mtime, UTC).isoformat()
        except OSError:
            mt = ""
        timeline.append({"path": str(p), "mtime": mt, "goal_preview": g})

    if beliefs or counter_beliefs or timeline:
        traits.append({"id": "verbosity", "note": "基于会话条数与 goal 长度的启发式占位", "score": 0.5})

    return {
        "available": True,
        "mode": "heuristic",
        "beliefs": beliefs,
        "counter_beliefs": counter_beliefs,
        "uncertainty": uncertainty,
        "traits": traits,
        "timeline": timeline,
    }


def build_memory_user_model_overview_v2(
    settings: Settings,
    *,
    days: int = 14,
    with_dialectic: bool = True,
) -> dict[str, Any]:
    """``memory_user_model_v2``：嵌套 v1 行为块 + ``dialectic``（启发式或后续接 LLM）。"""
    _root, recent_all, session_paths, recent_sessions, parse_errors = _load_recent_sessions_for_user_model(
        settings,
        days=days,
    )
    v1 = build_memory_user_model_overview(settings, days=days)
    dialectic: dict[str, Any]
    if with_dialectic:
        if not recent_sessions:
            dialectic = {
                "available": False,
                "mode": "none",
                "reason": "no_recent_sessions",
                "beliefs": [],
                "counter_beliefs": [],
                "uncertainty": [],
                "traits": [],
                "timeline": [],
            }
        else:
            dialectic = _heuristic_dialectic_block(recent_sessions, session_paths)
    else:
        dialectic = {"available": False, "mode": "disabled", "reason": "with_dialectic_false"}

    out = dict(v1)
    out["schema_version"] = "memory_user_model_v2"
    out["honcho_parity"] = "behavior_extract+dialectic_heuristic"
    out["notes_zh"] = (
        "v2 在 v1 行为统计基础上增加 dialectic 块；"
        "当前为启发式抽取（非完整 Honcho 在线学习）。"
    )
    out["dialectic"] = dialectic
    out["dialectic_parse_errors"] = int(parse_errors)
    return out


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
    root, recent_paths, _session_paths, recent_sessions, parse_errors = _load_recent_sessions_for_user_model(
        settings,
        days=days,
    )
    pattern = ".cai-session*.json"
    paths = list_session_files(cwd=str(root), pattern=pattern, limit=2000)
    total = len(paths)

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
    with_store: bool = False,
) -> dict[str, Any]:
    """RFC：可归档的导出包，嵌套当前 ``memory_user_model_v1`` 概览。

    当 ``with_store=True`` 时附加 ``user_model_store``（``user_model_store_snapshot_v1``），
    与 ``memory user-model export --with-store`` 对齐。
    """
    overview = build_memory_user_model_overview(settings, days=days)
    out: dict[str, Any] = {
        "schema_version": "user_model_bundle_v1",
        "exported_at": datetime.now(UTC).isoformat(),
        "bundle_kind": "behavior_overview",
        "overview": overview,
    }
    if with_store:
        from cai_agent.user_model_store import export_store_payload

        root = Path(settings.workspace).expanduser().resolve()
        out["user_model_store"] = export_store_payload(root)
    return out


def build_memory_user_model_overview_v3(
    settings: Settings,
    *,
    days: int = 14,
    with_dialectic: bool = True,
    store_belief_limit: int = 80,
    store_event_limit: int = 40,
) -> dict[str, Any]:
    """``memory_user_model_v3``：v2 行为 + dialectic + SQLite ``user_model_store`` 快照。"""
    from cai_agent.user_model_store import export_store_payload

    base = (
        build_memory_user_model_overview_v2(
            settings,
            days=days,
            with_dialectic=with_dialectic,
        )
        if with_dialectic
        else build_memory_user_model_overview(settings, days=days)
    )
    root = Path(settings.workspace).expanduser().resolve()
    store = export_store_payload(root, belief_limit=store_belief_limit, event_limit=store_event_limit)
    out = dict(base)
    out["schema_version"] = "memory_user_model_v3"
    out["honcho_parity"] = "behavior_extract+dialectic_heuristic+sqlite_store"
    out["notes_zh"] = (
        (out.get("notes_zh") or "")
        + " v3 附带 .cai/user_model_store.sqlite3 中的 beliefs/events 快照；"
        "可用 `memory user-model learn/query` 维护。"
    ).strip()
    out["user_model_store"] = store
    return out
