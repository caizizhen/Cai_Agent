from __future__ import annotations

import argparse
from collections import Counter
import json
import os
import shlex
import signal
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import urllib.error
import urllib.request

import threading
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from importlib import resources
from pathlib import Path
from typing import Any, cast

from cai_agent import __version__
from cai_agent.agent_registry import list_agent_names, load_agent_text
from cai_agent.command_registry import list_command_names, load_command_text
from cai_agent.config import Settings
from cai_agent.doctor import run_doctor
from cai_agent.graph import build_app, initial_state
from cai_agent.board_state import (
    attach_group_summary,
    attach_status_summary,
    attach_failed_summary,
    attach_trend_summary,
    build_board_payload,
    filter_board_payload,
    save_last_workflow_snapshot,
)
from cai_agent.hook_runtime import (
    describe_hooks_catalog,
    enabled_hook_ids,
    preview_project_hooks,
    resolve_hooks_json_path,
    run_project_hooks,
)
from cai_agent.llm import get_usage_counters, reset_usage_counters
from cai_agent.llm_factory import chat_completion_by_role
from cai_agent.model_gateway import (
    build_model_capabilities_payload,
    infer_model_capabilities,
    smoke_chat_profile,
)
from cai_agent.models import fetch_models, ping_profile
from cai_agent.mcp_presets import (
    allowed_mcp_preset_choices,
    build_mcp_preset_report,
    build_mcp_preset_template,
    expand_mcp_preset_choice,
)
from cai_agent.profiles import (
    PRESETS,
    Profile,
    ProfilesError,
    add_profile,
    apply_preset,
    build_profile_contract_payload,
    build_profile,
    edit_profile,
    profile_to_public_dict,
    remove_profile,
    write_models_to_toml,
)
from cai_agent.exporter import build_export_ecc_dir_diff_report, export_target
from cai_agent.feedback import BUG_REPORT_CATEGORIES, feedback_path
from cai_agent.memory import (
    annotate_memory_states,
    build_memory_entries_jsonl_validate_report,
    fix_memory_entries_jsonl,
    export_memory_entries_bundle,
    build_memory_health_payload,
    extract_memory_entries_structured,
    evaluate_memory_entry_states,
    extract_basic_instincts_from_session,
    extract_memory_entries_from_session,
    import_memory_entries_bundle,
    load_memory_entries,
    load_memory_entries_validated,
    prune_expired_memory_entries,
    save_instincts,
    search_memory_entries,
    sort_memory_rows,
    validate_memory_entries_bundle,
)
from cai_agent.plugin_registry import list_plugin_surface
from cai_agent.quality_gate import run_quality_gate
from cai_agent.release_runbook import build_release_runbook_payload, resolve_release_repo_root
from cai_agent.rules import load_rule_text
from cai_agent.security_scan import run_pii_scan, run_security_scan
from cai_agent.schedule import (
    add_schedule_task,
    append_schedule_audit_event,
    compute_due_tasks,
    compute_schedule_stats_from_audit,
    enrich_schedule_tasks_for_display,
    list_schedule_tasks,
    load_schedule_doc,
    mark_schedule_task_run,
    remove_schedule_task,
    save_schedule_doc,
)
from cai_agent.session import (
    aggregate_sessions,
    build_observe_payload,
    list_session_files,
    load_session,
    save_session,
)
from cai_agent.session_events import (
    RUN_SCHEMA_VERSION,
    normalize_session_run_events,
    wrap_run_events,
)
from cai_agent.progress_ring import build_progress_ring_summary, global_ring, reset_global_ring
from cai_agent.skill_evolution import clear_session_skill_touches
from cai_agent.recall_audit import (
    append_negative_recall_line,
    append_recall_audit_line,
    build_recall_evaluation_payload,
)
from cai_agent.skill_registry import load_related_skill_texts
from cai_agent.task_state import new_task
from cai_agent.tools import dispatch, tools_spec_markdown
from cai_agent.workflow import get_workflow_template, list_workflow_templates, run_workflow


def _run_continue_json_fail_payload(
    *,
    command: str,
    error: str,
    message: str,
    task: Any,
    settings: Settings | None = None,
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """run/continue --json 失败路径的稳定外壳（含 events 信封）。"""
    tid = str(getattr(task, "task_id", "") or "").strip() or None
    ev_items: list[dict[str, Any]] = [
        {
            "event": "run.failed",
            "command": command,
            "error": error,
            "task_id": tid,
        },
    ]
    out: dict[str, Any] = {
        "run_schema_version": RUN_SCHEMA_VERSION,
        "ok": False,
        "error": error,
        "message": message,
        "task_id": tid,
        "task": task.to_dict(),
        "events": wrap_run_events(ev_items),
        "answer": "",
        "iteration": None,
        "finished": False,
        "config": settings.config_loaded_from if settings else None,
        "workspace": settings.workspace if settings else None,
        "provider": settings.provider if settings else None,
        "model": settings.model if settings else None,
        "mcp_enabled": settings.mcp_enabled if settings else False,
        "elapsed_ms": int(getattr(task, "elapsed_ms", 0) or 0),
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "tool_calls_count": 0,
        "used_tools": [],
        "last_tool": None,
        "error_count": 0,
        "post_gate": None,
    }
    if extras:
        out.update(extras)
    return out


def _session_file_json_extra(sess: dict[str, Any]) -> dict[str, Any]:
    """从已解析的会话 JSON 提取稳定字段（供 `sessions --json` 等使用）。"""
    ev = sess.get("events")
    events_count = len(normalize_session_run_events(ev))
    td = sess.get("task")
    task_id: str | None = None
    if isinstance(td, dict):
        tid = str(td.get("task_id") or "").strip()
        task_id = tid or None
    rs = sess.get("run_schema_version")
    tt = sess.get("total_tokens")
    ec = sess.get("error_count")
    return {
        "events_count": events_count,
        "run_schema_version": rs if isinstance(rs, str) else None,
        "task_id": task_id,
        "total_tokens": int(tt) if isinstance(tt, int) else None,
        "error_count": int(ec) if isinstance(ec, int) else None,
    }


def _build_insights_payload(
    *,
    cwd: str,
    pattern: str,
    limit: int,
    days: int,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    since = now - timedelta(days=max(days, 1))
    window_meta: dict[str, Any] = {
        "days": max(days, 1),
        "since": since.isoformat(),
        "pattern": pattern,
        "limit": limit,
    }
    files = list_session_files(cwd=cwd, pattern=pattern, limit=limit)
    window_files = [p for p in files if datetime.fromtimestamp(p.stat().st_mtime, UTC) >= since]
    if not window_files:
        return {
            "schema_version": "1.1",
            "generated_at": now.isoformat(),
            "window": window_meta,
            "sessions_in_window": 0,
            "parse_skipped": 0,
            "failure_rate": 0.0,
            "total_tokens": 0,
            "tool_calls_total": 0,
            "avg_tokens_per_session": 0,
            "avg_tool_calls_per_session": 0.0,
            "models_top": [],
            "tools_top": [],
            "latest_session_path": None,
            "top_error_sessions": [],
        }

    model_counts: Counter[str] = Counter()
    tool_counts: Counter[str] = Counter()
    total = 0
    parse_skipped = 0
    total_tokens = 0
    total_tool_calls = 0
    error_sessions = 0
    latest_session_path: str | None = None
    top_error_sessions: list[dict[str, Any]] = []

    for p in window_files:
        if latest_session_path is None:
            latest_session_path = str(p)
        try:
            sess = load_session(str(p))
        except Exception:
            parse_skipped += 1
            continue
        total += 1
        model = sess.get("model")
        if isinstance(model, str) and model.strip():
            model_counts[model.strip()] += 1
        tt = sess.get("total_tokens")
        if isinstance(tt, int):
            total_tokens += tt
        msgs = sess.get("messages")
        msg_list = msgs if isinstance(msgs, list) else []
        tc, used, _, msg_err = _collect_tool_stats(
            msg_list if isinstance(msg_list, list) else [],
        )
        total_tool_calls += tc
        for name in used:
            tool_counts[name] += 1
        sess_err = sess.get("error_count")
        sess_err_i = int(sess_err) if isinstance(sess_err, int) else msg_err
        if sess_err_i > 0:
            error_sessions += 1
            top_error_sessions.append(
                {
                    "path": str(p),
                    "error_count": sess_err_i,
                    "model": model if isinstance(model, str) else None,
                },
            )

    top_error_sessions.sort(key=lambda x: int(x.get("error_count") or 0), reverse=True)
    return {
        "schema_version": "1.1",
        "generated_at": now.isoformat(),
        "window": window_meta,
        "sessions_in_window": total,
        "parse_skipped": parse_skipped,
        "failure_rate": (float(error_sessions) / total) if total else 0.0,
        "total_tokens": total_tokens,
        "tool_calls_total": total_tool_calls,
        "avg_tokens_per_session": int(total_tokens / total) if total else 0,
        "avg_tool_calls_per_session": (float(total_tool_calls) / total) if total else 0.0,
        "models_top": [
            {"model": m, "count": c}
            for m, c in model_counts.most_common(5)
        ],
        "tools_top": [
            {"tool": t, "count": c}
            for t, c in tool_counts.most_common(10)
        ],
        "latest_session_path": latest_session_path,
        "top_error_sessions": top_error_sessions[:5],
    }


def _build_memory_nudge_payload(
    *,
    cwd: str,
    days: int,
    session_pattern: str,
    session_limit: int,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    since = now - timedelta(days=max(days, 1))
    sessions = list_session_files(cwd=cwd, pattern=session_pattern, limit=session_limit)
    recent_sessions = [
        p for p in sessions if datetime.fromtimestamp(p.stat().st_mtime, UTC) >= since
    ]

    root = Path(cwd).resolve()
    entries, warns = load_memory_entries_validated(root)
    inst_dir = root / "memory" / "instincts"
    latest_instincts = sorted(
        inst_dir.glob("instincts-*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ) if inst_dir.is_dir() else []
    latest_instinct_path = str(latest_instincts[0]) if latest_instincts else None

    actions: list[str] = []
    thresholds = {
        "high": {"recent_sessions_min": 8, "memory_entries_max": 0},
        "medium": {"recent_sessions_min": 4, "memory_entries_max": 2},
    }
    severity = "low"
    if (
        len(recent_sessions) >= int(thresholds["high"]["recent_sessions_min"])
        and len(entries) <= int(thresholds["high"]["memory_entries_max"])
    ):
        severity = "high"
        actions.append(
            "近期会话较多但暂无结构化记忆，建议立即执行 `cai-agent memory extract --limit 20`",
        )
    elif (
        len(recent_sessions) >= int(thresholds["medium"]["recent_sessions_min"])
        and len(entries) <= int(thresholds["medium"]["memory_entries_max"])
    ):
        severity = "medium"
        actions.append("近期会话增长较快，建议补充 memory extract 并检查记忆分类质量")

    if latest_instinct_path is None and len(recent_sessions) >= 3:
        if severity == "low":
            severity = "medium"
        actions.append("尚未生成 instincts 快照，建议执行 `cai-agent memory extract` 触发沉淀")

    if warns:
        if severity == "low":
            severity = "medium"
        actions.append("检测到 memory/entries.jsonl 存在无效行，建议先修复再继续累积记忆")

    if not actions:
        actions.append("记忆状态健康：保持每周至少一次 `cai-agent memory extract --limit 10`")

    # 风险分数用于后续调度门禁联动：会话越多、记忆越少、告警越多则分数越高。
    risk_score = (len(recent_sessions) * 8) - (len(entries) * 5) + (len(warns) * 12)
    if latest_instinct_path is None:
        risk_score += 6
    risk_score = max(0, min(100, int(risk_score)))

    trend = "stable"
    history_path = root / "memory" / "nudge-history.jsonl"
    if history_path.is_file():
        try:
            lines = [ln.strip() for ln in history_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            if lines:
                prev_obj = json.loads(lines[-1])
                if isinstance(prev_obj, dict):
                    prev = str(prev_obj.get("severity") or "low").strip().lower()
                    rank = {"low": 0, "medium": 1, "high": 2}
                    d = rank.get(severity, 0) - rank.get(prev, 0)
                    if d > 0:
                        trend = "escalated"
                    elif d < 0:
                        trend = "deescalated"
        except Exception:
            trend = "stable"

    return {
        "schema_version": "1.1",
        "generated_at": now.isoformat(),
        "window": {
            "days": max(days, 1),
            "since": since.isoformat(),
            "session_pattern": session_pattern,
            "session_limit": max(session_limit, 1),
        },
        "recent_sessions": len(recent_sessions),
        "memory_entries": len(entries),
        "memory_warnings": warns,
        "latest_instinct_path": latest_instinct_path,
        "severity": severity,
        "risk_score": risk_score,
        "trend": trend,
        "threshold_policy": thresholds,
        "actions": actions,
    }


def _build_memory_nudge_report_payload(
    *,
    cwd: str,
    history_file: str | None,
    limit: int,
    days: int,
    freshness_days: int = 14,
) -> dict[str, Any]:
    root = Path(cwd).resolve()
    health_snap = build_memory_health_payload(
        root,
        days=max(1, int(days)),
        freshness_days=int(freshness_days),
    )
    history_path = Path(history_file).expanduser() if isinstance(history_file, str) and history_file.strip() else (root / "memory" / "nudge-history.jsonl")
    if not history_path.is_absolute():
        history_path = (root / history_path).resolve()
    since = datetime.now(UTC) - timedelta(days=max(1, int(days)))
    if not history_path.is_file():
        return {
            "schema_version": "1.2",
            "history_file": str(history_path),
            "days": max(1, int(days)),
            "since": since.isoformat(),
            "history_total": 0,
            "rows_total": 0,
            "entries_considered": 0,
            "severity_counts": {"low": 0, "medium": 0, "high": 0, "unknown": 0},
            "latest_severity": None,
            "severity_trend": [],
            "severity_jumps": [],
            "avg_recent_sessions": 0.0,
            "avg_memory_entries": 0.0,
            "reports": [],
            "health_score": float(health_snap.get("health_score") or 0.0),
            "health_grade": str(health_snap.get("grade") or "D"),
            "freshness": float(health_snap.get("freshness") or 0.0),
            "freshness_days": int((health_snap.get("window") or {}).get("freshness_days") or freshness_days),
            "since_freshness": str((health_snap.get("window") or {}).get("since_freshness") or ""),
            "memory_entries_for_freshness": int((health_snap.get("counts") or {}).get("memory_entries") or 0),
            "fresh_entries": int((health_snap.get("counts") or {}).get("fresh_entries") or 0),
        }

    rows: list[dict[str, Any]] = []
    sev_counts: dict[str, int] = {"low": 0, "medium": 0, "high": 0, "unknown": 0}
    raw_lines = history_path.read_text(encoding="utf-8").splitlines()[-max(1, limit):]
    for line in raw_lines:
        raw = line.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        generated_raw = obj.get("generated_at")
        generated_dt = None
        if isinstance(generated_raw, str) and generated_raw.strip():
            try:
                generated_dt = datetime.fromisoformat(generated_raw.replace("Z", "+00:00"))
                if generated_dt.tzinfo is None:
                    generated_dt = generated_dt.replace(tzinfo=UTC)
            except ValueError:
                generated_dt = None
        if generated_dt is None or generated_dt < since:
            continue
        sev = str(obj.get("severity") or "unknown").strip().lower()
        if sev not in ("low", "medium", "high"):
            sev = "unknown"
        sev_counts[sev] = int(sev_counts.get(sev, 0)) + 1
        rows.append(
            {
                "generated_at": generated_dt.isoformat(),
                "severity": sev,
                "recent_sessions": int(obj.get("recent_sessions") or 0),
                "memory_entries": int(obj.get("memory_entries") or 0),
            },
        )

    rows.sort(key=lambda r: str(r.get("generated_at") or ""))
    trend = [str(r.get("severity") or "unknown") for r in rows]
    sev_rank = {"low": 0, "medium": 1, "high": 2, "unknown": -1}
    jumps: list[dict[str, Any]] = []
    for i in range(1, len(rows)):
        prev = str(rows[i - 1].get("severity") or "unknown")
        curr = str(rows[i].get("severity") or "unknown")
        if sev_rank.get(curr, -1) > sev_rank.get(prev, -1):
            jumps.append(
                {
                    "from": prev,
                    "to": curr,
                    "at": rows[i].get("generated_at"),
                    "delta": sev_rank.get(curr, -1) - sev_rank.get(prev, -1),
                },
            )

    avg_recent = (sum(int(r.get("recent_sessions") or 0) for r in rows) / len(rows)) if rows else 0.0
    avg_mem = (sum(int(r.get("memory_entries") or 0) for r in rows) / len(rows)) if rows else 0.0
    return {
        "schema_version": "1.2",
        "history_file": str(history_path),
        "days": max(1, int(days)),
        "since": since.isoformat(),
        "history_total": len(rows),
        "rows_total": len(rows),
        "entries_considered": len(rows),
        "severity_counts": sev_counts,
        "latest_severity": trend[-1] if trend else None,
        "severity_trend": trend,
        "severity_jumps": jumps,
        "avg_recent_sessions": round(avg_recent, 2),
        "avg_memory_entries": round(avg_mem, 2),
        "reports": rows,
        "health_score": float(health_snap.get("health_score") or 0.0),
        "health_grade": str(health_snap.get("grade") or "D"),
        "freshness": float(health_snap.get("freshness") or 0.0),
        "freshness_days": int((health_snap.get("window") or {}).get("freshness_days") or freshness_days),
        "since_freshness": str((health_snap.get("window") or {}).get("since_freshness") or ""),
        "memory_entries_for_freshness": int((health_snap.get("counts") or {}).get("memory_entries") or 0),
        "fresh_entries": int((health_snap.get("counts") or {}).get("fresh_entries") or 0),
    }


def _extract_session_recall_hits(
    *,
    session: dict[str, Any],
    query: str,
    use_regex: bool,
    case_sensitive: bool,
    snippet_len: int,
) -> list[dict[str, Any]]:
    import re

    q = query if case_sensitive else query.lower()
    hits: list[dict[str, Any]] = []
    messages = session.get("messages")
    if not isinstance(messages, list):
        return hits
    for idx, msg in enumerate(messages, start=1):
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = msg.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        hay = content if case_sensitive else content.lower()
        matched = False
        match_start = 0
        match_end = 0
        if use_regex:
            flags = 0 if case_sensitive else re.IGNORECASE
            m = re.search(query, content, flags=flags)
            if m is not None:
                matched = True
                match_start, match_end = m.start(), m.end()
        else:
            pos = hay.find(q)
            if pos >= 0:
                matched = True
                match_start, match_end = pos, pos + len(q)
        if not matched:
            continue
        left = max(0, match_start - max(snippet_len // 2, 20))
        right = min(len(content), match_end + max(snippet_len // 2, 20))
        snippet = content[left:right].replace("\n", " ")
        hits.append(
            {
                "message_index": idx,
                "role": str(role) if isinstance(role, str) else None,
                "snippet": snippet,
            },
        )
    return hits


def _recall_row_score(
    *,
    mtime: int,
    now_ts: int,
    hits_count: int,
    query: str,
    text_for_density: str,
    case_sensitive: bool,
) -> tuple[float, dict[str, float]]:
    """融合 recency / hits_count / keyword_density 的轻量评分。"""
    age_sec = max(0, now_ts - int(mtime or 0))
    # 7 天半衰，近期结果更靠前。
    recency = max(0.0, 1.0 - (float(age_sec) / float(7 * 24 * 60 * 60)))
    hit_strength = min(1.0, float(max(hits_count, 0)) / 5.0)
    density = 0.0
    if query.strip() and text_for_density.strip():
        q = query if case_sensitive else query.lower()
        hay = text_for_density if case_sensitive else text_for_density.lower()
        occ = hay.count(q)
        density = min(1.0, float(occ) / max(1.0, float(len(hay)) / 220.0))
    score = round((recency * 0.45) + (hit_strength * 0.35) + (density * 0.20), 4)
    return score, {
        "recency": round(recency, 4),
        "hit_strength": round(hit_strength, 4),
        "keyword_density": round(density, 4),
    }


def _recall_sort_mode(sort: str | None) -> str:
    s = (sort or "recent").strip().lower()
    if s in ("recent", "default", ""):
        return "recent"
    if s == "density":
        return "density"
    if s == "combined":
        return "combined"
    return "recent"


def _recall_ranking_for_sort(sort_mode: str) -> dict[str, Any]:
    if sort_mode == "density":
        return {
            "strategy": "density(keyword_density,hit_strength,recency)",
            "weights": {"keyword_density": 0.7, "hit_strength": 0.2, "recency": 0.1},
        }
    if sort_mode == "combined":
        return {
            "strategy": "combined(recency*keyword_density,hit_strength)",
            "weights": {"recency_times_density": 0.65, "hit_strength": 0.35},
        }
    return {
        "strategy": "hybrid(recency,hit_strength,keyword_density)",
        "weights": {"recency": 0.45, "hit_strength": 0.35, "keyword_density": 0.2},
    }


def _recall_score_for_sort_mode(
    sort_mode: str,
    *,
    mtime: int,
    now_ts: int,
    hits_count: int,
    query: str,
    text_for_density: str,
    case_sensitive: bool,
) -> tuple[float, dict[str, float]]:
    """按 ``sort_mode`` 计算最终 ``score`` 与分解（始终含 recency / hit_strength / keyword_density）。"""
    base, br = _recall_row_score(
        mtime=mtime,
        now_ts=now_ts,
        hits_count=hits_count,
        query=query,
        text_for_density=text_for_density,
        case_sensitive=case_sensitive,
    )
    rec = float(br.get("recency") or 0.0)
    hs = float(br.get("hit_strength") or 0.0)
    den = float(br.get("keyword_density") or 0.0)
    if sort_mode == "density":
        score = round((den * 0.7) + (hs * 0.2) + (rec * 0.1), 4)
    elif sort_mode == "combined":
        score = round((rec * den * 0.65) + (hs * 0.35), 4)
    else:
        score = base
    out = dict(br)
    out["sort_mode"] = sort_mode
    return score, out


def _sort_recall_rows(
    rows: list[dict[str, Any]],
    *,
    sort_mode: str,
) -> None:
    """就地排序；tie-break 用 mtime 新者优先。"""
    rows.sort(
        key=lambda x: (
            float(x.get("score") or 0.0),
            int(x.get("mtime") or 0),
        ),
        reverse=True,
    )


_RECALL_NO_HIT_HINTS: dict[str, str] = {
    "window_too_narrow": "时间窗口内没有可检索的会话文件，请尝试增大 --days 或检查会话 mtime。",
    "pattern_no_match": "窗口内有会话，但没有任何消息内容与查询/正则匹配；请检查关键词或改用 --regex。",
    "index_empty": "索引中没有条目（entries 为空）；请先运行 cai-agent recall-index build。",
    "all_skipped": "窗口内的会话文件均无法解析为有效 JSON（或全部被跳过），请检查文件是否损坏。",
}


def _recall_no_hit_reason_scan(
    *,
    files_seen: int,
    candidates_in_window: int,
    sessions_scanned: int,
    parse_skipped: int,
) -> str | None:
    """0 命中时的原因枚举（S3-02）；有命中时返回 None。"""
    if candidates_in_window <= 0:
        if files_seen <= 0:
            return "pattern_no_match"
        return "window_too_narrow"
    if sessions_scanned <= 0 and parse_skipped >= candidates_in_window:
        return "all_skipped"
    return "pattern_no_match"


def _recall_no_hit_reason_index(
    *,
    entries_len: int,
    rows_len: int,
) -> str | None:
    if entries_len <= 0:
        return "index_empty"
    if rows_len <= 0:
        return "pattern_no_match"
    return None


def _build_recall_payload(
    *,
    cwd: str,
    pattern: str,
    limit: int,
    days: int,
    query: str,
    use_regex: bool,
    case_sensitive: bool,
    hits_per_session: int,
    session_limit: int,
    sort: str | None = None,
) -> dict[str, Any]:
    sort_mode = _recall_sort_mode(sort)
    now = datetime.now(UTC)
    now_ts = int(now.timestamp())
    since = now - timedelta(days=max(days, 1))
    files = list_session_files(cwd=cwd, pattern=pattern, limit=limit)
    files_seen = len(files)
    parse_skipped = 0
    sessions_scanned = 0
    sessions_with_hits = 0
    hits_total = 0
    result_rows: list[dict[str, Any]] = []
    candidates_in_window = 0
    for p in files:
        mtime = datetime.fromtimestamp(p.stat().st_mtime, UTC)
        if mtime < since:
            continue
        candidates_in_window += 1
        try:
            sess = load_session(str(p))
        except Exception:
            parse_skipped += 1
            continue
        sessions_scanned += 1
        hits = _extract_session_recall_hits(
            session=sess,
            query=query,
            use_regex=use_regex,
            case_sensitive=case_sensitive,
            snippet_len=220,
        )
        if not hits:
            continue
        sessions_with_hits += 1
        selected = hits[: max(1, hits_per_session)]
        hits_total += len(selected)
        answer = sess.get("answer")
        answer_preview = (
            str(answer).strip()[:120] + ("…" if len(str(answer).strip()) > 120 else "")
            if isinstance(answer, str) and answer.strip()
            else ""
        )
        density_parts: list[str] = []
        msgs = sess.get("messages")
        if isinstance(msgs, list):
            for h in selected:
                if not isinstance(h, dict):
                    continue
                mi = h.get("message_index")
                if isinstance(mi, int) and 1 <= mi <= len(msgs):
                    m = msgs[mi - 1]
                    if isinstance(m, dict):
                        c = m.get("content")
                        if isinstance(c, str) and c.strip():
                            density_parts.append(c)
        density_blob = (
            " ".join(density_parts)
            if density_parts
            else " ".join(str(h.get("snippet") or "") for h in selected)
        )
        score, score_breakdown = _recall_score_for_sort_mode(
            sort_mode,
            mtime=int(p.stat().st_mtime),
            now_ts=now_ts,
            hits_count=len(selected),
            query=query,
            text_for_density=density_blob,
            case_sensitive=case_sensitive,
        )
        result_rows.append(
            {
                "path": str(p),
                "mtime": int(p.stat().st_mtime),
                "model": sess.get("model") if isinstance(sess.get("model"), str) else None,
                "task_id": (
                    str((sess.get("task") or {}).get("task_id"))
                    if isinstance(sess.get("task"), dict)
                    else None
                ),
                "answer_preview": answer_preview,
                "hits": selected,
                "hits_count": len(selected),
                "score": score,
                "score_breakdown": score_breakdown,
            },
        )
    _sort_recall_rows(result_rows, sort_mode=sort_mode)
    trimmed = result_rows[: max(1, session_limit)]
    hits_sum = sum(int(x.get("hits_count") or 0) for x in trimmed)
    no_hit: str | None = None
    if hits_sum <= 0:
        no_hit = _recall_no_hit_reason_scan(
            files_seen=files_seen,
            candidates_in_window=candidates_in_window,
            sessions_scanned=sessions_scanned,
            parse_skipped=parse_skipped,
        )
    return {
        "schema_version": "1.3",
        "generated_at": now.isoformat(),
        "query": query,
        "regex": use_regex,
        "case_sensitive": case_sensitive,
        "sort": sort_mode,
        "no_hit_reason": no_hit,
        "window": {
            "days": max(days, 1),
            "since": since.isoformat(),
            "pattern": pattern,
            "limit": limit,
            "hits_per_session": max(1, hits_per_session),
            "session_limit": max(1, session_limit),
            "sort": sort_mode,
        },
        "sessions_scanned": sessions_scanned,
        "sessions_with_hits": len(trimmed),
        "hits_total": hits_sum,
        "parse_skipped": parse_skipped,
        "results": trimmed,
        "ranking": _recall_ranking_for_sort(sort_mode),
    }


def _resolve_recall_index_path(*, cwd: str, index_path: str | None) -> Path:
    if isinstance(index_path, str) and index_path.strip():
        p = Path(index_path.strip()).expanduser()
        if not p.is_absolute():
            return (Path(cwd).resolve() / p).resolve()
        return p.resolve()
    return (Path(cwd).resolve() / ".cai-recall-index.json")


def _session_row_for_recall_index(*, p: Path, sess: dict[str, Any]) -> dict[str, Any]:
    fragments: list[str] = []
    ans = sess.get("answer")
    if isinstance(ans, str) and ans.strip():
        fragments.append(ans.strip())
    msgs = sess.get("messages")
    if isinstance(msgs, list):
        for msg in msgs:
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if isinstance(content, str) and content.strip():
                fragments.append(content.strip())
    text_blob = "\n".join(fragments)
    return {
        "path": str(p),
        "mtime": int(p.stat().st_mtime),
        "model": sess.get("model") if isinstance(sess.get("model"), str) else None,
        "task_id": (
            str((sess.get("task") or {}).get("task_id"))
            if isinstance(sess.get("task"), dict)
            else None
        ),
        "answer_preview": (str(ans).strip()[:120] if isinstance(ans, str) else ""),
        "content": text_blob,
    }


def _build_recall_index(
    *,
    cwd: str,
    pattern: str,
    limit: int,
    days: int,
    index_path: str | None,
) -> dict[str, Any]:
    """构建轻量 recall 索引（JSON），用于加速后续查询。"""
    now = datetime.now(UTC)
    since = now - timedelta(days=max(days, 1))
    files = list_session_files(cwd=cwd, pattern=pattern, limit=limit)
    parse_skipped = 0
    sessions_indexed = 0
    rows: list[dict[str, Any]] = []
    for p in files:
        mtime = datetime.fromtimestamp(p.stat().st_mtime, UTC)
        if mtime < since:
            continue
        try:
            sess = load_session(str(p))
        except Exception:
            parse_skipped += 1
            continue
        sessions_indexed += 1
        rows.append(_session_row_for_recall_index(p=p, sess=sess))
    rows.sort(key=lambda x: int(x.get("mtime") or 0), reverse=True)
    payload = {
        "recall_index_schema_version": "1.1",
        "generated_at": now.isoformat(),
        "window": {
            "days": max(days, 1),
            "since": since.isoformat(),
            "pattern": pattern,
            "limit": limit,
        },
        "sessions_indexed": sessions_indexed,
        "parse_skipped": parse_skipped,
        "entries": rows,
    }
    idx_path = _resolve_recall_index_path(cwd=cwd, index_path=index_path)
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    idx_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "index_file": str(idx_path),
        "sessions_indexed": sessions_indexed,
        "parse_skipped": parse_skipped,
        "recall_index_schema_version": "1.1",
        "mode": "full",
    }


def _refresh_recall_index(
    *,
    cwd: str,
    pattern: str,
    limit: int,
    days: int,
    index_path: str | None,
    prune_missing: bool,
) -> dict[str, Any]:
    """增量刷新索引：按 path 合并；mtime 未变则跳过重解析；可选删除磁盘已不存在的条目。"""
    now = datetime.now(UTC)
    since = now - timedelta(days=max(days, 1))
    idx_path = _resolve_recall_index_path(cwd=cwd, index_path=index_path)

    old_rows: list[dict[str, Any]] = []
    if idx_path.is_file():
        try:
            old_doc = json.loads(idx_path.read_text(encoding="utf-8"))
            if isinstance(old_doc, dict):
                ent = old_doc.get("entries")
                if isinstance(ent, list):
                    old_rows = [dict(x) for x in ent if isinstance(x, dict)]
        except Exception:
            old_rows = []

    merged_by_path: dict[str, dict[str, Any]] = {}
    for row in old_rows:
        pth = str(row.get("path") or "").strip()
        if not pth:
            continue
        try:
            key = str(Path(pth).expanduser().resolve())
        except Exception:
            key = pth
        merged_by_path[key] = row

    files = list_session_files(cwd=cwd, pattern=pattern, limit=limit)
    parse_skipped = 0
    sessions_touched = 0
    sessions_skipped_unchanged = 0

    for p in files:
        mtime = datetime.fromtimestamp(p.stat().st_mtime, UTC)
        if mtime < since:
            continue
        key = str(p.resolve())
        prev = merged_by_path.get(key)
        if isinstance(prev, dict):
            prev_mtime = prev.get("mtime")
            if isinstance(prev_mtime, int) and prev_mtime == int(p.stat().st_mtime):
                sessions_skipped_unchanged += 1
                continue
        try:
            sess = load_session(str(p))
        except Exception:
            parse_skipped += 1
            continue
        sessions_touched += 1
        merged_by_path[key] = _session_row_for_recall_index(p=p, sess=sess)

    pruned_missing = 0
    pruned_stale_window = 0
    if prune_missing:
        for pth in list(merged_by_path.keys()):
            try:
                pp = Path(pth).expanduser().resolve()
            except Exception:
                merged_by_path.pop(pth, None)
                pruned_missing += 1
                continue
            if not pp.is_file():
                merged_by_path.pop(pth, None)
                pruned_missing += 1
                continue
            try:
                mt = datetime.fromtimestamp(pp.stat().st_mtime, UTC)
            except Exception:
                merged_by_path.pop(pth, None)
                pruned_missing += 1
                continue
            if mt < since:
                merged_by_path.pop(pth, None)
                pruned_stale_window += 1

    merged = list(merged_by_path.values())
    merged.sort(key=lambda x: int(x.get("mtime") or 0), reverse=True)

    payload = {
        "recall_index_schema_version": "1.1",
        "generated_at": now.isoformat(),
        "window": {
            "days": max(days, 1),
            "since": since.isoformat(),
            "pattern": pattern,
            "limit": limit,
        },
        "sessions_indexed": len(merged),
        "parse_skipped": parse_skipped,
        "entries": merged,
        "refresh": {
            "sessions_touched": sessions_touched,
            "sessions_skipped_unchanged": sessions_skipped_unchanged,
            "pruned_missing": pruned_missing,
            "pruned_stale_window": pruned_stale_window,
        },
    }
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    idx_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "index_file": str(idx_path),
        "sessions_indexed": len(merged),
        "parse_skipped": parse_skipped,
        "recall_index_schema_version": "1.1",
        "mode": "incremental",
        "sessions_touched": sessions_touched,
        "sessions_skipped_unchanged": sessions_skipped_unchanged,
        "pruned_missing": pruned_missing,
        "pruned_stale_window": pruned_stale_window,
    }


def _build_recall_payload_from_index(
    *,
    index_file: str,
    query: str,
    use_regex: bool,
    case_sensitive: bool,
    session_limit: int,
    sort: str | None = None,
) -> dict[str, Any]:
    sort_mode = _recall_sort_mode(sort)
    now_ts = int(time.time())
    doc = json.loads(Path(index_file).expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("index file root must be object")
    entries = doc.get("entries")
    if not isinstance(entries, list):
        entries = []
    entries_len = len(entries)
    rows: list[dict[str, Any]] = []
    total_hits = 0
    for row in entries:
        if not isinstance(row, dict):
            continue
        txt = row.get("content")
        if not isinstance(txt, str) or not txt:
            continue
        fake_sess = {
            "messages": [{"role": "assistant", "content": txt}],
        }
        hits = _extract_session_recall_hits(
            session=fake_sess,
            query=query,
            use_regex=use_regex,
            case_sensitive=case_sensitive,
            snippet_len=220,
        )
        if not hits:
            continue
        total_hits += len(hits)
        density_blob = txt.strip()
        score, score_breakdown = _recall_score_for_sort_mode(
            sort_mode,
            mtime=int(row.get("mtime") or 0),
            now_ts=now_ts,
            hits_count=len(hits),
            query=query,
            text_for_density=density_blob,
            case_sensitive=case_sensitive,
        )
        rows.append(
            {
                "path": row.get("path"),
                "mtime": row.get("mtime"),
                "model": row.get("model"),
                "task_id": row.get("task_id"),
                "answer_preview": row.get("answer_preview"),
                "hits_count": len(hits),
                "hits": hits[:3],
                "score": score,
                "score_breakdown": score_breakdown,
            },
        )
    _sort_recall_rows(rows, sort_mode=sort_mode)
    trimmed = rows[: max(1, session_limit)]
    hits_sum = sum(int(x.get("hits_count") or 0) for x in trimmed)
    no_hit = _recall_no_hit_reason_index(entries_len=entries_len, rows_len=len(rows)) if hits_sum <= 0 else None
    return {
        "schema_version": "1.3",
        "query": query,
        "regex": use_regex,
        "case_sensitive": case_sensitive,
        "sort": sort_mode,
        "no_hit_reason": no_hit,
        "source": "index",
        "index_file": str(Path(index_file).expanduser().resolve()),
        "sessions_scanned": len(entries),
        "sessions_with_hits": len(trimmed),
        "hits_total": hits_sum,
        "parse_skipped": 0,
        "results": trimmed,
        "ranking": _recall_ranking_for_sort(sort_mode),
    }


def _build_recall_payload_from_fts5(
    *,
    cwd: str,
    query: str,
    limit: int,
    days: int,
    hits_per_session: int,
    session_limit: int,
    use_regex: bool,
    case_sensitive: bool,
    sort: str | None = None,
) -> dict[str, Any]:
    from cai_agent.recall_fts5 import fts5_db_path, search_fts5_recall

    if not fts5_db_path(cwd).is_file():
        raise FileNotFoundError("fts5_index_missing")
    if use_regex:
        raise ValueError("FTS5 模式暂不支持 --regex，请使用默认 recall 或 JSON 索引")
    sort_mode = _recall_sort_mode(sort)
    now = datetime.now(UTC)
    since = now - timedelta(days=max(days, 1))
    rows = search_fts5_recall(
        cwd=cwd,
        query=query,
        limit=session_limit,
        days=days,
        hits_per_session=hits_per_session,
    )
    _sort_recall_rows(rows, sort_mode=sort_mode)
    trimmed = rows[: max(1, session_limit)]
    hits_sum = sum(int(x.get("hits_count") or 0) for x in trimmed)
    no_hit: str | None = None
    if hits_sum <= 0:
        no_hit = "pattern_no_match"
    return {
        "schema_version": "1.3",
        "generated_at": now.isoformat(),
        "query": query,
        "regex": False,
        "case_sensitive": case_sensitive,
        "sort": sort_mode,
        "no_hit_reason": no_hit,
        "source": "fts5",
        "window": {
            "days": max(days, 1),
            "since": since.isoformat(),
            "hits_per_session": max(1, hits_per_session),
            "session_limit": max(1, session_limit),
            "sort": sort_mode,
        },
        "sessions_scanned": len(rows),
        "sessions_with_hits": len(trimmed),
        "hits_total": hits_sum,
        "parse_skipped": 0,
        "results": trimmed,
        "ranking": _recall_ranking_for_sort(sort_mode),
    }


def _apply_recall_summarize_heuristic(payload: dict[str, Any], *, top: int) -> dict[str, Any]:
    out = dict(payload)
    results = out.get("results")
    summaries: list[dict[str, Any]] = []
    if isinstance(results, list):
        for r in results[: max(1, top)]:
            if not isinstance(r, dict):
                continue
            parts: list[str] = []
            for h in (r.get("hits") or [])[:5]:
                if isinstance(h, dict):
                    sn = h.get("snippet")
                    if isinstance(sn, str) and sn.strip():
                        parts.append(sn.strip())
            blob = " ".join(parts)[:400]
            summaries.append({"path": r.get("path"), "summary": blob or "(empty)"})
    out["summaries"] = summaries
    out["summarize_method"] = "heuristic_snippets"
    out["summarize_top"] = int(top)
    return out


def _search_recall_index(
    *,
    cwd: str,
    query: str,
    regex: bool,
    case_sensitive: bool,
    max_hits: int,
    index_path: str | None = None,
    sort: str | None = None,
) -> dict[str, Any]:
    idx_path = _resolve_recall_index_path(cwd=cwd, index_path=index_path)
    return _build_recall_payload_from_index(
        index_file=str(idx_path),
        query=query,
        use_regex=regex,
        case_sensitive=case_sensitive,
        session_limit=max(1, max_hits),
        sort=sort,
    )


def _benchmark_recall_index(
    *,
    cwd: str,
    query: str,
    regex: bool,
    case_sensitive: bool,
    days: int,
    max_hits: int,
    pattern: str,
    limit: int,
    ensure_index: bool,
    runs: int,
    index_path: str | None,
    sort: str | None = None,
) -> dict[str, Any]:
    """对比直扫 recall 与索引 recall 的耗时与命中质量。"""
    started_scan = time.perf_counter()
    scan_payload = _build_recall_payload(
        cwd=cwd,
        pattern=pattern,
        limit=limit,
        days=days,
        query=query,
        use_regex=regex,
        case_sensitive=case_sensitive,
        hits_per_session=3,
        session_limit=max(1, max_hits),
        sort=sort,
    )
    scan_ms = int((time.perf_counter() - started_scan) * 1000)

    idx_file = _resolve_recall_index_path(cwd=cwd, index_path=index_path)
    if ensure_index or (not idx_file.is_file()):
        _build_recall_index(
            cwd=cwd,
            pattern=pattern,
            limit=limit,
            days=days,
            index_path=index_path,
        )

    started_idx = time.perf_counter()
    index_payload = _build_recall_payload_from_index(
        index_file=str(idx_file),
        query=query,
        use_regex=regex,
        case_sensitive=case_sensitive,
        session_limit=max(1, max_hits),
        sort=sort,
    )
    index_ms = int((time.perf_counter() - started_idx) * 1000)

    scan_hits = int(scan_payload.get("hits_total") or 0)
    idx_hits = int(index_payload.get("hits_total") or 0)
    speedup = None
    if index_ms > 0:
        speedup = round(float(scan_ms) / float(index_ms), 3)

    return {
        "schema_version": "recall_benchmark_v1",
        "query": query,
        "regex": regex,
        "case_sensitive": case_sensitive,
        "window_days": max(1, int(days)),
        "scan": {
            "elapsed_ms": scan_ms,
            "sessions_scanned": int(scan_payload.get("sessions_scanned") or 0),
            "sessions_with_hits": int(scan_payload.get("sessions_with_hits") or 0),
            "hits_total": scan_hits,
        },
        "index": {
            "elapsed_ms": index_ms,
            "sessions_scanned": int(index_payload.get("sessions_scanned") or 0),
            "sessions_with_hits": int(index_payload.get("sessions_with_hits") or 0),
            "hits_total": idx_hits,
            "index_file": str(idx_file),
        },
        "comparison": {
            "speedup_scan_over_index": speedup,
            "hits_delta": idx_hits - scan_hits,
            "scan_faster": scan_ms < index_ms,
            "index_faster": index_ms < scan_ms,
        },
    }


def _build_observe_report_payload(
    observe_payload: dict[str, Any],
    *,
    warn_failure_rate: float,
    fail_failure_rate: float,
    warn_token_budget: int,
    fail_token_budget: int,
    warn_tool_errors: int,
    fail_tool_errors: int,
) -> dict[str, Any]:
    obs = observe_payload
    ag = obs.get("aggregates") if isinstance(obs.get("aggregates"), dict) else {}
    failure_rate = float(ag.get("failure_rate", 0.0) or 0.0)
    total_tokens = int(ag.get("total_tokens", 0) or 0)
    tool_errors = int(ag.get("tool_errors_total", 0) or 0)

    alerts: list[dict[str, Any]] = []

    def add_alert(metric: str, value: float | int, warn_t: float | int, fail_t: float | int) -> None:
        level = "ok"
        if value >= fail_t:
            level = "fail"
        elif value >= warn_t:
            level = "warn"
        alerts.append(
            {
                "metric": metric,
                "value": value,
                "warn_threshold": warn_t,
                "fail_threshold": fail_t,
                "level": level,
            },
        )

    add_alert("failure_rate", failure_rate, warn_failure_rate, fail_failure_rate)
    add_alert("total_tokens", total_tokens, warn_token_budget, fail_token_budget)
    add_alert("tool_errors_total", tool_errors, warn_tool_errors, fail_tool_errors)

    state = "pass"
    if any(a.get("level") == "fail" for a in alerts):
        state = "fail"
    elif any(a.get("level") == "warn" for a in alerts):
        state = "warn"

    return {
        "schema_version": "observe_report_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "state": state,
        "alerts": alerts,
        "observe": {
            "schema_version": obs.get("schema_version"),
            "sessions_count": int(obs.get("sessions_count", 0) or 0),
            "aggregates": ag,
        },
    }


def _parse_recall_index_since_ts(window: object) -> int | None:
    if not isinstance(window, dict):
        return None
    raw = window.get("since")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return int(dt.timestamp())
    except ValueError:
        return None


def _recall_index_doctor(
    *,
    cwd: str,
    index_path: str | None,
    fix: bool,
) -> tuple[dict[str, Any], int]:
    """索引体检（S3-03）。返回 (payload, exit_code)。"""
    idx = _resolve_recall_index_path(cwd=cwd, index_path=index_path)
    base: dict[str, Any] = {
        "schema_version": "recall_index_doctor_v1",
        "index_file": str(idx),
        "is_healthy": True,
        "issues": [],
        "stale_paths": [],
        "missing_files": [],
        "schema_version_ok": True,
        "fixed": False,
        "removed_missing": 0,
        "removed_stale": 0,
    }
    if not idx.is_file():
        base["is_healthy"] = False
        base["schema_version_ok"] = False
        base["issues"] = ["index_file_missing"]
        return base, 2
    try:
        raw_text = idx.read_text(encoding="utf-8")
        doc = json.loads(raw_text)
    except json.JSONDecodeError:
        base["is_healthy"] = False
        base["schema_version_ok"] = False
        base["issues"] = ["index_json_parse_error"]
        return base, 2
    if not isinstance(doc, dict):
        base["is_healthy"] = False
        base["schema_version_ok"] = False
        base["issues"] = ["index_root_not_object"]
        return base, 2

    issues: list[str] = []
    stale_paths: list[str] = []
    missing_files: list[str] = []
    ver = doc.get("recall_index_schema_version")
    schema_ok = ver == "1.1"
    if not schema_ok:
        base["schema_version_ok"] = False
        issues.append(f"recall_index_schema_version_unsupported:{ver!r}")

    window = doc.get("window")
    since_ts = _parse_recall_index_since_ts(window)
    if since_ts is None:
        issues.append("index_window_since_missing_or_invalid")

    entries = doc.get("entries")
    if not isinstance(entries, list):
        issues.append("index_entries_not_array")
        entries = []

    for row in entries:
        if not isinstance(row, dict):
            issues.append("index_entry_not_object")
            continue
        pth = str(row.get("path") or "").strip()
        if not pth:
            issues.append("index_entry_missing_path")
            continue
        try:
            pp = Path(pth).expanduser().resolve()
        except Exception:
            missing_files.append(pth)
            issues.append(f"missing_file:{pth}")
            continue
        if not pp.is_file():
            missing_files.append(str(pp))
            issues.append(f"missing_file:{pp}")
            continue
        if since_ts is not None:
            try:
                disk_mtime = int(pp.stat().st_mtime)
            except OSError:
                missing_files.append(str(pp))
                issues.append(f"missing_file:{pp}")
                continue
            if disk_mtime < since_ts:
                stale_paths.append(str(pp))
                issues.append(f"stale_path:{pp}")

    # 去重列表，保持顺序
    def uniq(seq: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for x in seq:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    stale_paths = uniq(stale_paths)
    missing_files = uniq(missing_files)
    # issues 保留顺序去重
    issues_u: list[str] = []
    seen_i: set[str] = set()
    for it in issues:
        if it not in seen_i:
            seen_i.add(it)
            issues_u.append(it)
    issues = issues_u

    is_healthy = len(issues) == 0
    base["stale_paths"] = stale_paths
    base["missing_files"] = missing_files
    base["issues"] = issues
    base["is_healthy"] = is_healthy
    base["entries_count"] = len([e for e in entries if isinstance(e, dict)])

    exit_code = 0 if is_healthy else 2

    if fix and (missing_files or stale_paths or any(x == "index_entry_not_object" for x in issues)):
        new_entries: list[dict[str, Any]] = []
        removed_missing = 0
        removed_stale = 0
        removed_invalid = 0
        for row in entries:
            if not isinstance(row, dict):
                removed_invalid += 1
                continue
            pth = str(row.get("path") or "").strip()
            if not pth:
                removed_invalid += 1
                continue
            try:
                pp = Path(pth).expanduser().resolve()
            except Exception:
                removed_missing += 1
                continue
            if not pp.is_file():
                removed_missing += 1
                continue
            if since_ts is not None:
                try:
                    if int(pp.stat().st_mtime) < since_ts:
                        removed_stale += 1
                        continue
                except OSError:
                    removed_missing += 1
                    continue
            new_entries.append(row)

        new_doc = dict(doc)
        new_doc["entries"] = new_entries
        new_doc["generated_at"] = datetime.now(UTC).isoformat()
        idx.write_text(json.dumps(new_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        before_count = base.get("entries_count")
        fixed_payload, fixed_exit = _recall_index_doctor(cwd=cwd, index_path=index_path, fix=False)
        fixed_payload["fixed"] = True
        fixed_payload["removed_missing"] = removed_missing
        fixed_payload["removed_stale"] = removed_stale
        fixed_payload["removed_invalid"] = removed_invalid
        fixed_payload["entries_count_before_fix"] = before_count
        return fixed_payload, fixed_exit

    return base, exit_code


def _recall_index_info(
    *,
    cwd: str,
    index_path: str | None,
) -> dict[str, Any]:
    idx = _resolve_recall_index_path(cwd=cwd, index_path=index_path)
    if not idx.is_file():
        return {
            "ok": False,
            "index_file": str(idx),
            "error": "index_not_found",
        }
    doc = json.loads(idx.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        return {
            "ok": False,
            "index_file": str(idx),
            "error": "index_invalid",
        }
    entries = doc.get("entries")
    count = len(entries) if isinstance(entries, list) else 0
    return {
        "ok": True,
        "index_file": str(idx),
        "recall_index_schema_version": doc.get("recall_index_schema_version"),
        "generated_at": doc.get("generated_at"),
        "entries_count": count,
        "sessions_indexed": doc.get("sessions_indexed", count),
        "window": doc.get("window"),
    }


def _clear_recall_index(
    *,
    cwd: str,
    index_path: str | None,
) -> dict[str, Any]:
    idx = _resolve_recall_index_path(cwd=cwd, index_path=index_path)
    if not idx.exists():
        return {"ok": True, "removed": False, "index_file": str(idx)}
    idx.unlink()
    return {"ok": True, "removed": True, "index_file": str(idx)}


def _run_release_ga_gate(
    *,
    cwd: str,
    max_failure_rate: float,
    max_tokens: int | None,
    run_quality_gate_check: bool,
    run_security_scan_check: bool,
    include_lint: bool,
    include_typecheck: bool,
    with_doctor: bool,
    with_memory_nudge: bool,
    memory_nudge_fail_on: str,
    with_memory_state: bool,
    memory_state_max_stale_rate: float,
    memory_state_max_expired_rate: float,
    memory_state_stale_days: int,
    memory_state_stale_confidence: float,
    with_memory_policy: bool = False,
) -> dict[str, Any]:
    settings = Settings.from_env(config_path=None, workspace_hint=cwd)
    release_root = resolve_release_repo_root(cwd)
    ag = aggregate_sessions(cwd=cwd, limit=200)
    failure_rate = float(ag.get("failure_rate", 0.0) or 0.0)
    total_tokens = int(ag.get("total_tokens", 0) or 0)
    token_budget = int(max_tokens) if isinstance(max_tokens, int) else int(settings.cost_budget_max_tokens)
    checks: list[dict[str, Any]] = []

    fail_rate_ok = failure_rate <= max_failure_rate
    checks.append(
        {
            "name": "session_failure_rate",
            "ok": fail_rate_ok,
            "actual": round(failure_rate, 6),
            "threshold": round(max_failure_rate, 6),
            "detail": f"failure_rate={failure_rate:.4f} threshold={max_failure_rate:.4f}",
        },
    )

    token_ok = total_tokens <= token_budget
    checks.append(
        {
            "name": "token_budget",
            "ok": token_ok,
            "actual": total_tokens,
            "threshold": token_budget,
            "detail": f"total_tokens={total_tokens} threshold={token_budget}",
        },
    )

    release_runbook = build_release_runbook_payload(repo_root=release_root, workspace=cwd)
    rel_changelog = release_runbook.get("changelog") if isinstance(release_runbook.get("changelog"), dict) else {}
    rel_bilingual = rel_changelog.get("bilingual") if isinstance(rel_changelog.get("bilingual"), dict) else {}
    rel_semantic = rel_changelog.get("semantic") if isinstance(rel_changelog.get("semantic"), dict) else {}
    checks.append(
        {
            "name": "changelog_bilingual",
            "ok": bool(rel_bilingual.get("ok")),
            "actual": {
                "lines_en": int(rel_bilingual.get("lines_en", 0) or 0),
                "lines_zh": int(rel_bilingual.get("lines_zh", 0) or 0),
                "line_ratio": float(rel_bilingual.get("line_ratio", 0.0) or 0.0),
            },
            "threshold": {"line_ratio_min": 0.5},
            "detail": (
                f"ok={bool(rel_bilingual.get('ok'))} "
                f"ratio={float(rel_bilingual.get('line_ratio', 0.0) or 0.0):.3f}"
            ),
        },
    )
    checks.append(
        {
            "name": "changelog_semantic",
            "ok": bool(rel_semantic.get("ok")),
            "actual": {
                "h2_count_en": int(rel_semantic.get("h2_count_en", 0) or 0),
                "h2_count_zh": int(rel_semantic.get("h2_count_zh", 0) or 0),
            },
            "threshold": {"same_h2_count": True},
            "detail": (
                f"ok={bool(rel_semantic.get('ok'))} "
                f"h2_en={int(rel_semantic.get('h2_count_en', 0) or 0)} "
                f"h2_zh={int(rel_semantic.get('h2_count_zh', 0) or 0)}"
            ),
        },
    )

    if run_security_scan_check:
        sec = run_security_scan(settings)
        sec_ok = bool(sec.get("ok"))
        checks.append(
            {
                "name": "security_scan",
                "ok": sec_ok,
                "findings_count": int(sec.get("findings_count", 0) or 0),
                "detail": (
                    f"findings={int(sec.get('findings_count', 0) or 0)}"
                    f" scanned_files={int(sec.get('scanned_files', 0) or 0)}"
                ),
            },
        )

    if run_quality_gate_check:
        gate = run_quality_gate(
            settings,
            enable_compile=settings.quality_gate_compile,
            enable_test=settings.quality_gate_test,
            enable_lint=bool(include_lint) or settings.quality_gate_lint,
            enable_typecheck=bool(include_typecheck) or settings.quality_gate_typecheck,
            enable_security_scan=False,
            report_dir=None,
        )
        gate_ok = bool(gate.get("ok"))
        checks.append(
            {
                "name": "quality_gate",
                "ok": gate_ok,
                "failed_count": int(gate.get("failed_count", 0) or 0),
                "detail": f"failed_count={int(gate.get('failed_count', 0) or 0)}",
            },
        )

    if with_doctor:
        try:
            doctor_settings = Settings.from_env(config_path=None, workspace_hint=cwd)
            doctor_rc = int(run_doctor(doctor_settings))
        except Exception:
            doctor_rc = 2
        checks.append(
            {
                "name": "doctor",
                "ok": doctor_rc == 0,
                "exit_code": doctor_rc,
                "detail": f"doctor_rc={doctor_rc}",
            },
        )

    if with_memory_nudge:
        fail_on = str(memory_nudge_fail_on or "high").strip().lower()
        if fail_on not in ("medium", "high"):
            fail_on = "high"
        nudge = _build_memory_nudge_payload(
            cwd=cwd,
            days=7,
            session_pattern=".cai-session*.json",
            session_limit=100,
        )
        sev = str(nudge.get("severity") or "low").strip().lower()
        sev_rank = {"low": 0, "medium": 1, "high": 2}
        nudge_ok = sev_rank.get(sev, 0) < sev_rank.get(fail_on, 2)
        checks.append(
            {
                "name": "memory_nudge",
                "ok": nudge_ok,
                "actual": sev,
                "threshold": fail_on,
                "detail": f"severity={sev} fail_on={fail_on}",
            },
        )

    if with_memory_state:
        state_payload = evaluate_memory_entry_states(
            cwd,
            stale_after_days=int(max(1, memory_state_stale_days)),
            min_active_confidence=float(max(0.0, min(1.0, memory_state_stale_confidence))),
        )
        counts = state_payload.get("counts") if isinstance(state_payload.get("counts"), dict) else {}
        rows_obj = state_payload.get("rows")
        rows_list = rows_obj if isinstance(rows_obj, list) else []
        total_entries = int(state_payload.get("total_entries", len(rows_list)) or len(rows_list))
        stale_count = int(counts.get("stale", 0) or 0)
        expired_count = int(counts.get("expired", 0) or 0)
        stale_rate = (float(stale_count) / total_entries) if total_entries else 0.0
        expired_rate = (float(expired_count) / total_entries) if total_entries else 0.0
        state_ok = (stale_rate <= memory_state_max_stale_rate) and (expired_rate <= memory_state_max_expired_rate)
        checks.append(
            {
                "name": "memory_state",
                "ok": state_ok,
                "actual": {
                    "stale_rate": round(stale_rate, 6),
                    "expired_rate": round(expired_rate, 6),
                    "stale_count": stale_count,
                    "expired_count": expired_count,
                    "total_entries": total_entries,
                },
                "threshold": {
                    "max_stale_rate": round(memory_state_max_stale_rate, 6),
                    "max_expired_rate": round(memory_state_max_expired_rate, 6),
                    "stale_days": int(max(1, memory_state_stale_days)),
                    "stale_confidence": float(max(0.0, min(1.0, memory_state_stale_confidence))),
                },
                "detail": (
                    f"stale_rate={stale_rate:.4f}<= {memory_state_max_stale_rate:.4f}, "
                    f"expired_rate={expired_rate:.4f}<= {memory_state_max_expired_rate:.4f}"
                ),
            },
        )

    if with_memory_policy:
        from cai_agent.memory import build_memory_entries_jsonl_validate_report as _mem_val_rep

        mrep = _mem_val_rep(cwd)
        m_exists = bool(mrep.get("exists"))
        m_ok = (not m_exists) or bool(mrep.get("ok"))
        checks.append(
            {
                "name": "memory_policy_entries",
                "ok": m_ok,
                "actual": {
                    "entries_file_exists": m_exists,
                    "valid_lines": int(mrep.get("valid_lines") or 0),
                    "invalid_count": len(mrep.get("invalid_lines") or []) if isinstance(mrep.get("invalid_lines"), list) else 0,
                },
                "threshold": {"schema": "memory_entry_v1"},
                "detail": str(mrep.get("entries_file") or ""),
            },
        )

    ok = all(bool(c.get("ok")) for c in checks)
    failed_checks = [str(c.get("name") or "") for c in checks if not bool(c.get("ok"))]
    failed_check_details = [
        {
            "name": str(c.get("name") or ""),
            "reason": str(c.get("detail") or ""),
        }
        for c in checks
        if not bool(c.get("ok"))
    ]
    state = "pass" if ok else "fail"
    return {
        "schema_version": "release_ga_gate_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(Path(cwd).resolve()),
        "ok": ok,
        "state": state,
        "checks_passed": len(checks) - len(failed_checks),
        "checks_failed": len(failed_checks),
        "failed_checks": failed_checks,
        "failed_check_details": failed_check_details,
        "failure_rate": failure_rate,
        "total_tokens": total_tokens,
        "checks": checks,
        "release_runbook": release_runbook,
        "aggregates": {
            "sessions_count": int(ag.get("sessions_count", 0) or 0),
            "failure_rate": failure_rate,
            "total_tokens": total_tokens,
            "token_budget": token_budget,
        },
    }


def _build_observe_report(
    *,
    cwd: str,
    pattern: str,
    limit: int,
    failure_rate_warn: float,
    failure_rate_crit: float,
    tokens_warn: int,
    run_events_warn: int,
) -> dict[str, Any]:
    obs = build_observe_payload(cwd=cwd, pattern=pattern, limit=limit)
    ag = obs.get("aggregates") if isinstance(obs.get("aggregates"), dict) else {}
    failure_rate = float(ag.get("failure_rate", 0.0) or 0.0)
    total_tokens = int(ag.get("total_tokens", 0) or 0)
    run_events_total = int(ag.get("run_events_total", 0) or 0)
    checks: list[dict[str, Any]] = []

    sev = "ok"
    if failure_rate >= failure_rate_crit:
        sev = "critical"
    elif failure_rate >= failure_rate_warn:
        sev = "warning"
    checks.append(
        {
            "name": "failure_rate",
            "severity": sev,
            "actual": round(failure_rate, 6),
            "threshold_warn": round(failure_rate_warn, 6),
            "threshold_critical": round(failure_rate_crit, 6),
        },
    )

    checks.append(
        {
            "name": "total_tokens",
            "severity": "warning" if total_tokens >= tokens_warn else "ok",
            "actual": total_tokens,
            "threshold_warn": int(tokens_warn),
        },
    )
    checks.append(
        {
            "name": "run_events_total",
            "severity": "warning" if run_events_total <= run_events_warn else "ok",
            "actual": run_events_total,
            "threshold_warn": int(run_events_warn),
        },
    )
    has_critical = any(str(c.get("severity")) == "critical" for c in checks)
    has_warning = any(str(c.get("severity")) == "warning" for c in checks)
    state = "ok"
    if has_critical:
        state = "critical"
    elif has_warning:
        state = "warning"
    return {
        "schema_version": "observe_report_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "state": state,
        "checks": checks,
        "observe": obs,
    }


def _execute_scheduled_goal(
    *,
    config_path: str | None,
    workspace_hint: str | None,
    workspace_override: str | None,
    model_override: str | None,
    goal: str,
) -> tuple[bool, str]:
    """执行单个 schedule 目标；返回 (ok, answer_or_error)。"""
    try:
        settings = Settings.from_env(
            config_path=config_path,
            workspace_hint=workspace_hint,
        )
    except Exception as e:
        return False, f"load_settings_failed: {e}"

    if isinstance(model_override, str) and model_override.strip():
        settings = replace(settings, model=model_override.strip())
    if isinstance(workspace_override, str) and workspace_override.strip():
        settings = replace(settings, workspace=os.path.abspath(workspace_override.strip()))

    reset_usage_counters()
    app = build_app(settings)
    state = initial_state(settings, goal)
    try:
        final = app.invoke(state)
    except Exception as e:
        return False, f"invoke_failed: {e}"
    answer = str((final.get("answer") or "")).strip()
    if not bool(final.get("finished")):
        return False, answer or "unfinished"
    return True, answer


def _maybe_metrics_cli(
    *,
    module: str,
    event: str,
    latency_ms: float,
    tokens: int = 0,
    success: bool = True,
) -> None:
    """Append one ``metrics_schema_v1`` line when ``CAI_METRICS_JSONL`` is set."""
    from cai_agent.metrics import maybe_append_metrics_from_env, metrics_event_v1

    maybe_append_metrics_from_env(
        metrics_event_v1(
            module=str(module).strip(),
            event=str(event).strip(),
            latency_ms=float(latency_ms),
            tokens=int(tokens),
            success=bool(success),
        ),
    )


def _schedule_task_row_snapshot(cwd: str, task_id: str) -> dict[str, Any]:
    tid = str(task_id or "").strip()
    if not tid:
        return {}
    for row in list_schedule_tasks(cwd):
        if not isinstance(row, dict):
            continue
        if str(row.get("id") or "").strip() != tid:
            continue
        return {
            "last_status": row.get("last_status"),
            "retry_count": row.get("retry_count"),
            "next_retry_at": row.get("next_retry_at"),
            "max_retries": row.get("max_retries"),
        }
    return {}


def _resolve_schedule_path(root: Path, raw_path: str | None, default_name: str) -> Path:
    if isinstance(raw_path, str) and raw_path.strip():
        p = Path(raw_path.strip()).expanduser()
        if not p.is_absolute():
            p = (root / p).resolve()
        else:
            p = p.resolve()
        return p
    return (root / default_name).resolve()


def _resolve_gateway_map_path(root: Path, raw_path: str | None) -> Path:
    return _resolve_schedule_path(root, raw_path, ".cai/gateway/telegram-session-map.json")


def _parse_allowed_chat_ids(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for x in raw:
        s = str(x).strip()
        if s and s not in out:
            out.append(s)
    return out


def _telegram_chat_id_allowed(chat_id: str, doc: dict[str, Any]) -> bool:
    """若 ``allowed_chat_ids`` 非空，则仅允许列表中的 ``chat_id``；空列表表示不启用白名单（兼容旧文件）。"""
    allowed = _parse_allowed_chat_ids(doc.get("allowed_chat_ids"))
    if not allowed:
        return True
    return str(chat_id or "").strip() in set(allowed)


def _load_gateway_map(path: Path) -> dict[str, Any]:
    empty: dict[str, Any] = {
        "schema_version": "gateway_telegram_map_v1",
        "bindings": {},
        "allowed_chat_ids": [],
    }
    if not path.is_file():
        return dict(empty)
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(empty)
    if not isinstance(obj, dict):
        return dict(empty)
    binds = obj.get("bindings")
    if not isinstance(binds, dict):
        binds = {}
    out: dict[str, dict[str, str]] = {}
    for k, v in binds.items():
        if not isinstance(k, str) or not k.strip() or not isinstance(v, dict):
            continue
        chat_id = str(v.get("chat_id") or "").strip()
        user_id = str(v.get("user_id") or "").strip()
        session_file = str(v.get("session_file") or "").strip()
        if not chat_id or not user_id or not session_file:
            continue
        out[k.strip()] = {
            "chat_id": chat_id,
            "user_id": user_id,
            "session_file": session_file,
        }
    allowed = _parse_allowed_chat_ids(obj.get("allowed_chat_ids"))
    return {
        "schema_version": "gateway_telegram_map_v1",
        "bindings": out,
        "allowed_chat_ids": allowed,
    }


def _save_gateway_map(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _gateway_continue_hint_payload(
    *,
    root: Path,
    map_path: Path,
    chat_id: str | None,
    user_id: str | None,
) -> dict[str, Any]:
    """Hermes S6-04：生成与绑定 ``session_file`` 对应的 ``continue`` 命令提示（只读）。"""
    doc = _load_gateway_map(map_path)
    binds = doc.get("bindings")
    if not isinstance(binds, dict):
        binds = {}
    cid = str(chat_id or "").strip()
    uid = str(user_id or "").strip()
    rows: list[dict[str, Any]] = []
    if cid or uid:
        key = f"{cid}:{uid}"
        row = binds.get(key) if isinstance(binds.get(key), dict) else None
        if not row:
            return {
                "schema_version": "gateway_telegram_continue_hint_v1",
                "ok": False,
                "error": "binding_not_found",
                "map_file": str(map_path),
                "chat_id": cid,
                "user_id": uid,
            }
        rows = [row]
    else:
        rows = [v for _, v in sorted(binds.items(), key=lambda x: x[0]) if isinstance(v, dict)]

    hints: list[dict[str, Any]] = []
    base = root.resolve()
    for row in rows:
        sf = str(row.get("session_file") or "").strip()
        abs_path = ""
        exists = False
        if sf:
            p = Path(sf).expanduser()
            if not p.is_absolute():
                p = (base / p).resolve()
            else:
                p = p.resolve()
            abs_path = str(p)
            exists = p.is_file()
        cmd = ("cai-agent continue " + shlex.quote(abs_path)) if abs_path else ""
        hints.append(
            {
                "chat_id": row.get("chat_id"),
                "user_id": row.get("user_id"),
                "session_file": sf or None,
                "session_path_resolved": abs_path or None,
                "session_file_exists": exists,
                "continue_cli": cmd,
            },
        )
    return {
        "schema_version": "gateway_telegram_continue_hint_v1",
        "ok": True,
        "action": "continue_hint",
        "map_file": str(map_path),
        "workspace_root": str(base),
        "hints": hints,
        "note": (
            "在 workspace_root 下执行 continue；Telegram webhook（execute-on-update）与 CLI 共用绑定 session_file（S6-04）。"
        ),
    }


def _extract_telegram_ids_from_update(obj: dict[str, Any]) -> tuple[str | None, str | None]:
    """从 Telegram update JSON 中提取 chat_id/user_id。"""
    candidates: list[dict[str, Any]] = []
    for key in ("message", "edited_message", "callback_query", "channel_post"):
        val = obj.get(key)
        if isinstance(val, dict):
            candidates.append(val)
    for item in candidates:
        chat_obj = item.get("chat")
        from_obj = item.get("from")
        if isinstance(item.get("message"), dict):
            inner = item.get("message")
            if isinstance(inner, dict):
                chat_obj = inner.get("chat") if isinstance(inner.get("chat"), dict) else chat_obj
                from_obj = inner.get("from") if isinstance(inner.get("from"), dict) else from_obj
        if not isinstance(from_obj, dict):
            sender_chat = item.get("sender_chat")
            if isinstance(sender_chat, dict):
                from_obj = sender_chat
        chat_id = str(chat_obj.get("id")).strip() if isinstance(chat_obj, dict) and "id" in chat_obj else ""
        user_id = str(from_obj.get("id")).strip() if isinstance(from_obj, dict) and "id" in from_obj else ""
        if chat_id and user_id:
            return chat_id, user_id
    return None, None


def _resolve_gateway_session_from_update(
    *,
    root: Path,
    map_path: Path,
    update_obj: dict[str, Any],
    create_missing: bool,
    session_template: str,
) -> dict[str, Any]:
    doc = _load_gateway_map(map_path)
    bindings = doc.get("bindings")
    if not isinstance(bindings, dict):
        bindings = {}
        doc["bindings"] = bindings
    chat_id, user_id = _extract_telegram_ids_from_update(update_obj)
    if not chat_id or not user_id:
        return {
            "schema_version": "gateway_telegram_map_v1",
            "action": "resolve-update",
            "ok": False,
            "error": "invalid_update",
            "message": "无法从 update JSON 提取 chat_id/user_id",
        }
    if not _telegram_chat_id_allowed(chat_id, doc):
        return {
            "schema_version": "gateway_telegram_map_v1",
            "action": "resolve-update",
            "ok": False,
            "error": "not_allowed",
            "message": "chat_id 不在 allowed_chat_ids 白名单（S6-03）",
            "map_file": str(map_path),
            "chat_id": chat_id,
            "user_id": user_id,
            "binding": None,
        }
    key = f"{chat_id}:{user_id}"
    row = bindings.get(key) if isinstance(bindings.get(key), dict) else None
    created = False
    if row is None and create_missing:
        rel = session_template.format(chat_id=chat_id, user_id=user_id)
        p = Path(rel).expanduser()
        if not p.is_absolute():
            p = (root / p).resolve()
        else:
            p = p.resolve()
        row = {"chat_id": chat_id, "user_id": user_id, "session_file": str(p)}
        bindings[key] = row
        _save_gateway_map(map_path, doc)
        created = True
    return {
        "schema_version": "gateway_telegram_map_v1",
        "action": "resolve-update",
        "ok": bool(row),
        "created": created,
        "map_file": str(map_path),
        "chat_id": chat_id,
        "user_id": user_id,
        "binding": row,
    }


def _send_telegram_message(
    *,
    bot_token: str,
    chat_id: str,
    text: str,
    timeout_sec: float = 8.0,
) -> tuple[bool, dict[str, Any]]:
    token = str(bot_token or "").strip()
    cid = str(chat_id or "").strip()
    if not token or not cid:
        return False, {"ok": False, "error": "invalid_args", "message": "bot_token/chat_id 不能为空"}
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = json.dumps({"chat_id": cid, "text": str(text or "")}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=max(float(timeout_sec), 0.1)) as resp:
            resp_body = resp.read().decode("utf-8")
        obj = json.loads(resp_body)
        if isinstance(obj, dict):
            return bool(obj.get("ok")), obj
        return False, {"ok": False, "error": "invalid_response", "raw": resp_body[:500]}
    except urllib.error.HTTPError as e:
        try:
            raw = e.read().decode("utf-8")
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return False, parsed
            return False, {"ok": False, "error": "http_error", "status": int(e.code), "raw": raw[:500]}
        except Exception:
            return False, {"ok": False, "error": "http_error", "status": int(e.code)}
    except Exception as e:
        return False, {"ok": False, "error": "send_failed", "message": str(e)}


def _run_gateway_telegram_webhook_server(
    *,
    root: Path,
    host: str,
    port: int,
    map_path: Path,
    session_template: str,
    create_missing: bool,
    execute_on_update: bool,
    goal_template: str,
    reply_on_execution: bool,
    telegram_bot_token: str | None,
    reply_template: str,
    reply_on_deny: bool,
    deny_message: str,
    log_file: Path,
    max_requests: int,
) -> dict[str, Any]:
    class _Handler(BaseHTTPRequestHandler):
        server_version = "cai-gateway/0.1"

        def _write_json(self, code: int, payload: dict[str, Any]) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/telegram/update":
                self._write_json(404, {"ok": False, "error": "not_found"})
                return
            content_length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(max(content_length, 0))
            try:
                obj = json.loads(raw.decode("utf-8"))
            except Exception as e:
                self._write_json(400, {"ok": False, "error": "invalid_json", "message": str(e)})
                return
            if not isinstance(obj, dict):
                self._write_json(400, {"ok": False, "error": "invalid_json_root"})
                return
            payload = _resolve_gateway_session_from_update(
                root=root,
                map_path=map_path,
                update_obj=obj,
                create_missing=create_missing,
                session_template=session_template,
            )
            execution: dict[str, Any] | None = None
            err0 = str(payload.get("error") or "")
            deny_reply_result: dict[str, Any] | None = None
            if (
                err0 == "not_allowed"
                and bool(reply_on_deny)
                and isinstance(telegram_bot_token, str)
                and telegram_bot_token.strip()
            ):
                cid_deny = str(payload.get("chat_id") or "").strip()
                if cid_deny:
                    deny_reply_result = _telegram_send_text_chunked(
                        bot_token=telegram_bot_token.strip(),
                        chat_id=cid_deny,
                        text=str(deny_message or "未授权。").strip() or "未授权。",
                    )
            if bool(payload.get("ok")) and execute_on_update:
                chat_id = str(payload.get("chat_id") or "").strip()
                user_id = str(payload.get("user_id") or "").strip()
                binding = payload.get("binding") if isinstance(payload.get("binding"), dict) else {}
                bound_session_file = str(binding.get("session_file") or "").strip()
                text_hint = ""
                msg = obj.get("message")
                if isinstance(msg, dict):
                    text_hint = str(msg.get("text") or "").strip()
                first_tok = text_hint.strip().split(None, 1)[0] if text_hint.strip() else ""
                if first_tok.startswith("/"):
                    ans_slash = _telegram_slash_reply_text(
                        first_tok,
                        map_path=map_path,
                        root=root,
                        user_id=user_id,
                    )
                    execution = {
                        "triggered": True,
                        "slash": True,
                        "ok": True,
                        "command": first_tok,
                        "answer_preview": ans_slash[:500],
                        "session_file": bound_session_file or None,
                    }
                    if reply_on_execution:
                        if telegram_bot_token:
                            execution["reply"] = _telegram_send_text_chunked(
                                bot_token=telegram_bot_token,
                                chat_id=chat_id,
                                text=ans_slash,
                            )
                        else:
                            execution["reply"] = {
                                "ok": False,
                                "error": "missing_bot_token",
                                "message": "未配置 Telegram bot token",
                            }
                else:
                    goal = goal_template.format(
                        chat_id=chat_id,
                        user_id=user_id,
                        text=text_hint,
                    ).strip()
                    ok_exec, out_exec = _execute_gateway_telegram_goal(
                        config_path=None,
                        workspace_root=str(root),
                        session_file=bound_session_file or None,
                        model_override=None,
                        goal=goal,
                    )
                    execution = {
                        "triggered": True,
                        "ok": bool(ok_exec),
                        "goal": goal,
                        "answer_preview": out_exec[:240],
                        "session_file": bound_session_file or None,
                        "persisted_session": bool(bound_session_file),
                    }
                    if reply_on_execution:
                        reply_text = reply_template.format(
                            chat_id=chat_id,
                            user_id=user_id,
                            text=text_hint,
                            answer=out_exec,
                            ok=str(bool(ok_exec)).lower(),
                        ).strip()
                        if telegram_bot_token:
                            reply_result = _telegram_send_text_chunked(
                                bot_token=telegram_bot_token,
                                chat_id=chat_id,
                                text=reply_text,
                            )
                        else:
                            reply_result = {
                                "ok": False,
                                "error": "missing_bot_token",
                                "message": "未配置 Telegram bot token",
                            }
                        execution["reply"] = reply_result
            elif execute_on_update:
                if err0 == "not_allowed":
                    execution = {
                        "triggered": False,
                        "ok": False,
                        "reason": "not_allowed",
                        "deny_reply": deny_reply_result,
                    }
                else:
                    execution = {"triggered": False, "ok": False, "reason": "resolve_failed"}
            if execution is not None:
                payload = {**payload, "execution": execution}
            log_row = {
                "ts": datetime.now(UTC).isoformat(),
                "remote": str(self.client_address[0]) if self.client_address else "",
                "payload": payload,
            }
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with log_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps(log_row, ensure_ascii=False) + "\n")
            if err0 == "not_allowed":
                code = 200
            elif bool(payload.get("ok")):
                code = 200
            else:
                code = 422
            self.server._handled += 1  # type: ignore[attr-defined]
            self._write_json(code, payload)
            if self.server._handled >= self.server._max_requests:  # type: ignore[attr-defined]
                self.server._stop_requested = True  # type: ignore[attr-defined]

        def log_message(self, _fmt: str, *_args: Any) -> None:
            return

    srv = ThreadingHTTPServer((host, port), _Handler)
    srv.timeout = 0.25
    srv._handled = 0  # type: ignore[attr-defined]
    srv._max_requests = max(max_requests, 1)  # type: ignore[attr-defined]
    srv._stop_requested = False  # type: ignore[attr-defined]
    try:
        while not bool(srv._stop_requested):  # type: ignore[attr-defined]
            srv.handle_request()
    finally:
        srv.server_close()
    return {
        "schema_version": "gateway_telegram_webhook_v1",
        "ok": True,
        "host": host,
        "port": port,
        "path": "/telegram/update",
        "handled_requests": int(srv._handled),  # type: ignore[attr-defined]
        "max_requests": int(srv._max_requests),  # type: ignore[attr-defined]
        "map_file": str(map_path),
        "log_file": str(log_file),
        "create_missing": bool(create_missing),
        "execute_on_update": bool(execute_on_update),
        "reply_on_execution": bool(reply_on_execution),
        "reply_on_deny": bool(reply_on_deny),
    }


def _telegram_send_message(
    *,
    bot_token: str,
    chat_id: str,
    text: str,
    timeout_sec: float = 8.0,
) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    req_body = json.dumps(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=req_body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    status_code = 200
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8")
            status_code = int(getattr(resp, "status", 200) or 200)
            obj = json.loads(raw)
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": "http_error", "status": int(e.code), "message": str(e)}
    except Exception as e:
        return {"ok": False, "error": "request_failed", "message": str(e)}
    if not isinstance(obj, dict):
        return {"ok": False, "error": "invalid_response"}
    return {
        "ok": bool(obj.get("ok")),
        "status": status_code,
    }


def _telegram_send_text_chunked(
    *,
    bot_token: str,
    chat_id: str,
    text: str,
    timeout_sec: float = 8.0,
    chunk_max: int = 3900,
) -> dict[str, Any]:
    """Telegram sendMessage 单条上限约 4096 UTF-8 字符；按块顺序发送（S6-02）。"""
    body = str(text or "")
    if len(body) <= chunk_max:
        return _telegram_send_message(
            bot_token=bot_token,
            chat_id=chat_id,
            text=body,
            timeout_sec=timeout_sec,
        )
    chunks: list[dict[str, Any]] = []
    for i in range(0, len(body), chunk_max):
        part = body[i : i + chunk_max]
        r = _telegram_send_message(
            bot_token=bot_token,
            chat_id=chat_id,
            text=part,
            timeout_sec=timeout_sec,
        )
        chunks.append(r)
        if not r.get("ok"):
            return {
                "ok": False,
                "error": "chunk_send_failed",
                "chunk_index": len(chunks) - 1,
                "chunks_attempted": len(chunks),
                "last": r,
            }
    return {"ok": True, "chunks": len(chunks), "last": chunks[-1] if chunks else {}}


def _telegram_admin_user_ids_from_env() -> set[str]:
    raw = str(os.environ.get("CAI_TELEGRAM_ADMIN_USER_IDS", "") or "")
    return {x.strip() for x in raw.split(",") if x.strip()}


def _telegram_slash_reply_text(
    slash_first_token: str,
    *,
    map_path: Path,
    root: Path,
    user_id: str,
) -> str:
    sl = slash_first_token.strip().lower()
    if sl in ("/ping",):
        return "pong — CAI Agent Telegram webhook"
    if sl in ("/status",):
        return f"ok — map={map_path.name}；完整 JSON 请在本机运行: cai-agent gateway status --json"
    if sl in ("/stop",):
        uid = str(user_id or "").strip()
        if (
            os.environ.get("CAI_TELEGRAM_STOP_WEBHOOK", "").strip() == "1"
            and uid
            and uid in _telegram_admin_user_ids_from_env()
        ):
            from cai_agent import gateway_lifecycle

            out = gateway_lifecycle.stop_webhook_subprocess(root)
            return (
                f"已执行 gateway stop：ok={out.get('ok')} stopped={out.get('stopped')} "
                f"error={out.get('error') or ''}"
            )
        return (
            "要停止本机 webhook 请在服务器执行：cai-agent gateway stop\n"
            "（运维可将您的 Telegram user_id 列入环境变量 CAI_TELEGRAM_ADMIN_USER_IDS，"
            "并设置 CAI_TELEGRAM_STOP_WEBHOOK=1 后，/stop 才会在本聊天触发停止。）"
        )
    if sl in ("/help", "/start"):
        return (
            "命令: /ping /status /help /stop /new；普通文本在开启 execute-on-update 时写入绑定会话并执行（与 CLI run/continue 同源）。"
            " 本机续聊可先运行: cai-agent gateway telegram continue-hint --chat-id <id> --user-id <id>"
        )
    if sl.startswith("/new"):
        return (
            "在工作区根执行 `cai-agent continue <会话文件>` 续聊；若不知路径，运行 "
            "`cai-agent gateway telegram continue-hint --chat-id … --user-id …`（S6-04）。"
        )
    return f"未知命令 {slash_first_token!r}；发送 /help"


def _acquire_schedule_daemon_lock(
    *,
    lock_path: Path,
    stale_lock_sec: float,
) -> tuple[bool, str]:
    now = datetime.now(UTC)
    payload = {
        "pid": os.getpid(),
        "started_at": now.isoformat(),
    }
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return False, f"mkdir_failed: {e}"

    if lock_path.exists() and stale_lock_sec > 0:
        try:
            data = json.loads(lock_path.read_text(encoding="utf-8"))
            started = data.get("started_at")
            if isinstance(started, str) and started.strip():
                age = (now - datetime.fromisoformat(started)).total_seconds()
                if age >= stale_lock_sec:
                    lock_path.unlink(missing_ok=True)
        except Exception:
            # Corrupted/old lock file: keep conservative behavior and let exclusive create decide.
            pass
    try:
        with lock_path.open("x", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return True, "ok"
    except FileExistsError:
        try:
            holder = lock_path.read_text(encoding="utf-8").strip()
            if len(holder) > 200:
                holder = holder[:200] + "…"
        except Exception:
            holder = "(unreadable)"
        return False, f"lock_exists: {holder}"
    except Exception as e:
        return False, f"lock_create_failed: {e}"


def _append_schedule_daemon_log(log_path: Path, row: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _collect_tool_stats(messages: list[dict[str, object]]) -> tuple[int, list[str], str | None, int]:
    names: list[str] = []
    errors = 0
    last_tool: str | None = None
    for m in messages:
        if m.get("role") != "user":
            continue
        content = m.get("content")
        if not isinstance(content, str):
            continue
        try:
            obj = json.loads(content)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        tn = obj.get("tool")
        if isinstance(tn, str) and tn.strip():
            tool_name = tn.strip()
            names.append(tool_name)
            last_tool = tool_name
            result = obj.get("result")
            if isinstance(result, str):
                r = result.lower()
                if (
                    "失败" in result
                    or "error" in r
                    or "exception" in r
                    or "traceback" in r
                ):
                    errors += 1
    uniq = sorted(set(names))
    return len(names), uniq, last_tool, errors


def _resolve_gateway_session_file_path(workspace_root: str, session_file: str | None) -> Path | None:
    s = str(session_file or "").strip()
    if not s:
        return None
    p = Path(s).expanduser()
    if not p.is_absolute():
        p = (Path(workspace_root).expanduser().resolve() / p).resolve()
    else:
        p = p.resolve()
    return p


def _execute_gateway_telegram_goal(
    *,
    config_path: str | None,
    workspace_root: str,
    session_file: str | None,
    model_override: str | None,
    goal: str,
) -> tuple[bool, str]:
    """与 ``run`` / ``continue`` 一致：有绑定 ``session_file`` 时加载历史、invoke 后写回同一路径（S6-02）。"""
    try:
        settings = Settings.from_env(
            config_path=config_path,
            workspace_hint=workspace_root,
        )
    except Exception as e:
        return False, f"load_settings_failed: {e}"

    if isinstance(model_override, str) and model_override.strip():
        settings = replace(settings, model=model_override.strip())

    sp = _resolve_gateway_session_file_path(workspace_root, session_file)
    reset_usage_counters()
    task = new_task("run")
    task.status = "running"

    if sp is not None and sp.is_file():
        try:
            sess = load_session(str(sp))
        except Exception as e:
            return False, f"load_session_failed: {e}"
        messages = sess.get("messages")
        if not isinstance(messages, list) or not messages:
            return False, "会话文件不合法：messages 必须是非空数组"
        state: dict[str, Any] = {
            "messages": list(messages) + [{"role": "user", "content": goal}],
            "iteration": 0,
            "pending": None,
            "finished": False,
        }
    else:
        state = initial_state(settings, goal)

    app = build_app(settings)
    started = time.perf_counter()
    try:
        final = app.invoke(state)
    except Exception as e:
        task.status = "failed"
        task.ended_at = time.time()
        task.error = str(e)[:800]
        return False, f"invoke_failed: {e}"

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    task.ended_at = time.time()
    task.elapsed_ms = elapsed_ms
    answer = str((final.get("answer") or "")).strip()
    ok_run = bool(final.get("finished"))
    task.status = "completed" if ok_run else "failed"
    task.error = None if ok_run else "unfinished"

    usage = get_usage_counters()
    msgs = final.get("messages") if isinstance(final.get("messages"), list) else []
    tool_calls_count, used_tools, last_tool, error_count = _collect_tool_stats(cast(list[dict[str, object]], msgs))

    cmd = "run"
    run_events: list[dict[str, object]] = [
        {"event": "run.started", "command": cmd, "task_id": task.task_id},
        {
            "event": "run.finished",
            "command": cmd,
            "task_id": task.task_id,
            "finished": ok_run,
            "status": task.status,
        },
    ]

    if sp is not None:
        payload = {
            "version": 2,
            "run_schema_version": RUN_SCHEMA_VERSION,
            "goal": goal,
            "workspace": settings.workspace,
            "config": settings.config_loaded_from,
            "provider": settings.provider,
            "model": settings.model,
            "profile": settings.active_profile_id,
            "active_profile_id": settings.active_profile_id,
            "subagent_profile_id": settings.subagent_profile_id,
            "planner_profile_id": settings.planner_profile_id,
            "mcp_enabled": settings.mcp_enabled,
            "elapsed_ms": elapsed_ms,
            "total_tokens": usage.get("total_tokens", 0),
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "tool_calls_count": tool_calls_count,
            "used_tools": used_tools,
            "last_tool": last_tool,
            "error_count": error_count,
            "messages": msgs,
            "answer": final.get("answer"),
            "task": task.to_dict(),
            "events": wrap_run_events(list(run_events)),
            "post_gate": None,
        }
        try:
            save_session(str(sp), payload)
        except Exception as e:
            return False, f"save_session_failed: {e}"

    return ok_run, answer or ("unfinished" if not ok_run else "")


def _print_hook_status(
    settings: Settings,
    *,
    event: str,
    json_output: bool,
    hook_payload: dict[str, Any] | None = None,
    hooks_dir: str | None = None,
) -> None:
    hp = resolve_hooks_json_path(settings, hooks_dir=hooks_dir)
    results = run_project_hooks(settings, event, hook_payload, hooks_path=hp)
    if json_output:
        return
    ids = enabled_hook_ids(settings, event, hooks_path=hp)
    if not ids and not results:
        return
    parts: list[str] = []
    if ids:
        parts.append("enabled=" + ",".join(ids))
    if results:
        # 将关键状态压缩到单行，便于 CI / 日志快速定位 blocked/error。
        status_bits: list[str] = []
        for r in results[:20]:
            hid = str(r.get("id") or "?")
            st = str(r.get("status") or "unknown")
            bit = f"{hid}:{st}"
            reason = r.get("reason")
            if isinstance(reason, str) and reason.strip():
                bit += f"({reason.strip()[:80]})"
            status_bits.append(bit)
        if len(results) > 20:
            status_bits.append(f"...+{len(results) - 20}")
        parts.append("results=" + "; ".join(status_bits))
    print(f"[hook:{event}] " + " | ".join(parts), file=sys.stderr)


def _inject_plan_file(goal: str, plan_path: str) -> str:
    p = Path(plan_path).expanduser().resolve()
    if not p.is_file():
        msg = f"计划文件不存在: {p}"
        raise FileNotFoundError(msg)
    body = p.read_text(encoding="utf-8").strip()
    return (
        "下列为已保存的实现计划，请在执行时遵循：\n\n"
        f"{body}\n\n---\n\n用户任务：\n{goal}"
    )


def _resolve_config_target(settings: Settings) -> Path:
    """决定 `models add/use/edit/rm` 写入哪个 TOML 文件：已加载的 > CWD 下的默认名。"""
    if settings.config_loaded_from:
        return Path(settings.config_loaded_from).expanduser().resolve()
    return (Path.cwd() / "cai-agent.toml").resolve()


def _resolve_active_after_mutation(
    current_active: str | None, profiles: tuple[Profile, ...], *, prefer: str | None = None,
) -> str | None:
    if prefer and any(p.id == prefer for p in profiles):
        return prefer
    if current_active and any(p.id == current_active for p in profiles):
        return current_active
    return profiles[0].id if profiles else None


def _settings_workspace_hint(args: argparse.Namespace) -> str | None:
    """供 ``Settings.from_env`` 在 cwd 链上找不到 TOML 时，沿工作区目录继续查找。"""
    w = getattr(args, "workspace", None)
    if isinstance(w, str) and w.strip():
        return w.strip()
    return None


def _load_settings_for_models(config_path: str | None) -> Settings | int:
    try:
        return Settings.from_env(config_path=config_path)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        return 2
    except ProfilesError as e:
        print(f"模型 profile 配置错误: {e}", file=sys.stderr)
        return 2


def _cmd_models_list(settings: Settings, *, json_output: bool, list_providers: bool = False) -> int:
    if list_providers:
        from cai_agent.provider_registry import providers_json_payload

        payload_pr = providers_json_payload()
        if json_output:
            print(json.dumps(payload_pr, ensure_ascii=False))
        else:
            print(f"provider_registry: count={payload_pr.get('count')}")
            for row in payload_pr.get("providers") or []:
                eid = row.get("id")
                env = row.get("api_key_env")
                hint = row.get("capabilities_hint") if isinstance(row.get("capabilities_hint"), dict) else {}
                caps = hint.get("capabilities") if isinstance(hint.get("capabilities"), dict) else {}
                print(
                    f"  - {eid}  env={env}  url={row.get('base_url')} "
                    f"ctx={hint.get('context_window', '?')} stream={caps.get('streaming', '?')} "
                    f"tools={caps.get('tool_calling', '?')} local={caps.get('local_private', '?')} "
                    f"cost={hint.get('cost_hint', '?')}",
                )
        return 0
    rows = [profile_to_public_dict(p) for p in settings.profiles]
    active = settings.active_profile_id
    profile_contract = build_profile_contract_payload(
        settings.profiles,
        profiles_explicit=bool(settings.profiles_explicit),
        active_profile_id=settings.active_profile_id,
        subagent_profile_id=settings.subagent_profile_id,
        planner_profile_id=settings.planner_profile_id,
        env_active_override=os.getenv("CAI_ACTIVE_MODEL"),
    )
    if json_output:
        payload = {
            "schema_version": "models_list_v1",
            "active": active,
            "subagent": settings.subagent_profile_id,
            "planner": settings.planner_profile_id,
            "profile_contract": profile_contract,
            "profiles": rows,
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    if not rows:
        print("(无 profile)")
        return 0
    print(
        f"active={active}"
        + (f" subagent={settings.subagent_profile_id}" if settings.subagent_profile_id else "")
        + (f" planner={settings.planner_profile_id}" if settings.planner_profile_id else ""),
    )
    print(
        f"contract={profile_contract.get('source_kind')} "
        f"migration={profile_contract.get('migration_state')}",
    )
    for r in rows:
        mark = "*" if r["id"] == active else " "
        env = r.get("api_key_env")
        env_note = ""
        if env:
            env_note = f" env={env}" + ("" if r.get("api_key_env_present") else "(未导出)")
        notes_raw = (r.get("notes") or "")
        notes = str(notes_raw).strip().replace("\n", " ")
        if len(notes) > 40:
            notes = notes[:37] + "…"
        notes_note = f" | {notes}" if notes else ""
        print(
            f"{mark} {r['id']:<20} provider={r['provider']:<18} model={r['model']} "
            f"base_url={r['base_url']}{env_note}{notes_note}",
        )
    return 0


def _build_add_profile(args: argparse.Namespace) -> Profile:
    raw: dict[str, Any] = {
        "id": args.pid,
        "provider": args.provider,
        "base_url": args.base_url,
        "model": args.model_field,
        "api_key_env": args.api_key_env,
        "api_key": args.api_key_literal,
        "temperature": args.temperature,
        "timeout_sec": args.timeout_sec,
        "anthropic_version": args.anthropic_version,
        "max_tokens": args.max_tokens,
        "notes": args.notes,
    }
    if args.preset:
        raw = apply_preset(raw, args.preset)
    return build_profile(raw, hint=f"add {args.pid}")


def _cmd_models(args: argparse.Namespace) -> int:
    action = getattr(args, "models_action", None) or "list"

    loaded = _load_settings_for_models(args.config)
    if isinstance(loaded, int):
        return loaded
    settings: Settings = loaded

    if action == "list":
        return _cmd_models_list(
            settings,
            json_output=bool(getattr(args, "json_output", False)),
            list_providers=bool(getattr(args, "models_list_providers", False)),
        )

    if action == "fetch":
        try:
            models = fetch_models(settings)
        except Exception as e:
            print(f"获取模型列表失败: {e}", file=sys.stderr)
            return 2
        if getattr(args, "json_output", False):
            print(
                json.dumps(
                    {"schema_version": "models_fetch_v1", "models": models},
                    ensure_ascii=False,
                ),
            )
        else:
            if not models:
                print("(无模型)")
            else:
                for m in models:
                    print(m)
        return 0

    if action == "capabilities":
        pid = getattr(args, "id", None)
        targets = (
            [p for p in settings.profiles if p.id == pid]
            if pid
            else list(settings.profiles)
        )
        if pid and not targets:
            print(f"profile 不存在: {pid}", file=sys.stderr)
            return 2
        payload_caps = build_model_capabilities_payload(
            targets,
            active_profile_id=settings.active_profile_id,
            context_window_fallback=int(getattr(settings, "context_window", 0) or 0) or None,
        )
        if getattr(args, "json_output", False):
            print(json.dumps(payload_caps, ensure_ascii=False))
        else:
            print(
                f"model_capabilities: count={payload_caps.get('count')} "
                f"active={payload_caps.get('active_profile_id') or '-'}",
            )
            for row in payload_caps.get("profiles") or []:
                caps = row.get("capabilities") if isinstance(row.get("capabilities"), dict) else {}
                print(
                    f"  - {row.get('profile_id')}: provider={row.get('provider')} "
                    f"model={row.get('model')} ctx={row.get('context_window', '?')} "
                    f"streaming={caps.get('streaming')} tools={caps.get('tool_calling')} "
                    f"vision={caps.get('vision')} json={caps.get('json_mode')} "
                    f"local={caps.get('local_private')} cost={row.get('cost_hint')}",
                )
        return 0

    if action == "onboarding":
        from cai_agent.provider_registry import build_model_onboarding_flow_v1

        try:
            flow = build_model_onboarding_flow_v1(
                profile_id=str(getattr(args, "onboarding_profile_id", "") or ""),
                preset=str(getattr(args, "onboarding_preset", "") or ""),
                model=getattr(args, "onboarding_model", None),
                set_active=not bool(getattr(args, "onboarding_no_set_active", False)),
            )
        except ProfilesError as e:
            print(f"模型 onboarding 配置错误: {e}", file=sys.stderr)
            return 2
        if bool(getattr(args, "json_output", False)):
            print(json.dumps(flow, ensure_ascii=False))
        else:
            print(f"model onboarding: profile={flow.get('profile_id')} preset={flow.get('preset')}")
            for row in flow.get("commands") or []:
                print(f"- {row.get('step')}: {row.get('command')}")
            print("boundaries:")
            for item in flow.get("boundaries") or []:
                print(f"- {item}")
        return 0

    if action == "ping":
        timeout_sec = float(getattr(args, "timeout_sec", 10.0) or 10.0)
        preset = getattr(args, "ping_preset", None)
        do_chat_smoke = bool(getattr(args, "chat_smoke", False))
        if preset and getattr(args, "id", None):
            print("不能同时指定 profile id 与 --preset", file=sys.stderr)
            return 2
        if preset:
            from cai_agent.profiles import apply_preset, build_profile

            raw = {"id": f"preset:{preset}", "model": "ping-probe"}
            raw = apply_preset(raw, str(preset))
            prof = build_profile(raw, hint=f"ping-preset:{preset}")
            targets = [prof]
        else:
            pid = getattr(args, "id", None)
            targets = (
                [p for p in settings.profiles if p.id == pid] if pid else list(settings.profiles)
            )
            if pid and not targets:
                print(f"profile 不存在: {pid}", file=sys.stderr)
                return 2
        results: list[dict[str, Any]] = []
        for p in targets:
            r = ping_profile(p, trust_env=settings.http_trust_env, timeout_sec=timeout_sec)
            if do_chat_smoke and r.get("status") == "OK":
                smoke = smoke_chat_profile(
                    settings,
                    p,
                    prompt=str(getattr(args, "chat_smoke_prompt", "") or "Reply with OK."),
                )
                r["chat_smoke"] = smoke
                r["chat_status"] = smoke.get("status")
                if smoke.get("status") != "OK":
                    r["status"] = "CHAT_FAIL"
                    r["message"] = f"chat smoke failed: {smoke.get('message') or smoke.get('status')}"
            results.append(r)
        if getattr(args, "json_output", False):
            print(
                json.dumps(
                    {"schema_version": "models_ping_v1", "results": results},
                    ensure_ascii=False,
                ),
            )
        else:
            for r in results:
                status = r.get("status")
                msg = r.get("message")
                http = r.get("http_status")
                extra = ""
                if http is not None:
                    extra += f" http={http}"
                if msg:
                    extra += f" msg={msg}"
                chat_status = r.get("chat_status")
                if chat_status:
                    extra += f" chat={chat_status}"
                print(f"{r.get('profile_id')}: {status}{extra}")
        fail = any(r.get("status") != "OK" for r in results)
        # Back-compat: `--fail-on-any-error` is a no-op alias (exit rules match default since S1-03).
        _ = bool(getattr(args, "fail_on_ping_error", False))
        # S1-03: align with exit 0/2 — any non-OK ping is exit 2.
        return 2 if fail else 0

    if action == "route-wizard":
        from cai_agent.model_routing import build_models_route_wizard_v1

        if not getattr(args, "json_output", False):
            print("models route-wizard 需使用 --json", file=sys.stderr)
            return 2
        doc_w = build_models_route_wizard_v1(
            use_profile=str(getattr(args, "route_wizard_profile", "") or ""),
            match_phase=getattr(args, "route_wizard_phase", None),
            match_task_kind=getattr(args, "route_wizard_task_kind", None),
            match_tokens_gt=getattr(args, "route_wizard_tokens_gt", None),
        )
        if bool(getattr(args, "route_wizard_dry_run", False)):
            doc_w = dict(doc_w)
            doc_w["dry_run"] = True
        print(json.dumps(doc_w, ensure_ascii=False))
        return 0

    if action == "suggest":
        task_desc = " ".join(getattr(args, "task_description", []) or []).strip()
        if not task_desc:
            print("task_description 不能为空", file=sys.stderr)
            return 2
        td_lower = task_desc.lower()
        _TASK_HINTS: list[tuple[str, list[str], str]] = [
            ("security", ["安全", "audit", "漏洞", "security", "扫描", "secret", "exploit"], "安全审查类任务"),
            ("fast", ["快速", "草稿", "初稿", "draft", "fast", "quick", "simple"], "轻量/草稿任务"),
            ("code_review", ["review", "代码审查", "pr", "diff", "重构", "refactor"], "代码审查类任务"),
            ("planning", ["规划", "plan", "架构", "design", "方案", "策略"], "规划/架构任务"),
            ("analysis", ["分析", "analyze", "统计", "data", "趋势", "insight"], "数据/分析任务"),
        ]
        matched_role = "default"
        matched_reason = "无特征匹配，建议使用 active profile"
        for role_key, keywords, reason in _TASK_HINTS:
            if any(kw in td_lower for kw in keywords):
                matched_role = role_key
                matched_reason = reason
                break
        _ROLE_PROFILE_MAP = {
            "security": "security",
            "code_review": "reviewer",
            "planning": "planner",
            "fast": None,
            "analysis": None,
        }
        suggested_profile_ids: list[str] = []
        role_hint = _ROLE_PROFILE_MAP.get(matched_role)
        for p in settings.profiles:
            pid = p.id.lower()
            notes = (p.notes or "").lower()
            if role_hint and (role_hint in pid or role_hint in notes):
                suggested_profile_ids.append(p.id)
        if not suggested_profile_ids and matched_role != "default":
            for p in settings.profiles:
                provider = (p.provider or "").lower()
                if matched_role in ("security", "planning", "code_review"):
                    if "anthropic" in provider or "claude" in (p.model or "").lower():
                        suggested_profile_ids.append(p.id)
                        break
        if not suggested_profile_ids:
            if settings.active_profile_id:
                suggested_profile_ids = [settings.active_profile_id]
        suggest_result = {
            "schema_version": "models_suggest_v1",
            "task_description": task_desc,
            "matched_role": matched_role,
            "reason": matched_reason,
            "suggested_profiles": suggested_profile_ids[:3],
            "active_profile_id": settings.active_profile_id,
            "subagent_profile_id": settings.subagent_profile_id,
            "planner_profile_id": settings.planner_profile_id,
            "available_profiles": [p.id for p in settings.profiles],
            "hint": (
                f"建议使用 `cai-agent models use {suggested_profile_ids[0]}`"
                if suggested_profile_ids
                else "保持当前 active profile"
            ),
        }
        if bool(getattr(args, "json_output", False)):
            print(json.dumps(suggest_result, ensure_ascii=False))
        else:
            print(f"task: {task_desc!r}")
            print(f"matched_role: {matched_role} — {matched_reason}")
            print(f"suggested_profiles: {suggest_result['suggested_profiles'] or ['(使用 active)']}")
            print(f"hint: {suggest_result['hint']}")
        return 0

    if action == "route":
        if not settings.profiles_explicit:
            print(
                "当前仅有从 [llm] 合成的隐式 profile；请先用 "
                "`cai-agent models add` 创建显式 [[models.profile]] 后再配置路由。",
                file=sys.stderr,
            )
            return 2
        us = bool(getattr(args, "unset_subagent", False))
        up = bool(getattr(args, "unset_planner", False))
        arg_sub = getattr(args, "subagent", None)
        arg_pln = getattr(args, "planner", None)
        if us and arg_sub is not None:
            print("不能同时指定 --subagent 与 --unset-subagent", file=sys.stderr)
            return 2
        if up and arg_pln is not None:
            print("不能同时指定 --planner 与 --unset-planner", file=sys.stderr)
            return 2
        if not (us or up or arg_sub is not None or arg_pln is not None):
            print(
                "请至少指定 --subagent、--planner、--unset-subagent、--unset-planner 之一",
                file=sys.stderr,
            )
            return 2

        base_route_profiles: tuple[Profile, ...] = settings.profiles
        target = _resolve_config_target(settings)
        ids = {p.id for p in base_route_profiles}
        new_sub = settings.subagent_profile_id
        new_pln = settings.planner_profile_id

        if us:
            new_sub = None
        elif arg_sub is not None:
            s = str(arg_sub).strip()
            if s not in ids:
                print(f"profile 不存在: {s}", file=sys.stderr)
                return 2
            new_sub = s

        if up:
            new_pln = None
        elif arg_pln is not None:
            pl = str(arg_pln).strip()
            if pl not in ids:
                print(f"profile 不存在: {pl}", file=sys.stderr)
                return 2
            new_pln = pl

        try:
            write_models_to_toml(
                target,
                base_route_profiles,
                active=settings.active_profile_id,
                subagent=new_sub,
                planner=new_pln,
            )
        except Exception as e:
            print(f"写入 {target} 失败: {e}", file=sys.stderr)
            return 2
        print(
            "[models] route ok | "
            f"active={settings.active_profile_id} "
            f"subagent={new_sub or '-'} "
            f"planner={new_pln or '-'} "
            f"file={target}",
        )
        return 0

    if action == "routing-test":
        role_raw = str(getattr(args, "routing_test_role", "active") or "active").strip().lower()
        goal = str(getattr(args, "routing_test_goal", "") or "").strip()
        total_used = int(getattr(args, "routing_test_total_tokens", 0) or 0)
        from cai_agent.model_routing import (
            build_model_fallback_candidates_v1,
            build_routing_explain_v1,
            first_matching_routing_rule,
        )

        rules = settings.model_routing_rules
        rout_on = settings.model_routing_enabled
        cost_max = int(settings.cost_budget_max_tokens or 0)
        matched = first_matching_routing_rule(
            rules,
            role=role_raw,
            goal=goal,
            cost_budget_max_tokens=cost_max,
            total_tokens_used=total_used,
        )
        base_id = str(settings.active_profile_id or "")
        eff = matched.profile_id if matched is not None else base_id
        mr: dict[str, Any] | None = None
        if matched is not None:
            mr = {
                "profile": matched.profile_id,
                "roles": list(matched.roles),
                "goal_regex": matched.goal_regex,
                "goal_substring": matched.goal_substring,
                "cost_budget_remaining_tokens_below": matched.cost_budget_remaining_tokens_below,
            }
        rem: int | None
        if cost_max > 0:
            rem = max(0, int(cost_max) - int(total_used))
        else:
            rem = None
        profile_by_id = {p.id: p for p in settings.profiles}
        base_profile = profile_by_id.get(base_id)
        effective_profile = profile_by_id.get(eff)
        explain = build_routing_explain_v1(
            model_routing_enabled=rout_on,
            matched=matched,
            base_profile_id=base_id,
            effective_profile_id=eff,
            role=role_raw,
            rules_count=len(rules),
            cost_budget_max_tokens=cost_max,
            total_tokens_used=total_used,
            cost_budget_remaining=rem,
        )
        out_rt = {
            "schema_version": "models_routing_test_v1",
            "role": role_raw,
            "goal_preview": goal[:500],
            "model_routing_enabled": rout_on,
            "rules_count": len(rules),
            "cost_budget_max_tokens": cost_max,
            "total_tokens_used": total_used,
            "cost_budget_remaining": rem,
            "base_profile_id": base_id,
            "effective_profile_id": eff,
            "matched_rule": mr,
            "explain": explain,
        }
        out_rt["fallback_candidates"] = build_model_fallback_candidates_v1(
            tuple(settings.profiles),
            effective_profile_id=eff,
            cost_budget_remaining=rem,
            context_window_fallback=int(getattr(settings, "context_window", 0) or 0) or None,
        )
        if base_profile is not None:
            out_rt["base_capabilities"] = infer_model_capabilities(
                base_profile,
                context_window_fallback=int(getattr(settings, "context_window", 0) or 0) or None,
            ).to_public_dict()
        if effective_profile is not None:
            out_rt["effective_capabilities"] = infer_model_capabilities(
                effective_profile,
                context_window_fallback=int(getattr(settings, "context_window", 0) or 0) or None,
            ).to_public_dict()
        if bool(getattr(args, "json_output", False)):
            print(json.dumps(out_rt, ensure_ascii=False))
        else:
            print(f"effective_profile_id={eff}")
            print(explain.get("summary_zh") or "")
            if effective_profile is not None:
                caps = infer_model_capabilities(
                    effective_profile,
                    context_window_fallback=int(getattr(settings, "context_window", 0) or 0) or None,
                )
                print(
                    f"capabilities: streaming={caps.streaming} "
                    f"tools={caps.tool_calling} vision={caps.vision} "
                    f"json={caps.json_mode} local={caps.local_private}",
                )
            fbc = out_rt.get("fallback_candidates") if isinstance(out_rt.get("fallback_candidates"), dict) else {}
            cand = fbc.get("candidates") if isinstance(fbc.get("candidates"), list) else []
            if cand:
                first = cand[0]
                print(
                    "fallback_candidate: "
                    f"{first.get('profile_id')} reasons={','.join(first.get('reasons') or [])} "
                    "(explain_only)",
                )
        return 0

    # 以下动作会改写 TOML：先算新的 profiles 集合，再写回。
    target = _resolve_config_target(settings)
    # 合成 default 不应持久化：仅显式配置才作为写入基线。
    base_profiles: tuple[Profile, ...] = (
        settings.profiles if settings.profiles_explicit else ()
    )
    base_active = settings.active_profile_id if settings.profiles_explicit else None
    next_subagent = settings.subagent_profile_id
    next_planner = settings.planner_profile_id

    try:
        if action == "add":
            new_p = _build_add_profile(args)
            new_profiles = add_profile(base_profiles, new_p)
            next_active = _resolve_active_after_mutation(
                base_active,
                new_profiles,
                prefer=new_p.id if args.set_active else None,
            )
        elif action == "use":
            if not any(p.id == args.id for p in base_profiles):
                print(f"profile 不存在: {args.id}", file=sys.stderr)
                return 2
            new_profiles = base_profiles
            next_active = args.id
        elif action == "rm":
            new_profiles = remove_profile(base_profiles, args.id)
            prefer = None if base_active == args.id else base_active
            next_active = _resolve_active_after_mutation(prefer, new_profiles)
            if next_subagent == args.id:
                next_subagent = None
            if next_planner == args.id:
                next_planner = None
        elif action == "edit":
            updates: dict[str, Any] = {
                "provider": args.provider,
                "base_url": args.base_url,
                "model": args.model_field,
                "api_key_env": args.api_key_env,
                "api_key": args.api_key_literal,
                "temperature": args.temperature,
                "timeout_sec": args.timeout_sec,
                "anthropic_version": args.anthropic_version,
                "max_tokens": args.max_tokens,
                "notes": args.notes,
            }
            new_profiles = edit_profile(base_profiles, args.id, updates)
            next_active = _resolve_active_after_mutation(
                base_active, new_profiles,
            )
        else:
            print(f"未知子命令: {action}", file=sys.stderr)
            return 2
    except ProfilesError as e:
        print(f"操作失败: {e}", file=sys.stderr)
        return 2

    try:
        write_models_to_toml(
            target,
            new_profiles,
            active=next_active,
            subagent=next_subagent,
            planner=next_planner,
        )
    except Exception as e:
        print(f"写入 {target} 失败: {e}", file=sys.stderr)
        return 2
    print(
        f"[models] {action} ok | active={next_active} "
        f"profiles={len(new_profiles)} file={target}",
    )
    if action == "use" and next_active:
        from cai_agent.tui_session_strip import build_profile_switched_line

        print(build_profile_switched_line(str(next_active)))
    return 0


def _default_global_config_path() -> Path:
    """`cai-agent init --global` 写入的默认用户级配置位置。

    Windows 优先 ``%APPDATA%\\cai-agent\\cai-agent.toml``（更符合 Windows 习惯，
    也能被 :func:`cai_agent.config._user_config_candidates` 最先命中）；
    其它平台使用 ``~/.config/cai-agent/cai-agent.toml``。
    """
    if os.name == "nt":
        appdata = os.getenv("APPDATA")
        if isinstance(appdata, str) and appdata.strip():
            return Path(appdata).expanduser() / "cai-agent" / "cai-agent.toml"
    xdg = os.getenv("XDG_CONFIG_HOME")
    if isinstance(xdg, str) and xdg.strip():
        return Path(xdg).expanduser() / "cai-agent" / "cai-agent.toml"
    return Path.home() / ".config" / "cai-agent" / "cai-agent.toml"


def _install_support_docs() -> dict[str, str]:
    return {
        "onboarding": "docs/ONBOARDING.zh-CN.md",
        "docs_index": "docs/README.zh-CN.md",
        "changelog_zh": "CHANGELOG.zh-CN.md",
        "changelog_en": "CHANGELOG.md",
    }


def _init_next_steps(*, preset: str) -> list[str]:
    steps = [
        "cai-agent doctor",
        'cai-agent run "用一句话描述当前工作区用途"',
    ]
    if preset == "starter":
        steps.insert(1, "cai-agent models use local-lmstudio")
    return steps


def _cmd_init(
    *,
    force: bool,
    is_global: bool = False,
    preset: str = "default",
    json_output: bool = False,
) -> int:
    if is_global:
        dest = _default_global_config_path()
    else:
        dest = Path.cwd() / "cai-agent.toml"
    preset_norm = "starter" if (preset or "").strip().lower() == "starter" else "default"
    if dest.exists() and not force:
        if json_output:
            print(
                json.dumps(
                    {
                        "schema_version": "init_cli_v1",
                        "ok": False,
                        "error": "config_exists",
                        "config_path": str(dest.resolve()),
                        "global": is_global,
                        "preset": preset_norm,
                        "support_docs": _install_support_docs(),
                        "message": f"配置已存在: {dest}；若需覆盖请添加 --force",
                    },
                    ensure_ascii=False,
                ),
            )
        else:
            label = "用户级全局" if is_global else "当前目录"
            print(
                f"{label} 配置已存在: {dest}；若需覆盖请添加 --force",
                file=sys.stderr,
            )
        # S1-03: logical / precondition failure → exit 2 (not 1).
        return 2
    tpl_name = (
        "templates/cai-agent.starter.toml"
        if preset_norm == "starter"
        else "templates/cai-agent.example.toml"
    )
    try:
        tpl = resources.files("cai_agent").joinpath(tpl_name)
        data = tpl.read_bytes()
    except Exception as e:
        if json_output:
            print(
                json.dumps(
                    {
                        "schema_version": "init_cli_v1",
                        "ok": False,
                        "error": "template_read_failed",
                        "template": tpl_name,
                        "message": str(e),
                    },
                    ensure_ascii=False,
                ),
            )
        else:
            print(f"读取内置配置模板失败: {e}", file=sys.stderr)
        return 2
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        if json_output:
            print(
                json.dumps(
                    {
                        "schema_version": "init_cli_v1",
                        "ok": False,
                        "error": "mkdir_failed",
                        "path": str(dest.parent),
                        "message": str(e),
                    },
                    ensure_ascii=False,
                ),
            )
        else:
            print(f"创建目录失败 {dest.parent}: {e}", file=sys.stderr)
        return 2
    dest.write_bytes(data)
    if json_output:
        print(
            json.dumps(
                {
                    "schema_version": "init_cli_v1",
                    "ok": True,
                    "config_path": str(dest.resolve()),
                    "preset": preset_norm,
                    "global": is_global,
                    "support_docs": _install_support_docs(),
                    "next_steps": _init_next_steps(preset=preset_norm),
                },
                ensure_ascii=False,
            ),
        )
        return 0
    print(f"已生成 {dest.resolve()}")
    if is_global:
        print(
            "[--global] 任意目录运行 `cai-agent ui` 在没有项目级 cai-agent.toml 时都会读它；"
            "项目级 ./cai-agent.toml（或 --config / CAI_CONFIG）仍具有更高优先级。",
        )
    print(
        "下一步: 编辑其中 [llm] 或 [[models.profile]] 指向你的 API；"
        "然后执行 cai-agent doctor 与 cai-agent run \"…\"。",
    )
    print("建议顺序:")
    for step in _init_next_steps(preset=preset_norm):
        print(f"- {step}")
    print(
        "多模型: cai-agent models list；新增条目: "
        "cai-agent models add --preset lmstudio|ollama|vllm|openrouter|gateway|zhipu …",
    )
    if preset_norm == "starter":
        print(
            "starter 模板已启用多条 profile；设置密钥后可用 "
            "`cai-agent models use local-lmstudio`（或其它 id）切换。",
        )
    print(
        "说明: docs/ONBOARDING.zh-CN.md（首次使用） | "
        "docs/README.zh-CN.md（文档入口） | "
        "CHANGELOG.zh-CN.md / CHANGELOG.md（升级差异）。",
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--config",
        default=None,
        metavar="PATH",
        help="TOML 配置文件（未指定时可用环境变量 CAI_CONFIG 或当前目录 cai-agent.toml）",
    )
    common.add_argument(
        "--model",
        default=None,
        metavar="MODEL_ID",
        help="临时覆盖当前模型（优先级高于配置文件/环境变量）",
    )

    parser = argparse.ArgumentParser(prog="cai-agent")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser(
        "init",
        help="在当前目录生成 cai-agent.toml（来自内置示例），或用 --global 写到用户目录",
    )
    init_p.add_argument(
        "--force",
        action="store_true",
        help="覆盖已存在的 cai-agent.toml",
    )
    init_p.add_argument(
        "--global",
        action="store_true",
        dest="global_flag",
        help=(
            "写入用户级全局位置（Windows: %%APPDATA%%\\cai-agent\\cai-agent.toml；"
            "其它: ~/.config/cai-agent/cai-agent.toml）；"
            "项目级 ./cai-agent.toml 优先级仍更高"
        ),
    )
    init_p.add_argument(
        "--preset",
        default="default",
        dest="init_preset",
        choices=["default", "starter"],
        help=(
            "default: 仅 [llm]，默认指向本机 LM Studio。"
            "starter: 预置 LM Studio / Ollama / vLLM / OpenRouter / 智谱 GLM / 自建 OpenAI 兼容网关等多条 [[models.profile]]"
        ),
    )
    init_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="stdout 仅输出 init_cli_v1 JSON（成功或 config_exists 等错误）",
    )

    ecc_p = sub.add_parser(
        "ecc",
        help="ECC：rules/skills/hooks 资产目录约定与最小脚手架（跨 harness 导出见 export）",
    )
    ecc_p.add_argument(
        "--config",
        default=None,
        help="配置文件路径（可选；与全局 --config 解析规则一致）",
    )
    ecc_p.add_argument(
        "-w",
        "--workspace",
        default=None,
        help="工作区根目录（可选；layout 用于覆盖展示根，scaffold 为写入根）",
    )
    ecc_sub = ecc_p.add_subparsers(dest="ecc_action", required=True)
    ecc_layout_p = ecc_sub.add_parser(
        "layout",
        help="输出 ecc_asset_layout_v1（约定路径与 hooks 解析结果）",
    )
    ecc_layout_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="stdout 仅输出一行 JSON",
    )
    ecc_scaffold_p = ecc_sub.add_parser(
        "scaffold",
        help="从内置模板创建最小 rules/skills/hooks 样例（不覆盖已有文件）",
    )
    ecc_scaffold_p.add_argument("--json", action="store_true", dest="json_output")
    ecc_scaffold_p.add_argument(
        "--dry-run",
        action="store_true",
        dest="ecc_scaffold_dry_run",
        help="只打印将创建的路径，不写盘",
    )

    plan_p = sub.add_parser(
        "plan",
        parents=[common],
        help="仅生成实现计划草案（不实际调用工具），类似 Claude Code 的 Plan 模式",
    )
    plan_p.add_argument(
        "goal",
        nargs="+",
        help="要规划的任务描述（可多个词）",
    )
    plan_p.add_argument(
        "-w",
        "--workspace",
        default=None,
        help="工作区根目录（默认当前目录或环境变量 CAI_WORKSPACE）",
    )
    plan_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以一行 JSON 输出规划结果（便于脚本或其他 Agent 调用）",
    )
    plan_p.add_argument(
        "--write-plan",
        default=None,
        metavar="PATH",
        help="将计划写入文件（.md 文本）；与控制台输出内容相同",
    )

    run_p = sub.add_parser(
        "run",
        parents=[common],
        help="根据自然语言目标运行本地 Agent",
    )
    run_p.add_argument(
        "goal",
        nargs="+",
        help="任务描述（可多个词）",
    )
    run_p.add_argument(
        "-w",
        "--workspace",
        default=None,
        help="工作区根目录（默认当前目录或环境变量 CAI_WORKSPACE）",
    )
    run_p.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="只打印最终回答，不打印过程",
    )
    run_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="将 answer 与迭代次数等以一行 JSON 打印到 stdout（隐含不打印过程日志）",
    )
    run_p.add_argument(
        "--save-session",
        default=None,
        metavar="PATH",
        help="将本轮运行后的会话写入 JSON 文件",
    )
    run_p.add_argument(
        "--load-session",
        default=None,
        metavar="PATH",
        help="先从 JSON 会话恢复 messages，再追加本次 goal 继续运行",
    )
    run_p.add_argument(
        "--plan-file",
        default=None,
        metavar="PATH",
        help="将计划文件内容注入到本次 goal 之前（最小 run 联动）",
    )
    run_p.add_argument(
        "--auto-approve",
        action="store_true",
        help="permissions=ask 时等价于设置 CAI_AUTO_APPROVE=1（本进程内）",
    )

    doctor_p = sub.add_parser(
        "doctor",
        parents=[common],
        help="打印当前解析后的配置与工作区诊断信息（API Key 打码）",
    )
    doctor_p.add_argument(
        "-w",
        "--workspace",
        default=None,
        help="覆盖工作区目录（默认来自配置 / 当前目录）",
    )
    doctor_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以一行 JSON 输出诊断（schema_version=doctor_v1）",
    )
    doctor_p.add_argument(
        "--fail-on-missing-api-key",
        action="store_true",
        help="非 mock 且 API Key 为空时 exit 2（可与 --json 同用于 CI）",
    )

    cont_p = sub.add_parser(
        "continue",
        parents=[common],
        help="基于历史会话 JSON 继续提问（等价于 run --load-session）",
    )
    cont_p.add_argument(
        "session",
        help="历史会话 JSON 文件路径（通常由 --save-session 生成）",
    )
    cont_p.add_argument(
        "goal",
        nargs="+",
        help="继续追问的任务描述",
    )
    cont_p.add_argument(
        "-w",
        "--workspace",
        default=None,
        help="工作区根目录（默认当前目录或环境变量 CAI_WORKSPACE）",
    )
    cont_p.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="只打印最终回答，不打印过程",
    )
    cont_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="将 answer 与迭代次数等以一行 JSON 打印到 stdout",
    )
    cont_p.add_argument(
        "--save-session",
        default=None,
        metavar="PATH",
        help="将继续运行后的会话写入 JSON 文件",
    )
    cont_p.add_argument(
        "--plan-file",
        default=None,
        metavar="PATH",
        help="将计划文件内容注入到本次 goal 之前",
    )
    cont_p.add_argument(
        "--auto-approve",
        action="store_true",
        help="permissions=ask 时设置 CAI_AUTO_APPROVE=1（本进程内）",
    )

    # models 子命令专用父 parser：仅提供 --config，避免与 `common.--model` 冲突。
    # 注意：--config 只挂在 `models` 顶层上，**不**挂在各子动作上；否则子动作会再
    # 定义一份 --config=None 覆盖掉外层值（argparse 的 parents 语义）。
    models_parent = argparse.ArgumentParser(add_help=False)
    models_parent.add_argument(
        "--config", default=None, metavar="PATH",
        help="TOML 配置文件（未指定时可用环境变量 CAI_CONFIG 或当前目录 cai-agent.toml）",
    )

    models_p = sub.add_parser(
        "models",
        parents=[models_parent],
        help="模型 profile 管理：list/use/add/edit/rm/ping/fetch/capabilities/onboarding/suggest/route/routing-test",
    )
    models_sub = models_p.add_subparsers(dest="models_action", required=False)

    _ml = models_sub.add_parser("list", help="列出已配置的模型 profile")
    _ml.add_argument("--json", action="store_true", dest="json_output")
    _ml.add_argument(
        "--providers",
        action="store_true",
        dest="models_list_providers",
        help="列出内置 Provider Registry（预设 API 面；与 --json 联用输出 provider_registry_v1）",
    )

    _mu = models_sub.add_parser("use", help="切换激活 profile 并写回配置")
    _mu.add_argument("id", help="profile id")

    _ma = models_sub.add_parser("add", help="新增一个 profile")
    _ma.add_argument("--id", required=True, dest="pid")
    _ma.add_argument(
        "--preset",
        default=None,
        choices=sorted(PRESETS.keys()),
    )
    _ma.add_argument("--provider", default=None)
    _ma.add_argument("--base-url", default=None, dest="base_url")
    _ma.add_argument("--model", dest="model_field", default=None)
    _ma.add_argument("--api-key-env", default=None, dest="api_key_env")
    _ma.add_argument("--api-key", default=None, dest="api_key_literal")
    _ma.add_argument("--temperature", type=float, default=None)
    _ma.add_argument("--timeout-sec", type=float, default=None, dest="timeout_sec")
    _ma.add_argument("--anthropic-version", default=None, dest="anthropic_version")
    _ma.add_argument("--max-tokens", type=int, default=None, dest="max_tokens")
    _ma.add_argument("--notes", default=None)
    _ma.add_argument(
        "--set-active", action="store_true", dest="set_active",
        help="添加后立即设为 active",
    )

    _me = models_sub.add_parser("edit", help="编辑现有 profile 字段")
    _me.add_argument("id", help="profile id")
    _me.add_argument("--provider", default=None)
    _me.add_argument("--base-url", default=None, dest="base_url")
    _me.add_argument("--model", dest="model_field", default=None)
    _me.add_argument("--api-key-env", default=None, dest="api_key_env")
    _me.add_argument("--api-key", default=None, dest="api_key_literal")
    _me.add_argument("--temperature", type=float, default=None)
    _me.add_argument("--timeout-sec", type=float, default=None, dest="timeout_sec")
    _me.add_argument("--anthropic-version", default=None, dest="anthropic_version")
    _me.add_argument("--max-tokens", type=int, default=None, dest="max_tokens")
    _me.add_argument("--notes", default=None)

    _mr = models_sub.add_parser("rm", help="删除一个 profile")
    _mr.add_argument("id", help="profile id")

    _mp = models_sub.add_parser("ping", help="对 profile 做 /models 健康检查")
    _mp.add_argument("id", nargs="?", default=None, help="profile id（缺省 ping 全部）")
    _mp.add_argument(
        "--preset",
        default=None,
        dest="ping_preset",
        choices=sorted(PRESETS.keys()),
        help="不写盘：用内置 preset 临时构造 profile 做探活（与 positional id 互斥）",
    )
    _mp.add_argument("--json", action="store_true", dest="json_output")
    _mp.add_argument("--timeout-sec", type=float, default=10.0, dest="timeout_sec")
    _mp.add_argument(
        "--chat-smoke",
        action="store_true",
        dest="chat_smoke",
        help="在 /models 探活成功后追加一次最小 chat smoke（会消耗 token；失败时 exit 2）",
    )
    _mp.add_argument(
        "--chat-smoke-prompt",
        default="Reply with OK.",
        dest="chat_smoke_prompt",
        help="--chat-smoke 使用的最小提示词",
    )
    _mp.add_argument(
        "--fail-on-any-error",
        action="store_true",
        dest="fail_on_ping_error",
        help="显式门禁别名：与默认一致，任一 status 非 OK 时 exit 2（兼容旧脚本）",
    )

    _mf = models_sub.add_parser(
        "fetch",
        help="调用当前激活 profile 的 /v1/models 端点列出模型（原 `cai-agent models` 行为）",
    )
    _mf.add_argument("--json", action="store_true", dest="json_output")

    _mcaps = models_sub.add_parser(
        "capabilities",
        help="输出 profile/model 能力元数据（context/tool/vision/json/reasoning/local/cost）",
    )
    _mcaps.add_argument("id", nargs="?", default=None, help="profile id（缺省输出全部）")
    _mcaps.add_argument("--json", action="store_true", dest="json_output")

    _mon = models_sub.add_parser(
        "onboarding",
        help="输出 add -> capabilities -> ping -> chat-smoke -> use -> routing-test 接入命令链",
    )
    _mon.add_argument("--id", required=True, dest="onboarding_profile_id", help="要创建/验证的 profile id")
    _mon.add_argument("--preset", required=True, dest="onboarding_preset", help="provider preset，如 openai/openrouter/lmstudio")
    _mon.add_argument("--model", default=None, dest="onboarding_model", help="可选模型名")
    _mon.add_argument("--no-set-active", action="store_true", dest="onboarding_no_set_active")
    _mon.add_argument("--json", action="store_true", dest="json_output")

    _mrs = models_sub.add_parser(
        "suggest",
        help="根据任务描述关键词启发式推荐适合的 profile（基于 provider / notes 字段）",
    )
    _mrs.add_argument(
        "task_description",
        nargs="+",
        help="任务描述文本（例如：'安全审查 Python 代码' / '快速草稿'）",
    )
    _mrs.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="输出 models_suggest_v1 JSON",
    )

    _mrtx = models_sub.add_parser(
        "routing-test",
        help="模拟 [models.routing] 首条命中（仅 --json；不写配置）",
    )
    _mrtx.add_argument(
        "--role",
        default="active",
        dest="routing_test_role",
        choices=("active", "subagent", "planner"),
        help="当前调用角色（与路由 rules 的 roles 对齐）",
    )
    _mrtx.add_argument(
        "--goal",
        default="",
        dest="routing_test_goal",
        help="用于 goal_regex / goal_substring 匹配的目标文本",
    )
    _mrtx.add_argument(
        "--total-tokens-used",
        type=int,
        default=0,
        dest="routing_test_total_tokens",
        help="与 [cost].budget_max_tokens 组合模拟剩余预算（成本条件规则）",
    )
    _mrtx.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="输出 models_routing_test_v1 JSON（含 explain）；省略则输出 effective_profile + 中文摘要",
    )

    _mrt = models_sub.add_parser(
        "route",
        help="写回 [models] 的 subagent / planner 路由（不改 active、不改 profile 表体）",
    )
    _mrt.add_argument(
        "--subagent",
        default=None,
        metavar="ID",
        help="子代理使用的 profile id；与 --unset-subagent 互斥",
    )
    _mrt.add_argument(
        "--planner",
        default=None,
        metavar="ID",
        help="规划器使用的 profile id；与 --unset-planner 互斥",
    )
    _mrt.add_argument(
        "--unset-subagent",
        action="store_true",
        dest="unset_subagent",
        help="清除 subagent 路由（子代理回退到 active）",
    )
    _mrt.add_argument(
        "--unset-planner",
        action="store_true",
        dest="unset_planner",
        help="清除 planner 路由",
    )

    _mrwiz = models_sub.add_parser(
        "route-wizard",
        help="生成可追加的 [[models.route]] TOML 片段（--json；可选 --dry-run 仅预览）",
    )
    _mrwiz.add_argument("--use-profile", required=True, dest="route_wizard_profile")
    _mrwiz.add_argument("--match-phase", default=None, dest="route_wizard_phase")
    _mrwiz.add_argument("--match-task-kind", default=None, dest="route_wizard_task_kind")
    _mrwiz.add_argument("--match-tokens-gt", type=int, default=None, dest="route_wizard_tokens_gt")
    _mrwiz.add_argument("--dry-run", action="store_true", dest="route_wizard_dry_run")
    _mrwiz.add_argument("--json", action="store_true", dest="json_output")

    # 顶层兼容：不带子命令时等价于 list。
    models_p.add_argument("--json", action="store_true", dest="json_output")

    sub.add_parser(
        "model",
        parents=[models_parent],
        help="Hermes 别名：TTY 下打开模型面板；否则输出 models suggest 启发式 JSON",
    )

    runtime_p = sub.add_parser(
        "runtime",
        parents=[common],
        help="运行后端：列出可用 backend 或对指定 backend 做 echo 自检（H1-RT）",
    )
    runtime_sub = runtime_p.add_subparsers(dest="runtime_action", required=True)
    runtime_list_p = runtime_sub.add_parser("list", help="列出内置运行后端注册表")
    runtime_list_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="输出 runtime_registry_v1 JSON",
    )
    runtime_test_p = runtime_sub.add_parser("test", help="在指定 backend 上执行 echo 自检")
    runtime_test_p.add_argument(
        "--backend",
        default="local",
        dest="runtime_backend_name",
        help="backend 名称（默认 local）",
    )
    runtime_test_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="输出 runtime_test_v1 JSON",
    )

    plugins_p = sub.add_parser(
        "plugins",
        parents=[common],
        help="输出当前项目插件化扩展面清单（skills/commands/agents/hooks/rules/mcp）",
    )
    plugins_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以 JSON 对象输出扩展面信息",
    )
    plugins_p.add_argument(
        "--fail-on-min-health",
        type=int,
        default=None,
        metavar="SCORE",
        help="可选：扩展面 health_score < SCORE（0~100）时 exit 2，便于 CI",
    )
    plugins_p.add_argument(
        "--with-compat-matrix",
        action="store_true",
        dest="plugins_with_compat_matrix",
        help="与 --json 联用：附加 plugin_compat_matrix_v1（跨 harness 兼容矩阵）",
    )
    plugins_p.add_argument(
        "--compat-check",
        action="store_true",
        dest="plugins_compat_check",
        help=(
            "ECC-03b：附加 plugin_compat_matrix_check_v1 自检结果；"
            "与 --json 联用时放在 compat_check 字段，否则打印摘要；"
            "检查失败（missing / mismatches）时 exit 2"
        ),
    )
    skills_p = sub.add_parser(
        "skills",
        parents=[common],
        help="Skills：hub（manifest/suggest/serve/fetch/install）+ improve / usage / lint / promote / revert",
    )
    skills_sub = skills_p.add_subparsers(dest="skills_action", required=True)
    skills_hub_p = skills_sub.add_parser("hub", help="Hub 分发相关子命令")
    skills_hub_sub = skills_hub_p.add_subparsers(dest="skills_hub_action", required=True)
    skills_hub_manifest_p = skills_hub_sub.add_parser(
        "manifest",
        help="导出 skills/ 下可分发技能文件清单（JSON）",
    )
    skills_hub_manifest_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="输出 skills_hub_manifest_v2 JSON",
    )
    skills_hub_suggest_p = skills_hub_sub.add_parser(
        "suggest",
        help="技能自进化 MVP：根据任务文本生成可落盘的技能草稿路径与预览（可选 --write）",
    )
    skills_hub_suggest_p.add_argument(
        "skills_suggest_goal",
        metavar="GOAL",
        nargs="+",
        help="已完成的任务描述（用于命名草稿文件；建议放在选项前）",
    )
    skills_hub_suggest_p.add_argument(
        "--write",
        action="store_true",
        help="在 suggested_path 不存在时写入预览 Markdown",
    )
    skills_hub_suggest_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="输出 skills_evolution_suggest_v1 JSON",
    )
    # §25 补齐：skills hub serve
    skills_hub_serve_p = skills_hub_sub.add_parser(
        "serve",
        help="启动 Skills Hub HTTP 分发服务（GET /manifest、GET /skill/<name>）",
    )
    skills_hub_serve_p.add_argument(
        "--host",
        default="127.0.0.1",
        help="监听主机（默认 127.0.0.1）",
    )
    skills_hub_serve_p.add_argument(
        "--port",
        type=int,
        default=7891,
        help="监听端口（默认 7891）",
    )
    skills_hub_serve_p.add_argument(
        "--timeout",
        type=float,
        default=None,
        dest="serve_timeout",
        metavar="SECONDS",
        help="服务超时秒数（默认：永久运行直到 Ctrl+C）",
    )
    skills_hub_serve_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="停止后以 JSON 输出结果",
    )
    skills_hub_fetch_p = skills_hub_sub.add_parser(
        "fetch",
        help="从远程 URL 拉取 agentskills 兼容 manifest JSON（stdout 原样或 --json 包装）",
    )
    skills_hub_fetch_p.add_argument(
        "skills_hub_fetch_url",
        metavar="URL",
        help="manifest.json 或兼容端点 URL",
    )
    skills_hub_fetch_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="输出 skills_hub_fetch_v1 JSON（含 remote 原文）",
    )
    skills_hub_list_remote_p = skills_hub_sub.add_parser(
        "list-remote",
        help="索引远程 manifest 的 entries[]（skills_hub_list_remote_v1）；可选 --sync-mirror",
    )
    skills_hub_list_remote_p.add_argument(
        "skills_hub_list_remote_url",
        metavar="URL",
        help="manifest.json 或兼容端点 URL",
    )
    skills_hub_list_remote_p.add_argument(
        "--sync-mirror",
        action="store_true",
        dest="skills_hub_sync_mirror",
        help="将摘要追加到 .cai/skills-registry-mirror.jsonl",
    )
    skills_hub_list_remote_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="stdout 输出 skills_hub_list_remote_v1 JSON",
    )
    skills_hub_install_p = skills_hub_sub.add_parser(
        "install",
        help="按 skills_hub_manifest_v2 将条目复制到 .cursor/skills（可选 --only 过滤 name）",
    )
    skills_hub_install_p.add_argument(
        "--manifest",
        required=False,
        default=None,
        metavar="PATH",
        help="skills_hub_manifest_v2 JSON 文件路径（与 --from 二选一）",
    )
    skills_hub_install_p.add_argument(
        "--from",
        dest="hub_install_from_url",
        default=None,
        metavar="URL",
        help="远程 manifest URL（GET JSON；与 --manifest 二选一）",
    )
    skills_hub_install_p.add_argument(
        "--only",
        default="",
        help="逗号分隔的 name 列表；空表示安装 manifest 中全部条目",
    )
    skills_hub_install_p.add_argument(
        "--dest",
        default=".cursor/skills",
        help="相对工作区根的目标目录（默认 .cursor/skills）",
    )
    skills_hub_install_p.add_argument(
        "--dry-run",
        action="store_true",
        help="仅输出计划，不写入文件",
    )
    skills_hub_install_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="stdout 输出 skills_hub_pack_install_v1 JSON",
    )
    skills_improve_p = skills_sub.add_parser(
        "improve",
        help="技能自改进：在 skills/<SKILL_ID> 追加「历史改进」节（默认预览；--apply 写入）",
    )
    skills_improve_p.add_argument(
        "skills_improve_skill_id",
        metavar="SKILL_ID",
        help="相对 skills/ 的路径，如 foo.md 或 sub/bar.md",
    )
    skills_improve_p.add_argument(
        "--apply",
        action="store_true",
        dest="skills_improve_apply",
        help="写入文件（默认 dry-run，仅输出 JSON/预览）",
    )
    skills_improve_p.add_argument(
        "--llm",
        action="store_true",
        dest="skills_improve_llm",
        help="结合用量记录调用模型生成摘要（需有效 API 配置）",
    )
    skills_improve_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="输出 skills_evolution_runtime_v1 JSON",
    )
    skills_usage_p = skills_sub.add_parser(
        "usage",
        help="聚合 .cai/skill-usage.jsonl 中的技能加载命中统计",
    )
    skills_usage_p.add_argument(
        "--skill",
        default="",
        dest="skills_usage_skill",
        metavar="ID",
        help="仅统计某一 skill_id（相对 skills/）",
    )
    skills_usage_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="输出 skills_usage_aggregate_v1 JSON",
    )
    skills_usage_p.add_argument(
        "--trend",
        type=int,
        default=None,
        dest="skills_usage_trend_days",
        metavar="DAYS",
        help="与 --json 同用：输出 skills_usage_trend_v1（按 UTC 日历日聚合，默认 14 天）",
    )
    skills_revert_p = skills_sub.add_parser(
        "revert",
        help="按 hist_id 回滚 skills/ 中一次「历史改进」追加块（默认预览；--apply 写盘）",
    )
    skills_revert_p.add_argument(
        "skills_revert_skill_id",
        metavar="SKILL_ID",
        help="相对 skills/ 的路径，如 foo.md",
    )
    skills_revert_p.add_argument(
        "--to",
        required=True,
        dest="skills_revert_hist_id",
        metavar="HIST_ID",
        help="<!-- cai:hist id=... --> 中的 UUID",
    )
    skills_revert_p.add_argument(
        "--apply",
        action="store_true",
        dest="skills_revert_apply",
        help="执行回滚写盘",
    )
    skills_revert_p.add_argument("--json", action="store_true", dest="json_output")
    skills_promote_p = skills_sub.add_parser(
        "promote",
        help="将 skills/_evolution_*.md 草稿提升为正式 skills/*.md（写盘后 skills lint，失败回滚）",
    )
    skills_promote_p.add_argument(
        "skills_promote_src",
        metavar="SRC",
        help="相对 skills/ 的草稿路径，如 _evolution_my-goal.md",
    )
    skills_promote_p.add_argument(
        "--to",
        required=False,
        default="",
        dest="skills_promote_to",
        help="目标文件名（相对 skills/）；缺省时仅 --auto 模式有意义",
    )
    skills_promote_p.add_argument(
        "--auto",
        action="store_true",
        dest="skills_promote_auto",
        help="按 skill-usage 命中阈值自动 promote（CAI_SKILLS_PROMOTE_THRESHOLD，默认 5）",
    )
    skills_promote_p.add_argument(
        "--threshold",
        type=int,
        default=None,
        dest="skills_promote_threshold",
        help="覆盖 --auto 的命中阈值",
    )
    skills_promote_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="输出 skills_promote_v1 / skills_promote_auto_v1 JSON",
    )
    skills_lint_p = skills_sub.add_parser(
        "lint",
        help="校验 skills/ 下文件的 agentskills 风格 frontmatter（skills_lint_v1）",
    )
    skills_lint_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="输出 skills_lint_v1 JSON",
    )
    cmd_list_p = sub.add_parser(
        "commands",
        parents=[common],
        help="列出仓库 commands/ 下可用命令模板",
    )
    cmd_list_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以 JSON 数组输出命令名称",
    )
    cmd_run_p = sub.add_parser(
        "command",
        parents=[common],
        help="按命令模板（commands/<name>.md）执行任务",
    )
    cmd_run_p.add_argument(
        "name",
        help="命令名（如 plan、code-review、verify）",
    )
    cmd_run_p.add_argument(
        "goal",
        nargs="+",
        help="任务描述（可多个词）",
    )
    cmd_run_p.add_argument(
        "-w",
        "--workspace",
        default=None,
        help="工作区根目录（默认当前目录或环境变量 CAI_WORKSPACE）",
    )
    cmd_run_p.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="只打印最终回答，不打印过程",
    )
    cmd_run_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="将 answer 与迭代次数等以一行 JSON 打印到 stdout",
    )
    cmd_run_p.add_argument(
        "--save-session",
        default=None,
        metavar="PATH",
        help="将本轮运行后的会话写入 JSON 文件",
    )
    cmd_run_p.add_argument(
        "--plan-file",
        default=None,
        metavar="PATH",
        help="将计划文件内容注入到本次 goal 之前",
    )
    cmd_run_p.add_argument(
        "--auto-approve",
        action="store_true",
        help="permissions=ask 时设置 CAI_AUTO_APPROVE=1（本进程内）",
    )
    fix_build_p = sub.add_parser(
        "fix-build",
        parents=[common],
        help="快捷执行 /fix-build 命令模板（等价于 command fix-build）",
    )
    fix_build_p.add_argument(
        "goal",
        nargs="+",
        help="构建失败修复目标描述（可多个词）",
    )
    fix_build_p.add_argument(
        "-w",
        "--workspace",
        default=None,
        help="工作区根目录（默认当前目录或环境变量 CAI_WORKSPACE）",
    )
    fix_build_p.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="只打印最终回答，不打印过程",
    )
    fix_build_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="将 answer 与迭代次数等以一行 JSON 打印到 stdout",
    )
    fix_build_p.add_argument(
        "--save-session",
        default=None,
        metavar="PATH",
        help="将本轮运行后的会话写入 JSON 文件",
    )
    fix_build_p.add_argument(
        "--plan-file",
        default=None,
        metavar="PATH",
        help="将计划文件内容注入到本次 goal 之前",
    )
    fix_build_p.add_argument(
        "--auto-approve",
        action="store_true",
        help="permissions=ask 时设置 CAI_AUTO_APPROVE=1（本进程内）",
    )
    fix_build_p.add_argument(
        "--no-gate",
        action="store_true",
        help="修复后不自动执行 quality-gate",
    )
    ag_list_p = sub.add_parser(
        "agents",
        parents=[common],
        help="列出仓库 agents/ 下可用子代理模板",
    )
    ag_list_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以 JSON 数组输出子代理名称",
    )
    ag_run_p = sub.add_parser(
        "agent",
        parents=[common],
        help="按子代理模板（agents/<name>.md）执行任务",
    )
    ag_run_p.add_argument(
        "name",
        help="子代理名（如 planner、code-reviewer、security-reviewer）",
    )
    ag_run_p.add_argument(
        "goal",
        nargs="+",
        help="任务描述（可多个词）",
    )
    ag_run_p.add_argument(
        "-w",
        "--workspace",
        default=None,
        help="工作区根目录（默认当前目录或环境变量 CAI_WORKSPACE）",
    )
    ag_run_p.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="只打印最终回答，不打印过程",
    )
    ag_run_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="将 answer 与迭代次数等以一行 JSON 打印到 stdout",
    )
    ag_run_p.add_argument(
        "--save-session",
        default=None,
        metavar="PATH",
        help="将本轮运行后的会话写入 JSON 文件",
    )
    ag_run_p.add_argument(
        "--plan-file",
        default=None,
        metavar="PATH",
        help="将计划文件内容注入到本次 goal 之前",
    )
    ag_run_p.add_argument(
        "--auto-approve",
        action="store_true",
        help="permissions=ask 时设置 CAI_AUTO_APPROVE=1（本进程内）",
    )
    mcp_p = sub.add_parser(
        "mcp-check",
        parents=[common],
        help="检查 MCP Bridge 连通性并打印可用工具",
        epilog=(
            "WebSearch·Notebook 预设：--preset websearch | notebook | websearch/notebook。"
            " 最短：--preset websearch/notebook --list-only ；"
            "--preset websearch --print-template 。"
            " 文档：docs/WEBSEARCH_NOTEBOOK_MCP.zh-CN.md"
        ),
    )
    mcp_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以 JSON 输出检查结果",
    )
    mcp_p.add_argument(
        "--force",
        action="store_true",
        help="强制刷新工具列表（跳过本地缓存）",
    )
    mcp_p.add_argument(
        "--verbose",
        action="store_true",
        help="输出更多诊断信息（provider/model/耗时等）",
    )
    mcp_p.add_argument(
        "--tool",
        default=None,
        metavar="TOOL_NAME",
        help="额外调用一个 MCP 工具做真实探活",
    )
    mcp_p.add_argument(
        "--args",
        default="{}",
        metavar="JSON",
        help="与 --tool 配合使用的 JSON 参数，默认 {}",
    )
    mcp_p.add_argument(
        "--preset",
        choices=list(allowed_mcp_preset_choices()),
        default=None,
        help="按 WebSearch / Notebook 预设能力进行工具诊断；支持 websearch、notebook、websearch/notebook",
    )
    mcp_p.add_argument(
        "--list-only",
        action="store_true",
        help="仅做工具列表探测，不执行 --tool 探活",
    )
    mcp_p.add_argument(
        "--print-template",
        action="store_true",
        help="当使用 --preset 时输出可复制的 MCP 配置模板片段",
    )
    mcp_serve_p = sub.add_parser(
        "mcp-serve",
        parents=[common],
        help="MCP stdio 服务：initialize + tools/list（内置工具清单 MVP，Hermes H3）",
    )
    sess_p = sub.add_parser(
        "sessions",
        help="列出当前目录近期会话文件（默认 .cai-session-*.json）",
    )
    sess_p.add_argument(
        "--pattern",
        default=".cai-session*.json",
        help="匹配模式（相对当前目录）",
    )
    sess_p.add_argument(
        "--limit",
        type=int,
        default=20,
        help="最多显示条目数",
    )
    sess_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以 JSON 数组输出",
    )
    sess_p.add_argument(
        "--details",
        action="store_true",
        help="输出每个会话的摘要（消息数/工具调用数/最后回答预览）",
    )

    stats_p = sub.add_parser(
        "stats",
        help="汇总当前目录近期会话的耗时与工具调用等指标（基于保存的会话 JSON）",
    )
    stats_p.add_argument(
        "--pattern",
        default=".cai-session*.json",
        help="匹配模式（相对当前目录）",
    )
    stats_p.add_argument(
        "--limit",
        type=int,
        default=50,
        help="最多统计的会话文件数",
    )
    stats_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以 JSON 对象输出汇总结果",
    )
    insights_p = sub.add_parser(
        "insights",
        help="跨会话趋势洞察（近期模型/工具使用与异常会话）",
    )
    insights_p.add_argument(
        "--pattern",
        default=".cai-session*.json",
        help="匹配模式（相对当前目录）",
    )
    insights_p.add_argument(
        "--limit",
        type=int,
        default=200,
        help="最多扫描的会话文件数（按最近修改时间倒序）",
    )
    insights_p.add_argument(
        "--days",
        type=int,
        default=7,
        help="仅统计最近 N 天会话",
    )
    insights_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以 JSON 对象输出洞察结果",
    )
    insights_p.add_argument(
        "--fail-on-max-failure-rate",
        type=float,
        default=None,
        metavar="RATE",
        help="可选：窗口内 failure_rate >= RATE（0~1）时 exit 2，便于 CI",
    )
    insights_p.add_argument(
        "--cross-domain",
        action="store_true",
        dest="insights_cross_domain",
        help="需与 --json 同用：输出 insights_cross_domain_v1（按 UTC 日对齐的 recall/memory/schedule 趋势，S7-03）",
    )
    recall_p = sub.add_parser(
        "recall",
        help="跨会话检索：按关键词/正则匹配历史会话内容（Hermes-style recall）",
    )
    recall_p.add_argument(
        "--query",
        default="",
        metavar="TEXT",
        help="检索关键词（默认子串匹配）或正则表达式（--regex）；与 --evaluate 同用时可为空",
    )
    recall_p.add_argument(
        "--regex",
        action="store_true",
        default=False,
        help="将 --query 按正则表达式解释",
    )
    recall_p.add_argument(
        "--pattern",
        default=".cai-session*.json",
        help="匹配会话文件模式（相对当前目录）",
    )
    recall_p.add_argument(
        "--limit",
        type=int,
        default=50,
        help="最多扫描文件数（按最近修改时间倒序）",
    )
    recall_p.add_argument(
        "--days",
        type=int,
        default=30,
        help="仅检索最近 N 天会话",
    )
    recall_p.add_argument(
        "--sort",
        default="recent",
        choices=("recent", "density", "combined"),
        help="结果排序：recent=时间衰减混合（默认）；density=命中密度优先；combined=recency×density 与命中强度混合",
    )
    recall_p.add_argument(
        "--max-hits",
        type=int,
        default=20,
        help="最多返回命中条数",
    )
    recall_p.add_argument(
        "--max-matches",
        type=int,
        default=None,
        help="--max-hits 的兼容别名（若指定则覆盖 --max-hits）",
    )
    recall_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以 JSON 输出检索结果",
    )
    recall_p.add_argument(
        "--use-index",
        action="store_true",
        default=False,
        help="使用 `.cai-recall-index.json` 加速检索（需先运行 `recall-index build`）",
    )
    recall_p.add_argument(
        "--index-path",
        default=None,
        dest="index_path",
        help="索引文件路径（默认 .cai-recall-index.json）",
    )
    recall_p.add_argument(
        "--fts5",
        action="store_true",
        default=False,
        help="使用 SQLite FTS5 索引（需先 `recall-index build --engine fts5`）",
    )
    recall_p.add_argument(
        "--summarize",
        action="store_true",
        default=False,
        help="对 Top 结果生成启发式摘要（拼接 snippet，写入 summaries[]）",
    )
    recall_p.add_argument(
        "--summarize-top",
        type=int,
        default=5,
        metavar="N",
        help="与 --summarize 同用：最多摘要前 N 条会话（默认 5）",
    )
    recall_p.add_argument(
        "--case-sensitive",
        action="store_true",
        default=False,
        help="子串/正则匹配区分大小写（默认不区分）",
    )
    recall_p.add_argument(
        "--evaluate",
        action="store_true",
        default=False,
        help="不执行检索：输出 recall_evaluation_v1（基于 .cai/recall-audit.jsonl 的窗口统计）",
    )
    recall_p.add_argument(
        "--evaluate-days",
        type=int,
        default=14,
        dest="evaluate_days",
        help="与 --evaluate 同用：UTC 日历窗口天数（默认 14）",
    )
    recall_idx_p = sub.add_parser(
        "recall-index",
        help="构建/管理 recall 索引（加速跨会话检索）",
    )
    recall_idx_sub = recall_idx_p.add_subparsers(dest="recall_index_action", required=True)

    recall_idx_build = recall_idx_sub.add_parser("build", help="重建索引文件")
    recall_idx_build.add_argument("--pattern", default=".cai-session*.json")
    recall_idx_build.add_argument("--limit", type=int, default=200)
    recall_idx_build.add_argument("--days", type=int, default=30)
    recall_idx_build.add_argument(
        "--engine",
        choices=("legacy", "fts5"),
        default="legacy",
        help="索引引擎：legacy=JSON（默认）；fts5=SQLite FTS5（.cai-recall-fts5.sqlite）",
    )
    recall_idx_build.add_argument("--json", action="store_true", dest="json_output")
    recall_idx_build.add_argument("--index-path", default=None, dest="index_path")

    recall_idx_refresh = recall_idx_sub.add_parser(
        "refresh",
        help="增量刷新索引（mtime 未变则跳过解析；可加 --prune 清理缺失/过期条目）",
    )
    recall_idx_refresh.add_argument("--pattern", default=".cai-session*.json")
    recall_idx_refresh.add_argument("--limit", type=int, default=200)
    recall_idx_refresh.add_argument("--days", type=int, default=30)
    recall_idx_refresh.add_argument(
        "--prune",
        action="store_true",
        default=False,
        help="移除磁盘已不存在或超出 --days 窗口的索引条目",
    )
    recall_idx_refresh.add_argument("--json", action="store_true", dest="json_output")
    recall_idx_refresh.add_argument("--index-path", default=None, dest="index_path")

    recall_idx_search = recall_idx_sub.add_parser("search", help="通过索引执行检索")
    recall_idx_search.add_argument("--query", required=True)
    recall_idx_search.add_argument("--regex", action="store_true", default=False)
    recall_idx_search.add_argument("--days", type=int, default=30)
    recall_idx_search.add_argument("--max-hits", type=int, default=20)
    recall_idx_search.add_argument(
        "--sort",
        default="recent",
        choices=("recent", "density", "combined"),
        help="与 `recall` 一致的排序策略（默认 recent）",
    )
    recall_idx_search.add_argument("--json", action="store_true", dest="json_output")
    recall_idx_search.add_argument("--index-path", default=None, dest="index_path")

    recall_idx_bench = recall_idx_sub.add_parser(
        "benchmark",
        help="对比 recall 直扫与索引检索性能（同 query）",
    )
    recall_idx_bench.add_argument("--query", required=True)
    recall_idx_bench.add_argument("--regex", action="store_true", default=False)
    recall_idx_bench.add_argument("--days", type=int, default=30)
    recall_idx_bench.add_argument("--pattern", default=".cai-session*.json")
    recall_idx_bench.add_argument("--limit", type=int, default=200)
    recall_idx_bench.add_argument("--max-hits", type=int, default=20)
    recall_idx_bench.add_argument(
        "--sort",
        default="recent",
        choices=("recent", "density", "combined"),
        help="与 `recall` 一致的排序策略（默认 recent）",
    )
    recall_idx_bench.add_argument("--runs", type=int, default=3, help="基准重复次数（默认 3）")
    recall_idx_bench.add_argument(
        "--ensure-index",
        action="store_true",
        default=False,
        help="若索引不存在则自动先 build",
    )
    recall_idx_bench.add_argument("--json", action="store_true", dest="json_output")
    recall_idx_bench.add_argument("--index-path", default=None, dest="index_path")

    recall_idx_info = recall_idx_sub.add_parser("info", help="查看索引信息")
    recall_idx_info.add_argument("--json", action="store_true", dest="json_output")
    recall_idx_info.add_argument("--index-path", default=None, dest="index_path")

    recall_idx_clear = recall_idx_sub.add_parser("clear", help="删除索引文件")
    recall_idx_clear.add_argument("--json", action="store_true", dest="json_output")
    recall_idx_clear.add_argument("--index-path", default=None, dest="index_path")

    recall_idx_doctor = recall_idx_sub.add_parser(
        "doctor",
        help="索引健康检查：缺失文件、相对窗口过旧路径、schema 版本（S3-03）",
    )
    recall_idx_doctor.add_argument(
        "--fix",
        action="store_true",
        default=False,
        help="移除缺失/过旧/无效条目并写回索引（等价于 prune 索引侧）",
    )
    recall_idx_doctor.add_argument("--json", action="store_true", dest="json_output")
    recall_idx_doctor.add_argument("--index-path", default=None, dest="index_path")
    qg_p = sub.add_parser(
        "quality-gate",
        parents=[common],
        help="质量门禁：compile、pytest、可选 ruff/mypy/extra/security（见 [quality_gate]）",
    )
    qg_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以 JSON 输出质量门禁结果",
    )
    qg_p.add_argument(
        "-w",
        "--workspace",
        default=None,
        help="工作区根目录（默认当前目录或环境变量 CAI_WORKSPACE）",
    )
    qg_p.add_argument("--no-compile", action="store_true", help="跳过 compile 检查")
    qg_p.add_argument("--no-test", action="store_true", help="跳过 test 检查")
    qg_p.add_argument("--lint", action="store_true", help="启用 lint 检查（ruff）")
    qg_p.add_argument(
        "--typecheck",
        action="store_true",
        help="启用静态类型检查（python -m mypy，路径见 [quality_gate] typecheck_paths）",
    )
    qg_p.add_argument("--security-scan", action="store_true", help="在质量门禁中启用安全扫描")
    qg_p.add_argument(
        "--report-dir",
        default=None,
        metavar="DIR",
        help="写入 quality-gate.json / quality-gate.jsonl / quality-gate-junit.xml",
    )
    sec_p = sub.add_parser(
        "security-scan",
        parents=[common],
        help="执行轻量安全扫描（敏感信息模式 + 风险摘要）",
    )
    sec_p.add_argument(
        "-w",
        "--workspace",
        default=None,
        help="工作区根目录（默认当前目录或环境变量 CAI_WORKSPACE）",
    )
    sec_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以 JSON 输出扫描结果",
    )
    sec_p.add_argument(
        "--exclude-glob",
        action="append",
        default=[],
        dest="exclude_globs",
        help="附加忽略路径模式（可多次指定），如 --exclude-glob \"**/*.md\"",
    )
    sec_p.add_argument("--disable-aws", action="store_true", help="禁用 AKIA 规则")
    sec_p.add_argument("--disable-github", action="store_true", help="禁用 ghp_ 规则")
    sec_p.add_argument("--disable-openai", action="store_true", help="禁用 sk- 规则")
    sec_p.add_argument("--disable-anthropic", action="store_true", help="禁用 sk-ant- 规则（Anthropic key）")
    sec_p.add_argument("--disable-openrouter", action="store_true", help="禁用 sk-or- 规则（OpenRouter key）")
    sec_p.add_argument("--disable-private-key", action="store_true", help="禁用 BEGIN PRIVATE KEY 规则")
    sec_p.add_argument(
        "--disable-profile-plaintext-key",
        action="store_true",
        help="禁用 models.profile / [llm] 段 api_key 明文告警规则",
    )
    sec_p.add_argument(
        "--badge",
        action="store_true",
        dest="security_badge",
        help="追加输出 security_badge_v1 JSON（shields.io 兼容）到 stdout；与 --json 同用时追加在 JSON 行后",
    )

    pii_p = sub.add_parser(
        "pii-scan",
        parents=[common],
        help="PII/敏感信息专项扫描（信用卡、身份证、手机号、JWT 等）—— 面向 session/prompt/日志文件",
    )
    pii_p.add_argument(
        "target",
        nargs="?",
        default=None,
        help="扫描目标目录或文件（默认：当前工作区 .cai/ 目录，若不存在则为当前目录）",
    )
    pii_p.add_argument("--json", action="store_true", dest="json_output", help="以 JSON 输出结果")
    pii_p.add_argument(
        "--no-recursive",
        action="store_true",
        dest="no_recursive",
        help="不递归扫描子目录",
    )
    pii_p.add_argument(
        "--enable-email",
        action="store_true",
        dest="enable_email",
        help="启用邮箱地址规则（默认关闭，因低信噪比）",
    )
    pii_p.add_argument(
        "--enable-ipv4",
        action="store_true",
        dest="enable_ipv4",
        help="启用内网 IPv4 规则（默认关闭）",
    )
    pii_p.add_argument(
        "--fail-on-high",
        action="store_true",
        dest="fail_on_high",
        help="存在 high 级别发现时 exit 2",
    )
    pii_p.add_argument(
        "--exclude-glob",
        action="append",
        default=[],
        dest="exclude_globs",
        help="附加排除 glob（可多次指定）",
    )

    hooks_p = sub.add_parser(
        "hooks",
        parents=[common],
        help="项目 hooks.json 自检：列出条目或按事件预览/执行外部 command 钩子",
    )
    hooks_p.add_argument(
        "-w",
        "--workspace",
        default=None,
        help="工作区根目录（默认当前目录或环境变量 CAI_WORKSPACE）",
    )
    hooks_p.add_argument(
        "--hooks-dir",
        default=None,
        help="相对工作区根的 hooks 目录（默认依次尝试 hooks/ 与 .cai/hooks/）",
    )
    hooks_sub = hooks_p.add_subparsers(dest="hooks_action", required=True)
    hooks_list = hooks_sub.add_parser("list", help="列出 hooks.json 中全部条目及 profile/禁用 下的摘要")
    hooks_list.add_argument("--json", action="store_true", dest="json_output")
    hooks_run = hooks_sub.add_parser(
        "run-event",
        help="对指定事件运行（或仅预览）匹配的外部 command 钩子",
    )
    hooks_run.add_argument("event", help="事件名，如 observe_start / workflow_start")
    hooks_run.add_argument(
        "--dry-run",
        action="store_true",
        help="仅输出 planned/skipped/blocked 分类，不执行子进程",
    )
    hooks_run.add_argument(
        "--payload",
        default="{}",
        help="传给钩子的 JSON 对象字符串（写入 CAI_HOOK_PAYLOAD；默认 {}）",
    )
    hooks_run.add_argument("--json", action="store_true", dest="json_output")

    memory_p = sub.add_parser("memory", help="记忆管理命令")
    memory_sub = memory_p.add_subparsers(dest="memory_action", required=True)
    memory_extract = memory_sub.add_parser("extract", help="从会话提取记忆")
    memory_extract.add_argument("--pattern", default=".cai-session*.json")
    memory_extract.add_argument("--limit", type=int, default=10)
    memory_extract.add_argument(
        "--structured",
        action="store_true",
        dest="extract_structured",
        help="可选 LLM 结构化抽取（mock 模式退化为启发式规则；需要 api_key 才触发真实 LLM）",
    )
    memory_list = memory_sub.add_parser("list", help="列出结构化记忆条目（entries.jsonl）")
    memory_list.add_argument("--limit", type=int, default=50)
    memory_list.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="输出 JSON 对象 memory_list_v1（含 entries[]：id/category/confidence/expires_at/state 等）",
    )
    memory_list.add_argument(
        "--sort",
        default="none",
        choices=("none", "confidence", "created_at"),
        help="list 结果排序（默认按文件顺序；无效行会被校验过滤）",
    )
    memory_list.add_argument("--state-stale-after-days", type=int, default=30, help="状态评估：超过 N 天视为 stale（默认 30）")
    memory_list.add_argument("--state-min-active-confidence", type=float, default=0.4, help="状态评估：低于该置信度视为 stale（默认 0.4）")
    memory_validate_entries = memory_sub.add_parser(
        "validate-entries",
        help="校验 memory/entries.jsonl 行级 memory_entry_v1（与 schemas/memory_entry_v1.schema.json 对齐）",
    )
    memory_validate_entries.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="输出 memory_entries_file_validate_v1 JSON（默认人类可读摘要）",
    )
    memory_entries_p = memory_sub.add_parser(
        "entries",
        help="memory/entries.jsonl 维护子命令",
    )
    memory_entries_sub = memory_entries_p.add_subparsers(dest="memory_entries_action", required=True)
    memory_entries_fix = memory_entries_sub.add_parser(
        "fix",
        help="删除无法通过 memory_entry_v1 校验的行并重写 entries.jsonl",
    )
    memory_entries_fix.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="仅统计将丢弃的行数，不写盘",
    )
    memory_entries_fix.add_argument("--json", action="store_true", dest="json_output")
    memory_instincts = memory_sub.add_parser("instincts", help="列出 instinct Markdown 快照路径")
    memory_instincts.add_argument("--limit", type=int, default=20)
    memory_instincts.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以 JSON 对象 memory_instincts_list_v1 输出 paths[]",
    )
    memory_search = memory_sub.add_parser("search", help="按子串搜索记忆条目")
    memory_search.add_argument("query", help="搜索子串")
    memory_search.add_argument("--limit", type=int, default=50)
    memory_search.add_argument(
        "--sort",
        default="",
        help="confidence 或 created_at（命中后排序再截断）",
    )
    memory_search.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="输出 JSON 对象 memory_search_v1（含 hits[]）",
    )
    memory_prune = memory_sub.add_parser("prune", help="按策略清理记忆条目（过期/低置信度/超额保留）")
    memory_prune.add_argument(
        "--min-confidence",
        type=float,
        default=0.0,
        help="低于该置信度的条目会被删除（默认 0.0，不按置信度删）",
    )
    memory_prune.add_argument(
        "--max-entries",
        type=int,
        default=0,
        help="最多保留条目数（按 created_at 新到旧保留；0 表示不限制）",
    )
    memory_prune.add_argument(
        "--drop-non-active",
        action="store_true",
        default=False,
        help="先按状态机移除 stale/expired（需配合状态阈值参数）",
    )
    memory_prune.add_argument("--state-stale-after-days", type=int, default=30, help="状态评估：超过 N 天视为 stale（默认 30）")
    memory_prune.add_argument("--state-min-active-confidence", type=float, default=0.4, help="状态评估：低于该置信度视为 stale（默认 0.4）")
    memory_prune.add_argument("--json", action="store_true", dest="json_output")
    memory_state = memory_sub.add_parser("state", help="评估记忆条目的状态机分布（active/stale/expired）")
    memory_state.add_argument("--stale-days", type=int, default=30, help="超过 N 天未更新视为 stale（默认 30）")
    memory_state.add_argument(
        "--stale-confidence",
        type=float,
        default=0.4,
        help="低于该置信度的非过期条目视为 stale（默认 0.4）",
    )
    memory_state.add_argument("--json", action="store_true", dest="json_output")
    memory_health = memory_sub.add_parser(
        "health",
        help="记忆健康综合评分（freshness/coverage/conflict_rate，S2-01）",
    )
    memory_health.add_argument("--days", type=int, default=30, help="coverage：近期会话窗口天数（默认 30）")
    memory_health.add_argument(
        "--freshness-days",
        type=int,
        default=14,
        help="freshness：条目创建时间窗口天数（默认 14）",
    )
    memory_health.add_argument(
        "--session-pattern",
        default=".cai-session*.json",
        help="coverage：会话文件 glob（默认 .cai-session*.json）",
    )
    memory_health.add_argument("--session-limit", type=int, default=200, help="最多扫描会话文件数（默认 200）")
    memory_health.add_argument(
        "--conflict-threshold",
        type=float,
        default=0.85,
        help="冲突检测相似度阈值 0~1（默认 0.85）",
    )
    memory_health.add_argument(
        "--max-conflict-compare-entries",
        type=int,
        default=400,
        help="冲突检测最多参与两两比较的最近条目数（默认 400；超大库时可调低以控耗时）",
    )
    memory_health.add_argument(
        "--fail-on-grade",
        default=None,
        choices=("A", "B", "C", "D"),
        help="当 health grade 不优于该档时返回 exit 2（如 C 表示仅 A/B 通过）",
    )
    memory_health.add_argument("--json", action="store_true", dest="json_output")
    memory_export = memory_sub.add_parser("export", help="导出记忆目录")
    memory_export.add_argument("file")
    memory_export.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="stdout 输出 memory_instincts_export_v1（含 output_file、snapshots_exported）",
    )
    memory_import = memory_sub.add_parser("import", help="导入记忆文件")
    memory_import.add_argument("file")
    memory_export_entries = memory_sub.add_parser(
        "export-entries",
        help="导出校验后的 memory/entries.jsonl 为 JSON bundle（schema: memory_entries_bundle_v1）",
    )
    memory_export_entries.add_argument("file")
    memory_export_entries.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="stdout 输出 memory_entries_export_result_v1（含 output_file、entries_count、export_warnings）",
    )
    memory_import_entries = memory_sub.add_parser(
        "import-entries",
        help="从 bundle 导入条目（任一行无效则整批失败，不写入）",
    )
    memory_import_entries.add_argument("file")
    memory_import_entries.add_argument(
        "--dry-run",
        action="store_true",
        help="仅校验 bundle，不写入 entries.jsonl",
    )
    memory_import_entries.add_argument(
        "--error-report",
        default=None,
        help="可选：校验失败时将结构化错误写入文件（相对工作区或绝对路径）",
    )
    memory_nudge = memory_sub.add_parser(
        "nudge",
        help="根据近期会话与记忆状态给出沉淀提醒（Hermes-style memory nudge）",
    )
    memory_nudge.add_argument("--days", type=int, default=7, help="回顾最近 N 天会话")
    memory_nudge.add_argument(
        "--session-pattern",
        default=".cai-session*.json",
        help="会话文件匹配模式（相对当前目录）",
    )
    memory_nudge.add_argument("--session-limit", type=int, default=50, help="最多扫描会话文件数")
    memory_nudge.add_argument(
        "--write-file",
        default=None,
        help="可选：将 nudge JSON 写入文件（用于 schedule/CI 消费）",
    )
    memory_nudge.add_argument(
        "--fail-on-severity",
        default=None,
        choices=("medium", "high"),
        help="当 severity 达到阈值时返回非 0（medium|high）",
    )
    memory_nudge.add_argument(
        "--history-file",
        default=None,
        help="可选：将本次 nudge JSON 追加到 JSONL 历史（默认 memory/nudge-history.jsonl；与 --write-file 指向同一文件时只写一次）",
    )
    memory_nudge.add_argument("--json", action="store_true", dest="json_output")
    memory_nudge_report = memory_sub.add_parser(
        "nudge-report",
        help="汇总 memory nudge 历史 JSONL，输出趋势报告",
    )
    memory_nudge_report.add_argument(
        "--history-file",
        default="memory/nudge-history.jsonl",
        help="nudge 历史 JSONL 路径（相对工作区或绝对路径）",
    )
    memory_nudge_report.add_argument("--limit", type=int, default=200, help="最多读取历史条目数")
    memory_nudge_report.add_argument("--days", type=int, default=30, help="仅统计最近 N 天历史（默认 30）")
    memory_nudge_report.add_argument(
        "--freshness-days",
        type=int,
        default=14,
        help="与 memory health 一致：计算 freshness 的创建时间窗口天数（默认 14）",
    )
    memory_nudge_report.add_argument("--json", action="store_true", dest="json_output")
    memory_provider = memory_sub.add_parser(
        "provider",
        help="输出 memory provider / user-model provider 覆盖只读契约（HM-05d）",
    )
    memory_provider.add_argument("--json", action="store_true", dest="json_output")
    memory_user_model = memory_sub.add_parser(
        "user-model",
        help="用户建模：会话行为概览（v1/v2/v3）+ SQLite store 的 init/list、learn、query、export（见子命令）",
    )
    memory_user_model.add_argument(
        "--days",
        type=int,
        default=14,
        dest="user_model_days",
        help="按会话文件 mtime 统计最近 N 天内的数量（默认 14）",
    )
    memory_user_model.add_argument("--json", action="store_true", dest="json_output")
    memory_user_model.add_argument(
        "--with-dialectic",
        action="store_true",
        default=False,
        help="输出 memory_user_model_v2（含 dialectic 启发式块）",
    )
    um_sub = memory_user_model.add_subparsers(dest="user_model_action", required=False)
    um_export = um_sub.add_parser(
        "export",
        help="导出 user_model_bundle_v1（嵌套 memory_user_model_v1 overview）",
    )
    um_export.add_argument(
        "--days",
        type=int,
        default=14,
        dest="user_model_days",
        help="统计窗口天数（仅写在 export 子命令后时生效）",
    )
    um_export.add_argument(
        "--with-store",
        action="store_true",
        dest="user_model_export_with_store",
        help="在 bundle 中附加 user_model_store_snapshot_v1（.cai/user_model_store.sqlite3）",
    )
    um_store = um_sub.add_parser(
        "store",
        help="SQLite user_model_store：初始化库文件或列出近期 beliefs",
    )
    um_store_sub = um_store.add_subparsers(dest="user_model_store_action", required=True)
    um_store_init = um_store_sub.add_parser("init", help="创建 .cai/user_model_store.sqlite3 及表结构")
    um_store_init.add_argument("--json", action="store_true", dest="json_output")
    um_store_list = um_store_sub.add_parser("list", help="按 updated_at 倒序列出 beliefs")
    um_store_list.add_argument("--limit", type=int, default=50, dest="user_store_list_limit")
    um_store_list.add_argument("--json", action="store_true", dest="json_output")
    um_query = um_sub.add_parser(
        "query",
        help="在 SQLite user_model_store 中按子串检索 beliefs（需先 learn 或运行带 --with-store-v3 的概览以初始化库）",
    )
    um_query.add_argument(
        "--text",
        required=True,
        dest="user_model_query_text",
        help="匹配 belief 文本的子串",
    )
    um_query.add_argument("--limit", type=int, default=20)
    um_query.add_argument("--json", action="store_true", dest="json_output")
    um_learn = um_sub.add_parser(
        "learn",
        help="向 SQLite user_model_store 写入/更新一条 belief，并记录事件",
    )
    um_learn.add_argument("--belief", required=True, help="信念文本")
    um_learn.add_argument("--confidence", type=float, default=0.5, help="0~1，默认 0.5")
    um_learn.add_argument("--tag", action="append", default=[], help="可重复：标签")
    um_learn.add_argument("--json", action="store_true", dest="json_output")
    memory_user_model.add_argument(
        "--with-store-v3",
        action="store_true",
        default=False,
        help="无子命令时输出 memory_user_model_v3（含 .cai/user_model_store.sqlite3 快照）",
    )

    schedule_p = sub.add_parser(
        "schedule",
        help="定时任务管理（add/list/rm/run-due/daemon/stats）",
    )
    schedule_sub = schedule_p.add_subparsers(dest="schedule_action", required=True)

    schedule_add = schedule_sub.add_parser("add", help="新增一个定时任务")
    schedule_add.add_argument("--every-minutes", type=int, required=True, help="执行周期（分钟）")
    schedule_add.add_argument("--goal", required=True, help="到点时要执行的目标文本")
    schedule_add.add_argument(
        "--workspace",
        default=".",
        help="任务执行时使用的工作区（默认当前目录）",
    )
    schedule_add.add_argument("--model", default=None, help="可选模型覆盖")
    schedule_add.add_argument(
        "--depends-on",
        action="append",
        default=[],
        help="依赖的任务 id（可重复；依赖任务未 completed 时不会触发执行）",
    )
    schedule_add.add_argument(
        "--retry-max-attempts",
        type=int,
        default=1,
        help="失败重试次数上限（含首次执行，默认 1）",
    )
    schedule_add.add_argument(
        "--retry-backoff-sec",
        type=float,
        default=0.0,
        help="单次 run-due/daemon 内连续执行同一 goal 时的退避秒数（默认 0）",
    )
    schedule_add.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="跨轮次失败后的最大重试次数（指数退避 60*2^(n-1)s；达到上限后为 failed_exhausted，默认 3）",
    )
    schedule_add.add_argument("--disabled", action="store_true", default=False, help="创建后默认禁用")
    schedule_add.add_argument("--json", action="store_true", dest="json_output")

    schedule_add_nudge = schedule_sub.add_parser(
        "add-memory-nudge",
        help="一键新增 memory nudge 巡检任务模板",
    )
    schedule_add_nudge.add_argument("--every-minutes", type=int, default=1440, help="执行周期（分钟，默认 1440=每天）")
    schedule_add_nudge.add_argument("--days", type=int, default=7, help="nudge 分析窗口天数")
    schedule_add_nudge.add_argument("--session-limit", type=int, default=50, help="nudge 扫描会话上限")
    schedule_add_nudge.add_argument(
        "--output-file",
        default=".cai/memory-nudge-latest.json",
        help="nudge JSON 输出路径（相对工作区或绝对路径）",
    )
    schedule_add_nudge.add_argument(
        "--fail-on-severity",
        default="high",
        choices=("medium", "high"),
        help="达到阈值时 `memory nudge` 返回非 0（默认 high）",
    )
    schedule_add_nudge.add_argument(
        "--workspace",
        default=".",
        help="任务执行时使用的工作区（默认当前目录）",
    )
    schedule_add_nudge.add_argument("--model", default=None, help="可选模型覆盖")
    schedule_add_nudge.add_argument("--disabled", action="store_true", default=False, help="创建后默认禁用")
    schedule_add_nudge.add_argument("--json", action="store_true", dest="json_output")

    schedule_list = schedule_sub.add_parser("list", help="列出定时任务")
    schedule_list.add_argument("--json", action="store_true", dest="json_output")

    schedule_rm = schedule_sub.add_parser("rm", help="删除定时任务")
    schedule_rm.add_argument("id", help="任务 id")
    schedule_rm.add_argument("--json", action="store_true", dest="json_output")

    schedule_due = schedule_sub.add_parser("run-due", help="执行当前到点任务")
    schedule_due.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="真正执行到点任务（默认 dry-run 仅预览）",
    )
    schedule_due.add_argument("--json", action="store_true", dest="json_output")

    schedule_daemon = schedule_sub.add_parser(
        "daemon",
        help="轮询执行到点任务（默认 dry-run；加 --execute 才会真实执行）",
    )
    schedule_daemon.add_argument(
        "--interval-sec",
        type=float,
        default=30.0,
        help="轮询间隔秒数（默认 30）",
    )
    schedule_daemon.add_argument(
        "--max-cycles",
        type=int,
        default=0,
        help="最多轮询次数（0 表示无限直到 Ctrl+C）",
    )
    schedule_daemon.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="真实执行到点任务（默认仅预览）",
    )
    schedule_daemon.add_argument(
        "--lock-file",
        default=".cai-schedule-daemon.lock",
        help="单实例锁文件路径（相对工作区或绝对路径）",
    )
    schedule_daemon.add_argument(
        "--stale-lock-sec",
        type=float,
        default=0.0,
        help="锁文件超过该秒数视为陈旧并可自动回收（默认 0 表示不回收）",
    )
    schedule_daemon.add_argument(
        "--jsonl-log",
        default=None,
        help="可选 JSONL 事件日志路径（相对工作区或绝对路径）",
    )
    schedule_daemon.add_argument(
        "--max-concurrent",
        type=int,
        default=1,
        help="每轮最多执行多少个到点任务（默认 1；多余任务本跳过并在下轮再判断；0 视为 1）",
    )
    schedule_daemon.add_argument("--json", action="store_true", dest="json_output")

    schedule_stats = schedule_sub.add_parser(
        "stats",
        help="从 .cai-schedule-audit.jsonl 聚合任务 SLA（成功次数、耗时分位等）",
    )
    schedule_stats.add_argument(
        "--days",
        type=int,
        default=30,
        help="仅统计最近 N 天内审计记录（按行 ts，默认 30，最大 366）",
    )
    schedule_stats.add_argument(
        "--audit-file",
        default=None,
        help="覆盖默认审计路径（默认工作区 .cai-schedule-audit.jsonl）",
    )
    schedule_stats.add_argument("--json", action="store_true", dest="json_output")
    schedule_stats.add_argument(
        "--fail-on-min-success-rate",
        type=float,
        default=None,
        metavar="RATE",
        help="可选：任一任务 run_count>=1 且 success_rate < RATE（0~1）时 exit 2",
    )

    cost_p = sub.add_parser("cost", help="成本治理命令")
    cost_sub = cost_p.add_subparsers(dest="cost_action", required=True)
    cost_budget = cost_sub.add_parser("budget", help="预算检查")
    cost_budget.add_argument("--check", action="store_true")
    cost_budget.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="覆盖 [cost] budget_max_tokens；未指定时读配置",
    )
    cost_report = cost_sub.add_parser(
        "report",
        help="按 profile / provider 聚合 metrics 与会话 tokens（cost_by_profile_v1）",
    )
    cost_report.add_argument(
        "--by-profile",
        action="store_true",
        dest="cost_by_profile",
        help="输出 profiles[]（默认开启；占位与 --json 同用）",
    )
    cost_report.add_argument(
        "--by-provider",
        action="store_true",
        dest="cost_by_provider",
        help="在 JSON 中附带 by_provider[]",
    )
    cost_report.add_argument(
        "--by-tenant",
        action="store_true",
        dest="cost_include_tenant",
        help="在 JSON 中附带 by_tenant[]（metrics 行需含 tenant_id / tenant）",
    )
    cost_report.add_argument(
        "--per-day",
        action="store_true",
        dest="cost_per_day",
        help="在 JSON 中附带 by_calendar_day（按 metrics.ts 日期聚合 tokens）",
    )
    cost_report.add_argument("--json", action="store_true", dest="json_output")

    api_p = sub.add_parser(
        "api",
        help="最小只读 HTTP JSON API（HM-02b）；默认端口 CAI_API_PORT 或 8788，鉴权 CAI_API_TOKEN",
    )
    api_sub = api_p.add_subparsers(dest="api_action", required=True)
    api_serve = api_sub.add_parser("serve", help="启动 api HTTP 服务（阻塞）")
    api_serve.add_argument("--host", default="127.0.0.1")
    api_serve.add_argument(
        "--port",
        type=int,
        default=None,
        dest="api_port",
        help="监听端口（默认读环境变量 CAI_API_PORT，未设置则为 8788）",
    )
    api_serve.add_argument(
        "-w",
        "--workspace",
        default=None,
        dest="api_workspace",
        help="工作区根目录（默认当前目录）",
    )

    feedback_p = sub.add_parser("feedback", help="用户反馈：写入 .cai/feedback.jsonl（可选 webhook）")
    feedback_sub = feedback_p.add_subparsers(dest="feedback_action", required=True)
    feedback_submit = feedback_sub.add_parser("submit", help="追加一条文本反馈")
    feedback_submit.add_argument("feedback_text", nargs="+", metavar="TEXT", help="反馈正文")
    feedback_submit.add_argument("--json", action="store_true", dest="json_output")
    feedback_list = feedback_sub.add_parser("list", help="列出最近反馈行")
    feedback_list.add_argument("--limit", type=int, default=30)
    feedback_list.add_argument("--json", action="store_true", dest="json_output")
    feedback_stats_p = feedback_sub.add_parser(
        "stats",
        help="汇总 .cai/feedback.jsonl（与 doctor --json / release_runbook.feedback 同源）",
    )
    feedback_stats_p.add_argument("--json", action="store_true", dest="json_output")
    feedback_bug = feedback_sub.add_parser(
        "bug",
        help="结构化问题反馈（等价 /bug），写入 .cai/feedback.jsonl；正文经脱敏后再落盘",
    )
    feedback_bug.add_argument(
        "bug_summary",
        nargs="+",
        metavar="SUMMARY",
        help="一句话摘要",
    )
    feedback_bug.add_argument(
        "--detail",
        default="",
        help="复现步骤或补充说明（写入前脱敏）",
    )
    feedback_bug.add_argument(
        "--detail-file",
        default="",
        metavar="PATH",
        help="从 UTF-8 文件读取 detail（优先于 --detail）",
    )
    feedback_bug.add_argument(
        "--category",
        choices=BUG_REPORT_CATEGORIES,
        default="other",
        help="问题类别（默认 other）",
    )
    feedback_bug.add_argument(
        "--attach-doctor-hint",
        action="store_true",
        help="文本模式下提示可附加 cai-agent doctor --json 作为环境摘要",
    )
    feedback_bug.add_argument("--json", action="store_true", dest="json_output")
    feedback_export = feedback_sub.add_parser(
        "export",
        help="导出 feedback JSONL 到指定路径（feedback_export_v1）",
    )
    feedback_export.add_argument(
        "--dest",
        required=True,
        metavar="PATH",
        help="输出文件路径（如 dist/feedback-export.jsonl）",
    )
    feedback_export.add_argument("--limit", type=int, default=None, dest="feedback_export_limit")
    feedback_export.add_argument("--json", action="store_true", dest="json_output")

    release_ga_p = sub.add_parser(
        "release-ga",
        help="发布前 GA 门禁检查（质量+安全+成本+失败率）",
    )
    release_ga_p.add_argument("--no-quality-gate", action="store_true", default=False)
    release_ga_p.add_argument("--with-security-scan", action="store_true", default=False)
    release_ga_p.add_argument(
        "--max-failure-rate",
        type=float,
        default=0.25,
        help="observe 聚合允许的最大失败率（默认 0.25）",
    )
    release_ga_p.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="覆盖 [cost] budget_max_tokens；未指定时读配置",
    )
    release_ga_p.add_argument("--with-doctor", action="store_true", default=False)
    release_ga_p.add_argument("--with-memory-nudge", action="store_true", default=False)
    release_ga_p.add_argument(
        "--memory-max-severity",
        choices=("medium", "high"),
        default="high",
        help="启用 --with-memory-nudge 时，允许的最高 memory nudge 严重度（默认 high）",
    )
    release_ga_p.add_argument("--with-memory-state", action="store_true", default=False)
    release_ga_p.add_argument(
        "--memory-max-stale-ratio",
        type=float,
        default=0.50,
        help="启用 --with-memory-state 时，允许的最大 stale 占比（默认 0.50）",
    )
    release_ga_p.add_argument(
        "--memory-max-expired-ratio",
        type=float,
        default=0.10,
        help="启用 --with-memory-state 时，允许的最大 expired 占比（默认 0.10）",
    )
    release_ga_p.add_argument(
        "--memory-state-stale-days",
        type=int,
        default=30,
        help="memory state 判定 stale 的天数阈值（默认 30）",
    )
    release_ga_p.add_argument(
        "--memory-state-stale-confidence",
        type=float,
        default=0.4,
        help="memory state 判定 stale 的置信度阈值（默认 0.4）",
    )
    release_ga_p.add_argument(
        "--with-memory-policy",
        action="store_true",
        default=False,
        help="校验 memory/entries.jsonl 行级 schema（与 validate-entries 同源）；文件不存在视为通过",
    )
    release_ga_p.add_argument("--json", action="store_true", dest="json_output")

    rel_cl_p = sub.add_parser(
        "release-changelog",
        parents=[common],
        help="检查仓库根 CHANGELOG.md 与 CHANGELOG.zh-CN.md 基本同步（H4-QA）",
    )
    rel_cl_p.add_argument("--json", action="store_true", dest="json_output")
    rel_cl_p.add_argument(
        "--semantic",
        action="store_true",
        dest="release_changelog_semantic",
        help="附加 changelog_semantic_v1（## 标题数量对齐启发式）",
    )

    claw_m_p = sub.add_parser(
        "claw-migrate",
        parents=[common],
        help="OpenClaw / Claw 配置迁移占位（H8-MIG）",
    )
    claw_m_p.add_argument(
        "--apply",
        action="store_true",
        dest="claw_migrate_apply",
        help="执行迁移（当前仍为占位，将返回 exit 3）",
    )

    export_p = sub.add_parser("export", parents=[common], help="导出到跨工具目录")
    export_p.add_argument("--target", required=True, choices=["cursor", "codex", "opencode"])
    export_p.add_argument(
        "--ecc-diff",
        action="store_true",
        dest="export_ecc_diff",
        help="仅输出 export_ecc_dir_diff_v1 JSON（对比仓库与 .cursor/cai-agent-export；不写文件）",
    )
    export_p.add_argument(
        "-w",
        "--workspace",
        default=None,
        help="工作区根目录（默认当前目录或环境变量 CAI_WORKSPACE）",
    )

    obs_p = sub.add_parser(
        "observe",
        help="可观测性：observe 聚合；子命令 report / export（按日 CSV·JSON·Markdown，S7-04）",
    )
    obs_p.add_argument("--pattern", default=".cai-session*.json")
    obs_p.add_argument("--limit", type=int, default=100)
    obs_p.add_argument(
        "--fail-on-max-failure-rate",
        type=float,
        default=None,
        metavar="RATE",
        help="可选：aggregates.failure_rate >= RATE（0~1）时 exit 2，与 insights 语义一致",
    )
    obs_p.add_argument("--json", action="store_true", dest="json_output")
    obs_sub = obs_p.add_subparsers(dest="observe_action", required=False)
    obs_rep = obs_sub.add_parser(
        "report",
        help="过去 N 天运营摘要（JSON 或 Markdown）；默认 --format json",
    )
    obs_rep.add_argument(
        "--days",
        type=int,
        default=7,
        help="回溯天数（默认 7）",
    )
    obs_rep.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="json",
        help="输出格式：markdown 或 json（默认 json）",
    )
    obs_rep.add_argument(
        "-o",
        "--output",
        default=None,
        help="写入文件路径（可选）；父目录不存在时创建；默认 stdout",
    )
    obs_exp = obs_sub.add_parser(
        "export",
        help="按 UTC 日历日导出（CSV / JSON / Markdown；S7-04）",
    )
    obs_exp.add_argument(
        "--days",
        type=int,
        default=30,
        dest="observe_export_days",
        help="回溯天数（默认 30）",
    )
    obs_exp.add_argument(
        "--format",
        choices=["csv", "json", "markdown"],
        default="json",
        dest="observe_export_format",
        help="输出格式（默认 json）",
    )
    obs_exp.add_argument(
        "-o",
        "--output",
        default=None,
        dest="observe_export_output",
        help="输出文件路径（可选）；未指定时写入 stdout",
    )

    obs_report_p = sub.add_parser("observe-report", help="基于 observe 生成告警与报表摘要")
    obs_report_p.add_argument("--pattern", default=".cai-session*.json")
    obs_report_p.add_argument("--limit", type=int, default=100)
    obs_report_p.add_argument("--warn-failure-rate", type=float, default=0.20)
    obs_report_p.add_argument("--fail-failure-rate", type=float, default=0.35)
    obs_report_p.add_argument("--warn-token-budget", type=int, default=40_000)
    obs_report_p.add_argument("--fail-token-budget", type=int, default=80_000)
    obs_report_p.add_argument("--warn-tool-errors", type=int, default=3)
    obs_report_p.add_argument("--fail-tool-errors", type=int, default=8)
    obs_report_p.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="将 state=warn 视为失败（exit 2）；默认仅在 state=fail 时 exit 2",
    )
    obs_report_p.add_argument("--json", action="store_true", dest="json_output")

    board_p = sub.add_parser(
        "board",
        help="任务/会话运营最小看板（observe + .cai/last-workflow.json）",
    )
    board_p.add_argument("--pattern", default=".cai-session*.json")
    board_p.add_argument("--limit", type=int, default=100)
    board_p.add_argument(
        "--failed-only",
        action="store_true",
        help="仅展示失败会话（error_count > 0）的看板视图",
    )
    board_p.add_argument(
        "--task-id",
        default="",
        help="按 task_id 精确过滤会话",
    )
    board_p.add_argument(
        "--status",
        action="append",
        default=[],
        help="按任务状态过滤（可重复）：pending/running/completed/failed/unknown",
    )
    board_p.add_argument(
        "--failed-top",
        type=int,
        default=5,
        help="失败摘要 recent 列表的最大条数（最小为 1）",
    )
    board_p.add_argument(
        "--group-top",
        type=int,
        default=5,
        help="聚合视图（模型/任务）TopN 条数（最小为 1）",
    )
    board_p.add_argument(
        "--trend-window",
        type=int,
        default=5,
        help="趋势对比窗口大小（recent/baseline 各取 N 条，最小为 1）",
    )
    board_p.add_argument(
        "--trend-recent",
        type=int,
        default=20,
        help="趋势视图 recent 窗口大小（按最新会话计数，最小 1）",
    )
    board_p.add_argument(
        "--trend-baseline",
        type=int,
        default=20,
        help="趋势视图 baseline 窗口大小（紧随 recent 之前，最小 1）",
    )
    board_p.add_argument(
        "--fail-on-failed-sessions",
        action="store_true",
        help="当前 board 输出中的会话列表含 error_count>0 时 exit 2（与筛选后列表一致，CI 门禁）",
    )
    board_p.add_argument("--json", action="store_true", dest="json_output")

    ops_p = sub.add_parser(
        "ops",
        parents=[common],
        help="运营聚合：失败率、调度 SLA、成本一页 JSON",
    )
    ops_sub = ops_p.add_subparsers(dest="ops_action", required=True)
    ops_dash = ops_sub.add_parser("dashboard", help="聚合 board + schedule stats + cost rollup")
    ops_dash.add_argument("--json", action="store_true", dest="json_output")
    ops_dash.add_argument(
        "--format",
        choices=["json", "text", "html"],
        default="text",
        dest="ops_format",
        help="输出格式：text（默认）/ json / html（生成单文件 HTML 仪表盘）",
    )
    ops_dash.add_argument(
        "-o",
        "--output",
        default=None,
        dest="ops_output",
        metavar="FILE",
        help="将结果写入文件（html 格式常与 -o dashboard.html 配合）",
    )
    ops_dash.add_argument("--pattern", default=".cai-session*.json")
    ops_dash.add_argument("--limit", type=int, default=100)
    ops_dash.add_argument("--schedule-days", type=int, default=30)
    ops_dash.add_argument("--audit-file", default=None)
    ops_dash.add_argument(
        "--html-refresh-seconds",
        type=int,
        default=0,
        dest="ops_html_refresh_seconds",
        help="仅 --format html：>0 时在 HTML 内加入 meta refresh（秒）",
    )

    ops_serve = ops_sub.add_parser("serve", help="启动只读 dynamic ops dashboard HTTP 服务")
    ops_serve.add_argument("--host", default="127.0.0.1")
    ops_serve.add_argument("--port", type=int, default=8765)
    ops_serve.add_argument(
        "--allow-workspace",
        action="append",
        default=[],
        dest="ops_allow_workspaces",
        metavar="DIR",
        help="允许通过 workspace query 访问的工作区根目录，可重复",
    )

    gateway_p = sub.add_parser(
        "gateway",
        help="Gateway MVP：管理 Telegram chat/user 到会话文件的映射",
    )
    gateway_sub = gateway_p.add_subparsers(dest="gateway_action", required=True)

    gw_setup = gateway_sub.add_parser(
        "setup",
        help="Gateway 引导：写入 .cai/gateway/telegram-config.json（Hermes S6-01）",
    )
    gw_setup.add_argument(
        "-w",
        "--workspace",
        default=None,
        dest="gateway_workspace",
        help="工作区根路径（默认当前目录；决定 .cai/gateway 位置与配置中的 workspace）",
    )
    gw_setup.add_argument("--telegram-bot-token", default=None, dest="gateway_setup_bot_token")
    gw_setup.add_argument(
        "--use-env-token",
        action="store_true",
        dest="gateway_setup_use_env_token",
        help="执行阶段从环境变量 CAI_TELEGRAM_BOT_TOKEN 读取 token（可与文件内 token 并存）",
    )
    gw_setup.add_argument(
        "--allow-chat-id",
        action="append",
        default=[],
        dest="gateway_setup_allow_chat_ids",
        metavar="CHAT_ID",
        help="追加到 telegram-session-map.json 的 allowed_chat_ids（可重复）",
    )
    gw_setup.add_argument("--host", default="127.0.0.1", dest="gateway_setup_host")
    gw_setup.add_argument("--port", type=int, default=18765, dest="gateway_setup_port")
    gw_setup.add_argument("--max-events", type=int, default=0, dest="gateway_setup_max_events")
    gw_setup.add_argument("--create-missing", action="store_true", dest="gateway_setup_create_missing")
    gw_setup.add_argument("--execute-on-update", action="store_true", dest="gateway_setup_execute_on_update")
    gw_setup.add_argument("--reply-on-execution", action="store_true", dest="gateway_setup_reply_on_execution")
    gw_setup.add_argument("--reply-on-deny", action="store_true", dest="gateway_setup_reply_on_deny")
    gw_setup.add_argument(
        "--goal-template",
        default="用户({user_id})在 chat({chat_id}) 发送消息：{text}",
        dest="gateway_setup_goal_template",
    )
    gw_setup.add_argument(
        "--reply-template",
        default="执行完成 ok={ok}\n{answer}",
        dest="gateway_setup_reply_template",
    )
    gw_setup.add_argument(
        "--deny-message",
        default="此 CAI Agent Bot 未授权本对话。",
        dest="gateway_setup_deny_message",
    )
    gw_setup.add_argument("--json", action="store_true", dest="json_output")

    gw_start = gateway_sub.add_parser(
        "start",
        help="按 telegram-config.json 后台启动 gateway telegram serve-webhook（写 PID 文件）",
    )
    gw_start.add_argument(
        "-w",
        "--workspace",
        default=None,
        dest="gateway_workspace",
        help="工作区根路径（默认当前目录）",
    )
    gw_start.add_argument("--json", action="store_true", dest="json_output")

    gw_stat = gateway_sub.add_parser("status", help="映射 / 白名单 / webhook 子进程状态（S6-01）")
    gw_stat.add_argument(
        "-w",
        "--workspace",
        default=None,
        dest="gateway_workspace",
        help="工作区根路径（默认当前目录）",
    )
    gw_stat.add_argument("--json", action="store_true", dest="json_output")

    gw_prod = gateway_sub.add_parser("prod-status", help="多平台 Gateway 生产状态只读摘要（HM-03e）")
    gw_prod.add_argument(
        "-w",
        "--workspace",
        default=None,
        dest="gateway_workspace",
        help="工作区根路径（默认当前目录）",
    )
    gw_prod.add_argument("--json", action="store_true", dest="json_output")

    gw_stop = gateway_sub.add_parser("stop", help="停止 start 写入 PID 的 webhook 子进程")
    gw_stop.add_argument(
        "-w",
        "--workspace",
        default=None,
        dest="gateway_workspace",
        help="工作区根路径（默认当前目录）",
    )
    gw_stop.add_argument("--json", action="store_true", dest="json_output")

    gw_tg = gateway_sub.add_parser("telegram", help="Telegram 映射管理")
    gw_tg.add_argument(
        "-w",
        "--workspace",
        default=None,
        dest="gateway_workspace",
        help="工作区根路径（默认当前目录；影响默认 map 路径等）",
    )
    gw_tg_sub = gw_tg.add_subparsers(dest="gateway_telegram_action", required=True)

    gw_plat = gateway_sub.add_parser(
        "platforms",
        help="多平台 Gateway 适配目录（Telegram 与其它 messenger 状态）",
    )
    gw_plat.add_argument(
        "-w",
        "--workspace",
        default=None,
        dest="gateway_workspace",
        help="工作区根路径（默认当前目录）",
    )
    gw_plat_sub = gw_plat.add_subparsers(dest="gateway_platforms_action", required=True)
    gw_plat_list = gw_plat_sub.add_parser("list", help="列出各平台实现阶段与引导字段")
    gw_plat_list.add_argument("--json", action="store_true", dest="json_output")

    gw_tg_bind = gw_tg_sub.add_parser("bind", help="绑定 chat_id+user_id 到会话文件")
    gw_tg_bind.add_argument("--chat-id", required=True)
    gw_tg_bind.add_argument("--user-id", required=True)
    gw_tg_bind.add_argument("--session-file", required=True, help="会话文件路径（相对当前目录或绝对路径）")
    gw_tg_bind.add_argument("--map-file", default=None, help="映射文件路径（默认 .cai/gateway/telegram-session-map.json）")
    gw_tg_bind.add_argument("--json", action="store_true", dest="json_output")

    gw_tg_get = gw_tg_sub.add_parser("get", help="查询单个 chat_id+user_id 映射")
    gw_tg_get.add_argument("--chat-id", required=True)
    gw_tg_get.add_argument("--user-id", required=True)
    gw_tg_get.add_argument("--map-file", default=None, help="映射文件路径（默认 .cai/gateway/telegram-session-map.json）")
    gw_tg_get.add_argument("--json", action="store_true", dest="json_output")

    gw_tg_list = gw_tg_sub.add_parser("list", help="列出所有 Telegram 会话映射")
    gw_tg_list.add_argument("--map-file", default=None, help="映射文件路径（默认 .cai/gateway/telegram-session-map.json）")
    gw_tg_list.add_argument("--json", action="store_true", dest="json_output")

    gw_tg_ch = gw_tg_sub.add_parser(
        "continue-hint",
        help="跨端续聊（S6-04）：输出与绑定 session_file 对应的 cai-agent continue 命令",
    )
    gw_tg_ch.add_argument(
        "--chat-id",
        default=None,
        help="与 --user-id 成对使用：仅该绑定；若两者皆省略则列出全部绑定",
    )
    gw_tg_ch.add_argument("--user-id", default=None, help="与 --chat-id 成对使用")
    gw_tg_ch.add_argument("--map-file", default=None, help="映射文件路径（默认 .cai/gateway/telegram-session-map.json）")
    gw_tg_ch.add_argument("--json", action="store_true", dest="json_output")

    gw_tg_allow = gw_tg_sub.add_parser("allow", help="Telegram chat_id 白名单（S6-03，写入映射 JSON）")
    gw_tg_allow_sub = gw_tg_allow.add_subparsers(dest="gateway_telegram_allow_action", required=True)
    gw_tg_allow_add = gw_tg_allow_sub.add_parser("add", help="追加允许的 chat_id")
    gw_tg_allow_add.add_argument("--chat-id", required=True)
    gw_tg_allow_add.add_argument("--map-file", default=None, help="映射文件路径（默认 .cai/gateway/telegram-session-map.json）")
    gw_tg_allow_add.add_argument("--json", action="store_true", dest="json_output")
    gw_tg_allow_list = gw_tg_allow_sub.add_parser("list", help="列出白名单 chat_id")
    gw_tg_allow_list.add_argument("--map-file", default=None, help="映射文件路径（默认 .cai/gateway/telegram-session-map.json）")
    gw_tg_allow_list.add_argument("--json", action="store_true", dest="json_output")
    gw_tg_allow_rm = gw_tg_allow_sub.add_parser("rm", help="移除 chat_id")
    gw_tg_allow_rm.add_argument("--chat-id", required=True)
    gw_tg_allow_rm.add_argument("--map-file", default=None, help="映射文件路径（默认 .cai/gateway/telegram-session-map.json）")
    gw_tg_allow_rm.add_argument("--json", action="store_true", dest="json_output")

    gw_tg_unbind = gw_tg_sub.add_parser("unbind", help="解除单个 chat_id+user_id 映射")
    gw_tg_unbind.add_argument("--chat-id", required=True)
    gw_tg_unbind.add_argument("--user-id", required=True)
    gw_tg_unbind.add_argument("--map-file", default=None, help="映射文件路径（默认 .cai/gateway/telegram-session-map.json）")
    gw_tg_unbind.add_argument("--json", action="store_true", dest="json_output")

    gw_tg_resolve = gw_tg_sub.add_parser("resolve-update", help="从 Telegram update JSON 解析并解析/创建映射")
    gw_tg_resolve.add_argument("--update-file", required=True, help="Telegram update JSON 文件路径")
    gw_tg_resolve.add_argument(
        "--session-template",
        default=".cai/gateway/sessions/tg-{chat_id}-{user_id}.json",
        help="当映射不存在时自动创建的会话文件模板（支持 {chat_id}/{user_id}）",
    )
    gw_tg_resolve.add_argument(
        "--create-missing",
        action="store_true",
        default=False,
        help="映射缺失时自动创建新映射与会话文件路径",
    )
    gw_tg_resolve.add_argument("--map-file", default=None, help="映射文件路径（默认 .cai/gateway/telegram-session-map.json）")
    gw_tg_resolve.add_argument("--json", action="store_true", dest="json_output")
    gw_tg_serve = gw_tg_sub.add_parser("serve-webhook", help="启动 Telegram webhook HTTP 入口（MVP）")
    gw_tg_serve.add_argument("--host", default="127.0.0.1", help="监听地址（默认 127.0.0.1）")
    gw_tg_serve.add_argument("--port", type=int, default=18765, help="监听端口（默认 18765）")
    gw_tg_serve.add_argument("--path", default="/telegram/update", help="Webhook 路径（默认 /telegram/update）")
    gw_tg_serve.add_argument(
        "--session-template",
        default=".cai/gateway/sessions/tg-{chat_id}-{user_id}.json",
        help="映射缺失时自动创建会话文件模板（支持 {chat_id}/{user_id}）",
    )
    gw_tg_serve.add_argument("--map-file", default=None, help="映射文件路径（默认 .cai/gateway/telegram-session-map.json）")
    gw_tg_serve.add_argument(
        "--event-log",
        default=".cai/gateway/telegram-webhook-events.jsonl",
        help="Webhook 事件 JSONL 日志路径",
    )
    gw_tg_serve.add_argument("--max-events", type=int, default=0, help="最多处理事件数（0=无限）")
    gw_tg_serve.add_argument(
        "--create-missing",
        action="store_true",
        default=False,
        help="映射缺失时自动创建新映射与会话文件路径",
    )
    gw_tg_serve.add_argument(
        "--execute-on-update",
        action="store_true",
        default=False,
        help="收到 update 后按绑定 session_file 执行（与 CLI run/continue 同源写回 JSON；不回发需省略 --reply-on-execution）",
    )
    gw_tg_serve.add_argument(
        "--goal-template",
        default="用户({user_id})在 chat({chat_id}) 发送消息：{text}",
        help="执行模式下的 goal 模板（支持 {chat_id}/{user_id}/{text}）",
    )
    gw_tg_serve.add_argument(
        "--reply-on-execution",
        action="store_true",
        default=False,
        help="执行完成后将结果回发到 Telegram（需 --telegram-bot-token）",
    )
    gw_tg_serve.add_argument(
        "--telegram-bot-token",
        default=None,
        help="Bot token（亦可设环境变量 CAI_TELEGRAM_BOT_TOKEN）",
    )
    gw_tg_serve.add_argument(
        "--reply-template",
        default="执行完成 ok={ok}\n{answer}",
        help="回发文本模板（支持 {chat_id}/{user_id}/{text}/{answer}/{ok}）",
    )
    gw_tg_serve.add_argument(
        "--reply-on-deny",
        action="store_true",
        default=False,
        help="白名单拒绝时仍向 chat 发送拒绝短讯（需 token；S6-03）",
    )
    gw_tg_serve.add_argument(
        "--deny-message",
        default="此 CAI Agent Bot 未授权本对话。",
        help="与 --reply-on-deny 配合",
    )
    gw_tg_serve.add_argument("--json", action="store_true", dest="json_output")

    # ---- Discord Gateway MVP（§24 补齐）----
    gw_dc = gateway_sub.add_parser("discord", help="Discord Gateway MVP — Bot Polling 接入")
    gw_dc.add_argument("-w", "--workspace", default=None, help="工作区根目录")
    gw_dc_sub = gw_dc.add_subparsers(dest="gateway_discord_action", required=True)

    gw_dc_bind = gw_dc_sub.add_parser("bind", help="绑定 channel_id → session_file")
    gw_dc_bind.add_argument("channel_id")
    gw_dc_bind.add_argument("session_file")
    gw_dc_bind.add_argument(
        "--guild-id",
        default=None,
        dest="discord_bind_guild_id",
        metavar="ID",
        help="可选：写入绑定行的 guild_id（排障/展示）",
    )
    gw_dc_bind.add_argument("--label", default=None, dest="discord_bind_label", help="可选：绑定备注")
    gw_dc_bind.add_argument("--json", action="store_true", dest="json_output")

    gw_dc_unbind = gw_dc_sub.add_parser("unbind", help="解绑 channel_id")
    gw_dc_unbind.add_argument("channel_id")
    gw_dc_unbind.add_argument("--json", action="store_true", dest="json_output")

    gw_dc_get = gw_dc_sub.add_parser("get", help="查询 channel_id 绑定")
    gw_dc_get.add_argument("channel_id")
    gw_dc_get.add_argument("--json", action="store_true", dest="json_output")

    gw_dc_list = gw_dc_sub.add_parser("list", help="列出所有绑定与白名单")
    gw_dc_list.add_argument("--json", action="store_true", dest="json_output")

    gw_dc_health = gw_dc_sub.add_parser("health", help="Discord 网关自检：本地映射 + 可选校验 Bot Token（GET /users/@me）")
    gw_dc_health.add_argument(
        "--bot-token",
        default=None,
        dest="discord_bot_token",
        help="Discord Bot Token（或 CAI_DISCORD_BOT_TOKEN）",
    )
    gw_dc_health.add_argument("--json", action="store_true", dest="json_output")

    gw_dc_regcmd = gw_dc_sub.add_parser(
        "register-commands",
        help="注册默认 Slash 命令（PUT Discord Application Commands，与文档 parity 表一致）",
    )
    gw_dc_regcmd.add_argument(
        "--guild-id",
        default=None,
        dest="discord_guild_id",
        metavar="ID",
        help="Guild Snowflake（推荐，生效快）；省略则为全局命令",
    )
    gw_dc_regcmd.add_argument(
        "--dry-run",
        action="store_true",
        dest="discord_dry_run",
        help="仅解析并展示将提交的命令体（仍需 Token 调 GET /oauth2/applications/@me）",
    )
    gw_dc_regcmd.add_argument(
        "--bot-token",
        default=None,
        dest="discord_bot_token",
        help="Discord Bot Token（或 CAI_DISCORD_BOT_TOKEN）",
    )
    gw_dc_regcmd.add_argument("--json", action="store_true", dest="json_output")

    gw_dc_listcmd = gw_dc_sub.add_parser("list-commands", help="列出 Discord 已注册的 Application Commands")
    gw_dc_listcmd.add_argument(
        "--guild-id",
        default=None,
        dest="discord_guild_id",
        metavar="ID",
        help="Guild Snowflake；省略则列全局命令",
    )
    gw_dc_listcmd.add_argument(
        "--bot-token",
        default=None,
        dest="discord_bot_token",
        help="Discord Bot Token（或 CAI_DISCORD_BOT_TOKEN）",
    )
    gw_dc_listcmd.add_argument("--json", action="store_true", dest="json_output")

    gw_dc_allow = gw_dc_sub.add_parser("allow", help="白名单管理")
    gw_dc_allow_sub = gw_dc_allow.add_subparsers(dest="dc_allow_action", required=True)
    gw_dc_allow_add = gw_dc_allow_sub.add_parser("add"); gw_dc_allow_add.add_argument("channel_id"); gw_dc_allow_add.add_argument("--json", action="store_true", dest="json_output")
    gw_dc_allow_rm = gw_dc_allow_sub.add_parser("rm"); gw_dc_allow_rm.add_argument("channel_id"); gw_dc_allow_rm.add_argument("--json", action="store_true", dest="json_output")
    gw_dc_allow_list = gw_dc_allow_sub.add_parser("list"); gw_dc_allow_list.add_argument("--json", action="store_true", dest="json_output")

    gw_dc_poll = gw_dc_sub.add_parser("serve-polling", help="启动 Discord Bot Polling 服务")
    gw_dc_poll.add_argument("--bot-token", default=None, dest="discord_bot_token", help="Discord Bot Token（或 CAI_DISCORD_BOT_TOKEN）")
    gw_dc_poll.add_argument("--poll-interval", type=float, default=2.0)
    gw_dc_poll.add_argument("--max-events", type=int, default=0)
    gw_dc_poll.add_argument("--execute-on-message", action="store_true", default=False)
    gw_dc_poll.add_argument("--reply-on-execution", action="store_true", default=False)
    gw_dc_poll.add_argument("--log-file", default=None)
    gw_dc_poll.add_argument("--json", action="store_true", dest="json_output")

    # ---- Slack Gateway MVP（§24 补齐）----
    gw_sl = gateway_sub.add_parser("slack", help="Slack Gateway MVP — Events API Webhook 接入")
    gw_sl.add_argument("-w", "--workspace", default=None, help="工作区根目录")
    gw_sl_sub = gw_sl.add_subparsers(dest="gateway_slack_action", required=True)

    gw_sl_bind = gw_sl_sub.add_parser("bind", help="绑定 channel_id → session_file")
    gw_sl_bind.add_argument("channel_id")
    gw_sl_bind.add_argument("session_file")
    gw_sl_bind.add_argument("--team-id", default=None, dest="team_id")
    gw_sl_bind.add_argument("--label", default=None)
    gw_sl_bind.add_argument("--json", action="store_true", dest="json_output")

    gw_sl_unbind = gw_sl_sub.add_parser("unbind", help="解绑 channel_id")
    gw_sl_unbind.add_argument("channel_id")
    gw_sl_unbind.add_argument("--json", action="store_true", dest="json_output")

    gw_sl_get = gw_sl_sub.add_parser("get", help="查询 channel_id 绑定")
    gw_sl_get.add_argument("channel_id")
    gw_sl_get.add_argument("--json", action="store_true", dest="json_output")

    gw_sl_list = gw_sl_sub.add_parser("list", help="列出所有绑定与白名单")
    gw_sl_list.add_argument("--json", action="store_true", dest="json_output")
    gw_sl_health = gw_sl_sub.add_parser("health", help="检查 Slack gateway 映射、Token 与 Signing Secret 状态")
    gw_sl_health.add_argument("--bot-token", default=None, dest="slack_bot_token", help="Slack Bot Token（或 CAI_SLACK_BOT_TOKEN）")
    gw_sl_health.add_argument("--signing-secret", default=None, dest="slack_signing_secret", help="Slack Signing Secret（或 CAI_SLACK_SIGNING_SECRET）")
    gw_sl_health.add_argument("--json", action="store_true", dest="json_output")

    gw_sl_allow = gw_sl_sub.add_parser("allow", help="白名单管理")
    gw_sl_allow_sub = gw_sl_allow.add_subparsers(dest="sl_allow_action", required=True)
    gw_sl_allow_add = gw_sl_allow_sub.add_parser("add"); gw_sl_allow_add.add_argument("channel_id"); gw_sl_allow_add.add_argument("--json", action="store_true", dest="json_output")
    gw_sl_allow_rm = gw_sl_allow_sub.add_parser("rm"); gw_sl_allow_rm.add_argument("channel_id"); gw_sl_allow_rm.add_argument("--json", action="store_true", dest="json_output")
    gw_sl_allow_list = gw_sl_allow_sub.add_parser("list"); gw_sl_allow_list.add_argument("--json", action="store_true", dest="json_output")

    gw_sl_serve = gw_sl_sub.add_parser("serve-webhook", help="启动 Slack Events API Webhook 服务")
    gw_sl_serve.add_argument("--bot-token", default=None, dest="slack_bot_token", help="Slack Bot Token（或 CAI_SLACK_BOT_TOKEN）")
    gw_sl_serve.add_argument("--signing-secret", default=None, dest="slack_signing_secret", help="Slack Signing Secret（或 CAI_SLACK_SIGNING_SECRET）")
    gw_sl_serve.add_argument("--host", default="0.0.0.0")
    gw_sl_serve.add_argument("--port", type=int, default=7892)
    gw_sl_serve.add_argument("--max-events", type=int, default=0)
    gw_sl_serve.add_argument("--execute-on-event", action="store_true", default=False)
    gw_sl_serve.add_argument("--execute-on-slash", action="store_true", default=False)
    gw_sl_serve.add_argument("--reply-on-execution", action="store_true", default=False)
    gw_sl_serve.add_argument("--log-file", default=None)
    gw_sl_serve.add_argument("--json", action="store_true", dest="json_output")

    # ---- Microsoft Teams Gateway（HM-03d）----
    gw_tm = gateway_sub.add_parser("teams", help="Microsoft Teams Gateway — Bot Framework Activity Webhook 接入")
    gw_tm.add_argument("-w", "--workspace", default=None, help="工作区根目录")
    gw_tm_sub = gw_tm.add_subparsers(dest="gateway_teams_action", required=True)

    gw_tm_bind = gw_tm_sub.add_parser("bind", help="绑定 conversation_id → session_file")
    gw_tm_bind.add_argument("conversation_id")
    gw_tm_bind.add_argument("session_file")
    gw_tm_bind.add_argument("--tenant-id", default=None, dest="teams_tenant_id")
    gw_tm_bind.add_argument("--service-url", default=None, dest="teams_service_url")
    gw_tm_bind.add_argument("--channel-id", default=None, dest="teams_channel_id")
    gw_tm_bind.add_argument("--label", default=None)
    gw_tm_bind.add_argument("--json", action="store_true", dest="json_output")

    gw_tm_unbind = gw_tm_sub.add_parser("unbind", help="解绑 conversation_id")
    gw_tm_unbind.add_argument("conversation_id")
    gw_tm_unbind.add_argument("--json", action="store_true", dest="json_output")

    gw_tm_get = gw_tm_sub.add_parser("get", help="查询 conversation_id 绑定")
    gw_tm_get.add_argument("conversation_id")
    gw_tm_get.add_argument("--json", action="store_true", dest="json_output")

    gw_tm_list = gw_tm_sub.add_parser("list", help="列出所有绑定与白名单")
    gw_tm_list.add_argument("--json", action="store_true", dest="json_output")

    gw_tm_health = gw_tm_sub.add_parser("health", help="检查 Teams gateway 映射与应用配置状态")
    gw_tm_health.add_argument("--app-id", default=None, dest="teams_app_id", help="Teams/Azure Bot App ID（或 CAI_TEAMS_APP_ID）")
    gw_tm_health.add_argument("--app-password", default=None, dest="teams_app_password", help="App password/secret（或 CAI_TEAMS_APP_PASSWORD）")
    gw_tm_health.add_argument("--tenant-id", default=None, dest="teams_tenant_id", help="Tenant ID（或 CAI_TEAMS_TENANT_ID）")
    gw_tm_health.add_argument("--webhook-secret", default=None, dest="teams_webhook_secret", help="本地接收器共享密钥（或 CAI_TEAMS_WEBHOOK_SECRET）")
    gw_tm_health.add_argument("--json", action="store_true", dest="json_output")

    gw_tm_manifest = gw_tm_sub.add_parser("manifest", help="输出 Teams app manifest 模板（不写文件）")
    gw_tm_manifest.add_argument("--app-id", required=True, dest="teams_app_id")
    gw_tm_manifest.add_argument("--bot-id", default=None, dest="teams_bot_id")
    gw_tm_manifest.add_argument("--name", default="CAI Agent", dest="teams_manifest_name")
    gw_tm_manifest.add_argument("--valid-domain", action="append", default=[], dest="teams_valid_domains")
    gw_tm_manifest.add_argument("--json", action="store_true", dest="json_output")

    gw_tm_allow = gw_tm_sub.add_parser("allow", help="白名单管理")
    gw_tm_allow_sub = gw_tm_allow.add_subparsers(dest="teams_allow_action", required=True)
    gw_tm_allow_add = gw_tm_allow_sub.add_parser("add"); gw_tm_allow_add.add_argument("conversation_id"); gw_tm_allow_add.add_argument("--json", action="store_true", dest="json_output")
    gw_tm_allow_rm = gw_tm_allow_sub.add_parser("rm"); gw_tm_allow_rm.add_argument("conversation_id"); gw_tm_allow_rm.add_argument("--json", action="store_true", dest="json_output")
    gw_tm_allow_list = gw_tm_allow_sub.add_parser("list"); gw_tm_allow_list.add_argument("--json", action="store_true", dest="json_output")

    gw_tm_serve = gw_tm_sub.add_parser("serve-webhook", help="启动 Teams Bot Framework Activity Webhook 服务")
    gw_tm_serve.add_argument("--webhook-secret", default=None, dest="teams_webhook_secret", help="本地共享密钥（或 CAI_TEAMS_WEBHOOK_SECRET）")
    gw_tm_serve.add_argument("--host", default="0.0.0.0")
    gw_tm_serve.add_argument("--port", type=int, default=7893)
    gw_tm_serve.add_argument("--max-events", type=int, default=0)
    gw_tm_serve.add_argument("--execute-on-message", action="store_true", default=False)
    gw_tm_serve.add_argument("--log-file", default=None)
    gw_tm_serve.add_argument("--json", action="store_true", dest="json_output")

    wf_p = sub.add_parser(
        "workflow",
        parents=[common],
        help="根据 JSON workflow 文件依次运行多个步骤任务（支持 on_error / budget_max_tokens / quality_gate）；或用 templates 列出/导出内置模板",
    )
    wf_p.add_argument(
        "file",
        nargs="?",
        default=None,
        help="workflow JSON 文件路径（包含 steps 数组）",
    )
    wf_p.add_argument(
        "--templates",
        action="store_true",
        dest="list_templates",
        help="列出所有内置 workflow 模板（与 --template 配合可导出完整 JSON）",
    )
    wf_p.add_argument(
        "--template",
        default=None,
        dest="template_id",
        metavar="TEMPLATE_ID",
        help="与 --templates 配合：输出指定模板完整 JSON（可用 --goal 填充 {{GOAL}}）",
    )
    wf_p.add_argument(
        "--goal",
        default="",
        dest="goal",
        help="与 --template 配合：替换模板中的 {{GOAL}} 占位符",
    )
    wf_p.add_argument(
        "-w",
        "--workspace",
        default=None,
        help="工作区根目录（默认当前目录或环境变量 CAI_WORKSPACE）",
    )
    wf_p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以 JSON 对象输出全部步骤结果与汇总",
    )
    wf_p.add_argument(
        "--fail-on-step-errors",
        action="store_true",
        help="任一 step 的 error_count>0 或 workflow task.status==failed 时 exit 2",
    )

    ui_p = sub.add_parser(
        "ui",
        parents=[common],
        help="交互式终端界面（Textual，类 Claude Code 会话）",
    )
    ui_p.add_argument(
        "-w",
        "--workspace",
        default=None,
        help="工作区根目录（默认当前目录或环境变量 CAI_WORKSPACE）",
    )

    args = parser.parse_args(argv)

    if args.command == "init":
        t_ini = time.perf_counter()
        rc_ini = _cmd_init(
            force=args.force,
            is_global=bool(getattr(args, "global_flag", False)),
            preset=str(getattr(args, "init_preset", "default") or "default"),
            json_output=bool(getattr(args, "json_output", False)),
        )
        _maybe_metrics_cli(
            module="init",
            event="init.apply",
            latency_ms=(time.perf_counter() - t_ini) * 1000.0,
            tokens=1 if int(rc_ini) == 0 else 0,
            success=(int(rc_ini) == 0),
        )
        return rc_ini

    if args.command == "ecc":
        t_ecc = time.perf_counter()
        from cai_agent.ecc_layout import build_ecc_asset_layout_payload, ecc_scaffold_workspace

        ws_ecc = getattr(args, "workspace", None)
        root_ecc = Path(str(ws_ecc)).expanduser().resolve() if ws_ecc else None
        try:
            settings_ecc = Settings.from_env(
                config_path=getattr(args, "config", None),
                workspace_hint=str(root_ecc) if root_ecc else None,
            )
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        ecc_act = str(getattr(args, "ecc_action", "") or "").strip().lower()
        if ecc_act == "layout":
            pl = build_ecc_asset_layout_payload(settings_ecc, root_override=root_ecc)
            if bool(getattr(args, "json_output", False)):
                print(json.dumps(pl, ensure_ascii=False))
            else:
                print(f"ECC workspace={pl.get('workspace')} hooks_resolved={pl.get('hooks_resolved_path')}")
                for row in pl.get("entries") or []:
                    if isinstance(row, dict):
                        print(f"- {row.get('id')}: {row.get('path')}")
            _maybe_metrics_cli(
                module="ecc",
                event="ecc.layout",
                latency_ms=(time.perf_counter() - t_ecc) * 1000.0,
                tokens=len(pl.get("entries") or []),
                success=True,
            )
            return 0
        if ecc_act == "scaffold":
            rbase = root_ecc if root_ecc is not None else Path.cwd().resolve()
            r = ecc_scaffold_workspace(
                rbase,
                dry_run=bool(getattr(args, "ecc_scaffold_dry_run", False)),
            )
            if bool(getattr(args, "json_output", False)):
                print(json.dumps(r, ensure_ascii=False))
            else:
                print(
                    f"[ecc scaffold] dry_run={r.get('dry_run')} "
                    f"created={len(r.get('created') or [])} skipped={len(r.get('skipped') or [])}",
                )
                for c in r.get("created") or []:
                    print(f"  + {c}")
                for s in r.get("skipped") or []:
                    print(f"  = {s}")
            _maybe_metrics_cli(
                module="ecc",
                event="ecc.scaffold",
                latency_ms=(time.perf_counter() - t_ecc) * 1000.0,
                tokens=len(r.get("created") or []),
                success=True,
            )
            return 0
        print(f"unknown ecc action: {ecc_act}", file=sys.stderr)
        return 2

    if args.command == "doctor":
        try:
            settings = Settings.from_env(
                config_path=args.config,
                workspace_hint=_settings_workspace_hint(args),
            )
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        if args.model:
            settings = replace(settings, model=str(args.model).strip())
        if args.workspace:
            settings = replace(
                settings,
                workspace=os.path.abspath(args.workspace),
            )
        t_doc = time.perf_counter()
        rc_doc = run_doctor(
            settings,
            json_output=bool(getattr(args, "json_output", False)),
            fail_on_missing_api_key=bool(
                getattr(args, "fail_on_missing_api_key", False),
            ),
        )
        _maybe_metrics_cli(
            module="doctor",
            event="doctor.run",
            latency_ms=(time.perf_counter() - t_doc) * 1000.0,
            tokens=0,
            success=(int(rc_doc) == 0),
        )
        return rc_doc

    if args.command == "plan":
        t_plan = time.perf_counter()
        try:
            settings = Settings.from_env(
                config_path=args.config,
                workspace_hint=_settings_workspace_hint(args),
            )
        except FileNotFoundError as e:
            if bool(getattr(args, "json_output", False)):
                print(
                    json.dumps(
                        {
                            "plan_schema_version": "1.0",
                            "ok": False,
                            "error": "config_not_found",
                            "message": str(e),
                            "generated_at": datetime.now(UTC).isoformat(),
                        },
                        ensure_ascii=False,
                    ),
                )
            else:
                print(str(e), file=sys.stderr)
            _maybe_metrics_cli(
                module="plan",
                event="plan.generate",
                latency_ms=(time.perf_counter() - t_plan) * 1000.0,
                tokens=0,
                success=False,
            )
            return 2
        if args.model:
            settings = replace(settings, model=str(args.model).strip())
        if args.workspace:
            settings = replace(
                settings,
                workspace=os.path.abspath(args.workspace),
            )
        goal = " ".join(args.goal).strip()
        if not goal:
            if bool(getattr(args, "json_output", False)):
                print(
                    json.dumps(
                        {
                            "plan_schema_version": "1.0",
                            "ok": False,
                            "error": "goal_empty",
                            "message": "goal 不能为空",
                            "generated_at": datetime.now(UTC).isoformat(),
                            "task": None,
                        },
                        ensure_ascii=False,
                    ),
                )
            else:
                print("goal 不能为空", file=sys.stderr)
            _maybe_metrics_cli(
                module="plan",
                event="plan.generate",
                latency_ms=(time.perf_counter() - t_plan) * 1000.0,
                tokens=0,
                success=False,
            )
            return 2

        rules_text = load_rule_text(settings)
        rules_block = (
            "\n\n下面是与本项目相关的工程规则与安全约定，请在规划中严格遵守：\n"
            f"{rules_text}\n"
        ) if rules_text else ""

        system = (
            "你是 CAI Agent 的规划助手，只负责在执行前给出实现方案，"
            "不会真正修改文件或运行命令。\n"
            "请以分步结构化方式输出：\n"
            "1) 总体目标与风险\n"
            "2) 需要修改/创建的文件列表\n"
            "3) 每个步骤的大致实现要点\n"
            "4) 验证与回滚策略\n\n"
            f"工作区根目录: {settings.workspace}\n\n"
            "下列是 Agent 在执行阶段可用的工具说明（只读/写入/搜索等）：\n"
            f"{tools_spec_markdown()}\n"
            "本次仅输出规划文本，不要再输出 JSON 工具调用指令。"
            f"{rules_block}"
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": goal},
        ]
        reset_usage_counters()
        plan_task = new_task("plan")
        plan_task.status = "running"
        started = time.perf_counter()
        try:
            plan_text = chat_completion_by_role(settings, messages, role="planner")
        except KeyboardInterrupt:
            plan_task.status = "failed"
            plan_task.ended_at = time.time()
            plan_task.elapsed_ms = int((time.perf_counter() - started) * 1000)
            plan_task.error = "interrupted"
            if bool(getattr(args, "json_output", False)):
                print(
                    json.dumps(
                        {
                            "plan_schema_version": "1.0",
                            "ok": False,
                            "error": "interrupted",
                            "message": "用户已手动停止",
                            "generated_at": datetime.now(UTC).isoformat(),
                            "goal": goal,
                            "workspace": settings.workspace,
                            "provider": settings.provider,
                            "model": settings.model,
                            "task": plan_task.to_dict(),
                            "usage": get_usage_counters(),
                        },
                        ensure_ascii=False,
                    ),
                )
            else:
                print("已手动停止（Ctrl+C）。", file=sys.stderr)
            u_int = get_usage_counters()
            _maybe_metrics_cli(
                module="plan",
                event="plan.generate",
                latency_ms=(time.perf_counter() - t_plan) * 1000.0,
                tokens=int(u_int.get("total_tokens") or 0),
                success=False,
            )
            return 130
        except Exception as e:
            plan_task.status = "failed"
            plan_task.ended_at = time.time()
            plan_task.elapsed_ms = int((time.perf_counter() - started) * 1000)
            plan_task.error = str(e)[:800]
            if bool(getattr(args, "json_output", False)):
                print(
                    json.dumps(
                        {
                            "plan_schema_version": "1.0",
                            "ok": False,
                            "error": "llm_error",
                            "message": str(e),
                            "generated_at": datetime.now(UTC).isoformat(),
                            "goal": goal,
                            "workspace": settings.workspace,
                            "provider": settings.provider,
                            "model": settings.model,
                            "task": plan_task.to_dict(),
                            "usage": get_usage_counters(),
                        },
                        ensure_ascii=False,
                    ),
                )
            else:
                print(f"生成计划失败: {e}", file=sys.stderr)
            u_err = get_usage_counters()
            _maybe_metrics_cli(
                module="plan",
                event="plan.generate",
                latency_ms=(time.perf_counter() - t_plan) * 1000.0,
                tokens=int(u_err.get("total_tokens") or 0),
                success=False,
            )
            return 2
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        usage = get_usage_counters()
        plan_task.ended_at = time.time()
        plan_task.elapsed_ms = elapsed_ms
        plan_task.status = "completed"
        if args.json_output:
            payload = {
                "plan_schema_version": "1.0",
                "ok": True,
                "generated_at": datetime.now(UTC).isoformat(),
                "goal": goal,
                "plan": plan_text.strip(),
                "workspace": settings.workspace,
                "provider": settings.provider,
                "model": settings.model,
                "elapsed_ms": elapsed_ms,
                "usage": usage,
                "task": plan_task.to_dict(),
            }
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(plan_text.strip())
            print(
                f"\n[plan] provider={settings.provider} model={settings.model} "
                f"elapsed_ms={elapsed_ms} "
                f"tokens={usage.get('total_tokens', 0)}",
                file=sys.stderr,
            )
        wp = getattr(args, "write_plan", None)
        if wp:
            out_p = Path(str(wp)).expanduser().resolve()
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(plan_text.strip() + "\n", encoding="utf-8")
        _maybe_metrics_cli(
            module="plan",
            event="plan.generate",
            latency_ms=(time.perf_counter() - t_plan) * 1000.0,
            tokens=int(usage.get("total_tokens") or 0),
            success=True,
        )
        return 0

    if args.command == "model":
        loaded_ma = _load_settings_for_models(args.config)
        if isinstance(loaded_ma, int):
            return loaded_ma
        settings_ma: Settings = loaded_ma
        if getattr(args, "model", None):
            settings_ma = replace(settings_ma, model=str(args.model).strip())
        if getattr(args, "workspace", None):
            settings_ma = replace(
                settings_ma,
                workspace=os.path.abspath(str(args.workspace)),
            )
        if sys.stdin.isatty() and sys.stdout.isatty():
            try:
                from cai_agent.tui_model_panel import run_standalone_model_panel

                return int(run_standalone_model_panel(settings_ma))
            except Exception as e:
                print(f"model 面板启动失败: {e}", file=sys.stderr)
                return 2
        ns_suggest = argparse.Namespace(
            config=args.config,
            models_action="suggest",
            task_description=["(non-interactive: use `cai-agent models suggest <task>` for custom text)"],
            json_output=True,
            workspace=getattr(args, "workspace", None),
            model=getattr(args, "model", None),
        )
        return _cmd_models(ns_suggest)

    if args.command == "models":
        t_mdl = time.perf_counter()
        rc_mdl = _cmd_models(args)
        act_m = str(getattr(args, "models_action", None) or "list").strip().lower()
        ev_m = {
            "list": "models.list",
            "fetch": "models.fetch",
            "ping": "models.ping",
            "route": "models.route",
            "route-wizard": "models.route_wizard",
            "routing-test": "models.routing_test",
            "onboarding": "models.onboarding",
            "suggest": "models.suggest",
            "add": "models.add",
            "use": "models.use",
            "rm": "models.rm",
            "edit": "models.edit",
        }.get(act_m, "models.cli")
        tok_m = 0
        if act_m == "list" and int(rc_mdl) == 0:
            ld = _load_settings_for_models(getattr(args, "config", None))
            if not isinstance(ld, int):
                tok_m = len(ld.profiles)
        elif act_m == "fetch" and int(rc_mdl) == 0 and bool(getattr(args, "json_output", False)):
            tok_m = 1
        elif act_m == "ping" and int(rc_mdl) == 0:
            ld2 = _load_settings_for_models(getattr(args, "config", None))
            if not isinstance(ld2, int):
                pid = getattr(args, "id", None)
                if pid:
                    tok_m = 1
                else:
                    tok_m = len(ld2.profiles)
        elif act_m in {"add", "use", "rm", "route", "route-wizard", "routing-test", "edit", "suggest"} and int(rc_mdl) == 0:
            tok_m = 1
        _maybe_metrics_cli(
            module="models",
            event=ev_m,
            latency_ms=(time.perf_counter() - t_mdl) * 1000.0,
            tokens=tok_m,
            success=(int(rc_mdl) == 0),
        )
        return rc_mdl

    if args.command == "runtime":
        try:
            settings_rt = Settings.from_env(
                config_path=args.config,
                workspace_hint=_settings_workspace_hint(args),
            )
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        if args.model:
            settings_rt = replace(settings_rt, model=str(args.model).strip())
        workspace_rt = getattr(args, "workspace", None)
        if workspace_rt:
            settings_rt = replace(
                settings_rt,
                workspace=os.path.abspath(workspace_rt),
            )
        act_rt = str(getattr(args, "runtime_action", "") or "").strip()
        t_rt = time.perf_counter()
        if act_rt == "list":
            from cai_agent.runtime.registry import list_runtimes_payload

            doc_rt = list_runtimes_payload()
            if bool(getattr(args, "json_output", False)):
                print(json.dumps(doc_rt, ensure_ascii=False))
            else:
                print("runtime backends:", ", ".join(doc_rt.get("backends") or []))
            _maybe_metrics_cli(
                module="runtime",
                event="runtime.list",
                latency_ms=(time.perf_counter() - t_rt) * 1000.0,
                tokens=len(doc_rt.get("backends") or []),
                success=True,
            )
            return 0
        if act_rt == "test":
            from cai_agent.runtime.registry import get_runtime_backend

            bname = str(getattr(args, "runtime_backend_name", "local") or "local").strip()
            be = get_runtime_backend(bname, settings=settings_rt)
            cwd = str(Path(settings_rt.workspace).resolve())
            res = be.exec(["echo", "hello"], cwd=cwd, timeout_sec=15.0)
            out_doc = {
                "schema_version": "runtime_test_v1",
                "backend": bname,
                "returncode": res.returncode,
                "stdout": (res.stdout or "").strip(),
                "stderr": (res.stderr or "").strip(),
                "error_kind": res.error_kind,
                "exists": be.exists(),
            }
            if bool(getattr(args, "json_output", False)):
                print(json.dumps(out_doc, ensure_ascii=False))
            else:
                print(
                    f"runtime test: backend={bname} rc={res.returncode} "
                    f"exists={be.exists()} err={res.error_kind!r}",
                )
                if res.stdout.strip():
                    print(res.stdout.strip())
            _maybe_metrics_cli(
                module="runtime",
                event="runtime.test",
                latency_ms=(time.perf_counter() - t_rt) * 1000.0,
                tokens=1,
                success=(res.returncode == 0),
            )
            return 0 if res.returncode == 0 else 2
        print("runtime: 未知子命令", file=sys.stderr)
        return 2

    if args.command == "plugins":
        try:
            settings = Settings.from_env(
                config_path=args.config,
                workspace_hint=_settings_workspace_hint(args),
            )
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        if args.model:
            settings = replace(settings, model=str(args.model).strip())
        t_plg = time.perf_counter()
        surface = list_plugin_surface(settings)
        if bool(getattr(args, "plugins_with_compat_matrix", False)):
            from cai_agent.plugin_registry import build_plugin_compat_matrix

            surface = {**surface, "compat_matrix": build_plugin_compat_matrix()}
        compat_check_fail = False
        if bool(getattr(args, "plugins_compat_check", False)):
            from cai_agent.plugin_registry import build_plugin_compat_matrix_check_v1

            compat_check = build_plugin_compat_matrix_check_v1()
            surface = {**surface, "compat_check": compat_check}
            compat_check_fail = not bool(compat_check.get("ok"))
        plg_tok = 0
        comps_plg = surface.get("components")
        if isinstance(comps_plg, dict):
            for meta_plg in comps_plg.values():
                if isinstance(meta_plg, dict):
                    plg_tok += int(meta_plg.get("files_count") or 0)
        if args.json_output:
            print(json.dumps(surface, ensure_ascii=False))
        else:
            print(f"project_root={surface.get('project_root')}")
            comps = surface.get("components")
            if isinstance(comps, dict):
                for name, meta in comps.items():
                    if not isinstance(meta, dict):
                        continue
                    exists = bool(meta.get("exists"))
                    files_count = int(meta.get("files_count", 0))
                    print(f"- {name}: exists={exists} files={files_count}")
            cc = surface.get("compat_check") if isinstance(surface.get("compat_check"), dict) else None
            if cc is not None:
                missing_c = cc.get("missing_components") or []
                missing_t = cc.get("missing_targets") or []
                mismatches = cc.get("row_mismatches") or []
                status = "ok" if cc.get("ok") else "fail"
                print(
                    f"compat_check={status} "
                    f"missing_components={len(missing_c)} "
                    f"missing_targets={len(missing_t)} "
                    f"row_mismatches={len(mismatches)}",
                )
                if missing_c:
                    print("  missing_components:", ", ".join(str(x) for x in missing_c))
                if missing_t:
                    print("  missing_targets:", ", ".join(str(x) for x in missing_t))
                for rm in mismatches:
                    if isinstance(rm, dict):
                        print(
                            "  mismatch:",
                            f"component={rm.get('component')!r}",
                            f"missing_target_keys={rm.get('missing_target_keys')}",
                        )
        min_h = getattr(args, "fail_on_min_health", None)
        health_fail = False
        if isinstance(min_h, int):
            hs = int(surface.get("health_score") or 0)
            if hs < int(min_h):
                health_fail = True
        failed = health_fail or compat_check_fail
        _maybe_metrics_cli(
            module="plugins",
            event="plugins.surface",
            latency_ms=(time.perf_counter() - t_plg) * 1000.0,
            tokens=plg_tok,
            success=not failed,
        )
        if failed:
            return 2
        return 0

    if args.command == "skills":
        act = str(getattr(args, "skills_action", "") or "").strip()
        if act == "usage":
            from cai_agent.skill_evolution import aggregate_skill_usage, build_skills_usage_trend_v1

            root_us = Path.cwd().resolve()
            filt = str(getattr(args, "skills_usage_skill", "") or "").strip() or None
            t_us = time.perf_counter()
            trend_days = getattr(args, "skills_usage_trend_days", None)
            if trend_days is not None:
                if not bool(getattr(args, "json_output", False)):
                    print("skills usage --trend 需与 --json 同用", file=sys.stderr)
                    return 2
                payload_us = build_skills_usage_trend_v1(
                    root_us,
                    days=int(trend_days) if int(trend_days) > 0 else 14,
                    skill_id=filt,
                )
            else:
                payload_us = aggregate_skill_usage(root_us, skill_id=filt)
            if bool(getattr(args, "json_output", False)):
                print(json.dumps(payload_us, ensure_ascii=False))
            else:
                bys = payload_us.get("by_skill_id") or {}
                print(
                    f"skills usage: events={payload_us.get('total_events')} "
                    f"distinct_skills={len(bys)}",
                )
                for sid, cnt in sorted(bys.items(), key=lambda x: (-x[1], x[0]))[:40]:
                    print(f"  {cnt:4d}  {sid}")
            _maybe_metrics_cli(
                module="skills",
                event="skills.usage",
                latency_ms=(time.perf_counter() - t_us) * 1000.0,
                tokens=int(payload_us.get("total_events") or 0),
                success=True,
            )
            return 0
        if act == "revert":
            from cai_agent.skill_evolution import revert_skill_append_by_hist_id

            root_rv = Path.cwd().resolve()
            sid = str(getattr(args, "skills_revert_skill_id", "") or "").strip()
            hid = str(getattr(args, "skills_revert_hist_id", "") or "").strip()
            apply_rv = bool(getattr(args, "skills_revert_apply", False))
            t_rv = time.perf_counter()
            try:
                out_rv = revert_skill_append_by_hist_id(
                    root=root_rv,
                    skill_id=sid,
                    hist_id=hid,
                    apply=apply_rv,
                )
            except ValueError as e:
                print(f"skills revert: {e}", file=sys.stderr)
                return 2
            if bool(getattr(args, "json_output", False)):
                print(json.dumps(out_rv, ensure_ascii=False))
            else:
                print(
                    f"skills revert: skill={out_rv.get('skill_id')} hist={out_rv.get('hist_id')} "
                    f"written={out_rv.get('written')}",
                )
            _maybe_metrics_cli(
                module="skills",
                event="skills.revert",
                latency_ms=(time.perf_counter() - t_rv) * 1000.0,
                tokens=1,
                success=True,
            )
            return 0
        if act == "promote":
            from cai_agent.skills import auto_promote_evolution_skills, promote_evolution_skill

            root_pr = Path.cwd().resolve()
            t_pr = time.perf_counter()
            try:
                if bool(getattr(args, "skills_promote_auto", False)):
                    out_pr = auto_promote_evolution_skills(
                        root=root_pr,
                        threshold=getattr(args, "skills_promote_threshold", None),
                    )
                else:
                    to_nm = str(getattr(args, "skills_promote_to", "") or "").strip()
                    if not to_nm:
                        print("skills promote: 需要 --to <name>（非 --auto 时）", file=sys.stderr)
                        return 2
                    out_pr = promote_evolution_skill(
                        root=root_pr,
                        src_rel=str(getattr(args, "skills_promote_src", "") or "").strip(),
                        dest_name=to_nm,
                    )
            except ValueError as e:
                print(f"skills promote: {e}", file=sys.stderr)
                return 2
            if bool(getattr(args, "json_output", False)):
                print(json.dumps(out_pr, ensure_ascii=False))
            else:
                if bool(getattr(args, "skills_promote_auto", False)):
                    print(
                        f"skills promote --auto: promoted={len(out_pr.get('promoted') or [])} "
                        f"skipped={len(out_pr.get('skipped') or [])}",
                    )
                else:
                    print(
                        f"skills promote: ok={out_pr.get('ok')} from={out_pr.get('from')} to={out_pr.get('to')}",
                    )
            _maybe_metrics_cli(
                module="skills",
                event="skills.promote",
                latency_ms=(time.perf_counter() - t_pr) * 1000.0,
                tokens=1,
                success=bool(out_pr.get("ok")) if not bool(getattr(args, "skills_promote_auto", False)) else True,
            )
            if bool(getattr(args, "skills_promote_auto", False)):
                return 0
            return 0 if out_pr.get("ok") else 2
        if act == "lint":
            from cai_agent.skills import lint_skills_workspace

            root_l = Path.cwd().resolve()
            t_l = time.perf_counter()
            payload_l = lint_skills_workspace(root=root_l)
            if bool(getattr(args, "json_output", False)):
                print(json.dumps(payload_l, ensure_ascii=False))
            else:
                n = int(payload_l.get("violation_count") or 0)
                print(f"skills lint: violations={n} ok={payload_l.get('ok')}")
                for v in (payload_l.get("violations") or [])[:30]:
                    if isinstance(v, dict):
                        print(f"  - {v.get('name')}: {','.join(v.get('reasons') or [])}")
            _maybe_metrics_cli(
                module="skills",
                event="skills.lint",
                latency_ms=(time.perf_counter() - t_l) * 1000.0,
                tokens=int(payload_l.get("violation_count") or 0),
                success=bool(payload_l.get("ok")),
            )
            return 0 if payload_l.get("ok") else 2
        if act == "improve":
            from cai_agent.skill_evolution import (
                build_default_improve_note,
                improve_skill_append_note,
                improve_skill_with_llm_summary,
            )

            root_im = Path.cwd().resolve()
            sid = str(getattr(args, "skills_improve_skill_id", "") or "").strip()
            if not sid:
                print("SKILL_ID 不能为空", file=sys.stderr)
                return 2
            apply_im = bool(getattr(args, "skills_improve_apply", False))
            use_llm = bool(getattr(args, "skills_improve_llm", False))
            t_im = time.perf_counter()
            try:
                if use_llm:
                    try:
                        settings_im = Settings.from_env(
                            config_path=args.config,
                            workspace_hint=_settings_workspace_hint(args),
                        )
                    except FileNotFoundError as e:
                        print(str(e), file=sys.stderr)
                        return 2
                    if args.model:
                        settings_im = replace(settings_im, model=str(args.model).strip())
                    if args.workspace:
                        settings_im = replace(
                            settings_im,
                            workspace=os.path.abspath(args.workspace),
                        )
                    out_im = improve_skill_with_llm_summary(
                        root=root_im,
                        skill_id=sid,
                        settings=settings_im,
                        apply=apply_im,
                    )
                else:
                    note = build_default_improve_note(root_im, sid)
                    out_im = improve_skill_append_note(
                        root=root_im,
                        skill_id=sid,
                        note_md=note,
                        apply=apply_im,
                    )
            except ValueError as e:
                print(f"skills improve: {e}", file=sys.stderr)
                return 2
            if bool(getattr(args, "json_output", False)):
                print(json.dumps(out_im, ensure_ascii=False))
            else:
                print(
                    f"skills improve: skill_id={out_im.get('skill_id')} "
                    f"written={out_im.get('written')} apply={apply_im} llm={use_llm}",
                )
                if not apply_im and out_im.get("preview_append"):
                    print(str(out_im.get("preview_append"))[:900], file=sys.stderr)
            _maybe_metrics_cli(
                module="skills",
                event="skills.improve",
                latency_ms=(time.perf_counter() - t_im) * 1000.0,
                tokens=1,
                success=True,
            )
            return 0
        if act != "hub":
            print("skills: 未知子命令（支持 hub / improve / usage / lint / promote / revert）", file=sys.stderr)
            return 2
        hub_act = str(getattr(args, "skills_hub_action", "") or "").strip()
        if hub_act not in ("manifest", "suggest", "serve", "fetch", "install", "list-remote"):
            print(
                "skills hub: 仅支持 manifest / suggest / serve / fetch / install / list-remote",
                file=sys.stderr,
            )
            return 2
        root_sk = Path.cwd().resolve()
        if hub_act == "manifest":
            from cai_agent.skills import build_skills_hub_manifest

            t_sk = time.perf_counter()
            payload_sm = build_skills_hub_manifest(root=str(root_sk))
            if bool(getattr(args, "json_output", False)):
                print(json.dumps(payload_sm, ensure_ascii=False))
            else:
                print(
                    f"skills Hub manifest: count={payload_sm.get('count')} "
                    f"skills_dir_exists={payload_sm.get('skills_dir_exists')}",
                )
            _maybe_metrics_cli(
                module="skills",
                event="skills.hub_manifest",
                latency_ms=(time.perf_counter() - t_sk) * 1000.0,
                tokens=int(payload_sm.get("count") or 0),
                success=True,
            )
            return 0
        if hub_act == "install":
            from cai_agent.skills import apply_skills_hub_manifest_selection, fetch_remote_skills_manifest

            from_url = str(getattr(args, "hub_install_from_url", "") or "").strip()
            doc: dict[str, Any]
            if from_url:
                try:
                    fetched = fetch_remote_skills_manifest(from_url)
                except Exception as e:
                    print(f"拉取远程 manifest 失败: {e}", file=sys.stderr)
                    return 2
                if not isinstance(fetched, dict):
                    print("远程 manifest 根须为 object", file=sys.stderr)
                    return 2
                doc = dict(fetched)
                doc["manifest_origin_url"] = from_url
            else:
                mp = Path(str(getattr(args, "manifest", "") or "")).expanduser().resolve()
                if not str(getattr(args, "manifest", "") or "").strip() or not mp.is_file():
                    print("需要 --manifest PATH 或 --from URL", file=sys.stderr)
                    return 2
                try:
                    doc = json.loads(mp.read_text(encoding="utf-8"))
                except json.JSONDecodeError as e:
                    print(f"manifest JSON 无效: {e}", file=sys.stderr)
                    return 2
                if not isinstance(doc, dict):
                    print("manifest 根须为 object", file=sys.stderr)
                    return 2
            only_raw = str(getattr(args, "only", "") or "").strip()
            only_set: frozenset[str] | None = None
            if only_raw:
                only_set = frozenset(x.strip() for x in only_raw.split(",") if x.strip())
            t_ins = time.perf_counter()
            try:
                out_ins = apply_skills_hub_manifest_selection(
                    root=str(root_sk),
                    manifest=doc,
                    only=only_set,
                    dest_rel=str(getattr(args, "dest", ".cursor/skills") or ".cursor/skills"),
                    dry_run=bool(getattr(args, "dry_run", False)),
                )
            except ValueError as e:
                print(str(e), file=sys.stderr)
                return 2
            if bool(getattr(args, "json_output", False)):
                print(json.dumps(out_ins, ensure_ascii=False))
            else:
                print(
                    f"skills install: dry_run={out_ins.get('dry_run')} "
                    f"copied={len(out_ins.get('copied') or [])} skipped={len(out_ins.get('skipped') or [])}",
                )
            _maybe_metrics_cli(
                module="skills",
                event="skills.hub_install",
                latency_ms=(time.perf_counter() - t_ins) * 1000.0,
                tokens=len(out_ins.get("copied") or []),
                success=True,
            )
            return 0
        if hub_act == "serve":
            from cai_agent.skills import serve_skills_hub

            srv_host = str(getattr(args, "host", "127.0.0.1") or "127.0.0.1")
            srv_port = int(getattr(args, "port", 7891) or 7891)
            srv_timeout = getattr(args, "serve_timeout", None)
            json_out_srv = bool(getattr(args, "json_output", False))
            if not json_out_srv:
                print(f"Skills Hub 服务启动中 http://{srv_host}:{srv_port}/manifest — Ctrl+C 停止")
            try:
                srv_result = serve_skills_hub(
                    root=str(root_sk),
                    host=srv_host,
                    port=srv_port,
                    timeout_seconds=srv_timeout,
                )
            except OSError as e:
                print(f"无法启动 Skills Hub 服务: {e}", file=sys.stderr)
                return 2
            if json_out_srv:
                print(json.dumps(srv_result, ensure_ascii=False))
            else:
                print(f"Skills Hub 服务已停止 ok={srv_result.get('ok')}")
            return 0
        if hub_act == "fetch":
            from cai_agent.skills import fetch_remote_skills_manifest

            url = str(getattr(args, "skills_hub_fetch_url", "") or "").strip()
            if not url:
                print("URL 不能为空", file=sys.stderr)
                return 2
            t_ft = time.perf_counter()
            try:
                doc = fetch_remote_skills_manifest(url)
            except Exception as e:
                print(f"skills hub fetch 失败: {e}", file=sys.stderr)
                return 2
            if bool(getattr(args, "json_output", False)):
                print(
                    json.dumps(
                        {"schema_version": "skills_hub_fetch_v1", "url": url, "manifest": doc},
                        ensure_ascii=False,
                    ),
                )
            else:
                print(json.dumps(doc, ensure_ascii=False))
            _maybe_metrics_cli(
                module="skills",
                event="skills.hub_fetch",
                latency_ms=(time.perf_counter() - t_ft) * 1000.0,
                tokens=1,
                success=True,
            )
            return 0
        if hub_act == "list-remote":
            from cai_agent.skills import list_remote_skills_registry_index

            url_lr = str(getattr(args, "skills_hub_list_remote_url", "") or "").strip()
            if not url_lr:
                print("URL 不能为空", file=sys.stderr)
                return 2
            t_lr = time.perf_counter()
            try:
                doc_lr = list_remote_skills_registry_index(
                    url_lr,
                    sync_mirror=bool(getattr(args, "skills_hub_sync_mirror", False)),
                    mirror_cwd=str(root_sk),
                )
            except Exception as e:
                print(f"skills hub list-remote 失败: {e}", file=sys.stderr)
                return 2
            if bool(getattr(args, "json_output", False)):
                print(json.dumps(doc_lr, ensure_ascii=False))
            else:
                print(
                    f"remote manifest: count={doc_lr.get('count')} "
                    f"schema={doc_lr.get('manifest_schema')!r}",
                )
            _maybe_metrics_cli(
                module="skills",
                event="skills.hub_list_remote",
                latency_ms=(time.perf_counter() - t_lr) * 1000.0,
                tokens=int(doc_lr.get("count") or 0),
                success=True,
            )
            return 0
        from cai_agent.skills import build_skill_evolution_suggest

        goal_ev = " ".join(getattr(args, "skills_suggest_goal", []) or []).strip()
        if not goal_ev:
            print("goal 不能为空", file=sys.stderr)
            return 2
        t_sug = time.perf_counter()
        payload_sug = build_skill_evolution_suggest(
            root=str(root_sk),
            goal=goal_ev,
            write=bool(getattr(args, "write", False)),
        )
        if bool(getattr(args, "json_output", False)):
            print(json.dumps(payload_sug, ensure_ascii=False))
        else:
            print(
                f"skills evolution suggest: path={payload_sug.get('suggested_path')} "
                f"written={payload_sug.get('written')}",
            )
        _maybe_metrics_cli(
            module="skills",
            event="skills.evolution_suggest",
            latency_ms=(time.perf_counter() - t_sug) * 1000.0,
            tokens=max(1, len(goal_ev) // 64),
            success=True,
        )
        return 0

    if args.command == "commands":
        try:
            settings = Settings.from_env(
                config_path=args.config,
                workspace_hint=_settings_workspace_hint(args),
            )
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        if args.model:
            settings = replace(settings, model=str(args.model).strip())
        t_cmdn = time.perf_counter()
        names = list_command_names(settings)
        if args.json_output:
            print(
                json.dumps(
                    {"schema_version": "commands_list_v1", "commands": names},
                    ensure_ascii=False,
                ),
            )
        else:
            if not names:
                print("(无命令模板)")
            for n in names:
                print(f"/{n}")
        _maybe_metrics_cli(
            module="commands",
            event="commands.list",
            latency_ms=(time.perf_counter() - t_cmdn) * 1000.0,
            tokens=len(names),
            success=True,
        )
        return 0

    if args.command == "agents":
        try:
            settings = Settings.from_env(
                config_path=args.config,
                workspace_hint=_settings_workspace_hint(args),
            )
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        if args.model:
            settings = replace(settings, model=str(args.model).strip())
        t_ag = time.perf_counter()
        names = list_agent_names(settings)
        if args.json_output:
            print(
                json.dumps(
                    {"schema_version": "agents_list_v1", "agents": names},
                    ensure_ascii=False,
                ),
            )
        else:
            if not names:
                print("(无子代理模板)")
            for n in names:
                print(n)
        _maybe_metrics_cli(
            module="agents",
            event="agents.list",
            latency_ms=(time.perf_counter() - t_ag) * 1000.0,
            tokens=len(names),
            success=True,
        )
        return 0

    if args.command == "mcp-check":
        try:
            settings = Settings.from_env(
                config_path=args.config,
                workspace_hint=_settings_workspace_hint(args),
            )
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        if args.model:
            settings = replace(settings, model=str(args.model).strip())
        started = time.perf_counter()
        try:
            txt = dispatch(settings, "mcp_list_tools", {"force": bool(args.force)})
            ok = not txt.startswith("[mcp_list_tools 失败]")
        except Exception as e:
            ok = False
            txt = f"{type(e).__name__}: {e}"
        tool_list: list[str] = []
        if isinstance(txt, str):
            for line in txt.splitlines():
                s = line.strip()
                if s.startswith("- "):
                    name = s[2:].strip()
                    if name:
                        tool_list.append(name)
        preset = str(getattr(args, "preset", "") or "").strip().lower() or None
        preset_names = expand_mcp_preset_choice(preset)
        preset_reports = [build_mcp_preset_report(name=name, tool_list=tool_list) for name in preset_names]
        preset_matches: list[str] = []
        preset_missing: list[str] = []
        for report in preset_reports:
            preset_matches.extend([str(x) for x in (report.get("matched_tools") or [])])
            preset_missing.extend([str(x) for x in (report.get("missing_tools") or [])])
        preset_matches = list(dict.fromkeys(preset_matches))
        preset_missing = list(dict.fromkeys(preset_missing))
        probe_result = None
        if ok and args.tool and not bool(getattr(args, "list_only", False)):
            try:
                probe_args = json.loads(args.args)
                if not isinstance(probe_args, dict):
                    raise ValueError("--args 必须是 JSON object")
                probe_result = dispatch(
                    settings,
                    "mcp_call_tool",
                    {"name": str(args.tool).strip(), "args": probe_args},
                )
                if isinstance(probe_result, str) and probe_result.startswith("[mcp_call_tool 失败]"):
                    ok = False
            except Exception as e:
                ok = False
                probe_result = f"{type(e).__name__}: {e}"
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        preset_payload: dict[str, Any] | None = None
        preset_hint: dict[str, Any] | None = None
        template_text: str | None = None
        if preset_names:
            aggregate_ok = all(bool(report.get("ok")) for report in preset_reports)
            preset_payload = {
                "name": preset,
                "selected_presets": preset_names,
                "recommended_tools": sorted(
                    {
                        str(tool)
                        for report in preset_reports
                        for tool in (report.get("recommended_tools") or [])
                    },
                ),
                "matched_tools": preset_matches,
                "matches": preset_matches,
                "missing_tools": preset_missing,
                "missing_keywords": preset_missing,
                "ok": aggregate_ok,
                "doc_path": "docs/WEBSEARCH_NOTEBOOK_MCP.zh-CN.md",
                "onboarding_path": "docs/ONBOARDING.zh-CN.md",
                "quickstart_commands": [
                    str(cmd)
                    for report in preset_reports
                    for cmd in (report.get("quickstart_commands") or [])
                ],
            }
            first_hint = next(
                (report.get("next_step") for report in preset_reports if isinstance(report.get("next_step"), dict)),
                None,
            )
            if isinstance(first_hint, dict):
                preset_hint = first_hint
            if bool(getattr(args, "print_template", False)):
                if len(preset_names) == 1:
                    template_text = build_mcp_preset_template(preset_names[0])
                else:
                    template_text = "\n".join(
                        [
                            build_mcp_preset_template(name).rstrip()
                            for name in preset_names
                        ],
                    )
        if args.json_output:
            payload = {
                "schema_version": "mcp_check_result_v1",
                "ok": ok,
                "provider": settings.provider,
                "model": settings.model,
                "mcp_enabled": settings.mcp_enabled,
                "mcp_base_url": settings.mcp_base_url,
                "force": bool(args.force),
                "tool": args.tool,
                "list_only": bool(getattr(args, "list_only", False)),
                "preset": preset_payload,
                "presets": preset_reports,
                "elapsed_ms": elapsed_ms,
                "result": txt,
                "tool_names": tool_list,
                "preset_matches": preset_matches,
                "preset_missing_keywords": preset_missing,
                "fallback_hint": preset_hint,
                "next_step": preset_hint,
                "template": template_text,
                "probe_result": probe_result,
            }
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"ok={ok}")
            print(f"mcp_enabled={settings.mcp_enabled}")
            print(f"mcp_base_url={settings.mcp_base_url}")
            if args.verbose:
                print(f"provider={settings.provider}")
                print(f"model={settings.model}")
                print(f"force={bool(args.force)}")
                print(f"tool={args.tool}")
                print(f"elapsed_ms={elapsed_ms}")
            print(txt)
            if preset_payload is not None:
                print(
                    "[preset] "
                    f"name={preset_payload.get('name')} "
                    f"ok={preset_payload.get('ok')} "
                    f"matched={len(preset_matches)} "
                    f"missing={len(preset_missing)}"
                )
                print(f"docs={preset_payload.get('doc_path')}")
                print(f"onboarding={preset_payload.get('onboarding_path')}")
                quickstart_commands = [
                    str(cmd)
                    for cmd in (preset_payload.get("quickstart_commands") or [])
                    if str(cmd).strip()
                ]
                if quickstart_commands:
                    print("--- preset quickstart ---")
                    for cmd in dict.fromkeys(quickstart_commands):
                        print(cmd)
                for report in preset_reports:
                    if not isinstance(report, dict):
                        continue
                    print(
                        f"- {report.get('title')} "
                        f"matched={len(report.get('matched_tools') or [])} "
                        f"missing={len(report.get('missing_tools') or [])} "
                        f"list={report.get('suggested_command')}",
                    )
            if preset_hint is not None:
                print("--- preset fallback hint ---")
                print(str(preset_hint.get("message") or ""))
                print(f"doc={preset_hint.get('doc_path')}")
                print(f"onboarding={preset_hint.get('onboarding_path')}")
                print(f"suggested={preset_hint.get('suggested_command')}")
                print(f"template={preset_hint.get('print_template_command')}")
            if template_text is not None:
                print("--- preset template ---")
                print(template_text)
            if probe_result is not None:
                print("--- tool probe ---")
                print(probe_result)
        _maybe_metrics_cli(
            module="mcp",
            event="mcp.check",
            latency_ms=float(elapsed_ms),
            tokens=len(tool_list),
            success=bool(ok),
        )
        return 0 if ok else 2

    if args.command == "mcp-serve":
        from cai_agent.mcp_serve import run_stdio_mcp_server

        return int(run_stdio_mcp_server())

    if args.command == "sessions":
        t_sess = time.perf_counter()
        files = list_session_files(
            cwd=os.getcwd(),
            pattern=str(args.pattern),
            limit=int(args.limit),
        )
        details: list[dict[str, object]] = []
        if args.details:
            for p in files:
                try:
                    sess = load_session(str(p))
                except Exception:
                    details.append(
                        {
                            "name": p.name,
                            "path": str(p),
                            "error": "parse_failed",
                        },
                    )
                    continue
                msgs = sess.get("messages")
                msg_list = msgs if isinstance(msgs, list) else []
                tc, used, last_tool, err_count = _collect_tool_stats(
                    msg_list if isinstance(msg_list, list) else [],
                )
                ans = sess.get("answer")
                ans_preview = ""
                if isinstance(ans, str) and ans.strip():
                    ans_preview = ans.strip()[:120] + ("…" if len(ans.strip()) > 120 else "")
                row: dict[str, object] = {
                    "name": p.name,
                    "path": str(p),
                    "messages_count": len(msg_list),
                    "tool_calls_count": tc,
                    "used_tools": used,
                    "last_tool": last_tool,
                    "error_count": err_count,
                    "answer_preview": ans_preview,
                }
                row.update(_session_file_json_extra(sess))
                details.append(row)
        if args.json_output:
            arr = []
            for i, p in enumerate(files):
                item: dict[str, object] = {
                    "name": p.name,
                    "path": str(p),
                    "mtime": int(p.stat().st_mtime),
                    "size": p.stat().st_size,
                }
                if args.details and i < len(details) and isinstance(details[i], dict):
                    item.update(details[i])
                elif not args.details:
                    try:
                        sess = load_session(str(p))
                        item.update(_session_file_json_extra(sess))
                    except Exception:
                        item["parse_error"] = True
                arr.append(item)
            print(
                json.dumps(
                    {
                        "schema_version": "sessions_list_v1",
                        "pattern": str(args.pattern),
                        "limit": int(args.limit),
                        "details": bool(args.details),
                        "sessions": arr,
                    },
                    ensure_ascii=False,
                ),
            )
        else:
            if not files:
                print("(无会话文件)")
            for i, p in enumerate(files, start=1):
                st = p.stat()
                print(f"{i:>2}. {p.name}\t{st.st_size} bytes")
                if args.details and i - 1 < len(details):
                    d = details[i - 1]
                    if "error" in d:
                        print("    [parse_failed]")
                    else:
                        print(
                            "    "
                            f"messages={d.get('messages_count')} "
                            f"tool_calls={d.get('tool_calls_count')} "
                            f"errors={d.get('error_count')} "
                            f"events={d.get('events_count')} "
                            f"last_tool={d.get('last_tool')}",
                        )
                        ap = d.get("answer_preview")
                        if isinstance(ap, str) and ap:
                            print(f"    answer={ap}")
        _maybe_metrics_cli(
            module="sessions",
            event="sessions.list",
            latency_ms=(time.perf_counter() - t_sess) * 1000.0,
            tokens=len(files),
            success=True,
        )
        return 0

    if args.command == "stats":
        t_stats = time.perf_counter()
        files = list_session_files(
            cwd=os.getcwd(),
            pattern=str(args.pattern),
            limit=int(args.limit),
        )
        total = 0
        total_elapsed = 0
        total_tool_calls = 0
        total_errors = 0
        by_model: dict[str, int] = {}
        run_events_total = 0
        sessions_with_events = 0
        parse_skipped = 0
        session_summaries: list[dict[str, Any]] = []

        for p in files:
            try:
                sess = load_session(str(p))
            except Exception:
                parse_skipped += 1
                continue
            total += 1
            elapsed = sess.get("elapsed_ms")
            if isinstance(elapsed, int):
                total_elapsed += elapsed
            model = sess.get("model")
            if isinstance(model, str) and model.strip():
                by_model[model] = by_model.get(model, 0) + 1
            msgs = sess.get("messages")
            msg_list = msgs if isinstance(msgs, list) else []
            tc, _, _, err_count = _collect_tool_stats(
                msg_list if isinstance(msg_list, list) else [],
            )
            total_tool_calls += tc
            total_errors += err_count
            extra = _session_file_json_extra(sess)
            evc = int(extra.get("events_count") or 0)
            run_events_total += evc
            if evc > 0:
                sessions_with_events += 1
            session_summaries.append(
                {
                    "name": p.name,
                    "events_count": evc,
                    "task_id": extra.get("task_id"),
                    "total_tokens": extra.get("total_tokens"),
                    "file_error_count": extra.get("error_count"),
                    "tool_calls_count": tc,
                    "message_tool_errors": err_count,
                },
            )

        summary = {
            "sessions_count": total,
            "elapsed_ms_total": total_elapsed,
            "elapsed_ms_avg": int(total_elapsed / total) if total else 0,
            "tool_calls_total": total_tool_calls,
            "tool_calls_avg": float(total_tool_calls) / total if total else 0.0,
            "tool_errors_total": total_errors,
            "tool_errors_avg": float(total_errors) / total if total else 0.0,
            "models_distribution": by_model,
        }
        if args.json_output:
            summary_json = {
                **summary,
                "stats_schema_version": "1.0",
                "run_events_total": run_events_total,
                "sessions_with_events": sessions_with_events,
                "parse_skipped": parse_skipped,
                "session_summaries": session_summaries,
            }
            print(json.dumps(summary_json, ensure_ascii=False))
        else:
            print(f"sessions_count={summary['sessions_count']}")
            print(f"elapsed_ms_total={summary['elapsed_ms_total']}")
            print(f"elapsed_ms_avg={summary['elapsed_ms_avg']}")
            print(f"tool_calls_total={summary['tool_calls_total']}")
            print(f"tool_calls_avg={summary['tool_calls_avg']:.2f}")
            print(f"tool_errors_total={summary['tool_errors_total']}")
            print(f"tool_errors_avg={summary['tool_errors_avg']:.2f}")
            print(
                f"run_events_total={run_events_total} "
                f"sessions_with_events={sessions_with_events} "
                f"parse_skipped={parse_skipped}",
            )
            if by_model:
                print("models_distribution:")
                for m, cnt in by_model.items():
                    print(f"  {m}: {cnt}")
        _maybe_metrics_cli(
            module="stats",
            event="stats.summary",
            latency_ms=(time.perf_counter() - t_stats) * 1000.0,
            tokens=int(summary.get("sessions_count") or 0),
            success=True,
        )
        return 0

    if args.command == "insights":
        t_ins = time.perf_counter()
        payload = _build_insights_payload(
            cwd=os.getcwd(),
            pattern=str(args.pattern),
            limit=int(args.limit),
            days=int(args.days),
        )
        if bool(getattr(args, "insights_cross_domain", False)):
            if not bool(args.json_output):
                print("insights: --cross-domain 需要同时指定 --json", file=sys.stderr)
                _maybe_metrics_cli(
                    module="insights",
                    event="insights.cross_domain",
                    latency_ms=(time.perf_counter() - t_ins) * 1000.0,
                    tokens=int(payload.get("sessions_in_window") or payload.get("total_tokens") or 0),
                    success=False,
                )
                return 2
            from cai_agent.insights_cross_domain import build_insights_cross_domain_v1

            doc = build_insights_cross_domain_v1(
                cwd=os.getcwd(),
                base_insights=payload,
                pattern=str(args.pattern),
                limit=int(args.limit),
                days=int(args.days),
            )
            print(json.dumps(doc, ensure_ascii=False))
        elif bool(args.json_output):
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(
                f"sessions_in_window={payload.get('sessions_in_window')} "
                f"failure_rate={float(payload.get('failure_rate', 0.0)):.2%} "
                f"total_tokens={payload.get('total_tokens')} "
                f"tool_calls_total={payload.get('tool_calls_total')}",
            )
            models_top = payload.get("models_top")
            if isinstance(models_top, list) and models_top:
                print("models_top:")
                for row in models_top:
                    if not isinstance(row, dict):
                        continue
                    print(f"  {row.get('model')}: {row.get('count')}")
            tools_top = payload.get("tools_top")
            if isinstance(tools_top, list) and tools_top:
                print("tools_top:")
                for row in tools_top[:5]:
                    if not isinstance(row, dict):
                        continue
                    print(f"  {row.get('tool')}: {row.get('count')}")
            top_err = payload.get("top_error_sessions")
            if isinstance(top_err, list) and top_err:
                print("top_error_sessions:")
                for row in top_err:
                    if not isinstance(row, dict):
                        continue
                    print(f"  {row.get('path')} errors={row.get('error_count')}")
        mx = getattr(args, "fail_on_max_failure_rate", None)
        rc_ins = 0
        if isinstance(mx, (int, float)):
            fr = float(payload.get("failure_rate") or 0.0)
            if fr + 1e-12 >= float(mx):
                rc_ins = 2
        tok_ins = int(payload.get("sessions_in_window") or payload.get("total_tokens") or 0)
        is_cd = bool(getattr(args, "insights_cross_domain", False)) and bool(args.json_output)
        _maybe_metrics_cli(
            module="insights",
            event="insights.cross_domain" if is_cd else "insights.summary",
            latency_ms=(time.perf_counter() - t_ins) * 1000.0,
            tokens=tok_ins,
            success=(rc_ins == 0),
        )
        return rc_ins

    if args.command == "recall":
        if bool(getattr(args, "evaluate", False)):
            ev = build_recall_evaluation_payload(
                os.getcwd(),
                days=int(getattr(args, "evaluate_days", 14) or 14),
            )
            if bool(getattr(args, "json_output", False)):
                print(json.dumps(ev, ensure_ascii=False))
            else:
                print(
                    f"[recall --evaluate] hit_rate={ev.get('recall_hit_rate')} "
                    f"queries={ev.get('recall_queries_total')} "
                    f"neg_events={ev.get('negative_events_total')}",
                )
                ntop = ev.get("negative_queries_top") or []
                if isinstance(ntop, list) and ntop:
                    print("top_negative_queries:")
                    for row in ntop[:8]:
                        if isinstance(row, dict):
                            print(f"  {row.get('count')}x  {row.get('query')!s}")
            return 0
        if not str(getattr(args, "query", "") or "").strip():
            print("recall: 请提供 --query，或使用 --evaluate 查看审计窗口统计", file=sys.stderr)
            return 2
        idx_arg = getattr(args, "index_path", None)
        idx_path = (
            str(idx_arg).strip()
            if isinstance(idx_arg, str) and str(idx_arg).strip()
            else None
        )
        t_rec = time.perf_counter()
        if bool(getattr(args, "fts5", False)):
            try:
                payload = _build_recall_payload_from_fts5(
                    cwd=os.getcwd(),
                    query=str(args.query),
                    limit=int(args.limit),
                    days=int(args.days),
                    hits_per_session=int(
                        args.max_matches if args.max_matches is not None else args.max_hits
                    ),
                    session_limit=int(args.limit),
                    use_regex=bool(args.regex),
                    case_sensitive=bool(getattr(args, "case_sensitive", False)),
                    sort=str(getattr(args, "sort", "recent") or "recent"),
                )
            except FileNotFoundError:
                if bool(args.json_output):
                    print(
                        json.dumps(
                            {
                                "ok": False,
                                "error": "fts5_index_missing",
                                "message": "FTS5 索引不存在，请先运行 cai-agent recall-index build --engine fts5",
                            },
                            ensure_ascii=False,
                        ),
                    )
                else:
                    print(
                        "FTS5 索引不存在，请先运行 cai-agent recall-index build --engine fts5",
                        file=sys.stderr,
                    )
                return 2
            except ValueError as e:
                if bool(args.json_output):
                    print(
                        json.dumps(
                            {"ok": False, "error": "fts5_unsupported", "message": str(e)},
                            ensure_ascii=False,
                        ),
                    )
                else:
                    print(str(e), file=sys.stderr)
                return 2
        elif bool(getattr(args, "use_index", False)):
            try:
                payload = _build_recall_payload_from_index(
                    index_file=str(_resolve_recall_index_path(cwd=os.getcwd(), index_path=idx_path)),
                    query=str(args.query),
                    use_regex=bool(args.regex),
                    case_sensitive=bool(getattr(args, "case_sensitive", False)),
                    session_limit=int(args.limit),
                    sort=str(getattr(args, "sort", "recent") or "recent"),
                )
            except FileNotFoundError:
                if bool(args.json_output):
                    print(
                        json.dumps(
                            {
                                "ok": False,
                                "error": "index_not_found",
                                "message": "索引文件不存在，请先运行 cai-agent recall-index build",
                            },
                            ensure_ascii=False,
                        ),
                    )
                else:
                    print("索引文件不存在，请先运行 cai-agent recall-index build", file=sys.stderr)
                return 2
            except Exception as e:
                if bool(args.json_output):
                    print(
                        json.dumps(
                            {"ok": False, "error": "index_read_failed", "message": str(e)},
                            ensure_ascii=False,
                        ),
                    )
                else:
                    print(f"读取索引失败: {e}", file=sys.stderr)
                return 2
        else:
            payload = _build_recall_payload(
                cwd=os.getcwd(),
                pattern=str(args.pattern),
                limit=int(args.limit),
                days=int(args.days),
                query=str(args.query),
                use_regex=bool(args.regex),
                case_sensitive=bool(getattr(args, "case_sensitive", False)),
                hits_per_session=int(
                    args.max_matches if args.max_matches is not None else args.max_hits
                ),
                session_limit=int(args.limit),
                sort=str(getattr(args, "sort", "recent") or "recent"),
            )
        if bool(getattr(args, "summarize", False)):
            payload = _apply_recall_summarize_heuristic(
                payload,
                top=int(getattr(args, "summarize_top", 5) or 5),
            )
        _tid: str | None = None
        for _r in (payload.get("results") or [])[:8]:
            if isinstance(_r, dict) and _r.get("task_id"):
                _tid = str(_r["task_id"])
                break
        append_recall_audit_line(
            os.getcwd(),
            query=str(args.query),
            hits_total=int(payload.get("hits_total") or 0),
            sessions_scanned=int(payload.get("sessions_scanned") or 0),
            sessions_with_hits=int(payload.get("sessions_with_hits") or 0),
            task_id=_tid,
            use_index=bool(getattr(args, "use_index", False)) or bool(getattr(args, "fts5", False)),
        )
        if int(payload.get("hits_total") or 0) <= 0:
            try:
                st_neg = Settings.from_env(config_path=None, workspace_hint=os.getcwd())
                if bool(getattr(st_neg, "memory_policy_recall_negative_audit", True)):
                    nhr = payload.get("no_hit_reason")
                    rn = str(nhr).strip() if isinstance(nhr, str) else None
                    append_negative_recall_line(os.getcwd(), query=str(args.query), reason=rn)
            except Exception:
                pass
        rec_ms = (time.perf_counter() - t_rec) * 1000.0
        _maybe_metrics_cli(
            module="recall",
            event="recall.query",
            latency_ms=rec_ms,
            tokens=int(payload.get("sessions_scanned") or 0),
            success=True,
        )
        if bool(args.json_output):
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(
                f"hits_total={payload.get('hits_total')} scanned={payload.get('sessions_scanned')} "
                f"matched_sessions={payload.get('sessions_with_hits')} "
                f"parse_skipped={payload.get('parse_skipped')}",
            )
            nhr = payload.get("no_hit_reason")
            if isinstance(nhr, str) and nhr.strip() and int(payload.get("hits_total") or 0) <= 0:
                hint = _RECALL_NO_HIT_HINTS.get(nhr.strip(), "")
                print(f"no_hit_reason={nhr}" + (f" — {hint}" if hint else ""))
            results = payload.get("results")
            if isinstance(results, list):
                for i, row in enumerate(results, start=1):
                    if not isinstance(row, dict):
                        continue
                    print(
                        f"{i:>2}. {row.get('path')} mtime={row.get('mtime')} model={row.get('model')}",
                    )
                    hits = row.get("hits")
                    if isinstance(hits, list) and hits:
                        sn = hits[0].get("snippet") if isinstance(hits[0], dict) else None
                        if isinstance(sn, str) and sn:
                            print(f"    {sn}")
        return 0

    if args.command == "recall-index":
        action = str(getattr(args, "recall_index_action", "build") or "build")
        cwd = os.getcwd()
        index_path_arg = getattr(args, "index_path", None)
        if action == "build":
            t_rix = time.perf_counter()
            eng = str(getattr(args, "engine", "legacy") or "legacy").strip().lower()
            if eng == "fts5":
                from cai_agent.recall_fts5 import build_fts5_recall_index

                payload = build_fts5_recall_index(
                    cwd=cwd,
                    pattern=str(args.pattern),
                    limit=int(args.limit),
                    days=int(args.days),
                )
            else:
                payload = _build_recall_index(
                    cwd=cwd,
                    pattern=str(args.pattern),
                    limit=int(args.limit),
                    days=int(args.days),
                    index_path=str(index_path_arg) if isinstance(index_path_arg, str) else None,
                )
            _maybe_metrics_cli(
                module="recall_index",
                event="recall_index.build",
                latency_ms=(time.perf_counter() - t_rix) * 1000.0,
                tokens=int(payload.get("sessions_indexed") or 0),
                success=True,
            )
            if bool(args.json_output):
                print(json.dumps(payload, ensure_ascii=False))
            else:
                print(
                    f"indexed_sessions={payload.get('sessions_indexed')} "
                    f"parse_skipped={payload.get('parse_skipped')} "
                    f"index_file={payload.get('index_file')}",
                )
            return 0
        if action == "refresh":
            t_rix = time.perf_counter()
            payload = _refresh_recall_index(
                cwd=cwd,
                pattern=str(args.pattern),
                limit=int(args.limit),
                days=int(args.days),
                index_path=str(index_path_arg) if isinstance(index_path_arg, str) else None,
                prune_missing=bool(getattr(args, "prune", False)),
            )
            _maybe_metrics_cli(
                module="recall_index",
                event="recall_index.refresh",
                latency_ms=(time.perf_counter() - t_rix) * 1000.0,
                tokens=int(payload.get("sessions_indexed") or payload.get("sessions_touched") or 0),
                success=True,
            )
            if bool(args.json_output):
                print(json.dumps(payload, ensure_ascii=False))
            else:
                print(
                    f"mode={payload.get('mode')} indexed_sessions={payload.get('sessions_indexed')} "
                    f"touched={payload.get('sessions_touched')} "
                    f"skipped_unchanged={payload.get('sessions_skipped_unchanged')} "
                    f"parse_skipped={payload.get('parse_skipped')} "
                    f"index_file={payload.get('index_file')}",
                )
            return 0
        if action == "search":
            t_rix = time.perf_counter()
            payload = _search_recall_index(
                cwd=cwd,
                query=str(args.query),
                regex=bool(args.regex),
                case_sensitive=bool(getattr(args, "case_sensitive", False)),
                max_hits=int(args.max_hits),
                index_path=str(index_path_arg) if isinstance(index_path_arg, str) else None,
                sort=str(getattr(args, "sort", "recent") or "recent"),
            )
            _maybe_metrics_cli(
                module="recall_index",
                event="recall_index.search",
                latency_ms=(time.perf_counter() - t_rix) * 1000.0,
                tokens=int(payload.get("sessions_scanned") or 0),
                success=True,
            )
            if bool(args.json_output):
                print(json.dumps(payload, ensure_ascii=False))
            else:
                print(
                    f"hits_total={payload.get('hits_total')} sessions_scanned={payload.get('sessions_scanned')} "
                    f"index_file={payload.get('index_file')}",
                )
                nhr2 = payload.get("no_hit_reason")
                if isinstance(nhr2, str) and nhr2.strip() and int(payload.get("hits_total") or 0) <= 0:
                    hint2 = _RECALL_NO_HIT_HINTS.get(nhr2.strip(), "")
                    print(f"no_hit_reason={nhr2}" + (f" — {hint2}" if hint2 else ""))
                results = payload.get("results")
                if isinstance(results, list):
                    for i, row in enumerate(results, start=1):
                        if not isinstance(row, dict):
                            continue
                        print(
                            f"{i:>2}. {row.get('path')} mtime={row.get('mtime')} model={row.get('model')}",
                        )
                        hits = row.get("hits")
                        if isinstance(hits, list) and hits:
                            sn = hits[0].get("snippet") if isinstance(hits[0], dict) else None
                            if isinstance(sn, str) and sn:
                                print(f"    {sn}")
            return 0
        if action == "benchmark":
            t_rix = time.perf_counter()
            payload = _benchmark_recall_index(
                cwd=cwd,
                query=str(args.query),
                regex=bool(args.regex),
                case_sensitive=bool(getattr(args, "case_sensitive", False)),
                days=int(args.days),
                pattern=str(args.pattern),
                limit=int(args.limit),
                max_hits=int(args.max_hits),
                index_path=str(index_path_arg) if isinstance(index_path_arg, str) else None,
                ensure_index=bool(getattr(args, "ensure_index", False)),
                runs=int(getattr(args, "runs", 3)),
                sort=str(getattr(args, "sort", "recent") or "recent"),
            )
            scan_blk = payload.get("scan") if isinstance(payload.get("scan"), dict) else {}
            _maybe_metrics_cli(
                module="recall_index",
                event="recall_index.benchmark",
                latency_ms=(time.perf_counter() - t_rix) * 1000.0,
                tokens=int(scan_blk.get("sessions_scanned") or 0),
                success=True,
            )
            if bool(args.json_output):
                print(json.dumps(payload, ensure_ascii=False))
            else:
                print(
                    f"benchmark query={payload.get('query')!r} runs={payload.get('runs')} "
                    f"scan_avg_ms={payload.get('scan_avg_ms')} index_avg_ms={payload.get('index_avg_ms')} "
                    f"speedup={payload.get('speedup_x')}",
                )
            return 0
        if action == "info":
            t_rix = time.perf_counter()
            payload = _recall_index_info(
                cwd=cwd,
                index_path=str(index_path_arg) if isinstance(index_path_arg, str) else None,
            )
            _maybe_metrics_cli(
                module="recall_index",
                event="recall_index.info",
                latency_ms=(time.perf_counter() - t_rix) * 1000.0,
                tokens=int(payload.get("entries_count") or 0),
                success=True,
            )
            if bool(args.json_output):
                print(json.dumps(payload, ensure_ascii=False))
            else:
                print(
                    f"ok={payload.get('ok')} entries_count={payload.get('entries_count')} "
                    f"index_file={payload.get('index_file')}",
                )
            return 0
        if action == "clear":
            t_rix = time.perf_counter()
            payload = _clear_recall_index(
                cwd=cwd,
                index_path=str(index_path_arg) if isinstance(index_path_arg, str) else None,
            )
            _maybe_metrics_cli(
                module="recall_index",
                event="recall_index.clear",
                latency_ms=(time.perf_counter() - t_rix) * 1000.0,
                tokens=int(payload.get("removed") or 0),
                success=True,
            )
            if bool(args.json_output):
                print(json.dumps(payload, ensure_ascii=False))
            else:
                print(f"removed={payload.get('removed')} index_file={payload.get('index_file')}")
            return 0
        if action == "doctor":
            t_rix = time.perf_counter()
            doc_payload, doc_rc = _recall_index_doctor(
                cwd=cwd,
                index_path=str(index_path_arg) if isinstance(index_path_arg, str) else None,
                fix=bool(getattr(args, "fix", False)),
            )
            iss = doc_payload.get("issues") if isinstance(doc_payload.get("issues"), list) else []
            miss = doc_payload.get("missing_files") if isinstance(doc_payload.get("missing_files"), list) else []
            stl = doc_payload.get("stale_paths") if isinstance(doc_payload.get("stale_paths"), list) else []
            _maybe_metrics_cli(
                module="recall_index",
                event="recall_index.doctor",
                latency_ms=(time.perf_counter() - t_rix) * 1000.0,
                tokens=len(iss) + len(miss) + len(stl),
                success=bool(doc_payload.get("is_healthy")),
            )
            if bool(args.json_output):
                print(json.dumps(doc_payload, ensure_ascii=False))
            else:
                print(
                    f"healthy={doc_payload.get('is_healthy')} "
                    f"issues={len(doc_payload.get('issues') or [])} "
                    f"missing={len(doc_payload.get('missing_files') or [])} "
                    f"stale={len(doc_payload.get('stale_paths') or [])} "
                    f"schema_ok={doc_payload.get('schema_version_ok')}",
                )
                if doc_payload.get("fixed"):
                    print(
                        f"fixed removed_missing={doc_payload.get('removed_missing', 0)} "
                        f"removed_stale={doc_payload.get('removed_stale', 0)}",
                    )
            return int(doc_rc)
        print(f"未知 recall-index 子命令: {action}", file=sys.stderr)
        return 2

    if args.command == "quality-gate":
        try:
            settings = Settings.from_env(
                config_path=args.config,
                workspace_hint=_settings_workspace_hint(args),
            )
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        if args.model:
            settings = replace(settings, model=str(args.model).strip())
        if args.workspace:
            settings = replace(
                settings,
                workspace=os.path.abspath(args.workspace),
            )
        t_qg = time.perf_counter()
        _print_hook_status(
            settings,
            event="quality_gate_start",
            json_output=bool(args.json_output),
        )
        try:
            result = run_quality_gate(
                settings,
                enable_compile=settings.quality_gate_compile
                and not bool(args.no_compile),
                enable_test=settings.quality_gate_test and not bool(args.no_test),
                enable_lint=bool(args.lint) or settings.quality_gate_lint,
                enable_typecheck=bool(args.typecheck)
                or settings.quality_gate_typecheck,
                enable_security_scan=bool(args.security_scan)
                or settings.quality_gate_security_scan,
                report_dir=getattr(args, "report_dir", None),
            )
        finally:
            _print_hook_status(
                settings,
                event="quality_gate_end",
                json_output=bool(args.json_output),
            )
        checks_qg = result.get("checks") if isinstance(result.get("checks"), list) else []
        _maybe_metrics_cli(
            module="quality_gate",
            event="quality_gate.run",
            latency_ms=(time.perf_counter() - t_qg) * 1000.0,
            tokens=len(checks_qg),
            success=bool(result.get("ok")),
        )
        if args.json_output:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(f"ok={result.get('ok')}")
            print(f"failed_count={result.get('failed_count')}")
            checks = result.get("checks")
            if isinstance(checks, list):
                for item in checks:
                    if not isinstance(item, dict):
                        continue
                    print(
                        f"- {item.get('name')}: exit={item.get('exit_code')} "
                        f"elapsed_ms={item.get('elapsed_ms')}",
                    )
        return 0 if bool(result.get("ok")) else 2

    if args.command == "security-scan":
        try:
            settings = Settings.from_env(
                config_path=args.config,
                workspace_hint=_settings_workspace_hint(args),
            )
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        if args.model:
            settings = replace(settings, model=str(args.model).strip())
        if args.workspace:
            settings = replace(
                settings,
                workspace=os.path.abspath(args.workspace),
            )
        exclude_globs = [
            str(x).strip()
            for x in (args.exclude_globs or [])
            if isinstance(x, str) and str(x).strip()
        ]
        ex_arg = exclude_globs if exclude_globs else None
        rule_flags = {
            "aws_access_key": True,
            "github_pat": True,
            "anthropic_api_key": True,
            "openrouter_api_key": True,
            "openai_like_key": True,
            "private_key_header": True,
            "cai_profile_plaintext_api_key": True,
        }
        rule_flags.update(dict(settings.security_scan_rule_overrides))
        if bool(args.disable_aws):
            rule_flags["aws_access_key"] = False
        if bool(args.disable_github):
            rule_flags["github_pat"] = False
        if bool(args.disable_openai):
            rule_flags["openai_like_key"] = False
        if bool(getattr(args, "disable_anthropic", False)):
            rule_flags["anthropic_api_key"] = False
        if bool(getattr(args, "disable_openrouter", False)):
            rule_flags["openrouter_api_key"] = False
        if bool(args.disable_private_key):
            rule_flags["private_key_header"] = False
        if bool(getattr(args, "disable_profile_plaintext_key", False)):
            rule_flags["cai_profile_plaintext_api_key"] = False
        _print_hook_status(
            settings,
            event="security_scan_start",
            json_output=bool(args.json_output),
        )
        try:
            t_ssc = time.perf_counter()
            result = run_security_scan(
                settings,
                exclude_globs=ex_arg,
                rule_flags=rule_flags,
            )
        except Exception as e:
            print(f"安全扫描失败: {e}", file=sys.stderr)
            return 2
        finally:
            _print_hook_status(
                settings,
                event="security_scan_end",
                json_output=bool(args.json_output),
            )
        _maybe_metrics_cli(
            module="security_scan",
            event="security_scan.run",
            latency_ms=(time.perf_counter() - t_ssc) * 1000.0,
            tokens=int(result.get("findings_count") or result.get("scanned_files") or 0),
            success=bool(result.get("ok")),
        )
        scan_ok = bool(result.get("ok"))
        fc = int(result.get("findings_count") or 0)
        hs = next(
            (
                True
                for f in (result.get("findings") or [])
                if isinstance(f, dict) and str(f.get("severity") or "").lower() == "high"
            ),
            False,
        )
        badge_color = "brightgreen" if scan_ok else ("red" if hs else "yellow")
        badge_msg = f"pass ({fc} findings)" if scan_ok else f"{'high risk' if hs else 'findings'} ({fc})"
        badge_payload: dict[str, Any] = {
            "schema_version": "security_badge_v1",
            "schemaVersion": 1,
            "label": "security-scan",
            "message": badge_msg,
            "color": badge_color,
            "namedLogo": "shieldsdotio",
            "findings_count": fc,
            "ok": scan_ok,
        }
        if args.json_output:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(f"ok={result.get('ok')}")
            print(f"scanned_files={result.get('scanned_files')}")
            print(f"findings_count={result.get('findings_count')}")
            findings = result.get("findings")
            if isinstance(findings, list):
                for item in findings[:20]:
                    if not isinstance(item, dict):
                        continue
                    print(
                        f"- [{item.get('severity')}] {item.get('rule')} "
                        f"{item.get('file')}:{item.get('line')}",
                    )
        if bool(getattr(args, "security_badge", False)):
            print(json.dumps(badge_payload, ensure_ascii=False))
        return 0 if scan_ok else 2

    if args.command == "pii-scan":
        try:
            settings = Settings.from_env(
                config_path=args.config,
                workspace_hint=_settings_workspace_hint(args),
            )
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        raw_target = getattr(args, "target", None)
        if raw_target:
            scan_target = Path(raw_target).expanduser()
        else:
            cai_dir = Path(settings.workspace) / ".cai"
            scan_target = cai_dir if cai_dir.is_dir() else Path(settings.workspace)
        pii_rule_flags: dict[str, bool] = {}
        if bool(getattr(args, "enable_email", False)):
            pii_rule_flags["email_address"] = True
        if bool(getattr(args, "enable_ipv4", False)):
            pii_rule_flags["ipv4_private"] = True
        t_pii = time.perf_counter()
        try:
            pii_result = run_pii_scan(
                scan_target,
                rule_flags=pii_rule_flags if pii_rule_flags else None,
                exclude_globs=list(getattr(args, "exclude_globs", []) or []),
                recursive=not bool(getattr(args, "no_recursive", False)),
            )
        except Exception as e:
            print(f"pii-scan 执行失败: {e}", file=sys.stderr)
            return 2
        _maybe_metrics_cli(
            module="security_scan",
            event="pii_scan.run",
            latency_ms=(time.perf_counter() - t_pii) * 1000.0,
            tokens=int(pii_result.get("scanned_files") or 0),
            success=bool(pii_result.get("ok")),
        )
        if bool(getattr(args, "json_output", False)):
            print(json.dumps(pii_result, ensure_ascii=False))
        else:
            print(f"ok={pii_result.get('ok')}")
            print(f"target={pii_result.get('target')}")
            print(f"scanned_files={pii_result.get('scanned_files')}")
            print(f"findings_count={pii_result.get('findings_count')} (high={pii_result.get('high_count')})")
            findings = pii_result.get("findings")
            if isinstance(findings, list):
                for item in findings[:20]:
                    if not isinstance(item, dict):
                        continue
                    print(
                        f"- [{item.get('severity')}] {item.get('rule')} "
                        f"{item.get('file')}:{item.get('line')}  {item.get('match', '')[:40]}"
                    )
        if bool(getattr(args, "fail_on_high", False)) and int(pii_result.get("high_count", 0)) > 0:
            return 2
        return 0

    if args.command == "hooks":
        try:
            settings = Settings.from_env(
                config_path=args.config,
                workspace_hint=_settings_workspace_hint(args),
            )
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        if args.model:
            settings = replace(settings, model=str(args.model).strip())
        if args.workspace:
            settings = replace(
                settings,
                workspace=os.path.abspath(args.workspace),
            )
        hooks_dir = getattr(args, "hooks_dir", None)
        hooks_dir_s = str(hooks_dir).strip() if hooks_dir is not None else ""
        hp = resolve_hooks_json_path(settings, hooks_dir=hooks_dir_s or None)
        if args.hooks_action == "list":
            t_hl = time.perf_counter()
            cat = describe_hooks_catalog(settings, hooks_path=hp)
            rows_hl = cat.get("hooks") if isinstance(cat.get("hooks"), list) else []
            n_hl = len(rows_hl)
            if bool(getattr(args, "json_output", False)):
                print(json.dumps(cat, ensure_ascii=False))
                err = cat.get("error")
                if err in ("hooks_json_not_found", "invalid_hooks_document"):
                    _maybe_metrics_cli(
                        module="hooks",
                        event="hooks.list",
                        latency_ms=(time.perf_counter() - t_hl) * 1000.0,
                        tokens=n_hl,
                        success=False,
                    )
                    return 2
            else:
                if cat.get("error") == "hooks_json_not_found":
                    print("[hooks] 未找到 hooks.json（尝试 hooks/ 与 .cai/hooks/）", file=sys.stderr)
                    _maybe_metrics_cli(
                        module="hooks",
                        event="hooks.list",
                        latency_ms=(time.perf_counter() - t_hl) * 1000.0,
                        tokens=0,
                        success=False,
                    )
                    return 2
                if cat.get("error") == "invalid_hooks_document":
                    print("[hooks] hooks.json 格式无效：缺少 hooks 数组", file=sys.stderr)
                    _maybe_metrics_cli(
                        module="hooks",
                        event="hooks.list",
                        latency_ms=(time.perf_counter() - t_hl) * 1000.0,
                        tokens=0,
                        success=False,
                    )
                    return 2
                print(f"hooks_file={cat.get('hooks_file')}")
                print(f"hooks_profile={cat.get('hooks_profile')}")
                rows = cat.get("hooks") if isinstance(cat.get("hooks"), list) else []
                print(f"entries={len(rows)}")
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    hid = row.get("id") or "?"
                    ev = row.get("event") or "?"
                    cmd = "y" if row.get("has_command") else "n"
                    rs = row.get("skip_or_block_reason")
                    rs_txt = f" reason={rs}" if rs else ""
                    print(
                        f"- id={hid} event={ev} enabled={row.get('enabled')} "
                        f"command={cmd} disabled={row.get('disabled_by_config')}{rs_txt}",
                    )
            _maybe_metrics_cli(
                module="hooks",
                event="hooks.list",
                latency_ms=(time.perf_counter() - t_hl) * 1000.0,
                tokens=n_hl,
                success=True,
            )
            return 0
        if args.hooks_action == "run-event":
            event = str(getattr(args, "event", "") or "").strip()
            if not event:
                print("event 不能为空", file=sys.stderr)
                return 2
            raw_pl = str(getattr(args, "payload", "") or "").strip() or "{}"
            try:
                pl_obj: Any = json.loads(raw_pl)
            except json.JSONDecodeError as e:
                print(f"--payload 须为 JSON 对象: {e}", file=sys.stderr)
                return 2
            if not isinstance(pl_obj, dict):
                print("--payload 须为 JSON object", file=sys.stderr)
                return 2
            dry = bool(getattr(args, "dry_run", False))
            t_hre = time.perf_counter()
            if hp is None or not hp.is_file():
                err_payload = {
                    "schema_version": "hooks_run_event_result_v1",
                    "event": event,
                    "hooks_file": None,
                    "dry_run": dry,
                    "error": "hooks_json_not_found",
                    "results": [],
                }
                if bool(getattr(args, "json_output", False)):
                    print(json.dumps(err_payload, ensure_ascii=False))
                else:
                    print("[hooks] 未找到 hooks.json", file=sys.stderr)
                _maybe_metrics_cli(
                    module="hooks",
                    event="hooks.run_event",
                    latency_ms=(time.perf_counter() - t_hre) * 1000.0,
                    tokens=0,
                    success=False,
                )
                return 2
            if dry:
                preview = preview_project_hooks(settings, event, hooks_path=hp)
                out_obj = {
                    "schema_version": "hooks_run_event_result_v1",
                    "event": event,
                    "hooks_file": str(hp),
                    "dry_run": True,
                    "results": preview,
                }
                if bool(getattr(args, "json_output", False)):
                    print(json.dumps(out_obj, ensure_ascii=False))
                else:
                    print(f"hooks_file={hp}")
                    print(f"event={event} dry_run=1")
                    for r in preview:
                        if not isinstance(r, dict):
                            continue
                        hid = r.get("id", "?")
                        st = r.get("status", "?")
                        rs = r.get("reason")
                        rs_txt = f" ({rs})" if isinstance(rs, str) and rs.strip() else ""
                        print(f"- {hid}: {st}{rs_txt}")
                _maybe_metrics_cli(
                    module="hooks",
                    event="hooks.run_event",
                    latency_ms=(time.perf_counter() - t_hre) * 1000.0,
                    tokens=len(preview),
                    success=True,
                )
                return 0
            results = run_project_hooks(
                settings,
                event,
                cast(dict[str, Any], pl_obj),
                hooks_path=hp,
            )
            out_obj = {
                "schema_version": "hooks_run_event_result_v1",
                "event": event,
                "hooks_file": str(hp),
                "dry_run": False,
                "results": results,
            }
            if bool(getattr(args, "json_output", False)):
                print(json.dumps(out_obj, ensure_ascii=False))
            else:
                print(f"hooks_file={hp}")
                print(f"event={event}")
                for r in results:
                    if not isinstance(r, dict):
                        continue
                    hid = r.get("id", "?")
                    st = r.get("status", "?")
                    rs = r.get("reason")
                    rc = r.get("returncode")
                    extra = ""
                    if isinstance(rs, str) and rs.strip():
                        extra += f" reason={rs}"
                    if rc is not None:
                        extra += f" rc={rc}"
                    print(f"- {hid}: {st}{extra}")
            bad = any(
                isinstance(r, dict) and str(r.get("status") or "") in ("error", "blocked")
                for r in results
            )
            _maybe_metrics_cli(
                module="hooks",
                event="hooks.run_event",
                latency_ms=(time.perf_counter() - t_hre) * 1000.0,
                tokens=len(results),
                success=not bad,
            )
            return 2 if bad else 0

    if args.command == "memory":
        settings_mem = Settings.from_env(config_path=None)
        mem_json = bool(getattr(args, "json_output", False))
        _print_hook_status(
            settings_mem,
            event="memory_start",
            json_output=mem_json,
        )
        try:
            root = Path.cwd().resolve()
            mem_dir = root / "memory" / "instincts"
            mem_dir.mkdir(parents=True, exist_ok=True)
            if args.memory_action == "extract":
                t_mx = time.perf_counter()
                from cai_agent.memory import require_memory_entries_jsonl_clean_before_write

                entries_jsonl = root / "memory" / "entries.jsonl"
                if entries_jsonl.is_file():
                    try:
                        require_memory_entries_jsonl_clean_before_write(root)
                    except ValueError as e:
                        msg = str(e).strip() or "entries_jsonl_dirty"
                        print(msg, file=sys.stderr)
                        print(
                            json.dumps(
                                {
                                    "schema_version": "memory_extract_v1",
                                    "ok": False,
                                    "error": "entries_jsonl_dirty",
                                    "message": msg,
                                    "written": [],
                                    "entries_appended": 0,
                                },
                                ensure_ascii=False,
                            ),
                        )
                        _maybe_metrics_cli(
                            module="memory",
                            event="memory.extract",
                            latency_ms=(time.perf_counter() - t_mx) * 1000.0,
                            tokens=0,
                            success=False,
                        )
                        return 2
                files = list_session_files(
                    cwd=str(root),
                    pattern=str(args.pattern),
                    limit=int(args.limit),
                )
                use_structured = bool(getattr(args, "extract_structured", False))
                settings_ex: Any = None
                if use_structured:
                    try:
                        settings_ex = Settings.from_env(config_path=None, workspace_hint=str(root))
                    except Exception:
                        settings_ex = None
                written: list[str] = []
                entries_appended = 0
                structured_results: list[dict[str, Any]] = []
                for p in files:
                    try:
                        sess = load_session(str(p))
                    except Exception:
                        continue
                    instincts = extract_basic_instincts_from_session(sess)
                    out = save_instincts(root, instincts)
                    if out:
                        written.append(str(out))
                    if use_structured:
                        sr = extract_memory_entries_structured(root, sess, settings=settings_ex)
                        entries_appended += int(sr.get("entries_written") or 0)
                        structured_results.append(sr)
                    elif extract_memory_entries_from_session(root, sess) is not None:
                        entries_appended += 1
                payload_ex: dict[str, Any] = {
                    "schema_version": "memory_extract_v1",
                    "written": written,
                    "entries_appended": entries_appended,
                }
                if use_structured:
                    payload_ex["structured"] = structured_results
                    payload_ex["structured_mode"] = True
                print(json.dumps(payload_ex, ensure_ascii=False))
                _maybe_metrics_cli(
                    module="memory",
                    event="memory.extract",
                    latency_ms=(time.perf_counter() - t_mx) * 1000.0,
                    tokens=int(entries_appended),
                    success=True,
                )
                return 0
            if args.memory_action == "list":
                t_ml = time.perf_counter()
                rows, vwarn = load_memory_entries_validated(root)
                for w in vwarn:
                    print(f"[memory] {w}", file=sys.stderr)
                rows = annotate_memory_states(
                    rows,
                    stale_after_days=int(getattr(args, "state_stale_after_days", 30)),
                    min_active_confidence=float(getattr(args, "state_min_active_confidence", 0.4)),
                )
                sort_key = str(getattr(args, "sort", "none") or "none")
                sort_memory_rows(rows, sort_key)
                rows = rows[: int(args.limit)]
                if args.json_output:
                    print(
                        json.dumps(
                            {
                                "schema_version": "memory_list_v1",
                                "limit": int(args.limit),
                                "sort": sort_key,
                                "entries": rows,
                            },
                            ensure_ascii=False,
                        ),
                    )
                else:
                    for row in rows:
                        tid = row.get("id", "")
                        cat = row.get("category", "")
                        snippet = str(row.get("text", ""))[:120].replace("\n", " ")
                        print(f"{tid}\t{cat}\t{snippet}")
                _maybe_metrics_cli(
                    module="memory",
                    event="memory.list",
                    latency_ms=(time.perf_counter() - t_ml) * 1000.0,
                    tokens=len(rows),
                    success=True,
                )
                return 0
            if args.memory_action == "validate-entries":
                t_mv = time.perf_counter()
                rep = build_memory_entries_jsonl_validate_report(root)
                ok_v = bool(rep.get("ok"))
                if bool(getattr(args, "json_output", False)):
                    print(json.dumps(rep, ensure_ascii=False))
                else:
                    print(
                        f"[memory validate-entries] file={rep.get('entries_file')} "
                        f"ok={ok_v} scanned={rep.get('lines_scanned')} valid={rep.get('valid_lines')}",
                    )
                    inv = rep.get("invalid_lines") or []
                    if isinstance(inv, list) and inv:
                        for row in inv[:20]:
                            if isinstance(row, dict):
                                print(f"  line {row.get('line')}: {row.get('errors')}", file=sys.stderr)
                        if len(inv) > 20:
                            print(f"  ... +{len(inv) - 20} more", file=sys.stderr)
                _maybe_metrics_cli(
                    module="memory",
                    event="memory.validate_entries",
                    latency_ms=(time.perf_counter() - t_mv) * 1000.0,
                    tokens=int(rep.get("lines_scanned") or 0),
                    success=ok_v,
                )
                return 0 if ok_v else 2
            if args.memory_action == "entries":
                if str(getattr(args, "memory_entries_action", "") or "").strip().lower() != "fix":
                    print("memory entries: 需要子命令 fix", file=sys.stderr)
                    return 2
                t_mfix = time.perf_counter()
                fx = fix_memory_entries_jsonl(
                    root,
                    dry_run=bool(getattr(args, "dry_run", False)),
                )
                if bool(getattr(args, "json_output", False)):
                    print(json.dumps(fx, ensure_ascii=False))
                else:
                    print(
                        f"[memory entries fix] {fx.get('message')} "
                        f"before={fx.get('lines_before')} after={fx.get('lines_after')} "
                        f"dropped={fx.get('dropped')} dry_run={fx.get('dry_run')}",
                    )
                _maybe_metrics_cli(
                    module="memory",
                    event="memory.entries_fix",
                    latency_ms=(time.perf_counter() - t_mfix) * 1000.0,
                    tokens=int(fx.get("dropped") or 0),
                    success=True,
                )
                return 0
            if args.memory_action == "instincts":
                t_mi = time.perf_counter()
                files = sorted(
                    mem_dir.glob("instincts-*.md"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                arr = [str(p) for p in files[: int(args.limit)]]
                if args.json_output:
                    print(
                        json.dumps(
                            {
                                "schema_version": "memory_instincts_list_v1",
                                "limit": int(args.limit),
                                "paths": arr,
                            },
                            ensure_ascii=False,
                        ),
                    )
                else:
                    for p in arr:
                        print(p)
                _maybe_metrics_cli(
                    module="memory",
                    event="memory.instincts",
                    latency_ms=(time.perf_counter() - t_mi) * 1000.0,
                    tokens=len(arr),
                    success=True,
                )
                return 0
            if args.memory_action == "search":
                sk = str(getattr(args, "sort", "") or "").strip() or None
                t_msr = time.perf_counter()
                hits = search_memory_entries(
                    root,
                    str(args.query),
                    limit=int(args.limit),
                    sort=sk,
                )
                if args.json_output:
                    print(
                        json.dumps(
                            {
                                "schema_version": "memory_search_v1",
                                "query": str(args.query),
                                "limit": int(args.limit),
                                "sort": sk,
                                "hits": hits,
                            },
                            ensure_ascii=False,
                        ),
                    )
                else:
                    for row in hits:
                        print(
                            f"{row.get('id')}\t{row.get('category')}\t{row.get('text', '')[:200]}",
                        )
                _maybe_metrics_cli(
                    module="memory",
                    event="memory.search",
                    latency_ms=(time.perf_counter() - t_msr) * 1000.0,
                    tokens=len(hits),
                    success=True,
                )
                return 0
            if args.memory_action == "prune":
                t_mp = time.perf_counter()
                n = prune_expired_memory_entries(
                    root,
                    min_confidence=float(getattr(args, "min_confidence", 0.0) or 0.0),
                    max_entries=int(getattr(args, "max_entries", 0) or 0),
                    drop_non_active=bool(getattr(args, "drop_non_active", False)),
                    stale_after_days=int(getattr(args, "state_stale_after_days", 30)),
                    min_active_confidence=float(getattr(args, "state_min_active_confidence", 0.4)),
                )
                if args.json_output:
                    print(json.dumps(n, ensure_ascii=False))
                else:
                    print(
                        f"removed_total={n.get('removed_total', 0)} "
                        f"expired={n.get('removed_expired', 0)} "
                        f"low_confidence={n.get('removed_low_confidence', 0)} "
                        f"over_limit={n.get('removed_over_limit', 0)} "
                        f"non_active={n.get('removed_non_active', 0)} "
                        f"invalid_json_lines={n.get('invalid_json_lines', 0)} "
                        f"kept_total={n.get('kept_total', 0)}",
                    )
                    br = n.get("removed_by_reason")
                    if isinstance(br, dict) and any(int(v or 0) > 0 for v in br.values()):
                        print(
                            "removed_by_reason="
                            + json.dumps(br, ensure_ascii=False, sort_keys=True),
                        )
                _maybe_metrics_cli(
                    module="memory",
                    event="memory.prune",
                    latency_ms=(time.perf_counter() - t_mp) * 1000.0,
                    tokens=int(n.get("removed_total") or 0),
                    success=True,
                )
                return 0
            if args.memory_action == "state":
                rows, vwarn = load_memory_entries_validated(root)
                for w in vwarn:
                    print(f"[memory] {w}", file=sys.stderr)
                t_ms = time.perf_counter()
                payload = evaluate_memory_entry_states(
                    root,
                    stale_after_days=int(getattr(args, "stale_days", 30)),
                    min_active_confidence=float(getattr(args, "stale_confidence", 0.4)),
                )
                _maybe_metrics_cli(
                    module="memory",
                    event="memory.state",
                    latency_ms=(time.perf_counter() - t_ms) * 1000.0,
                    tokens=int(payload.get("total_entries") or 0),
                    success=True,
                )
                if args.json_output:
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
                    print(
                        f"total={payload.get('total_entries', 0)} "
                        f"active={counts.get('active', 0)} "
                        f"stale={counts.get('stale', 0)} "
                        f"expired={counts.get('expired', 0)}",
                    )
                return 0
            if args.memory_action == "export":
                t_mex = time.perf_counter()
                target = Path(args.file).expanduser().resolve()
                files = sorted(
                    mem_dir.glob("instincts-*.md"),
                    key=lambda p: p.stat().st_mtime,
                )
                payload = [
                    {"path": str(p), "content": p.read_text(encoding="utf-8")}
                    for p in files
                ]
                target.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                if bool(getattr(args, "json_output", False)):
                    print(
                        json.dumps(
                            {
                                "schema_version": "memory_instincts_export_v1",
                                "output_file": str(target),
                                "snapshots_exported": len(files),
                            },
                            ensure_ascii=False,
                        ),
                    )
                else:
                    print(str(target))
                _maybe_metrics_cli(
                    module="memory",
                    event="memory.export",
                    latency_ms=(time.perf_counter() - t_mex) * 1000.0,
                    tokens=len(files),
                    success=True,
                )
                return 0
            if args.memory_action == "import":
                t_mim = time.perf_counter()
                src = Path(args.file).expanduser().resolve()
                arr = json.loads(src.read_text(encoding="utf-8"))
                if not isinstance(arr, list):
                    raise ValueError("memory import file must be array")
                count = 0
                for i, item in enumerate(arr, start=1):
                    if not isinstance(item, dict):
                        continue
                    content = item.get("content")
                    if not isinstance(content, str):
                        continue
                    p = mem_dir / f"instincts-import-{i:04d}.md"
                    p.write_text(content, encoding="utf-8")
                    count += 1
                print(
                    json.dumps(
                        {"schema_version": "memory_instincts_import_v1", "imported": count},
                        ensure_ascii=False,
                    ),
                )
                _maybe_metrics_cli(
                    module="memory",
                    event="memory.import",
                    latency_ms=(time.perf_counter() - t_mim) * 1000.0,
                    tokens=int(count),
                    success=True,
                )
                return 0
            if args.memory_action == "export-entries":
                t_mee = time.perf_counter()
                target = Path(args.file).expanduser().resolve()
                bundle = export_memory_entries_bundle(root)
                target.write_text(
                    json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                warns = bundle.get("export_warnings") or []
                for w in warns:
                    print(f"[memory] {w}", file=sys.stderr)
                if bool(getattr(args, "json_output", False)):
                    print(
                        json.dumps(
                            {
                                "schema_version": "memory_entries_export_result_v1",
                                "output_file": str(target),
                                "entries_count": len(bundle.get("entries") or []),
                                "export_warnings": list(warns) if isinstance(warns, list) else [],
                            },
                            ensure_ascii=False,
                        ),
                    )
                else:
                    print(str(target))
                ent_n = bundle.get("entries") if isinstance(bundle.get("entries"), list) else []
                _maybe_metrics_cli(
                    module="memory",
                    event="memory.export_entries",
                    latency_ms=(time.perf_counter() - t_mee) * 1000.0,
                    tokens=len(ent_n),
                    success=True,
                )
                return 0
            if args.memory_action == "import-entries":
                src = Path(args.file).expanduser().resolve()
                doc = json.loads(src.read_text(encoding="utf-8"))
                t_mie = time.perf_counter()
                dry_run = bool(getattr(args, "dry_run", False))
                valid_rows, errors = validate_memory_entries_bundle(doc)
                report_path_raw = getattr(args, "error_report", None)
                report_path: Path | None = None
                if errors and isinstance(report_path_raw, str) and report_path_raw.strip():
                    report_path = Path(report_path_raw).expanduser()
                    if not report_path.is_absolute():
                        report_path = (root / report_path).resolve()
                    report_payload = {
                        "schema_version": "memory_entries_import_errors_v1",
                        "source_file": str(src),
                        "errors_count": len(errors),
                        "errors": errors,
                    }
                    report_path.parent.mkdir(parents=True, exist_ok=True)
                    report_path.write_text(
                        json.dumps(report_payload, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                if dry_run:
                    payload: dict[str, Any] = {
                        "schema_version": "memory_entries_import_dry_run_v1",
                        "validated": len(valid_rows),
                        "dry_run": True,
                        "errors_count": len(errors),
                        "errors": errors,
                    }
                    if report_path is not None:
                        payload["error_report"] = str(report_path)
                    print(json.dumps(payload, ensure_ascii=False))
                if errors:
                    summary = (
                        f"[memory] 导入校验失败: total={len(valid_rows) + len(errors)} "
                        f"validated={len(valid_rows)} invalid={len(errors)}"
                    )
                    print(summary, file=sys.stderr)
                    first = errors[0] if isinstance(errors[0], dict) else {}
                    idx = first.get("entry_index")
                    path = first.get("path")
                    first_errs = first.get("errors") if isinstance(first.get("errors"), list) else []
                    if first_errs:
                        print(
                            f"[memory] 首个错误: entry_index={idx} path={path} reason={first_errs[0]}",
                            file=sys.stderr,
                        )
                    if report_path is not None:
                        print(f"[memory] 详细错误报告已写入: {report_path}", file=sys.stderr)
                    return 2
                if dry_run:
                    _maybe_metrics_cli(
                        module="memory",
                        event="memory.import_entries",
                        latency_ms=(time.perf_counter() - t_mie) * 1000.0,
                        tokens=len(valid_rows),
                        success=True,
                    )
                    return 0
                try:
                    n = import_memory_entries_bundle(root, doc)
                except ValueError as e:
                    print(str(e).strip() or "import rejected", file=sys.stderr)
                    _maybe_metrics_cli(
                        module="memory",
                        event="memory.import_entries",
                        latency_ms=(time.perf_counter() - t_mie) * 1000.0,
                        tokens=0,
                        success=False,
                    )
                    return 2
                print(
                    json.dumps(
                        {"schema_version": "memory_entries_import_result_v1", "imported": n},
                        ensure_ascii=False,
                    ),
                )
                _maybe_metrics_cli(
                    module="memory",
                    event="memory.import_entries",
                    latency_ms=(time.perf_counter() - t_mie) * 1000.0,
                    tokens=int(n),
                    success=True,
                )
                return 0
            if args.memory_action == "health":
                t_mh = time.perf_counter()
                payload = build_memory_health_payload(
                    root,
                    days=int(getattr(args, "days", 30)),
                    freshness_days=int(getattr(args, "freshness_days", 14)),
                    session_pattern=str(getattr(args, "session_pattern", ".cai-session*.json")),
                    session_limit=int(getattr(args, "session_limit", 200)),
                    conflict_threshold=float(getattr(args, "conflict_threshold", 0.85)),
                    max_conflict_compare_entries=int(
                        getattr(args, "max_conflict_compare_entries", 400) or 400,
                    ),
                )
                mh_ms = (time.perf_counter() - t_mh) * 1000.0
                counts_mh = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
                _maybe_metrics_cli(
                    module="memory",
                    event="memory.health",
                    latency_ms=mh_ms,
                    tokens=int(counts_mh.get("memory_entries") or 0),
                    success=True,
                )
                for w in payload.get("memory_warnings") or []:
                    if isinstance(w, str) and w.strip():
                        print(f"[memory] {w}", file=sys.stderr)
                out_text = json.dumps(payload, ensure_ascii=False)
                if bool(getattr(args, "json_output", False)):
                    print(out_text)
                else:
                    print(
                        f"[memory health] grade={payload.get('grade')} "
                        f"score={payload.get('health_score')} "
                        f"freshness={payload.get('freshness')} "
                        f"coverage={payload.get('coverage')} "
                        f"conflict_rate={payload.get('conflict_rate')}",
                    )
                    for i, action in enumerate(payload.get("actions") or [], start=1):
                        print(f"{i}. {action}")
                grade_rank = {"A": 4, "B": 3, "C": 2, "D": 1}
                fail_g = str(getattr(args, "fail_on_grade", "") or "").strip().upper()
                if fail_g in grade_rank:
                    got = str(payload.get("grade") or "D").strip().upper()
                    if grade_rank.get(got, 0) <= grade_rank.get(fail_g, 0):
                        return 2
                return 0
            if args.memory_action == "nudge":
                t_mn = time.perf_counter()
                payload = _build_memory_nudge_payload(
                    cwd=str(root),
                    days=int(getattr(args, "days", 7)),
                    session_pattern=str(getattr(args, "session_pattern", ".cai-session*.json")),
                    session_limit=int(getattr(args, "session_limit", 50)),
                )
                _maybe_metrics_cli(
                    module="memory",
                    event="memory.nudge",
                    latency_ms=(time.perf_counter() - t_mn) * 1000.0,
                    tokens=int(payload.get("memory_entries") or 0),
                    success=True,
                )
                out_text = json.dumps(payload, ensure_ascii=False)
                raw_write = getattr(args, "write_file", None)
                if isinstance(raw_write, str) and raw_write.strip():
                    out_path = Path(raw_write).expanduser()
                    if not out_path.is_absolute():
                        out_path = (root / out_path).resolve()
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_path.write_text(out_text + "\n", encoding="utf-8")
                    hist_raw = getattr(args, "history_file", None)
                    hist_path = (
                        Path(hist_raw).expanduser()
                        if isinstance(hist_raw, str) and hist_raw.strip()
                        else (root / "memory" / "nudge-history.jsonl")
                    )
                    if not hist_path.is_absolute():
                        hist_path = (root / hist_path).resolve()
                    if hist_path.resolve() != out_path.resolve():
                        hist_path.parent.mkdir(parents=True, exist_ok=True)
                        with hist_path.open("a", encoding="utf-8") as f:
                            f.write(out_text + "\n")
                if bool(getattr(args, "json_output", False)):
                    print(out_text)
                    if isinstance(raw_write, str) and raw_write.strip():
                        print(str(out_path))
                else:
                    print(
                        f"[memory nudge] severity={payload.get('severity')} "
                        f"recent_sessions={payload.get('recent_sessions')} "
                        f"memory_entries={payload.get('memory_entries')}",
                    )
                    for i, action in enumerate(payload.get("actions") or [], start=1):
                        print(f"{i}. {action}")
                    if isinstance(raw_write, str) and raw_write.strip():
                        print(f"written={out_path}")
                sev_map = {"low": 0, "medium": 1, "high": 2}
                fail_th = str(getattr(args, "fail_on_severity", "off") or "off").strip().lower()
                if fail_th in ("medium", "high"):
                    got = str(payload.get("severity") or "low").strip().lower()
                    if sev_map.get(got, 0) >= sev_map.get(fail_th, 99):
                        return 2
                return 0
            if args.memory_action == "nudge-report":
                t_mnr = time.perf_counter()
                payload = _build_memory_nudge_report_payload(
                    cwd=str(root),
                    history_file=getattr(args, "history_file", None),
                    limit=int(getattr(args, "limit", 200)),
                    days=int(getattr(args, "days", 30)),
                    freshness_days=int(getattr(args, "freshness_days", 14)),
                )
                _maybe_metrics_cli(
                    module="memory",
                    event="memory.nudge_report",
                    latency_ms=(time.perf_counter() - t_mnr) * 1000.0,
                    tokens=int(payload.get("entries_considered") or 0),
                    success=True,
                )
                if bool(getattr(args, "json_output", False)):
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(
                        f"[memory nudge report] entries={payload.get('entries_considered')} "
                        f"latest={payload.get('latest_severity')} "
                        f"high={payload.get('severity_counts', {}).get('high', 0)}",
                    )
                    print(f"history_file={payload.get('history_file')}")
                return 0
            if args.memory_action == "provider":
                t_mpv = time.perf_counter()
                from cai_agent.memory import build_memory_provider_contract_payload

                payload = build_memory_provider_contract_payload(root)
                _maybe_metrics_cli(
                    module="memory",
                    event="memory.provider",
                    latency_ms=(time.perf_counter() - t_mpv) * 1000.0,
                    tokens=len(payload.get("providers") or []),
                    success=bool(payload.get("ok")),
                )
                if bool(getattr(args, "json_output", False)):
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    providers = payload.get("providers") if isinstance(payload.get("providers"), list) else []
                    print(
                        f"[memory provider] providers={len(providers)} "
                        f"default={payload.get('default_provider')} ok={payload.get('ok')}",
                    )
                return 0
            if args.memory_action == "user-model":
                t_mum = time.perf_counter()
                from cai_agent.user_model import (
                    build_memory_user_model_overview,
                    build_memory_user_model_overview_v2,
                    build_memory_user_model_overview_v3,
                    build_user_model_bundle_v1,
                )
                from cai_agent.user_model_store import (
                    append_event,
                    init_user_model_store,
                    list_recent_beliefs,
                    query_beliefs_by_text,
                    upsert_belief,
                    user_model_store_path,
                )

                uact = str(getattr(args, "user_model_action", "") or "").strip().lower()
                days_um = int(getattr(args, "user_model_days", 14) or 14)
                sp_store = str(user_model_store_path(root))
                if uact == "store":
                    sact = str(getattr(args, "user_model_store_action", "") or "").strip().lower()
                    if sact == "init":
                        ppath = init_user_model_store(root)
                        out_s: dict[str, Any] = {
                            "schema_version": "memory_user_model_store_init_v1",
                            "ok": True,
                            "store_path": str(ppath),
                        }
                    elif sact == "list":
                        lim_sl = int(getattr(args, "user_store_list_limit", 50) or 50)
                        beliefs_sl = list_recent_beliefs(root, limit=lim_sl)
                        out_s = {
                            "schema_version": "memory_user_model_store_list_v1",
                            "store_path": sp_store,
                            "beliefs": beliefs_sl,
                        }
                    else:
                        print(f"unknown user-model store action: {sact}", file=sys.stderr)
                        return 2
                    if bool(getattr(args, "json_output", False)):
                        print(json.dumps(out_s, ensure_ascii=False))
                    elif sact == "init":
                        print(f"[memory user-model store init] store_path={out_s.get('store_path')}")
                    else:
                        bl = out_s.get("beliefs") or []
                        print(f"[memory user-model store list] n={len(bl)} store_path={out_s.get('store_path')}")
                        for b in bl[:40]:
                            if isinstance(b, dict):
                                print(f"  {b.get('confidence')}\t{(b.get('text') or '')[:120]}")
                    _maybe_metrics_cli(
                        module="memory",
                        event="memory.user_model.store",
                        latency_ms=(time.perf_counter() - t_mum) * 1000.0,
                        tokens=len(out_s.get("beliefs") or []) if sact == "list" else 1,
                        success=True,
                    )
                    return 0
                if uact == "query":
                    needle_q = str(getattr(args, "user_model_query_text", "") or "")
                    hits = query_beliefs_by_text(
                        root,
                        needle=needle_q,
                        limit=int(getattr(args, "limit", 20) or 20),
                    )
                    out_q: dict[str, Any] = {
                        "schema_version": "memory_user_model_query_v1",
                        "store_path": sp_store,
                        "needle": needle_q,
                        "hits": hits,
                    }
                    if bool(getattr(args, "json_output", False)):
                        print(json.dumps(out_q, ensure_ascii=False))
                    else:
                        print(f"[memory user-model query] hits={len(hits)} store_path={sp_store}")
                        for h in hits[:20]:
                            print(f"  {h.get('confidence')}\t{h.get('text', '')[:120]}")
                    _maybe_metrics_cli(
                        module="memory",
                        event="memory.user_model.query",
                        latency_ms=(time.perf_counter() - t_mum) * 1000.0,
                        tokens=len(hits),
                        success=True,
                    )
                    return 0
                if uact == "learn":
                    belief = str(getattr(args, "belief", "") or "").strip()
                    conf = float(getattr(args, "confidence", 0.5) or 0.5)
                    tags = [str(x) for x in (getattr(args, "tag", None) or []) if str(x).strip()]
                    try:
                        row = upsert_belief(root, text=belief, confidence=conf, tags=tags or None)
                    except ValueError as e:
                        out_bad: dict[str, Any] = {
                            "schema_version": "memory_user_model_learn_v1",
                            "ok": False,
                            "store_path": sp_store,
                            "error": "belief_invalid",
                            "message": str(e).strip() or "belief_invalid",
                        }
                        if bool(getattr(args, "json_output", False)):
                            print(json.dumps(out_bad, ensure_ascii=False))
                        else:
                            print(f"[memory user-model learn] error: {out_bad.get('message')}", file=sys.stderr)
                        _maybe_metrics_cli(
                            module="memory",
                            event="memory.user_model.learn",
                            latency_ms=(time.perf_counter() - t_mum) * 1000.0,
                            tokens=0,
                            success=False,
                        )
                        return 2
                    append_event(root, kind="learn", payload={"belief_id": row.get("id"), "text": belief[:200]})
                    out_l: dict[str, Any] = {
                        "schema_version": "memory_user_model_learn_v1",
                        "ok": True,
                        "store_path": sp_store,
                        "belief": row,
                    }
                    if bool(getattr(args, "json_output", False)):
                        print(json.dumps(out_l, ensure_ascii=False))
                    else:
                        print(f"[memory user-model learn] id={row.get('id')} confidence={row.get('confidence')}")
                    _maybe_metrics_cli(
                        module="memory",
                        event="memory.user_model.learn",
                        latency_ms=(time.perf_counter() - t_mum) * 1000.0,
                        tokens=1,
                        success=True,
                    )
                    return 0
                if uact == "export":
                    bundle = build_user_model_bundle_v1(
                        settings_mem,
                        days=days_um,
                        with_store=bool(getattr(args, "user_model_export_with_store", False)),
                    )
                    ov = bundle.get("overview") if isinstance(bundle.get("overview"), dict) else {}
                    tok_um = int(ov.get("sessions_recent_in_window") or 0)
                    _maybe_metrics_cli(
                        module="memory",
                        event="memory.user_model.export",
                        latency_ms=(time.perf_counter() - t_mum) * 1000.0,
                        tokens=tok_um,
                        success=True,
                    )
                    print(json.dumps(bundle, ensure_ascii=False))
                    return 0

                if bool(getattr(args, "with_store_v3", False)):
                    payload_um = build_memory_user_model_overview_v3(
                        settings_mem,
                        days=days_um,
                        with_dialectic=bool(getattr(args, "with_dialectic", False)),
                    )
                elif bool(getattr(args, "with_dialectic", False)):
                    payload_um = build_memory_user_model_overview_v2(
                        settings_mem,
                        days=days_um,
                        with_dialectic=True,
                    )
                else:
                    payload_um = build_memory_user_model_overview(settings_mem, days=days_um)
                tok_um = int(payload_um.get("sessions_recent_in_window") or 0)
                _maybe_metrics_cli(
                    module="memory",
                    event="memory.user_model",
                    latency_ms=(time.perf_counter() - t_mum) * 1000.0,
                    tokens=tok_um,
                    success=True,
                )
                if bool(getattr(args, "json_output", False)):
                    print(json.dumps(payload_um, ensure_ascii=False))
                else:
                    print(
                        f"[memory user-model] sessions_total={payload_um.get('sessions_total')} "
                        f"recent={payload_um.get('sessions_recent_in_window')} "
                        f"overlay={payload_um.get('overlay_present')}",
                    )
                return 0
        finally:
            _print_hook_status(
                settings_mem,
                event="memory_end",
                json_output=mem_json,
            )

    if args.command == "schedule":
        root = Path.cwd().resolve()
        if args.schedule_action == "add":
            t_sadd = time.perf_counter()
            try:
                job = add_schedule_task(
                    goal=str(args.goal),
                    every_minutes=int(args.every_minutes),
                    workspace=str(args.workspace) if getattr(args, "workspace", None) else None,
                    model=str(args.model) if getattr(args, "model", None) else None,
                    depends_on=[str(x) for x in list(getattr(args, "depends_on", []) or [])],
                    retry_max_attempts=int(getattr(args, "retry_max_attempts", 1)),
                    retry_backoff_sec=float(getattr(args, "retry_backoff_sec", 0.0)),
                    max_retries=int(getattr(args, "max_retries", 3)),
                    cwd=str(root),
                )
            except ValueError as e:
                msg = str(e).strip() or "schedule add rejected"
                if bool(args.json_output):
                    print(
                        json.dumps(
                            {
                                "schema_version": "schedule_add_invalid_v1",
                                "ok": False,
                                "error": "schedule_add_invalid",
                                "message": msg,
                            },
                            ensure_ascii=False,
                        ),
                    )
                else:
                    print(msg, file=sys.stderr)
                return 2
            sadd_ms = (time.perf_counter() - t_sadd) * 1000.0
            dep_n = job.get("depends_on") if isinstance(job.get("depends_on"), list) else []
            append_schedule_audit_event(
                task_id=str(job.get("id") or ""),
                status="created",
                action="schedule.add",
                cwd=str(root),
                event="task.completed",
                goal_preview=str(job.get("goal") or "")[:120],
                elapsed_ms=0,
                details={
                    "every_minutes": job.get("every_minutes"),
                    "depends_on": job.get("depends_on"),
                    "retry_max_attempts": job.get("retry_max_attempts"),
                    "retry_backoff_sec": job.get("retry_backoff_sec"),
                    "max_retries": job.get("max_retries"),
                },
            )
            if bool(args.disabled):
                doc = load_schedule_doc(str(root))
                tasks = doc.get("tasks")
                if isinstance(tasks, list):
                    for row in tasks:
                        if isinstance(row, dict) and str(row.get("id")) == str(job.get("id")):
                            row["enabled"] = False
                            break
                    save_schedule_doc(doc, str(root))
                    job["enabled"] = False
            if bool(args.json_output):
                print(
                    json.dumps(
                        {**job, "schema_version": "schedule_add_v1"},
                        ensure_ascii=False,
                    ),
                )
            else:
                print(
                    f"added id={job.get('id')} every_minutes={job.get('every_minutes')} "
                    f"enabled={job.get('enabled')}",
                )
            _maybe_metrics_cli(
                module="schedule",
                event="schedule.add",
                latency_ms=sadd_ms,
                tokens=len(dep_n),
                success=True,
            )
            return 0
        if args.schedule_action == "add-memory-nudge":
            t_amn = time.perf_counter()
            out_path = str(getattr(args, "output_file", ".cai/memory-nudge-latest.json"))
            fail_th = str(getattr(args, "fail_on_severity", "high") or "high").strip().lower()
            goal = (
                "Run: cai-agent memory nudge --json "
                f"--days {int(getattr(args, 'days', 7))} "
                f"--session-limit {int(getattr(args, 'session_limit', 50))} "
                f"--write-file {out_path} "
                f"--fail-on-severity {fail_th}"
            )
            job = add_schedule_task(
                goal=goal,
                every_minutes=int(getattr(args, "every_minutes", 1440)),
                workspace=str(args.workspace) if getattr(args, "workspace", None) else ".",
                model=str(args.model) if getattr(args, "model", None) else None,
                cwd=str(root),
            )
            if bool(args.disabled):
                doc = load_schedule_doc(str(root))
                tasks = doc.get("tasks")
                if isinstance(tasks, list):
                    for row in tasks:
                        if isinstance(row, dict) and str(row.get("id")) == str(job.get("id")):
                            row["enabled"] = False
                            break
                    save_schedule_doc(doc, str(root))
                    job["enabled"] = False
            payload = {
                "schema_version": "schedule_add_memory_nudge_v1",
                "template": "memory-nudge",
                "goal": goal,
                "job": job,
            }
            if bool(args.json_output):
                print(json.dumps(payload, ensure_ascii=False))
            else:
                print(
                    f"added memory-nudge template id={job.get('id')} every={job.get('every_minutes')}m "
                    f"enabled={job.get('enabled')}",
                )
                print(f"goal={goal}")
            _maybe_metrics_cli(
                module="schedule",
                event="schedule.add_memory_nudge",
                latency_ms=(time.perf_counter() - t_amn) * 1000.0,
                tokens=1,
                success=True,
            )
            return 0
        if args.schedule_action == "list":
            t_sl = time.perf_counter()
            raw_jobs = list_schedule_tasks(str(root))
            jobs = enrich_schedule_tasks_for_display(raw_jobs)
            _maybe_metrics_cli(
                module="schedule",
                event="schedule.list",
                latency_ms=(time.perf_counter() - t_sl) * 1000.0,
                tokens=len(jobs),
                success=True,
            )
            if bool(args.json_output):
                print(
                    json.dumps(
                        {"schema_version": "schedule_list_v1", "jobs": jobs},
                        ensure_ascii=False,
                    ),
                )
            else:
                if not jobs:
                    print("(无定时任务)")
                for j in jobs:
                    dep_ids: list[str] = []
                    for x in (j.get("depends_on") or []):
                        d = str(x or "").strip()
                        if d and d not in dep_ids:
                            dep_ids.append(d)
                    deps_s = ",".join(dep_ids) if dep_ids else "-"
                    chain_s = str(j.get("depends_on_chain") or "-")[:100]
                    dep_blk = "Y" if j.get("dependency_blocked") else "N"
                    dep_n = ",".join(str(x) for x in (j.get("dependents") or [])[:5]) or "-"
                    if len(j.get("dependents") or []) > 5:
                        dep_n = dep_n + ",…"
                    print(
                        f"{j.get('id')}\tevery={j.get('every_minutes')}m\tenabled={j.get('enabled')}\t"
                        f"run_count={j.get('run_count', 0)} last_status={j.get('last_status')}\t"
                        f"deps={deps_s}\tdep_blocked={dep_blk}\tdependents={dep_n}\tdep_chain={chain_s}\t"
                        f"goal={(str(j.get('goal') or '')[:60])}",
                    )
            return 0
        if args.schedule_action == "rm":
            t_srm = time.perf_counter()
            ok = remove_schedule_task(str(args.id), str(root))
            _maybe_metrics_cli(
                module="schedule",
                event="schedule.rm",
                latency_ms=(time.perf_counter() - t_srm) * 1000.0,
                tokens=1 if ok else 0,
                success=bool(ok),
            )
            if bool(args.json_output):
                print(
                    json.dumps(
                        {"schema_version": "schedule_rm_v1", "removed": ok},
                        ensure_ascii=False,
                    ),
                )
            else:
                print("removed=1" if ok else "removed=0")
            return 0 if ok else 2
        if args.schedule_action == "run-due":
            t_srd = time.perf_counter()
            due = compute_due_tasks(cwd=str(root))
            if not bool(args.execute):
                payload = {
                    "schema_version": "schedule_run_due_v1",
                    "mode": "dry-run",
                    "due_jobs": due,
                    "executed": [],
                }
                _maybe_metrics_cli(
                    module="schedule",
                    event="schedule.run_due",
                    latency_ms=(time.perf_counter() - t_srd) * 1000.0,
                    tokens=len(due),
                    success=True,
                )
                if bool(args.json_output):
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"due_jobs={len(due)}")
                    for j in due:
                        print(
                            f"- {j.get('id')} every={j.get('every_minutes')}m "
                            f"goal={str(j.get('goal') or '')[:80]}"
                        )
                return 0
            executed: list[dict[str, Any]] = []
            for j in due:
                tid = str(j.get("id") or "").strip()
                if not tid:
                    continue
                goal = str(j.get("goal") or "").strip()
                ws = j.get("workspace")
                workspace_override = str(ws).strip() if isinstance(ws, str) and str(ws).strip() else None
                mo = j.get("model")
                model_override = str(mo).strip() if isinstance(mo, str) and str(mo).strip() else None
                if not goal:
                    mark_schedule_task_run(
                        task_id=tid,
                        status="failed",
                        error="empty_goal",
                        cwd=str(root),
                    )
                    snap_eg = _schedule_task_row_snapshot(str(root), tid)
                    st_eg = str(snap_eg.get("last_status") or "failed")
                    executed.append(
                        {
                            "id": tid,
                            "ok": False,
                            "status": st_eg,
                            "error": "empty_goal",
                            "retry_count": snap_eg.get("retry_count"),
                            "next_retry_at": snap_eg.get("next_retry_at"),
                        },
                    )
                    append_schedule_audit_event(
                        task_id=tid,
                        status=st_eg,
                        action="schedule.run_due",
                        cwd=str(root),
                        event="task.failed",
                        goal_preview="",
                        elapsed_ms=0,
                        error="empty_goal",
                        details={"reason": "empty_goal", "retry_count": snap_eg.get("retry_count")},
                    )
                    continue
                max_attempts = int(j.get("retry_max_attempts") or 1)
                if max_attempts < 1:
                    max_attempts = 1
                backoff_sec = float(j.get("retry_backoff_sec") or 0.0)
                if backoff_sec < 0:
                    backoff_sec = 0.0
                gp120 = str(goal)[:120] + ("…" if len(str(goal)) > 120 else "")
                append_schedule_audit_event(
                    task_id=tid,
                    status="running",
                    action="schedule.run_due",
                    cwd=str(root),
                    event="task.started",
                    goal_preview=gp120,
                    elapsed_ms=0,
                    details={"mode": "run-due"},
                )
                attempts = 0
                ok = False
                out = ""
                t_run0 = time.perf_counter()
                while attempts < max_attempts:
                    attempts += 1
                    ok, out = _execute_scheduled_goal(
                        config_path=None,
                        workspace_hint=workspace_override,
                        workspace_override=workspace_override,
                        model_override=model_override,
                        goal=goal,
                    )
                    if ok:
                        break
                    if attempts < max_attempts and backoff_sec > 0:
                        time.sleep(backoff_sec)
                elapsed_ms_run = int(max(0.0, (time.perf_counter() - t_run0) * 1000.0))
                if ok:
                    mark_schedule_task_run(task_id=tid, status="completed", cwd=str(root))
                    preview = out[:160] + ("…" if len(out) > 160 else "")
                    executed.append(
                        {
                            "id": tid,
                            "ok": True,
                            "status": "completed",
                            "answer_preview": preview,
                            "workspace": workspace_override,
                            "model": model_override,
                            "attempts": attempts,
                        },
                    )
                    append_schedule_audit_event(
                        task_id=tid,
                        status="completed",
                        action="schedule.run_due",
                        cwd=str(root),
                        event="task.completed",
                        goal_preview=gp120,
                        elapsed_ms=elapsed_ms_run,
                        details={"attempts": attempts},
                    )
                else:
                    mark_schedule_task_run(
                        task_id=tid,
                        status="failed",
                        error=out,
                        cwd=str(root),
                    )
                    snap = _schedule_task_row_snapshot(str(root), tid)
                    persisted = str(snap.get("last_status") or "failed")
                    ev_fail = "task.retrying" if persisted == "retrying" else "task.failed"
                    executed.append(
                        {
                            "id": tid,
                            "ok": False,
                            "status": persisted,
                            "error": out,
                            "workspace": workspace_override,
                            "model": model_override,
                            "attempts": attempts,
                            "retry_count": snap.get("retry_count"),
                            "next_retry_at": snap.get("next_retry_at"),
                            "max_retries": snap.get("max_retries"),
                        },
                    )
                    append_schedule_audit_event(
                        task_id=tid,
                        status=persisted,
                        action="schedule.run_due",
                        cwd=str(root),
                        event=ev_fail,
                        goal_preview=gp120,
                        elapsed_ms=elapsed_ms_run,
                        error=str(out)[:500] if out else None,
                        details={
                            "attempts": attempts,
                            "error": str(out)[:500],
                            "retry_count": snap.get("retry_count"),
                            "next_retry_at": snap.get("next_retry_at"),
                        },
                    )
            payload = {
                "schema_version": "schedule_run_due_v1",
                "mode": "execute",
                "due_jobs": due,
                "executed": executed,
            }
            _maybe_metrics_cli(
                module="schedule",
                event="schedule.run_due",
                latency_ms=(time.perf_counter() - t_srd) * 1000.0,
                tokens=len(executed),
                success=True,
            )
            if bool(args.json_output):
                print(json.dumps(payload, ensure_ascii=False))
            else:
                print(f"executed={len(executed)} due_jobs={len(due)}")
            return 0
        if args.schedule_action == "daemon":
            interval_sec = max(0.2, float(args.interval_sec))
            max_cycles = int(args.max_cycles)
            execute = bool(args.execute)
            max_concurrent_raw = int(getattr(args, "max_concurrent", 1) or 1)
            max_concurrent = max(1, max_concurrent_raw)
            lock_path = _resolve_schedule_path(root, getattr(args, "lock_file", None), ".cai-schedule-daemon.lock")
            stale_lock_sec = max(0.0, float(getattr(args, "stale_lock_sec", 0.0) or 0.0))
            ok_lock, lock_msg = _acquire_schedule_daemon_lock(lock_path=lock_path, stale_lock_sec=stale_lock_sec)
            if not ok_lock:
                payload = {
                    "schema_version": "schedule_daemon_summary_v1",
                    "mode": "daemon",
                    "ok": False,
                    "error": "lock_conflict",
                    "message": lock_msg,
                }
                if bool(args.json_output):
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"[schedule-daemon] lock conflict: {lock_msg}", file=sys.stderr)
                return 2

            log_path_raw = getattr(args, "jsonl_log", None)
            log_path = _resolve_schedule_path(root, log_path_raw, ".cai-schedule-daemon.jsonl") if log_path_raw else None
            append_schedule_audit_event(
                task_id="",
                status="running",
                action="schedule.daemon",
                cwd=str(root),
                event="daemon.started",
                goal_preview="",
                elapsed_ms=0,
                details={
                    "execute": execute,
                    "interval_sec": interval_sec,
                    "max_cycles": max_cycles,
                    "max_concurrent": max_concurrent,
                    "lock_file": str(lock_path),
                },
                mirror_jsonl_path=log_path,
            )

            cycles = 0
            total_due = 0
            total_executed = 0
            total_skipped_concurrency = 0
            results: list[dict[str, Any]] = []
            interrupted = False
            t_daemon_total = time.perf_counter()
            try:
                while True:
                    cycles += 1
                    due = compute_due_tasks(cwd=str(root))
                    total_due += len(due)
                    cycle_exec: list[dict[str, Any]] = []
                    skipped_conc: list[dict[str, Any]] = []
                    ran_this_cycle = 0
                    if execute:
                        for j in due:
                            tid = str(j.get("id") or "").strip()
                            if not tid:
                                continue
                            if ran_this_cycle >= max_concurrent:
                                gp = str(j.get("goal") or "").strip()
                                skip_row = {
                                    "id": tid,
                                    "status": "skipped",
                                    "skip_reason": "skipped_due_to_concurrency",
                                    "max_concurrent": max_concurrent,
                                    "goal_preview": (gp[:120] + ("…" if len(gp) > 120 else "")) if gp else "",
                                }
                                skipped_conc.append(skip_row)
                                total_skipped_concurrency += 1
                                append_schedule_audit_event(
                                    task_id=tid,
                                    status="skipped",
                                    action="schedule.daemon",
                                    cwd=str(root),
                                    event="task.skipped",
                                    goal_preview=str(skip_row.get("goal_preview") or ""),
                                    elapsed_ms=0,
                                    error="skipped_due_to_concurrency",
                                    details={
                                        "reason": "skipped_due_to_concurrency",
                                        "max_concurrent": max_concurrent,
                                        "cycle": cycles,
                                    },
                                    mirror_jsonl_path=log_path,
                                )
                                continue
                            ran_this_cycle += 1
                            goal = str(j.get("goal") or "").strip()
                            ws = j.get("workspace")
                            workspace_override = (
                                str(ws).strip() if isinstance(ws, str) and str(ws).strip() else None
                            )
                            mo = j.get("model")
                            model_override = (
                                str(mo).strip() if isinstance(mo, str) and str(mo).strip() else None
                            )
                            if not goal:
                                mark_schedule_task_run(
                                    task_id=tid,
                                    status="failed",
                                    error="empty_goal",
                                    cwd=str(root),
                                )
                                snap_eg = _schedule_task_row_snapshot(str(root), tid)
                                st_eg = str(snap_eg.get("last_status") or "failed")
                                cycle_exec.append(
                                    {
                                        "id": tid,
                                        "ok": False,
                                        "status": st_eg,
                                        "error": "empty_goal",
                                        "retry_count": snap_eg.get("retry_count"),
                                        "next_retry_at": snap_eg.get("next_retry_at"),
                                    },
                                )
                                append_schedule_audit_event(
                                    task_id=tid,
                                    status=st_eg,
                                    action="schedule.daemon",
                                    cwd=str(root),
                                    event="task.failed",
                                    goal_preview="",
                                    elapsed_ms=0,
                                    error="empty_goal",
                                    details={
                                        "reason": "empty_goal",
                                        "cycle": cycles,
                                        "retry_count": snap_eg.get("retry_count"),
                                    },
                                    mirror_jsonl_path=log_path,
                                )
                                continue
                            max_attempts = int(j.get("retry_max_attempts") or 1)
                            if max_attempts < 1:
                                max_attempts = 1
                            backoff_sec = float(j.get("retry_backoff_sec") or 0.0)
                            if backoff_sec < 0:
                                backoff_sec = 0.0
                            gp120d = str(goal)[:120] + ("…" if len(str(goal)) > 120 else "")
                            append_schedule_audit_event(
                                task_id=tid,
                                status="running",
                                action="schedule.daemon",
                                cwd=str(root),
                                event="task.started",
                                goal_preview=gp120d,
                                elapsed_ms=0,
                                details={"mode": "daemon", "cycle": cycles},
                                mirror_jsonl_path=log_path,
                            )
                            attempts = 0
                            ok = False
                            out = ""
                            t_dm0 = time.perf_counter()
                            while attempts < max_attempts:
                                attempts += 1
                                ok, out = _execute_scheduled_goal(
                                    config_path=None,
                                    workspace_hint=workspace_override,
                                    workspace_override=workspace_override,
                                    model_override=model_override,
                                    goal=goal,
                                )
                                if ok:
                                    break
                                if attempts < max_attempts and backoff_sec > 0:
                                    time.sleep(backoff_sec)
                            elapsed_ms_dm = int(max(0.0, (time.perf_counter() - t_dm0) * 1000.0))
                            if ok:
                                mark_schedule_task_run(task_id=tid, status="completed", cwd=str(root))
                                preview = out[:160] + ("…" if len(out) > 160 else "")
                                cycle_exec.append(
                                    {
                                        "id": tid,
                                        "ok": True,
                                        "status": "completed",
                                        "answer_preview": preview,
                                        "attempts": attempts,
                                    },
                                )
                                append_schedule_audit_event(
                                    task_id=tid,
                                    status="completed",
                                    action="schedule.daemon",
                                    cwd=str(root),
                                    event="task.completed",
                                    goal_preview=gp120d,
                                    elapsed_ms=elapsed_ms_dm,
                                    details={"attempts": attempts, "cycle": cycles},
                                    mirror_jsonl_path=log_path,
                                )
                            else:
                                mark_schedule_task_run(
                                    task_id=tid,
                                    status="failed",
                                    error=out,
                                    cwd=str(root),
                                )
                                snap = _schedule_task_row_snapshot(str(root), tid)
                                persisted = str(snap.get("last_status") or "failed")
                                ev_dm = "task.retrying" if persisted == "retrying" else "task.failed"
                                cycle_exec.append(
                                    {
                                        "id": tid,
                                        "ok": False,
                                        "status": persisted,
                                        "error": out,
                                        "attempts": attempts,
                                        "retry_count": snap.get("retry_count"),
                                        "next_retry_at": snap.get("next_retry_at"),
                                        "max_retries": snap.get("max_retries"),
                                    },
                                )
                                append_schedule_audit_event(
                                    task_id=tid,
                                    status=persisted,
                                    action="schedule.daemon",
                                    cwd=str(root),
                                    event=ev_dm,
                                    goal_preview=gp120d,
                                    elapsed_ms=elapsed_ms_dm,
                                    error=str(out)[:500] if out else None,
                                    details={
                                        "attempts": attempts,
                                        "error": str(out)[:500],
                                        "cycle": cycles,
                                        "retry_count": snap.get("retry_count"),
                                        "next_retry_at": snap.get("next_retry_at"),
                                    },
                                    mirror_jsonl_path=log_path,
                                )
                    total_executed += len(cycle_exec)
                    cycle_row = {
                        "cycle": cycles,
                        "due_count": len(due),
                        "executed_count": len(cycle_exec),
                        "skipped_due_to_concurrency_count": len(skipped_conc),
                        "execute": execute,
                        "executed": cycle_exec,
                        "skipped_due_to_concurrency": skipped_conc,
                    }
                    results.append(cycle_row)
                    if log_path is not None:
                        append_schedule_audit_event(
                            task_id="",
                            status="ok",
                            action="schedule.daemon",
                            cwd=str(root),
                            event="daemon.cycle",
                            goal_preview="",
                            elapsed_ms=0,
                            details=cycle_row,
                            mirror_jsonl_path=log_path,
                        )
                    if max_cycles > 0 and cycles >= max_cycles:
                        break
                    time.sleep(interval_sec)
            except KeyboardInterrupt:
                interrupted = True
            finally:
                try:
                    lock_path.unlink(missing_ok=True)
                except Exception:
                    pass

            payload = {
                "schema_version": "schedule_daemon_summary_v1",
                "mode": "daemon",
                "execute": execute,
                "interval_sec": interval_sec,
                "max_cycles": max_cycles,
                "max_concurrent": max_concurrent,
                "cycles": cycles,
                "total_due": total_due,
                "total_executed": total_executed,
                "total_skipped_due_to_concurrency": total_skipped_concurrency,
                "interrupted": interrupted,
                "results": results,
                "lock_file": str(lock_path),
                "jsonl_log": str(log_path) if log_path is not None else None,
            }
            if bool(args.json_output):
                print(json.dumps(payload, ensure_ascii=False))
            else:
                print(
                    f"daemon cycles={cycles} total_due={total_due} total_executed={total_executed} "
                    f"skipped_concurrency={total_skipped_concurrency} max_concurrent={max_concurrent} "
                    f"execute={execute} interrupted={interrupted}",
                )
            _maybe_metrics_cli(
                module="schedule",
                event="schedule.daemon",
                latency_ms=(time.perf_counter() - t_daemon_total) * 1000.0,
                tokens=int(total_executed),
                success=not interrupted,
            )
            return 0
        if args.schedule_action == "stats":
            audit_raw = getattr(args, "audit_file", None)
            audit_arg = str(audit_raw).strip() if isinstance(audit_raw, str) and str(audit_raw).strip() else None
            t_ss = time.perf_counter()
            payload = compute_schedule_stats_from_audit(
                cwd=str(root),
                days=int(getattr(args, "days", 30) or 30),
                audit_path=audit_arg,
            )
            ss_ms = (time.perf_counter() - t_ss) * 1000.0
            tasks_ss = payload.get("tasks") if isinstance(payload.get("tasks"), list) else []
            _maybe_metrics_cli(
                module="schedule",
                event="schedule.stats",
                latency_ms=ss_ms,
                tokens=len(tasks_ss),
                success=True,
            )
            if bool(args.json_output):
                print(json.dumps(payload, ensure_ascii=False))
            else:
                print(
                    f"schedule stats days={payload.get('days')} audit={payload.get('audit_file')} "
                    f"tasks={len(payload.get('tasks') or [])}",
                )
                for t in payload.get("tasks") or []:
                    tid = str(t.get("task_id") or "")
                    sr = t.get("success_rate")
                    sr_s = f"{sr:.2f}" if isinstance(sr, float) else "-"
                    print(
                        f"{tid}\trun={t.get('run_count')} ok={t.get('success_count')} fail={t.get('fail_count')} "
                        f"rate={sr_s}\tavg_ms={t.get('avg_elapsed_ms')} p95_ms={t.get('p95_elapsed_ms')}\t"
                        f"goal={(str(t.get('goal_preview') or '')[:60])}",
                    )
            min_sr = getattr(args, "fail_on_min_success_rate", None)
            if isinstance(min_sr, (int, float)):
                thr = float(min_sr)
                for t in payload.get("tasks") or []:
                    if not isinstance(t, dict):
                        continue
                    rc = int(t.get("run_count") or 0)
                    if rc < 1:
                        continue
                    sr2 = t.get("success_rate")
                    if not isinstance(sr2, (int, float)):
                        continue
                    if float(sr2) + 1e-9 < thr:
                        return 2
            return 0

    if args.command == "cost":
        if args.cost_action == "report":
            from cai_agent.cost_aggregate import (
                build_compact_policy_explain_v1,
                build_cost_by_profile_v1,
            )

            t_cr = time.perf_counter()
            doc_cr = build_cost_by_profile_v1(
                os.getcwd(),
                include_by_tenant=bool(getattr(args, "cost_include_tenant", False)),
                include_by_calendar_day=bool(getattr(args, "cost_per_day", False)),
            )
            st_rep = Settings.from_env(config_path=None, workspace_hint=os.getcwd())
            doc_cr["compact_policy_explain_v1"] = build_compact_policy_explain_v1(
                cost_budget_max_tokens=int(getattr(st_rep, "cost_budget_max_tokens", 0) or 0),
                context_compact_after_iterations=int(
                    getattr(st_rep, "context_compact_after_iterations", 0) or 0,
                ),
                context_compact_min_messages=int(getattr(st_rep, "context_compact_min_messages", 0) or 0),
                context_compact_on_tool_error=bool(getattr(st_rep, "context_compact_on_tool_error", False)),
                context_compact_after_tool_calls=int(
                    getattr(st_rep, "context_compact_after_tool_calls", 0) or 0,
                ),
            )
            if not bool(getattr(args, "json_output", False)):
                print("[cost report] text summary（完整 JSON 含 cost_by_profile_v1 + compact_policy_explain_v1）：")
                profs = doc_cr.get("profiles") or []
                if isinstance(profs, list) and profs:
                    for row in profs[:12]:
                        if not isinstance(row, dict):
                            continue
                        print(
                            f"  profile={row.get('id')!s}\t"
                            f"tokens={int(row.get('total_tokens') or 0)}\t"
                            f"events={int(row.get('events') or 0)}",
                        )
                else:
                    print("  (no profile rows; metrics/sessions may be empty)")
                cpe = doc_cr.get("compact_policy_explain_v1") or {}
                lines = cpe.get("lines_zh") if isinstance(cpe, dict) else None
                if isinstance(lines, list) and lines:
                    print("compact / budget policy:")
                    for ln in lines:
                        if isinstance(ln, str) and ln.strip():
                            print(f"  {ln}")
                print("机读: cai-agent cost report --json")
                _maybe_metrics_cli(
                    module="cost",
                    event="cost.report",
                    latency_ms=(time.perf_counter() - t_cr) * 1000.0,
                    tokens=len(doc_cr.get("profiles") or []),
                    success=True,
                )
                return 0
            print(json.dumps(doc_cr, ensure_ascii=False))
            _maybe_metrics_cli(
                module="cost",
                event="cost.report",
                latency_ms=(time.perf_counter() - t_cr) * 1000.0,
                tokens=len(doc_cr.get("profiles") or []),
                success=True,
            )
            return 0
        if args.cost_action == "budget":
            from cai_agent.cost_aggregate import build_cost_budget_explain_v1

            settings_cost = Settings.from_env(config_path=None)
            t_cost = time.perf_counter()
            _print_hook_status(
                settings_cost,
                event="cost_budget_start",
                json_output=True,
            )
            rc_cost = 2
            total_t_cost = 0
            try:
                cfg_max = int(settings_cost.cost_budget_max_tokens)
                max_tokens = (
                    int(args.max_tokens) if args.max_tokens is not None else cfg_max
                )
                agg = aggregate_sessions(cwd=os.getcwd(), limit=200)
                total_tokens = int(agg.get("total_tokens", 0))
                total_t_cost = total_tokens
                state = "pass"
                if total_tokens > max_tokens:
                    state = "fail"
                elif total_tokens > int(max_tokens * 0.8):
                    state = "warn"
                explain_cb = build_cost_budget_explain_v1(
                    state=state,
                    total_tokens=total_tokens,
                    max_tokens=max_tokens,
                )
                payload = {
                    "schema_version": "cost_budget_v1",
                    "state": state,
                    "total_tokens": total_tokens,
                    "max_tokens": max_tokens,
                    "active_profile_id": str(settings_cost.active_profile_id or ""),
                    "explain": explain_cb,
                }
                print(json.dumps(payload, ensure_ascii=False))
                rc_cost = 0 if state != "fail" else 2
            finally:
                _print_hook_status(
                    settings_cost,
                    event="cost_budget_end",
                    json_output=True,
                )
            _maybe_metrics_cli(
                module="cost",
                event="cost.budget",
                latency_ms=(time.perf_counter() - t_cost) * 1000.0,
                tokens=total_t_cost,
                success=(rc_cost == 0),
            )
            return rc_cost

    if args.command == "api":
        aa = str(getattr(args, "api_action", "") or "").strip()
        if aa != "serve":
            print("api: 未知子命令", file=sys.stderr)
            return 2
        from cai_agent.api_http_server import run_agent_api_server

        port_raw = getattr(args, "api_port", None)
        if isinstance(port_raw, int):
            bind_port = int(port_raw)
        else:
            bind_port = int((os.environ.get("CAI_API_PORT") or "8788").strip() or "8788")
        ws_arg = getattr(args, "api_workspace", None)
        ws = Path(str(ws_arg).strip()).expanduser().resolve() if isinstance(ws_arg, str) and str(ws_arg).strip() else Path.cwd().resolve()
        return int(
            run_agent_api_server(
                host=str(getattr(args, "host", "127.0.0.1") or "127.0.0.1"),
                port=int(bind_port),
                workspace=ws,
            ),
        )

    if args.command == "feedback":
        from cai_agent.feedback import append_feedback, export_feedback_jsonl, feedback_stats, list_feedback

        root_fb = Path.cwd().resolve()
        act_fb = str(getattr(args, "feedback_action", "") or "").strip().lower()
        t_fb = time.perf_counter()
        if act_fb == "stats":
            st = feedback_stats(root_fb)
            if bool(getattr(args, "json_output", False)):
                print(json.dumps(st, ensure_ascii=False))
            else:
                print(
                    "[feedback] stats",
                    f"total={int(st.get('total') or 0)}",
                    f"latest_ts={st.get('latest_ts') or '-'}",
                    f"sources={st.get('sources') or {}}",
                )
            _maybe_metrics_cli(
                module="feedback",
                event="feedback.stats",
                latency_ms=(time.perf_counter() - t_fb) * 1000.0,
                tokens=int(st.get("total") or 0),
                success=True,
            )
            return 0
        if act_fb == "bug":
            from cai_agent.feedback import append_bug_report

            summ = " ".join(str(x) for x in (getattr(args, "bug_summary", []) or [])).strip()
            det_file = str(getattr(args, "detail_file", "") or "").strip()
            det = str(getattr(args, "detail", "") or "").strip()
            if det_file:
                p_df = Path(det_file).expanduser()
                if not p_df.is_file():
                    print("detail-file 不存在或不是文件", file=sys.stderr)
                    return 2
                det = p_df.read_text(encoding="utf-8", errors="replace")[:200_000]
            try:
                row = append_bug_report(
                    root_fb,
                    summary=summ,
                    detail=det,
                    category=str(getattr(args, "category", "other") or "other"),
                    cai_agent_version=__version__,
                )
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return 2
            if bool(getattr(args, "json_output", False)):
                print(json.dumps(row, ensure_ascii=False))
            else:
                print("[feedback] bug 已记录", row.get("ts"), "→", str(feedback_path(root_fb)))
                print("  category=", row.get("category"), "summary=", (row.get("summary") or "")[:120])
                if bool(getattr(args, "attach_doctor_hint", False)):
                    print("  hint: 附加环境摘要可执行: cai-agent doctor --json")
            _maybe_metrics_cli(
                module="feedback",
                event="feedback.bug",
                latency_ms=(time.perf_counter() - t_fb) * 1000.0,
                tokens=len(summ) + len(det),
                success=True,
            )
            return 0
        if act_fb == "submit":
            txt = " ".join(str(x) for x in (getattr(args, "feedback_text", []) or [])).strip()
            if not txt:
                print("反馈文本不能为空", file=sys.stderr)
                return 2
            row = append_feedback(root_fb, text=txt)
            if bool(getattr(args, "json_output", False)):
                print(json.dumps(row, ensure_ascii=False))
            else:
                print("[feedback] 已记录", row.get("ts"))
            _maybe_metrics_cli(
                module="feedback",
                event="feedback.submit",
                latency_ms=(time.perf_counter() - t_fb) * 1000.0,
                tokens=len(txt),
                success=True,
            )
            return 0
        if act_fb == "list":
            rows = list_feedback(root_fb, limit=int(getattr(args, "limit", 30) or 30))
            out = {"schema_version": "feedback_list_v1", "rows": rows}
            if bool(getattr(args, "json_output", False)):
                print(json.dumps(out, ensure_ascii=False))
            else:
                for r in rows[-20:]:
                    if isinstance(r, dict):
                        line = str(r.get("text") or r.get("summary") or "")
                        print(f"{r.get('ts')}\t{line[:120]}")
            _maybe_metrics_cli(
                module="feedback",
                event="feedback.list",
                latency_ms=(time.perf_counter() - t_fb) * 1000.0,
                tokens=len(rows),
                success=True,
            )
            return 0
        if act_fb == "export":
            dest_ex = str(getattr(args, "dest", "") or "").strip()
            if not dest_ex:
                print("需要 --dest PATH", file=sys.stderr)
                return 2
            lim_ex = getattr(args, "feedback_export_limit", None)
            out_ex = export_feedback_jsonl(
                root_fb,
                dest=dest_ex,
                limit=int(lim_ex) if isinstance(lim_ex, int) and not isinstance(lim_ex, bool) else None,
            )
            if bool(getattr(args, "json_output", False)):
                print(json.dumps(out_ex, ensure_ascii=False))
            else:
                print(f"[feedback] export rows={out_ex.get('rows')} -> {out_ex.get('dest')}")
            _maybe_metrics_cli(
                module="feedback",
                event="feedback.export",
                latency_ms=(time.perf_counter() - t_fb) * 1000.0,
                tokens=int(out_ex.get("rows") or 0),
                success=True,
            )
            return 0
        print("feedback: 未知子命令", file=sys.stderr)
        return 2

    if args.command == "release-changelog":
        anchor = Path.cwd().resolve()
        if getattr(args, "workspace", None):
            anchor = Path(os.path.abspath(str(args.workspace))).resolve()
        root_scan = anchor
        for _ in range(10):
            if (root_scan / "CHANGELOG.md").is_file():
                break
            if root_scan.parent == root_scan:
                break
            root_scan = root_scan.parent
        from cai_agent.changelog_sync import check_changelog_bilingual

        doc_cl = check_changelog_bilingual(repo_root=root_scan)
        sem = None
        if bool(getattr(args, "release_changelog_semantic", False)):
            from cai_agent.changelog_semantic import build_changelog_semantic_compare

            sem = build_changelog_semantic_compare(repo_root=root_scan)
        runbook = build_release_runbook_payload(repo_root=root_scan, workspace=anchor)
        if bool(getattr(args, "json_output", False)):
            if sem is None:
                print(json.dumps(doc_cl, ensure_ascii=False))
            else:
                print(
                    json.dumps(
                        {
                            "schema_version": "release_changelog_report_v1",
                            "ok": bool(doc_cl.get("ok")) and bool(sem.get("ok")),
                            "workspace": str(anchor),
                            "repo_root": str(root_scan),
                            "bilingual": doc_cl,
                            "semantic": sem,
                            "runbook": {
                                "schema_version": runbook.get("schema_version"),
                                "state": runbook.get("state"),
                                "runbook_steps": runbook.get("runbook_steps"),
                                "writeback_targets": runbook.get("writeback_targets"),
                            },
                        },
                        ensure_ascii=False,
                    ),
                )
        else:
            print(
                f"changelog bilingual: ok={doc_cl.get('ok')} "
                f"lines_en={doc_cl.get('lines_en')} lines_zh={doc_cl.get('lines_zh')} "
                f"ratio={doc_cl.get('line_ratio')}",
            )
            if sem is not None:
                print(
                    f"changelog semantic: ok={sem.get('ok')} "
                    f"h2_en={sem.get('h2_count_en')} h2_zh={sem.get('h2_count_zh')}",
                )
            print("runbook: cai-agent doctor --json -> cai-agent release-changelog --json --semantic")
            print("docs: docs/CHANGELOG_SYNC.zh-CN.md | docs/qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md")
        ok_cl = bool(doc_cl.get("ok"))
        if sem is not None:
            ok_cl = ok_cl and bool(sem.get("ok"))
        return 0 if ok_cl else 2

    if args.command == "claw-migrate":
        from cai_agent.claw_migrate import run_claw_migrate

        apply_m = bool(getattr(args, "claw_migrate_apply", False))
        return int(run_claw_migrate(dry_run=not apply_m))

    if args.command == "export":
        try:
            settings = Settings.from_env(
                config_path=args.config,
                workspace_hint=_settings_workspace_hint(args),
            )
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        if args.model:
            settings = replace(settings, model=str(args.model).strip())
        if args.workspace:
            settings = replace(
                settings,
                workspace=os.path.abspath(args.workspace),
            )
        _print_hook_status(
            settings,
            event="export_start",
            json_output=True,
        )
        t_exp = time.perf_counter()
        try:
            if bool(getattr(args, "export_ecc_diff", False)):
                result = build_export_ecc_dir_diff_report(settings, target=str(args.target))
            else:
                result = export_target(settings, str(args.target))
        finally:
            _print_hook_status(
                settings,
                event="export_end",
                json_output=True,
            )
        print(json.dumps(result, ensure_ascii=False))
        copied = result.get("copied") if isinstance(result.get("copied"), list) else []
        _maybe_metrics_cli(
            module="export",
            event="export.target",
            latency_ms=(time.perf_counter() - t_exp) * 1000.0,
            tokens=len(copied),
            success=True,
        )
        return 0

    if args.command == "observe":
        from cai_agent.metrics import maybe_append_metrics_from_env, metrics_event_v1

        settings_obs = Settings.from_env(config_path=None)
        act_ob = str(getattr(args, "observe_action", "") or "").strip()
        if act_ob == "export":
            from cai_agent.observe_export import (
                build_observe_export_v1,
                render_observe_export_csv,
                render_observe_export_markdown,
            )

            fmt = str(getattr(args, "observe_export_format", "json") or "json").lower()
            exp_json_out = fmt == "json"
            days_x = max(int(getattr(args, "observe_export_days", 30) or 30), 1)
            hook_exp: dict[str, Any] = {
                "kind": "export",
                "pattern": str(args.pattern),
                "limit": int(args.limit),
                "days": days_x,
                "format": fmt,
            }
            _print_hook_status(
                settings_obs,
                event="observe_start",
                json_output=exp_json_out,
                hook_payload=hook_exp,
            )
            t_ex0 = time.perf_counter()
            try:
                doc = build_observe_export_v1(
                    cwd=os.getcwd(),
                    pattern=str(args.pattern),
                    limit=int(args.limit),
                    days=days_x,
                )
            finally:
                _print_hook_status(
                    settings_obs,
                    event="observe_end",
                    json_output=exp_json_out,
                    hook_payload=hook_exp,
                )
            ex_ms = (time.perf_counter() - t_ex0) * 1000.0
            if fmt == "csv":
                body = render_observe_export_csv(doc)
            elif fmt == "markdown":
                body = render_observe_export_markdown(doc)
            else:
                body = json.dumps(doc, ensure_ascii=False, indent=2)
            out_path = getattr(args, "observe_export_output", None)
            if isinstance(out_path, str) and out_path.strip():
                outp = Path(out_path.strip())
                outp.parent.mkdir(parents=True, exist_ok=True)
                outp.write_text(body, encoding="utf-8")
            print(body)
            tok_sum = sum(int(r.get("token_total") or 0) for r in (doc.get("rows") or []) if isinstance(r, dict))
            maybe_append_metrics_from_env(
                metrics_event_v1(
                    module="observe",
                    event="observe.export",
                    latency_ms=ex_ms,
                    tokens=tok_sum,
                    success=True,
                ),
            )
            return 0

        if act_ob == "report":
            from cai_agent.observe_ops_report import build_observe_ops_report_v1, render_observe_ops_markdown

            fmt = str(getattr(args, "format", "json") or "json").lower()
            rep_json_out = fmt == "json"
            days = max(int(getattr(args, "days", 7) or 7), 1)
            hook_rep: dict[str, Any] = {
                "kind": "report",
                "pattern": str(args.pattern),
                "limit": int(args.limit),
                "days": days,
                "format": fmt,
            }
            _print_hook_status(
                settings_obs,
                event="observe_start",
                json_output=rep_json_out,
                hook_payload=hook_rep,
            )
            t_rep0 = time.perf_counter()
            try:
                doc = build_observe_ops_report_v1(
                    cwd=os.getcwd(),
                    pattern=str(args.pattern),
                    limit=int(args.limit),
                    days=days,
                )
            finally:
                _print_hook_status(
                    settings_obs,
                    event="observe_end",
                    json_output=rep_json_out,
                    hook_payload=hook_rep,
                )
            rep_ms = (time.perf_counter() - t_rep0) * 1000.0
            body = (
                json.dumps(doc, ensure_ascii=False, indent=2)
                if fmt == "json"
                else render_observe_ops_markdown(doc)
            )
            out_path = getattr(args, "output", None)
            if isinstance(out_path, str) and out_path.strip():
                outp = Path(out_path.strip())
                outp.parent.mkdir(parents=True, exist_ok=True)
                outp.write_text(body, encoding="utf-8")
            print(body)
            maybe_append_metrics_from_env(
                metrics_event_v1(
                    module="observe",
                    event="observe.report",
                    latency_ms=rep_ms,
                    tokens=int(doc.get("token_total") or 0),
                    success=True,
                ),
            )
            return 0

        obs_json = bool(getattr(args, "json_output", False))
        obs_payload: dict[str, Any] | None = None
        hook_sum = {"kind": "summary", "pattern": str(args.pattern), "limit": int(args.limit)}
        _print_hook_status(
            settings_obs,
            event="observe_start",
            json_output=obs_json,
            hook_payload=hook_sum,
        )
        t_sum0 = time.perf_counter()
        try:
            obs_payload = build_observe_payload(
                cwd=os.getcwd(),
                pattern=str(args.pattern),
                limit=int(args.limit),
            )
            if args.json_output:
                print(json.dumps(obs_payload, ensure_ascii=False))
            else:
                ag = obs_payload.get("aggregates") if isinstance(obs_payload.get("aggregates"), dict) else {}
                print(
                    f"schema={obs_payload.get('schema_version')} sessions={obs_payload.get('sessions_count')} "
                    f"failed={ag.get('failed_count')} tokens={ag.get('total_tokens')} "
                    f"run_events_total={ag.get('run_events_total', 0)}",
                )
        finally:
            _print_hook_status(
                settings_obs,
                event="observe_end",
                json_output=obs_json,
                hook_payload=hook_sum,
            )
        sum_ms = (time.perf_counter() - t_sum0) * 1000.0
        if obs_payload is not None:
            agm = obs_payload.get("aggregates") if isinstance(obs_payload.get("aggregates"), dict) else {}
            maybe_append_metrics_from_env(
                metrics_event_v1(
                    module="observe",
                    event="observe.summary",
                    latency_ms=sum_ms,
                    tokens=int(agm.get("total_tokens") or 0),
                    success=True,
                ),
            )
        mx_obs = getattr(args, "fail_on_max_failure_rate", None)
        if obs_payload is not None and isinstance(mx_obs, (int, float)):
            agx = obs_payload.get("aggregates") if isinstance(obs_payload.get("aggregates"), dict) else {}
            frx = float(agx.get("failure_rate") or 0.0)
            if frx + 1e-12 >= float(mx_obs):
                return 2
        return 0

    if args.command == "observe-report":
        t_obr = time.perf_counter()
        obs = build_observe_payload(
            cwd=os.getcwd(),
            pattern=str(getattr(args, "pattern", ".cai-session*.json")),
            limit=int(getattr(args, "limit", 100)),
        )
        payload = _build_observe_report_payload(
            observe_payload=obs,
            warn_failure_rate=float(getattr(args, "warn_failure_rate", 0.20)),
            fail_failure_rate=float(getattr(args, "fail_failure_rate", 0.35)),
            warn_token_budget=int(getattr(args, "warn_token_budget", 40_000)),
            fail_token_budget=int(getattr(args, "fail_token_budget", 80_000)),
            warn_tool_errors=int(getattr(args, "warn_tool_errors", 3)),
            fail_tool_errors=int(getattr(args, "fail_tool_errors", 8)),
        )
        if bool(getattr(args, "json_output", False)):
            print(json.dumps(payload, ensure_ascii=False))
        else:
            obs_obr = payload.get("observe") if isinstance(payload.get("observe"), dict) else {}
            ag_obr = obs_obr.get("aggregates") if isinstance(obs_obr.get("aggregates"), dict) else {}
            print(
                f"[observe-report] state={payload.get('state')} "
                f"sessions={obs_obr.get('sessions_count')} "
                f"failure_rate={ag_obr.get('failure_rate')} "
                f"total_tokens={ag_obr.get('total_tokens')} "
                f"tool_errors={ag_obr.get('tool_errors_total')}",
            )
            alerts = payload.get("alerts") or []
            if isinstance(alerts, list):
                for a in alerts:
                    if not isinstance(a, dict):
                        continue
                    print(f"- {a.get('severity')} {a.get('name')}: {a.get('detail')}")
        st = str(payload.get("state") or "")
        rc_obr = 0
        if st == "fail":
            rc_obr = 2
        elif bool(getattr(args, "fail_on_warn", False)) and st == "warn":
            rc_obr = 2
        obsr_m = payload.get("observe") if isinstance(payload.get("observe"), dict) else {}
        agm_m = obsr_m.get("aggregates") if isinstance(obsr_m.get("aggregates"), dict) else {}
        _maybe_metrics_cli(
            module="observe",
            event="observe.report",
            latency_ms=(time.perf_counter() - t_obr) * 1000.0,
            tokens=int(agm_m.get("total_tokens") or 0),
            success=(rc_obr == 0),
        )
        return rc_obr

    if args.command == "ops":
        oa = str(getattr(args, "ops_action", "") or "").strip()
        if oa == "serve":
            from cai_agent.ops_http_server import run_ops_api_server

            allow = [
                str(Path(p).expanduser().resolve())
                for p in (getattr(args, "ops_allow_workspaces", None) or [])
            ]
            if not allow:
                allow = [str(Path.cwd().resolve())]
            return int(
                run_ops_api_server(
                    host=str(getattr(args, "host", "127.0.0.1") or "127.0.0.1"),
                    port=int(getattr(args, "port", 8765)),
                    allow_workspaces=allow,
                ),
            )
        if oa != "dashboard":
            print("ops: 未知子命令", file=sys.stderr)
            return 2
        root_ops = Path.cwd().resolve()
        from cai_agent.ops_dashboard import build_ops_dashboard_payload

        t_ops = time.perf_counter()
        payload_ops = build_ops_dashboard_payload(
            cwd=str(root_ops),
            observe_pattern=str(getattr(args, "pattern", ".cai-session*.json")),
            observe_limit=int(getattr(args, "limit", 100)),
            schedule_days=int(getattr(args, "schedule_days", 30)),
            audit_path=getattr(args, "audit_file", None),
        )
        ops_fmt = str(getattr(args, "ops_format", "text") or "text").strip().lower()
        if bool(getattr(args, "json_output", False)):
            ops_fmt = "json"
        ops_out_path = getattr(args, "ops_output", None)
        if ops_fmt == "json":
            output_str = json.dumps(payload_ops, ensure_ascii=False)
        elif ops_fmt == "html":
            from cai_agent.ops_dashboard import build_ops_dashboard_html

            hrs = int(getattr(args, "ops_html_refresh_seconds", 0) or 0)
            output_str = build_ops_dashboard_html(
                payload_ops,
                html_refresh_seconds=hrs if hrs > 0 else None,
            )
        else:
            sm = payload_ops.get("summary") if isinstance(payload_ops.get("summary"), dict) else {}
            output_str = (
                "[ops dashboard] "
                f"sessions={sm.get('sessions_count')} failure_rate={sm.get('failure_rate')} "
                f"schedule_tasks={sm.get('schedule_tasks_in_stats')} "
                f"cost_tokens={sm.get('cost_total_tokens')}"
            )
        if ops_out_path:
            Path(ops_out_path).write_text(output_str, encoding="utf-8")
            print(f"ops dashboard 已写入 {ops_out_path}")
        else:
            print(output_str)
        sm_m = payload_ops.get("summary") if isinstance(payload_ops.get("summary"), dict) else {}
        _maybe_metrics_cli(
            module="ops",
            event="ops.dashboard",
            latency_ms=(time.perf_counter() - t_ops) * 1000.0,
            tokens=int(sm_m.get("sessions_count") or sm_m.get("schedule_tasks_in_stats") or 0),
            success=True,
        )
        return 0

    if args.command == "board":
        settings_board = Settings.from_env(config_path=None)
        t_bd = time.perf_counter()
        board_json = bool(getattr(args, "json_output", False))
        failed_only = bool(getattr(args, "failed_only", False))
        task_id_filter = str(getattr(args, "task_id", "") or "").strip()
        raw_statuses = getattr(args, "status", []) or []
        statuses_filter: list[str] = []
        if isinstance(raw_statuses, list):
            for raw in raw_statuses:
                parts = [p.strip().lower() for p in str(raw or "").split(",")]
                for s in parts:
                    if s and s not in statuses_filter:
                        statuses_filter.append(s)
        _print_hook_status(
            settings_board,
            event="board_start",
            json_output=board_json,
        )
        try:
            payload = build_board_payload(
                cwd=os.getcwd(),
                observe_pattern=str(args.pattern),
                observe_limit=int(args.limit),
            )
            payload = filter_board_payload(
                payload,
                failed_only=failed_only,
                task_id=task_id_filter or None,
                status_filters=statuses_filter,
            )
            payload = attach_failed_summary(
                payload,
                limit=max(1, int(getattr(args, "failed_top", 5))),
            )
            payload = attach_status_summary(payload)
            payload = attach_group_summary(
                payload,
                top_n=max(1, int(getattr(args, "group_top", 5))),
            )
            payload = attach_trend_summary(
                payload,
                recent_window=max(1, int(getattr(args, "trend_window", 10))),
            )
            payload["filters"] = {
                "failed_only": failed_only,
                "task_id": task_id_filter or None,
                "status": sorted(
                    {
                        str(s).strip().lower()
                        for s in statuses_filter
                        if str(s).strip()
                    },
                ),
            }
            if board_json:
                print(json.dumps(payload, ensure_ascii=False))
            else:
                obs = payload.get("observe") if isinstance(payload.get("observe"), dict) else {}
                ag = obs.get("aggregates") if isinstance(obs.get("aggregates"), dict) else {}
                status_summary = payload.get("status_summary")
                print(
                    f"[observe] schema={obs.get('schema_version')} "
                    f"sessions={obs.get('sessions_count')} "
                    f"failed={ag.get('failed_count')} tokens={ag.get('total_tokens')} "
                    f"run_events_total={ag.get('run_events_total', 0)}",
                )
                if isinstance(status_summary, dict):
                    counts = status_summary.get("counts")
                    if isinstance(counts, dict):
                        print(
                            "[status_summary] "
                            f"pending={counts.get('pending', 0)} "
                            f"running={counts.get('running', 0)} "
                            f"completed={counts.get('completed', 0)} "
                            f"failed={counts.get('failed', 0)}",
                        )
                failed_summary = payload.get("failed_summary")
                group_summary = payload.get("group_summary")
                recent_failed = (
                    failed_summary.get("recent")
                    if isinstance(failed_summary, dict)
                    else None
                )
                if isinstance(recent_failed, list) and recent_failed:
                    print("[recent_failed]")
                    for row in recent_failed:
                        if not isinstance(row, dict):
                            continue
                        print(
                            "  "
                            f"path={row.get('path')} "
                            f"task_id={row.get('task_id')} "
                            f"errors={row.get('error_count')}",
                        )
                if isinstance(group_summary, dict):
                    models_top = group_summary.get("models_top")
                    tasks_top = group_summary.get("tasks_top")
                    if isinstance(models_top, list) and models_top:
                        print("[models_top]")
                        for row in models_top:
                            if not isinstance(row, dict):
                                continue
                            print(f"  model={row.get('key')} count={row.get('count')}")
                    if isinstance(tasks_top, list) and tasks_top:
                        print("[tasks_top]")
                        for row in tasks_top:
                            if not isinstance(row, dict):
                                continue
                            print(f"  task_id={row.get('key')} count={row.get('count')}")
                trend_summary = payload.get("trend_summary")
                if isinstance(trend_summary, dict):
                    recent = trend_summary.get("recent")
                    baseline = trend_summary.get("baseline")
                    delta = trend_summary.get("delta")
                    if (
                        isinstance(recent, dict)
                        and isinstance(baseline, dict)
                        and isinstance(delta, dict)
                    ):
                        print(
                            "[trend] "
                            f"recent_n={recent.get('sessions_count')} "
                            f"baseline_n={baseline.get('sessions_count')} "
                            f"failure_rate_delta={delta.get('failure_rate_delta')} "
                            f"avg_tokens_delta={delta.get('avg_tokens_delta')}",
                        )
                wf = payload.get("last_workflow")
                if isinstance(wf, dict):
                    task = wf.get("task") if isinstance(wf.get("task"), dict) else {}
                    tid = task.get("task_id", "")
                    st = task.get("status", "")
                    print(f"[last_workflow] task_id={tid} status={st}")
                    steps = wf.get("steps") if isinstance(wf.get("steps"), list) else []
                    for s in steps:
                        if not isinstance(s, dict):
                            continue
                        nm = s.get("name", "")
                        ix = s.get("index", "")
                        ec = s.get("error_count", 0)
                        print(f"  step {ix} {nm} errors={ec}")
                else:
                    print("[last_workflow] (none — run `cai-agent workflow …` once)")
        finally:
            _print_hook_status(
                settings_board,
                event="board_end",
                json_output=board_json,
            )
        obs_bd = payload.get("observe") if isinstance(payload.get("observe"), dict) else {}
        _maybe_metrics_cli(
            module="board",
            event="board.summary",
            latency_ms=(time.perf_counter() - t_bd) * 1000.0,
            tokens=int(obs_bd.get("sessions_count") or 0),
            success=True,
        )
        if bool(getattr(args, "fail_on_failed_sessions", False)):
            obs2 = payload.get("observe") if isinstance(payload.get("observe"), dict) else {}
            sess_rows = obs2.get("sessions") if isinstance(obs2.get("sessions"), list) else []
            n_fail = sum(
                1
                for s in sess_rows
                if isinstance(s, dict) and int(s.get("error_count") or 0) > 0
            )
            if n_fail > 0:
                return 2
        return 0

    if args.command == "gateway":
        raw_gw = getattr(args, "gateway_workspace", None)
        if raw_gw is not None and str(raw_gw).strip():
            root = Path(str(raw_gw).strip()).expanduser().resolve()
        else:
            root = Path.cwd().resolve()

        ga = getattr(args, "gateway_action", None)
        if ga in {"setup", "start", "status", "prod-status", "stop"}:
            from cai_agent import gateway_lifecycle

            if ga == "setup":
                allow_raw = list(getattr(args, "gateway_setup_allow_chat_ids", None) or [])
                allow_ids = [str(x).strip() for x in allow_raw if str(x).strip()]
                tok_arg = getattr(args, "gateway_setup_bot_token", None)
                tok = str(tok_arg).strip() if tok_arg else None
                serve = {
                    "host": str(getattr(args, "gateway_setup_host", "127.0.0.1") or "127.0.0.1").strip(),
                    "port": int(getattr(args, "gateway_setup_port", 18765) or 18765),
                    "max_events": int(getattr(args, "gateway_setup_max_events", 0) or 0),
                    "create_missing": bool(getattr(args, "gateway_setup_create_missing", False)),
                    "execute_on_update": bool(getattr(args, "gateway_setup_execute_on_update", False)),
                    "reply_on_execution": bool(getattr(args, "gateway_setup_reply_on_execution", False)),
                    "reply_on_deny": bool(getattr(args, "gateway_setup_reply_on_deny", False)),
                    "goal_template": str(
                        getattr(
                            args,
                            "gateway_setup_goal_template",
                            "用户({user_id})在 chat({chat_id}) 发送消息：{text}",
                        )
                        or "用户({user_id})在 chat({chat_id}) 发送消息：{text}",
                    ),
                    "reply_template": str(
                        getattr(args, "gateway_setup_reply_template", "执行完成 ok={ok}\n{answer}")
                        or "执行完成 ok={ok}\n{answer}",
                    ),
                    "deny_message": str(
                        getattr(args, "gateway_setup_deny_message", "此 CAI Agent Bot 未授权本对话。")
                        or "此 CAI Agent Bot 未授权本对话。",
                    ),
                }
                out_st = gateway_lifecycle.build_setup_payload(
                    root=root,
                    use_env_token=bool(getattr(args, "gateway_setup_use_env_token", False)),
                    bot_token=tok,
                    workspace=str(root),
                    serve=serve,
                    allow_chat_ids=allow_ids or None,
                )
                json_st = bool(getattr(args, "json_output", False))
                if json_st:
                    print(json.dumps(out_st, ensure_ascii=False))
                else:
                    print(
                        f"[gateway setup] config={out_st.get('config_path')} workspace={out_st.get('workspace')}",
                    )
                return 0
            if ga == "start":
                out_st = gateway_lifecycle.start_webhook_subprocess(root)
                json_st = bool(getattr(args, "json_output", False))
                if json_st:
                    print(json.dumps(out_st, ensure_ascii=False))
                else:
                    if out_st.get("ok"):
                        print(
                            f"[gateway start] pid={out_st.get('pid')} pid_file={out_st.get('pid_file')} "
                            f"stdout={out_st.get('stdout_log')}",
                        )
                    else:
                        print(f"[gateway start] failed: {out_st.get('error')}", file=sys.stderr)
                return 0 if out_st.get("ok") else 2
            if ga == "status":
                t_gs = time.perf_counter()
                out_st = gateway_lifecycle.build_status_payload(root)
                gs_ms = (time.perf_counter() - t_gs) * 1000.0
                _maybe_metrics_cli(
                    module="gateway",
                    event="gateway.status",
                    latency_ms=gs_ms,
                    tokens=0,
                    success=True,
                )
                json_st = bool(getattr(args, "json_output", False))
                if json_st:
                    print(json.dumps(out_st, ensure_ascii=False))
                else:
                    print(
                        f"[gateway status] config_exists={out_st.get('config_exists')} "
                        f"webhook_running={out_st.get('webhook_running')} "
                        f"webhook_pid={out_st.get('webhook_pid')} allowlist={out_st.get('allowlist_enabled')}",
                    )
                return 0
            if ga == "prod-status":
                from cai_agent.gateway_production import build_gateway_production_summary_payload

                out_st = build_gateway_production_summary_payload(root)
                if bool(getattr(args, "json_output", False)):
                    print(json.dumps(out_st, ensure_ascii=False))
                else:
                    sm = out_st.get("summary") if isinstance(out_st.get("summary"), dict) else {}
                    print(
                        "[gateway prod-status] "
                        f"platforms={sm.get('platforms_count')} configured={sm.get('configured_count')} "
                        f"running={sm.get('running_count')} bindings={sm.get('bindings_count')}",
                    )
                return 0
            if ga == "stop":
                out_st = gateway_lifecycle.stop_webhook_subprocess(root)
                json_st = bool(getattr(args, "json_output", False))
                if json_st:
                    print(json.dumps(out_st, ensure_ascii=False))
                else:
                    print(
                        f"[gateway stop] ok={out_st.get('ok')} stopped={out_st.get('stopped')} "
                        f"error={out_st.get('error')}",
                    )
                if out_st.get("ok"):
                    return 0
                if str(out_st.get("error") or "") == "no_pid_file":
                    return 0
                return 2

        if ga == "platforms":
            actp = str(getattr(args, "gateway_platforms_action", "") or "").strip()
            if actp != "list":
                print("gateway platforms: 未知子命令", file=sys.stderr)
                return 2
            from cai_agent.gateway_platforms import build_gateway_platforms_payload

            payload_pf = build_gateway_platforms_payload(workspace=root)
            if bool(getattr(args, "json_output", False)):
                print(json.dumps(payload_pf, ensure_ascii=False))
            else:
                print("[gateway platforms]")
                for row in payload_pf.get("platforms") or []:
                    if not isinstance(row, dict):
                        continue
                    print(
                        f"- {row.get('id')}: implementation={row.get('implementation')} "
                        f"label={row.get('label')}",
                    )
            return 0
        map_path = _resolve_gateway_map_path(root, getattr(args, "map_file", None))
        doc = _load_gateway_map(map_path)
        bindings = doc.get("bindings")
        if not isinstance(bindings, dict):
            bindings = {}
            doc["bindings"] = bindings

        if getattr(args, "gateway_action", None) == "telegram":
            act = str(getattr(args, "gateway_telegram_action", "") or "").strip()
            if act == "bind":
                chat_id = str(getattr(args, "chat_id", "") or "").strip()
                user_id = str(getattr(args, "user_id", "") or "").strip()
                session_raw = str(getattr(args, "session_file", "") or "").strip()
                if not chat_id or not user_id or not session_raw:
                    print("chat-id/user-id/session-file 不能为空", file=sys.stderr)
                    return 2
                p = Path(session_raw).expanduser()
                if not p.is_absolute():
                    p = (root / p).resolve()
                else:
                    p = p.resolve()
                key = f"{chat_id}:{user_id}"
                row = {"chat_id": chat_id, "user_id": user_id, "session_file": str(p)}
                t_gtb = time.perf_counter()
                bindings[key] = row
                _save_gateway_map(map_path, doc)
                payload = {
                    "schema_version": "gateway_telegram_map_v1",
                    "action": "bind",
                    "ok": True,
                    "map_file": str(map_path),
                    "binding": row,
                    "bindings_count": len(bindings),
                }
                _maybe_metrics_cli(
                    module="gateway",
                    event="gateway.telegram.bind",
                    latency_ms=(time.perf_counter() - t_gtb) * 1000.0,
                    tokens=len(bindings),
                    success=True,
                )
                if bool(getattr(args, "json_output", False)):
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(
                        f"bound chat_id={chat_id} user_id={user_id} session_file={p} total={len(bindings)}",
                    )
                return 0
            if act == "get":
                chat_id = str(getattr(args, "chat_id", "") or "").strip()
                user_id = str(getattr(args, "user_id", "") or "").strip()
                key = f"{chat_id}:{user_id}"
                t_gtg = time.perf_counter()
                row = bindings.get(key) if isinstance(bindings.get(key), dict) else None
                payload = {
                    "schema_version": "gateway_telegram_map_v1",
                    "action": "get",
                    "ok": bool(row),
                    "map_file": str(map_path),
                    "binding": row,
                }
                _maybe_metrics_cli(
                    module="gateway",
                    event="gateway.telegram.get",
                    latency_ms=(time.perf_counter() - t_gtg) * 1000.0,
                    tokens=1 if row else 0,
                    success=bool(row),
                )
                if bool(getattr(args, "json_output", False)):
                    print(json.dumps(payload, ensure_ascii=False))
                elif row:
                    print(f"chat_id={row.get('chat_id')} user_id={row.get('user_id')} session_file={row.get('session_file')}")
                else:
                    print("(not found)")
                return 0 if row else 2
            if act == "list":
                t_gtl = time.perf_counter()
                items = [
                    v
                    for _, v in sorted(bindings.items(), key=lambda x: x[0])
                    if isinstance(v, dict)
                ]
                allowed_ids = _parse_allowed_chat_ids(doc.get("allowed_chat_ids"))
                payload = {
                    "schema_version": "gateway_telegram_map_v1",
                    "action": "list",
                    "ok": True,
                    "map_file": str(map_path),
                    "bindings": items,
                    "bindings_count": len(items),
                    "allowed_chat_ids": allowed_ids,
                    "allowlist_enabled": bool(allowed_ids),
                }
                _maybe_metrics_cli(
                    module="gateway",
                    event="gateway.telegram.list",
                    latency_ms=(time.perf_counter() - t_gtl) * 1000.0,
                    tokens=len(items),
                    success=True,
                )
                if bool(getattr(args, "json_output", False)):
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"bindings={len(items)} allowlist={len(allowed_ids)}")
                    for row in items:
                        print(f"- chat_id={row.get('chat_id')} user_id={row.get('user_id')} session_file={row.get('session_file')}")
                return 0
            if act == "continue-hint":
                cid_h = str(getattr(args, "chat_id", None) or "").strip()
                uid_h = str(getattr(args, "user_id", None) or "").strip()
                if (cid_h and not uid_h) or (uid_h and not cid_h):
                    print(
                        "gateway telegram continue-hint：请同时提供 --chat-id 与 --user-id，或两者皆省略以列出全部绑定",
                        file=sys.stderr,
                    )
                    return 2
                t_gch = time.perf_counter()
                payload_ch = _gateway_continue_hint_payload(
                    root=root,
                    map_path=map_path,
                    chat_id=cid_h or None,
                    user_id=uid_h or None,
                )
                hints_n = payload_ch.get("hints") if isinstance(payload_ch.get("hints"), list) else []
                _maybe_metrics_cli(
                    module="gateway",
                    event="gateway.telegram.continue_hint",
                    latency_ms=(time.perf_counter() - t_gch) * 1000.0,
                    tokens=len(hints_n),
                    success=bool(payload_ch.get("ok")),
                )
                json_ch = bool(getattr(args, "json_output", False))
                if json_ch:
                    print(json.dumps(payload_ch, ensure_ascii=False))
                else:
                    if not payload_ch.get("ok"):
                        print(
                            str(payload_ch.get("error") or "failed")
                            + f" chat_id={payload_ch.get('chat_id')} user_id={payload_ch.get('user_id')}",
                            file=sys.stderr,
                        )
                    else:
                        print("[gateway telegram continue-hint]")
                        print(str(payload_ch.get("note") or ""))
                        for h in payload_ch.get("hints") or []:
                            if not isinstance(h, dict):
                                continue
                            ex = h.get("session_file_exists")
                            print(
                                f"- chat_id={h.get('chat_id')} user_id={h.get('user_id')} "
                                f"exists={ex} path={h.get('session_path_resolved')}",
                            )
                            ccmd = str(h.get("continue_cli") or "").strip()
                            if ccmd:
                                print(f"  {ccmd}")
                return 0 if payload_ch.get("ok") else 2
            if act == "allow":
                sub_allow = str(getattr(args, "gateway_telegram_allow_action", "") or "").strip()
                allowed = _parse_allowed_chat_ids(doc.get("allowed_chat_ids"))
                if sub_allow == "add":
                    cid_a = str(getattr(args, "chat_id", "") or "").strip()
                    if not cid_a:
                        print("--chat-id 不能为空", file=sys.stderr)
                        return 2
                    if cid_a not in allowed:
                        allowed.append(cid_a)
                    doc["allowed_chat_ids"] = sorted(set(allowed))
                    t_gaa = time.perf_counter()
                    _save_gateway_map(map_path, doc)
                    out_a = {
                        "schema_version": "gateway_telegram_map_v1",
                        "action": "allow_add",
                        "ok": True,
                        "map_file": str(map_path),
                        "chat_id": cid_a,
                        "allowed_chat_ids": allowed,
                    }
                    _maybe_metrics_cli(
                        module="gateway",
                        event="gateway.telegram.allow_add",
                        latency_ms=(time.perf_counter() - t_gaa) * 1000.0,
                        tokens=len(allowed),
                        success=True,
                    )
                    if bool(getattr(args, "json_output", False)):
                        print(json.dumps(out_a, ensure_ascii=False))
                    else:
                        print(f"allow_add chat_id={cid_a} total={len(allowed)}")
                    return 0
                if sub_allow == "list":
                    t_gal = time.perf_counter()
                    out_l = {
                        "schema_version": "gateway_telegram_map_v1",
                        "action": "allow_list",
                        "ok": True,
                        "map_file": str(map_path),
                        "allowed_chat_ids": allowed,
                    }
                    _maybe_metrics_cli(
                        module="gateway",
                        event="gateway.telegram.allow_list",
                        latency_ms=(time.perf_counter() - t_gal) * 1000.0,
                        tokens=len(allowed),
                        success=True,
                    )
                    if bool(getattr(args, "json_output", False)):
                        print(json.dumps(out_l, ensure_ascii=False))
                    else:
                        print(f"allowed_chat_ids ({len(allowed)}): {','.join(allowed) if allowed else '(empty — 不限制)'}")
                    return 0
                if sub_allow == "rm":
                    cid_r = str(getattr(args, "chat_id", "") or "").strip()
                    if not cid_r:
                        print("--chat-id 不能为空", file=sys.stderr)
                        return 2
                    removed_r = cid_r in allowed
                    doc["allowed_chat_ids"] = [x for x in allowed if x != cid_r]
                    t_gar = time.perf_counter()
                    _save_gateway_map(map_path, doc)
                    out_r = {
                        "schema_version": "gateway_telegram_map_v1",
                        "action": "allow_rm",
                        "ok": removed_r,
                        "map_file": str(map_path),
                        "chat_id": cid_r,
                        "allowed_chat_ids": doc["allowed_chat_ids"],
                    }
                    _maybe_metrics_cli(
                        module="gateway",
                        event="gateway.telegram.allow_rm",
                        latency_ms=(time.perf_counter() - t_gar) * 1000.0,
                        tokens=1 if removed_r else 0,
                        success=bool(removed_r),
                    )
                    if bool(getattr(args, "json_output", False)):
                        print(json.dumps(out_r, ensure_ascii=False))
                    else:
                        print(f"allow_rm chat_id={cid_r} removed={removed_r}")
                    return 0 if removed_r else 2
                print("gateway telegram allow: 未知子命令", file=sys.stderr)
                return 2
            if act == "unbind":
                chat_id = str(getattr(args, "chat_id", "") or "").strip()
                user_id = str(getattr(args, "user_id", "") or "").strip()
                key = f"{chat_id}:{user_id}"
                t_gtu = time.perf_counter()
                row = bindings.pop(key, None)
                if row is not None:
                    _save_gateway_map(map_path, doc)
                payload = {
                    "schema_version": "gateway_telegram_map_v1",
                    "action": "unbind",
                    "ok": bool(row),
                    "removed": bool(row),
                    "map_file": str(map_path),
                    "binding": row if isinstance(row, dict) else None,
                    "bindings_count": len(bindings),
                }
                _maybe_metrics_cli(
                    module="gateway",
                    event="gateway.telegram.unbind",
                    latency_ms=(time.perf_counter() - t_gtu) * 1000.0,
                    tokens=len(bindings),
                    success=bool(row),
                )
                if bool(getattr(args, "json_output", False)):
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"removed={bool(row)} total={len(bindings)}")
                return 0 if row else 2
            if act == "resolve-update":
                json_out = bool(getattr(args, "json_output", False))
                update_raw = str(getattr(args, "update_file", "") or "").strip()
                if not update_raw:
                    payload = {
                        "schema_version": "gateway_telegram_map_v1",
                        "action": "resolve-update",
                        "ok": False,
                        "error": "invalid_args",
                        "message": "update-file 不能为空",
                    }
                    if json_out:
                        print(json.dumps(payload, ensure_ascii=False))
                    else:
                        print("update-file 不能为空", file=sys.stderr)
                    return 2
                up = Path(update_raw).expanduser()
                if not up.is_absolute():
                    up = (root / up).resolve()
                else:
                    up = up.resolve()
                try:
                    update_obj = json.loads(up.read_text(encoding="utf-8"))
                except Exception as e:
                    payload = {
                        "schema_version": "gateway_telegram_map_v1",
                        "action": "resolve-update",
                        "ok": False,
                        "error": "read_update_failed",
                        "message": str(e),
                    }
                    if json_out:
                        print(json.dumps(payload, ensure_ascii=False))
                    else:
                        print(f"读取 update JSON 失败: {e}", file=sys.stderr)
                    return 2
                if not isinstance(update_obj, dict):
                    payload = {
                        "schema_version": "gateway_telegram_map_v1",
                        "action": "resolve-update",
                        "ok": False,
                        "error": "invalid_update",
                        "message": "update JSON 根对象必须为 object",
                    }
                    if json_out:
                        print(json.dumps(payload, ensure_ascii=False))
                    else:
                        print("update JSON 根对象必须为 object", file=sys.stderr)
                    return 2
                tpl_r = str(
                    getattr(args, "session_template", ".cai/gateway/sessions/tg-{chat_id}-{user_id}.json")
                    or ".cai/gateway/sessions/tg-{chat_id}-{user_id}.json",
                ).strip()
                if bool(getattr(args, "create_missing", False)) and not tpl_r:
                    print("session-template 不能为空", file=sys.stderr)
                    return 2
                t_gru = time.perf_counter()
                payload = _resolve_gateway_session_from_update(
                    root=root,
                    map_path=map_path,
                    update_obj=update_obj,
                    create_missing=bool(getattr(args, "create_missing", False)),
                    session_template=tpl_r,
                )
                gru_ms = (time.perf_counter() - t_gru) * 1000.0
                row = payload.get("binding") if isinstance(payload.get("binding"), dict) else None
                created = bool(payload.get("created"))
                chat_id = str(payload.get("chat_id") or "").strip()
                user_id = str(payload.get("user_id") or "").strip()
                err_r = str(payload.get("error") or "")
                _maybe_metrics_cli(
                    module="gateway",
                    event="gateway.telegram.resolve_update",
                    latency_ms=gru_ms,
                    tokens=1 if row else 0,
                    success=(not err_r and bool(row)),
                )
                if json_out:
                    print(json.dumps(payload, ensure_ascii=False))
                elif err_r == "not_allowed":
                    print(payload.get("message") or "not_allowed", file=sys.stderr)
                elif row:
                    print(
                        f"resolved chat_id={chat_id} user_id={user_id} "
                        f"session_file={row.get('session_file')} created={created}",
                    )
                else:
                    print(f"mapping_not_found chat_id={chat_id} user_id={user_id}")
                if err_r == "not_allowed":
                    return 2
                return 0 if row else 2
            if act == "serve-webhook":
                host = str(getattr(args, "host", "127.0.0.1") or "127.0.0.1")
                port = int(getattr(args, "port", 18765))
                max_events = int(getattr(args, "max_events", 0))
                create_missing = bool(getattr(args, "create_missing", False))
                session_template = str(
                    getattr(args, "session_template", ".cai/gateway/sessions/tg-{chat_id}-{user_id}.json")
                    or ".cai/gateway/sessions/tg-{chat_id}-{user_id}.json",
                )
                log_path = _resolve_schedule_path(
                    root,
                    getattr(args, "log_file", None),
                    ".cai/gateway/telegram-webhook-events.jsonl",
                )
                tok_arg = getattr(args, "telegram_bot_token", None)
                tok_cli = str(tok_arg).strip() if tok_arg else ""
                tok_env = str(os.environ.get("CAI_TELEGRAM_BOT_TOKEN") or "").strip()
                tok = tok_cli or tok_env or None
                t_gws = time.perf_counter()
                payload = _run_gateway_telegram_webhook_server(
                    root=root,
                    host=host,
                    port=port,
                    map_path=map_path,
                    session_template=session_template,
                    create_missing=create_missing,
                    log_file=log_path,
                    max_requests=max_events,
                    execute_on_update=bool(getattr(args, "execute_on_update", False)),
                    goal_template=str(
                        getattr(args, "goal_template", "用户({user_id})在 chat({chat_id}) 发送消息：{text}")
                        or "用户({user_id})在 chat({chat_id}) 发送消息：{text}",
                    ),
                    reply_on_execution=bool(getattr(args, "reply_on_execution", False)),
                    telegram_bot_token=tok,
                    reply_template=str(
                        getattr(args, "reply_template", "执行完成 ok={ok}\n{answer}")
                        or "执行完成 ok={ok}\n{answer}",
                    ),
                    reply_on_deny=bool(getattr(args, "reply_on_deny", False)),
                    deny_message=str(
                        getattr(args, "deny_message", "此 CAI Agent Bot 未授权本对话。")
                        or "此 CAI Agent Bot 未授权本对话。",
                    ),
                )
                out = {
                    "schema_version": "gateway_telegram_map_v1",
                    "action": "serve-webhook",
                    "ok": bool(payload.get("ok")),
                    "host": payload.get("host"),
                    "port": payload.get("port"),
                    "path": payload.get("path"),
                    "events_handled": payload.get("handled_requests"),
                    "events_ok": payload.get("handled_requests"),
                    "map_file": payload.get("map_file"),
                    "log_file": payload.get("log_file"),
                    "create_missing": payload.get("create_missing"),
                }
                handled_n = int(payload.get("handled_requests") or out.get("events_handled") or 0)
                _maybe_metrics_cli(
                    module="gateway",
                    event="gateway.telegram.serve_webhook",
                    latency_ms=(time.perf_counter() - t_gws) * 1000.0,
                    tokens=handled_n,
                    success=bool(payload.get("ok")),
                )
                if bool(getattr(args, "json_output", False)):
                    print(json.dumps(out, ensure_ascii=False))
                else:
                    print(
                        f"gateway webhook stopped host={host} port={port} "
                        f"handled={out.get('events_handled')} log={out.get('log_file')}",
                    )
                return 0
        # ---- Discord Gateway（§24 补齐）----
        _gw_act = str(getattr(args, "gateway_action", "") or "").strip()
        if _gw_act == "discord":
            from cai_agent.gateway_discord import (
                discord_allow_add, discord_allow_list, discord_allow_rm,
                discord_bind, discord_gateway_health, discord_get_binding,
                discord_list_application_commands, discord_list_bindings,
                discord_register_application_commands, discord_unbind,
                serve_discord_polling,
            )
            dc_ws_raw = getattr(args, "workspace", None)
            dc_root = Path(os.path.abspath(dc_ws_raw)).resolve() if dc_ws_raw else Path.cwd().resolve()
            dc_act = str(getattr(args, "gateway_discord_action", "") or "").strip()
            json_out_dc = bool(getattr(args, "json_output", False))
            exit_dc = 0
            r: dict[str, Any] = {}
            if dc_act == "bind":
                r = discord_bind(
                    dc_root,
                    args.channel_id,
                    args.session_file,
                    guild_id=getattr(args, "discord_bind_guild_id", None),
                    label=getattr(args, "discord_bind_label", None),
                )
            elif dc_act == "unbind":
                r = discord_unbind(dc_root, args.channel_id)
            elif dc_act == "get":
                r = discord_get_binding(dc_root, args.channel_id)
            elif dc_act == "list":
                r = discord_list_bindings(dc_root)
            elif dc_act == "health":
                bot_tok_h = str(
                    getattr(args, "discord_bot_token", None) or os.environ.get("CAI_DISCORD_BOT_TOKEN", "") or "",
                )
                r = discord_gateway_health(dc_root, bot_token=bot_tok_h or None)
                tc = r.get("token_check") if isinstance(r.get("token_check"), dict) else {}
                if tc.get("performed") and tc.get("ok") is False:
                    exit_dc = 2
            elif dc_act == "register-commands":
                bot_tok_rc = str(
                    getattr(args, "discord_bot_token", None) or os.environ.get("CAI_DISCORD_BOT_TOKEN", "") or "",
                )
                if not bot_tok_rc:
                    print(
                        "Discord Bot Token 必须通过 --bot-token 或 CAI_DISCORD_BOT_TOKEN 提供",
                        file=sys.stderr,
                    )
                    return 2
                gid_raw = getattr(args, "discord_guild_id", None)
                gid = str(gid_raw).strip() if gid_raw else None
                r = discord_register_application_commands(
                    bot_tok_rc,
                    guild_id=gid,
                    dry_run=bool(getattr(args, "discord_dry_run", False)),
                )
                if not r.get("ok"):
                    exit_dc = 2
            elif dc_act == "list-commands":
                bot_tok_lc = str(
                    getattr(args, "discord_bot_token", None) or os.environ.get("CAI_DISCORD_BOT_TOKEN", "") or "",
                )
                if not bot_tok_lc:
                    print(
                        "Discord Bot Token 必须通过 --bot-token 或 CAI_DISCORD_BOT_TOKEN 提供",
                        file=sys.stderr,
                    )
                    return 2
                gid_raw2 = getattr(args, "discord_guild_id", None)
                gid2 = str(gid_raw2).strip() if gid_raw2 else None
                r = discord_list_application_commands(bot_tok_lc, guild_id=gid2)
                if not r.get("ok"):
                    exit_dc = 2
            elif dc_act == "allow":
                al_act = str(getattr(args, "dc_allow_action", "") or "")
                if al_act == "add":
                    r = discord_allow_add(dc_root, args.channel_id)
                elif al_act == "rm":
                    r = discord_allow_rm(dc_root, args.channel_id)
                else:
                    r = discord_allow_list(dc_root)
            elif dc_act == "serve-polling":
                bot_tok = str(getattr(args, "discord_bot_token", None) or os.environ.get("CAI_DISCORD_BOT_TOKEN", "") or "")
                if not bot_tok:
                    print("Discord Bot Token 必须通过 --bot-token 或 CAI_DISCORD_BOT_TOKEN 提供", file=sys.stderr)
                    return 2
                if not json_out_dc:
                    print(f"Discord Bot Polling 服务启动中（间隔 {getattr(args,'poll_interval',2.0)}s）— Ctrl+C 停止")
                r = serve_discord_polling(
                    root=dc_root,
                    bot_token=bot_tok,
                    poll_interval=float(getattr(args, "poll_interval", 2.0)),
                    max_events=int(getattr(args, "max_events", 0)),
                    execute_on_message=bool(getattr(args, "execute_on_message", False)),
                    reply_on_execution=bool(getattr(args, "reply_on_execution", False)),
                    log_file=getattr(args, "log_file", None),
                )
            else:
                print(f"unknown discord action: {dc_act}", file=sys.stderr)
                return 2
            if json_out_dc:
                print(json.dumps(r, ensure_ascii=False))
            elif dc_act == "health":
                tc2 = r.get("token_check") if isinstance(r.get("token_check"), dict) else {}
                print(
                    f"Discord health: bindings={r.get('bindings_count')} "
                    f"allowlist={r.get('allowlist_enabled')} "
                    f"token_checked={tc2.get('performed')} token_ok={tc2.get('ok')}",
                )
            elif dc_act == "register-commands":
                print(
                    f"register-commands ok={r.get('ok')} dry_run={r.get('dry_run')} "
                    f"registered={r.get('registered')} n_commands={len(r.get('commands') or [])}",
                )
            elif dc_act == "list-commands":
                cmds = r.get("commands") or []
                print(f"list-commands ok={r.get('ok')} n={len(cmds)} guild_id={r.get('guild_id')!r}")
            elif dc_act != "serve-polling":
                print(" ".join(f"{k}={v}" for k, v in r.items() if k != "bindings"))
            return exit_dc

        # ---- Slack Gateway（§24 补齐）----
        if _gw_act == "slack":
            from cai_agent.gateway_slack import (
                slack_allow_add, slack_allow_list, slack_allow_rm,
                slack_bind, slack_get_binding, slack_list_bindings,
                slack_gateway_health, slack_unbind, serve_slack_webhook,
            )
            sl_ws_raw = getattr(args, "workspace", None)
            sl_root = Path(os.path.abspath(sl_ws_raw)).resolve() if sl_ws_raw else Path.cwd().resolve()
            sl_act = str(getattr(args, "gateway_slack_action", "") or "").strip()
            json_out_sl = bool(getattr(args, "json_output", False))
            if sl_act == "bind":
                r = slack_bind(
                    sl_root,
                    args.channel_id,
                    args.session_file,
                    team_id=getattr(args, "team_id", None),
                    label=getattr(args, "label", None),
                )
            elif sl_act == "unbind":
                r = slack_unbind(sl_root, args.channel_id)
            elif sl_act == "get":
                r = slack_get_binding(sl_root, args.channel_id)
            elif sl_act == "list":
                r = slack_list_bindings(sl_root)
            elif sl_act == "health":
                bot_tok_sl = str(getattr(args, "slack_bot_token", None) or os.environ.get("CAI_SLACK_BOT_TOKEN", "") or "")
                signing_sec = str(getattr(args, "slack_signing_secret", None) or os.environ.get("CAI_SLACK_SIGNING_SECRET", "") or "")
                r = slack_gateway_health(
                    sl_root,
                    bot_token=bot_tok_sl or None,
                    signing_secret=signing_sec or None,
                )
            elif sl_act == "allow":
                al_act = str(getattr(args, "sl_allow_action", "") or "")
                if al_act == "add":
                    r = slack_allow_add(sl_root, args.channel_id)
                elif al_act == "rm":
                    r = slack_allow_rm(sl_root, args.channel_id)
                else:
                    r = slack_allow_list(sl_root)
            elif sl_act == "serve-webhook":
                bot_tok_sl = str(getattr(args, "slack_bot_token", None) or os.environ.get("CAI_SLACK_BOT_TOKEN", "") or "")
                signing_sec = str(getattr(args, "slack_signing_secret", None) or os.environ.get("CAI_SLACK_SIGNING_SECRET", "") or "")
                if not bot_tok_sl:
                    print("Slack Bot Token 必须通过 --bot-token 或 CAI_SLACK_BOT_TOKEN 提供", file=sys.stderr)
                    return 2
                sl_host = str(getattr(args, "host", "0.0.0.0") or "0.0.0.0")
                sl_port = int(getattr(args, "port", 7892))
                if not json_out_sl:
                    print(f"Slack Webhook 服务启动中 http://{sl_host}:{sl_port} — Ctrl+C 停止")
                r = serve_slack_webhook(
                    root=sl_root,
                    bot_token=bot_tok_sl,
                    signing_secret=signing_sec,
                    host=sl_host,
                    port=sl_port,
                    execute_on_event=bool(getattr(args, "execute_on_event", False)),
                    execute_on_slash=bool(getattr(args, "execute_on_slash", False)),
                    reply_on_execution=bool(getattr(args, "reply_on_execution", False)),
                    log_file=getattr(args, "log_file", None),
                    max_events=int(getattr(args, "max_events", 0)),
                )
            else:
                print(f"unknown slack action: {sl_act}", file=sys.stderr)
                return 2
            if json_out_sl:
                print(json.dumps(r, ensure_ascii=False))
            else:
                if sl_act == "health":
                    tc3 = r.get("token_check") if isinstance(r.get("token_check"), dict) else {}
                    print(
                        f"Slack health: bindings={r.get('bindings_count')} "
                        f"allowlist={r.get('allowlist_enabled')} "
                        f"signing_secret={r.get('signing_secret_configured')} "
                        f"token_checked={tc3.get('performed')} token_ok={tc3.get('ok')}",
                    )
                else:
                    print(" ".join(f"{k}={v}" for k, v in r.items() if k != "bindings"))
            return 0

        # ---- Microsoft Teams Gateway（HM-03d）----
        if _gw_act == "teams":
            from cai_agent.gateway_teams import (
                build_teams_manifest_payload,
                serve_teams_webhook,
                teams_allow_add,
                teams_allow_list,
                teams_allow_rm,
                teams_bind,
                teams_gateway_health,
                teams_get_binding,
                teams_list_bindings,
                teams_unbind,
            )

            tm_ws_raw = getattr(args, "workspace", None)
            tm_root = Path(os.path.abspath(tm_ws_raw)).resolve() if tm_ws_raw else Path.cwd().resolve()
            tm_act = str(getattr(args, "gateway_teams_action", "") or "").strip()
            json_out_tm = bool(getattr(args, "json_output", False))
            if tm_act == "bind":
                r = teams_bind(
                    tm_root,
                    args.conversation_id,
                    args.session_file,
                    tenant_id=getattr(args, "teams_tenant_id", None),
                    service_url=getattr(args, "teams_service_url", None),
                    channel_id=getattr(args, "teams_channel_id", None),
                    label=getattr(args, "label", None),
                )
            elif tm_act == "unbind":
                r = teams_unbind(tm_root, args.conversation_id)
            elif tm_act == "get":
                r = teams_get_binding(tm_root, args.conversation_id)
            elif tm_act == "list":
                r = teams_list_bindings(tm_root)
            elif tm_act == "health":
                app_id_tm = str(getattr(args, "teams_app_id", None) or os.environ.get("CAI_TEAMS_APP_ID", "") or "")
                app_pw_tm = str(
                    getattr(args, "teams_app_password", None) or os.environ.get("CAI_TEAMS_APP_PASSWORD", "") or "",
                )
                tenant_tm = str(getattr(args, "teams_tenant_id", None) or os.environ.get("CAI_TEAMS_TENANT_ID", "") or "")
                secret_tm = str(
                    getattr(args, "teams_webhook_secret", None) or os.environ.get("CAI_TEAMS_WEBHOOK_SECRET", "") or "",
                )
                r = teams_gateway_health(
                    tm_root,
                    app_id=app_id_tm or None,
                    app_password=app_pw_tm or None,
                    tenant_id=tenant_tm or None,
                    webhook_secret=secret_tm or None,
                )
            elif tm_act == "manifest":
                r = build_teams_manifest_payload(
                    app_id=str(getattr(args, "teams_app_id", "") or ""),
                    bot_id=getattr(args, "teams_bot_id", None),
                    name=str(getattr(args, "teams_manifest_name", "CAI Agent") or "CAI Agent"),
                    valid_domains=list(getattr(args, "teams_valid_domains", []) or []),
                )
                if not r.get("ok"):
                    return 2
            elif tm_act == "allow":
                al_act = str(getattr(args, "teams_allow_action", "") or "")
                if al_act == "add":
                    r = teams_allow_add(tm_root, args.conversation_id)
                elif al_act == "rm":
                    r = teams_allow_rm(tm_root, args.conversation_id)
                else:
                    r = teams_allow_list(tm_root)
            elif tm_act == "serve-webhook":
                secret_tm = str(
                    getattr(args, "teams_webhook_secret", None) or os.environ.get("CAI_TEAMS_WEBHOOK_SECRET", "") or "",
                )
                tm_host = str(getattr(args, "host", "0.0.0.0") or "0.0.0.0")
                tm_port = int(getattr(args, "port", 7893))
                if not json_out_tm:
                    print(f"Teams Webhook 服务启动中 http://{tm_host}:{tm_port} — Ctrl+C 停止")
                r = serve_teams_webhook(
                    root=tm_root,
                    webhook_secret=secret_tm,
                    host=tm_host,
                    port=tm_port,
                    execute_on_message=bool(getattr(args, "execute_on_message", False)),
                    log_file=getattr(args, "log_file", None),
                    max_events=int(getattr(args, "max_events", 0)),
                )
            else:
                print(f"unknown teams action: {tm_act}", file=sys.stderr)
                return 2
            if json_out_tm:
                print(json.dumps(r, ensure_ascii=False))
            else:
                if tm_act == "health":
                    tc4 = r.get("token_check") if isinstance(r.get("token_check"), dict) else {}
                    print(
                        f"Teams health: bindings={r.get('bindings_count')} "
                        f"allowlist={r.get('allowlist_enabled')} "
                        f"app_id={r.get('app_id_configured')} "
                        f"tenant_id={r.get('tenant_id_configured')} "
                        f"secret={r.get('webhook_secret_configured')} "
                        f"token_checked={tc4.get('performed')}",
                    )
                elif tm_act == "manifest":
                    print(json.dumps(r.get("manifest") or {}, ensure_ascii=False, indent=2))
                elif tm_act != "serve-webhook":
                    print(" ".join(f"{k}={v}" for k, v in r.items() if k != "bindings"))
            return 0

        return 2

    if args.command == "workflow":
        # --- workflow --templates（§23 补齐）---
        if bool(getattr(args, "list_templates", False)) or bool(getattr(args, "template_id", None)):
            json_out = bool(getattr(args, "json_output", False))
            tpl_id = getattr(args, "template_id", None)
            goal_str = str(getattr(args, "goal", "") or "")
            if tpl_id:
                try:
                    tpl = get_workflow_template(tpl_id, goal=goal_str)
                except KeyError as e:
                    print(str(e), file=sys.stderr)
                    return 2
                if json_out:
                    print(json.dumps(tpl, ensure_ascii=False, indent=2))
                else:
                    print(f"template={tpl_id}")
                    for i, s in enumerate(tpl.get("steps") or [], 1):
                        print(f"  step {i}: [{s.get('role','default')}] {s.get('name')} — {s.get('goal','')[:80]}")
            else:
                templates = list_workflow_templates()
                if json_out:
                    print(json.dumps({"schema_version": "workflow_templates_v1", "templates": templates}, ensure_ascii=False))
                else:
                    for t in templates:
                        print(f"  {t['id']}: {t['description']}")
            return 0
        # --- 正常 workflow run ---
        if not getattr(args, "file", None):
            print("用法: cai-agent workflow <file.json> 或 cai-agent workflow templates", file=sys.stderr)
            return 2
        try:
            settings = Settings.from_env(
                config_path=args.config,
                workspace_hint=_settings_workspace_hint(args),
            )
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            return 2
        if args.model:
            settings = replace(settings, model=str(args.model).strip())
        if args.workspace:
            settings = replace(
                settings,
                workspace=os.path.abspath(args.workspace),
            )
        wf_abs = str(Path(args.file).expanduser().resolve())
        wf_hook_payload = {"workflow_file": wf_abs}
        _print_hook_status(
            settings,
            event="workflow_start",
            json_output=bool(args.json_output),
            hook_payload=wf_hook_payload,
        )
        t_wf = time.perf_counter()
        try:
            result = run_workflow(settings, args.file)
        except Exception as e:
            print(f"运行 workflow 失败: {e}", file=sys.stderr)
            _print_hook_status(
                settings,
                event="workflow_end",
                json_output=bool(args.json_output),
                hook_payload=wf_hook_payload,
            )
            _maybe_metrics_cli(
                module="workflow",
                event="workflow.run",
                latency_ms=(time.perf_counter() - t_wf) * 1000.0,
                tokens=0,
                success=False,
            )
            return 2
        try:
            save_last_workflow_snapshot(
                Path.cwd(),
                result,
                workflow_file=wf_abs,
            )
        except Exception:
            pass
        end_payload = {
            **wf_hook_payload,
            "task": result.get("task"),
            "summary": result.get("summary"),
        }
        _print_hook_status(
            settings,
            event="workflow_end",
            json_output=bool(args.json_output),
            hook_payload=end_payload,
        )
        if args.json_output:
            print(json.dumps(result, ensure_ascii=False))
        else:
            steps = result.get("steps") or []
            summary = result.get("summary") or {}
            print(f"steps_count={summary.get('steps_count', len(steps))}")
            print(f"elapsed_ms_total={summary.get('elapsed_ms_total', 0)}")
            print(f"elapsed_ms_avg={summary.get('elapsed_ms_avg', 0)}")
            print(f"tool_calls_total={summary.get('tool_calls_total', 0)}")
            print(f"tool_errors_total={summary.get('tool_errors_total', 0)}")
            qg = result.get("quality_gate") if isinstance(result.get("quality_gate"), dict) else {}
            if qg.get("requested"):
                print(
                    "quality_gate "
                    f"ran={qg.get('ran')} "
                    f"ok={qg.get('ok')} "
                    f"failed_count={qg.get('failed_count')} "
                    f"skip_reason={qg.get('skip_reason')}",
                )
            for step in steps:
                name = step.get("name") or ""
                goal = (step.get("goal") or "")[:80]
                elapsed_ms = step.get("elapsed_ms")
                tools = step.get("tool_calls_count")
                errors = step.get("error_count")
                print(
                    f"- [{name}] elapsed_ms={elapsed_ms} "
                    f"tool_calls={tools} errors={errors} goal={goal!r}"
                )
        rc_wf = 0
        if bool(getattr(args, "fail_on_step_errors", False)):
            tk = result.get("task") if isinstance(result.get("task"), dict) else {}
            if str(tk.get("status") or "").strip().lower() == "failed":
                rc_wf = 2
            sm = result.get("summary") if isinstance(result.get("summary"), dict) else {}
            if rc_wf == 0 and int(sm.get("tool_errors_total") or 0) > 0:
                rc_wf = 2
            if rc_wf == 0:
                for st in result.get("steps") or []:
                    if isinstance(st, dict) and int(st.get("error_count") or 0) > 0:
                        rc_wf = 2
                        break
        qg = result.get("quality_gate") if isinstance(result.get("quality_gate"), dict) else {}
        if rc_wf == 0 and bool(qg.get("requested")) and bool(qg.get("ran")) and qg.get("ok") is False:
            rc_wf = 2
        wf_tk = result.get("task") if isinstance(result.get("task"), dict) else {}
        wf_sm = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        wf_done = str(wf_tk.get("status") or "").strip().lower() == "completed"
        _maybe_metrics_cli(
            module="workflow",
            event="workflow.run",
            latency_ms=(time.perf_counter() - t_wf) * 1000.0,
            tokens=int(wf_sm.get("budget_used") or 0),
            success=(wf_done and rc_wf == 0),
        )
        return rc_wf

    if args.command == "release-ga":
        t_rg = time.perf_counter()
        payload = _run_release_ga_gate(
            cwd=os.getcwd(),
            max_failure_rate=float(getattr(args, "max_failure_rate", 0.20)),
            max_tokens=(int(args.max_tokens) if getattr(args, "max_tokens", None) is not None else None),
            run_quality_gate_check=not bool(getattr(args, "no_quality_gate", False)),
            run_security_scan_check=bool(getattr(args, "with_security_scan", False)),
            include_lint=False,
            include_typecheck=False,
            with_doctor=bool(getattr(args, "with_doctor", False)),
            with_memory_nudge=bool(getattr(args, "with_memory_nudge", False)),
            memory_nudge_fail_on=str(getattr(args, "memory_max_severity", "high") or "high"),
            with_memory_state=bool(getattr(args, "with_memory_state", False)),
            memory_state_max_stale_rate=float(getattr(args, "memory_max_stale_ratio", 0.50)),
            memory_state_max_expired_rate=float(getattr(args, "memory_max_expired_ratio", 0.10)),
            memory_state_stale_days=int(getattr(args, "memory_state_stale_days", 30)),
            memory_state_stale_confidence=float(getattr(args, "memory_state_stale_confidence", 0.4)),
            with_memory_policy=bool(getattr(args, "with_memory_policy", False)),
        )
        if bool(getattr(args, "json_output", False)):
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(
                f"[release-ga] state={payload.get('state')} "
                f"checks_passed={payload.get('checks_passed')} "
                f"failure_rate={payload.get('failure_rate')} "
                f"total_tokens={payload.get('total_tokens')}",
            )
            failures = payload.get("failed_check_details") or []
            if failures:
                print("[release-ga] failed checks:")
                for x in failures:
                    if isinstance(x, dict):
                        print(f"- {x.get('name')}: {x.get('reason')}")
            rel = payload.get("release_runbook") if isinstance(payload.get("release_runbook"), dict) else {}
            print("[release-ga] runbook:")
            print("- cai-agent doctor --json")
            print("- cai-agent release-changelog --json --semantic")
            print("- python scripts/smoke_new_features.py")
            targets = rel.get("writeback_targets") if isinstance(rel.get("writeback_targets"), list) else []
            if targets:
                print("[release-ga] writeback targets:")
                for row in targets:
                    if isinstance(row, dict):
                        print(f"- {row.get('path')}")
            if isinstance(rel.get("feedback"), dict):
                print(
                    f"- feedback total={int((rel.get('feedback') or {}).get('total', 0) or 0)} "
                    "-> cai-agent feedback export --dest dist/feedback-export.jsonl --json",
                )
        rc_rg = 0 if str(payload.get("state")) == "pass" else 2
        chk = payload.get("checks") if isinstance(payload.get("checks"), list) else []
        _maybe_metrics_cli(
            module="release_ga",
            event="release_ga.gate",
            latency_ms=(time.perf_counter() - t_rg) * 1000.0,
            tokens=len(chk),
            success=(rc_rg == 0),
        )
        return rc_rg

    if args.command in ("run", "continue", "command", "agent", "fix-build"):
        try:
            settings = Settings.from_env(
                config_path=args.config,
                workspace_hint=_settings_workspace_hint(args),
            )
        except FileNotFoundError as e:
            if bool(getattr(args, "json_output", False)):
                t0 = new_task(str(args.command))
                t0.status = "failed"
                t0.error = "config_not_found"
                t0.ended_at = time.time()
                print(
                    json.dumps(
                        _run_continue_json_fail_payload(
                            command=str(args.command),
                            error="config_not_found",
                            message=str(e),
                            task=t0,
                            settings=None,
                        ),
                        ensure_ascii=False,
                    ),
                )
            else:
                print(str(e), file=sys.stderr)
            return 2
        if args.model:
            settings = replace(settings, model=str(args.model).strip())
        if args.workspace:
            settings = replace(
                settings,
                workspace=os.path.abspath(args.workspace),
            )
        goal = " ".join(args.goal).strip()
        if not goal:
            if bool(getattr(args, "json_output", False)):
                tg = new_task(str(args.command))
                tg.status = "failed"
                tg.error = "goal_empty"
                tg.ended_at = time.time()
                print(
                    json.dumps(
                        _run_continue_json_fail_payload(
                            command=str(args.command),
                            error="goal_empty",
                            message="goal 不能为空",
                            task=tg,
                            settings=settings,
                        ),
                        ensure_ascii=False,
                    ),
                )
            else:
                print("goal 不能为空", file=sys.stderr)
            return 2
        if args.command in ("command", "fix-build"):
            if args.command == "fix-build":
                cmd_name = "fix-build"
            else:
                cmd_name = str(args.name).strip().lstrip("/")
            cmd_text = load_command_text(settings, cmd_name)
            if not cmd_text:
                if bool(getattr(args, "json_output", False)):
                    tc = new_task(str(args.command))
                    tc.status = "failed"
                    tc.error = "command_not_found"
                    tc.ended_at = time.time()
                    print(
                        json.dumps(
                            _run_continue_json_fail_payload(
                                command=str(args.command),
                                error="command_not_found",
                                message=f"命令模板不存在: /{cmd_name}",
                                task=tc,
                                settings=settings,
                            ),
                            ensure_ascii=False,
                        ),
                    )
                else:
                    print(f"命令模板不存在: /{cmd_name}", file=sys.stderr)
                return 2
            skill_texts = load_related_skill_texts(settings, cmd_name, goal_hint=goal[:500])
            skill_block = ""
            if skill_texts:
                skill_block = (
                    "\n\n下面是自动匹配到的相关技能，请在执行中参考：\n\n"
                    + "\n\n---\n\n".join(skill_texts)
                )
            goal = (
                f"你当前正在执行命令 /{cmd_name}。\n"
                "请严格参考下方命令模板完成任务：\n\n"
                f"{cmd_text}{skill_block}\n\n"
                f"用户原始目标：{goal}"
            )
        if args.command == "agent":
            agent_name = str(args.name).strip()
            agent_text = load_agent_text(settings, agent_name)
            if not agent_text:
                if bool(getattr(args, "json_output", False)):
                    ta = new_task(str(args.command))
                    ta.status = "failed"
                    ta.error = "agent_not_found"
                    ta.ended_at = time.time()
                    print(
                        json.dumps(
                            _run_continue_json_fail_payload(
                                command=str(args.command),
                                error="agent_not_found",
                                message=f"子代理模板不存在: {agent_name}",
                                task=ta,
                                settings=settings,
                            ),
                            ensure_ascii=False,
                        ),
                    )
                else:
                    print(f"子代理模板不存在: {agent_name}", file=sys.stderr)
                return 2
            skill_texts = load_related_skill_texts(settings, agent_name, goal_hint=goal[:500])
            skill_block = ""
            if skill_texts:
                skill_block = (
                    "\n\n下面是自动匹配到的相关技能，请在执行中参考：\n\n"
                    + "\n\n---\n\n".join(skill_texts)
                )
            goal = (
                f"你当前正在扮演子代理 {agent_name}。\n"
                "请严格参考下方子代理模板完成任务：\n\n"
                f"{agent_text}{skill_block}\n\n"
                f"用户原始目标：{goal}"
            )

        pf = getattr(args, "plan_file", None)
        if pf:
            try:
                goal = _inject_plan_file(goal, str(pf))
            except OSError as e:
                if bool(getattr(args, "json_output", False)):
                    tp = new_task(str(args.command))
                    tp.status = "failed"
                    tp.error = "plan_file_error"
                    tp.ended_at = time.time()
                    print(
                        json.dumps(
                            _run_continue_json_fail_payload(
                                command=str(args.command),
                                error="plan_file_error",
                                message=f"读取计划文件失败: {e}",
                                task=tp,
                                settings=settings,
                            ),
                            ensure_ascii=False,
                        ),
                    )
                else:
                    print(f"读取计划文件失败: {e}", file=sys.stderr)
                return 2

        auto_on = bool(getattr(args, "auto_approve", False))
        prev_auto = os.environ.get("CAI_AUTO_APPROVE")
        if auto_on:
            os.environ["CAI_AUTO_APPROVE"] = "1"
        try:
            reset_usage_counters()
            reset_global_ring()
            clear_session_skill_touches()
            task = new_task(args.command)
            task.status = "running"
            _print_hook_status(
                settings,
                event="session_start",
                json_output=bool(args.json_output),
            )
            stop_requested = False
            last_sigint_at = 0.0
            prev_sigint_handler: Any = None

            def _on_sigint(_signum: int, _frame: Any) -> None:
                nonlocal stop_requested, last_sigint_at
                now = time.monotonic()
                # Two-stage stop:
                # 1st Ctrl+C => graceful stop request.
                # 2nd Ctrl+C within 2s => hard interrupt.
                if stop_requested and (now - last_sigint_at) <= 2.0:
                    raise KeyboardInterrupt
                stop_requested = True
                last_sigint_at = now
                print(
                    "已请求停止当前运行；再次按 Ctrl+C 可强制中断。",
                    file=sys.stderr,
                )

            if threading.current_thread() is threading.main_thread():
                prev_sigint_handler = signal.getsignal(signal.SIGINT)
                signal.signal(signal.SIGINT, _on_sigint)

            app = build_app(settings, should_stop=lambda: stop_requested)
            if args.command == "run":
                load_session_path = args.load_session
            elif args.command == "continue":
                load_session_path = args.session
            else:
                load_session_path = None
            if load_session_path:
                try:
                    sess = load_session(load_session_path)
                except Exception as e:
                    if bool(getattr(args, "json_output", False)):
                        print(
                            json.dumps(
                                _run_continue_json_fail_payload(
                                    command=str(args.command),
                                    error="load_session_failed",
                                    message=f"读取会话失败: {e}",
                                    task=task,
                                    settings=settings,
                                ),
                                ensure_ascii=False,
                            ),
                        )
                    else:
                        print(f"读取会话失败: {e}", file=sys.stderr)
                    return 2
                messages = sess.get("messages")
                if not isinstance(messages, list) or not messages:
                    if bool(getattr(args, "json_output", False)):
                        print(
                            json.dumps(
                                _run_continue_json_fail_payload(
                                    command=str(args.command),
                                    error="invalid_session",
                                    message="会话文件不合法：messages 必须是非空数组",
                                    task=task,
                                    settings=settings,
                                ),
                                ensure_ascii=False,
                            ),
                        )
                    else:
                        print("会话文件不合法：messages 必须是非空数组", file=sys.stderr)
                    return 2
                state = {
                    "messages": list(messages) + [{"role": "user", "content": goal}],
                    "iteration": 0,
                    "pending": None,
                    "finished": False,
                }
            else:
                state = initial_state(settings, goal)
            started = time.perf_counter()
            try:
                final = app.invoke(state)
            except KeyboardInterrupt:
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                task.ended_at = time.time()
                task.elapsed_ms = elapsed_ms
                task.status = "failed"
                task.error = "interrupted"
                if args.json_output:
                    intr_ev: list[dict[str, Any]] = [
                        {
                            "event": "run.started",
                            "command": str(getattr(args, "command", "run")),
                            "task_id": task.task_id,
                        },
                        {
                            "event": "run.interrupted",
                            "command": str(getattr(args, "command", "run")),
                            "task_id": task.task_id,
                        },
                    ]
                    payload = {
                        "run_schema_version": RUN_SCHEMA_VERSION,
                        "ok": False,
                        "error": "interrupted",
                        "message": "用户已手动停止",
                        "task_id": task.task_id,
                        "answer": "",
                        "iteration": None,
                        "finished": False,
                        "config": settings.config_loaded_from,
                        "workspace": settings.workspace,
                        "provider": settings.provider,
                        "model": settings.model,
                        "mcp_enabled": settings.mcp_enabled,
                        "elapsed_ms": elapsed_ms,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                        "tool_calls_count": 0,
                        "used_tools": [],
                        "last_tool": None,
                        "error_count": 0,
                        "task": task.to_dict(),
                        "post_gate": None,
                        "events": wrap_run_events(intr_ev),
                    }
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print("已手动停止（Ctrl+C）。", file=sys.stderr)
                return 130
            finally:
                if threading.current_thread() is threading.main_thread() and prev_sigint_handler is not None:
                    signal.signal(signal.SIGINT, prev_sigint_handler)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            task.ended_at = time.time()
            task.elapsed_ms = elapsed_ms

            if (
                not args.quiet
                and not args.json_output
                and final.get("messages")
            ):
                print("--- messages (last assistant) ---", file=sys.stderr)
                for m in final["messages"][-6:]:
                    role = m.get("role", "")
                    content = (m.get("content", "") or "")[:2000]
                    print(f"[{role}]\n{content}\n", file=sys.stderr)

            usage = get_usage_counters()
            task.status = "completed" if bool(final.get("finished")) else "failed"
            task.error = None if task.status == "completed" else "unfinished"
            gate_result = None
            if args.command == "fix-build" and not bool(getattr(args, "no_gate", False)):
                gate_result = run_quality_gate(
                    settings,
                    enable_compile=settings.quality_gate_compile,
                    enable_test=settings.quality_gate_test,
                    enable_lint=settings.quality_gate_lint,
                    enable_typecheck=settings.quality_gate_typecheck,
                    enable_security_scan=settings.quality_gate_security_scan,
                )
            msgs = final.get("messages") if isinstance(final.get("messages"), list) else []
            tool_calls_count, used_tools, last_tool, error_count = _collect_tool_stats(msgs)
            cmd = str(getattr(args, "command", "run"))
            run_events: list[dict[str, object]] = [
                {
                    "event": "run.started",
                    "command": cmd,
                    "task_id": task.task_id,
                },
                {
                    "event": "run.finished",
                    "command": cmd,
                    "task_id": task.task_id,
                    "finished": bool(final.get("finished")),
                    "status": task.status,
                },
            ]
            if args.json_output:
                payload = {
                    "run_schema_version": RUN_SCHEMA_VERSION,
                    "ok": str(task.status) == "completed",
                    "task_id": task.task_id,
                    "answer": (final.get("answer") or "").strip(),
                    "iteration": final.get("iteration"),
                    "finished": final.get("finished"),
                    "config": settings.config_loaded_from,
                    "workspace": settings.workspace,
                    "provider": settings.provider,
                    "model": settings.model,
                    "mcp_enabled": settings.mcp_enabled,
                    "elapsed_ms": elapsed_ms,
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                    "tool_calls_count": tool_calls_count,
                    "used_tools": used_tools,
                    "last_tool": last_tool,
                    "error_count": error_count,
                    "task": task.to_dict(),
                    "post_gate": gate_result,
                    "events": wrap_run_events(
                        [cast(dict[str, Any], x) for x in run_events],
                    ),
                    "progress_ring": build_progress_ring_summary(),
                }
                print(json.dumps(payload, ensure_ascii=False))
            else:
                print(final.get("answer", "").strip())
                if gate_result is not None:
                    print(
                        f"\n[fix-build] quality-gate ok={gate_result.get('ok')} failed_count={gate_result.get('failed_count')}",
                        file=sys.stderr,
                    )

            save_session_path = getattr(args, "save_session", None)
            if save_session_path:
                payload = {
                    "version": 2,
                    "run_schema_version": RUN_SCHEMA_VERSION,
                    "goal": goal,
                    "workspace": settings.workspace,
                    "config": settings.config_loaded_from,
                    "provider": settings.provider,
                    "model": settings.model,
                    "profile": settings.active_profile_id,
                    "active_profile_id": settings.active_profile_id,
                    "subagent_profile_id": settings.subagent_profile_id,
                    "planner_profile_id": settings.planner_profile_id,
                    "mcp_enabled": settings.mcp_enabled,
                    "elapsed_ms": elapsed_ms,
                    "total_tokens": usage.get("total_tokens", 0),
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                    "tool_calls_count": tool_calls_count,
                    "used_tools": used_tools,
                    "last_tool": last_tool,
                    "error_count": error_count,
                    "messages": final.get("messages") or [],
                    "answer": final.get("answer"),
                    "task": task.to_dict(),
                    "events": wrap_run_events(
                        [cast(dict[str, Any], x) for x in run_events],
                    ),
                    "post_gate": gate_result,
                }
                try:
                    save_session(str(save_session_path), payload)
                except Exception as e:
                    print(f"写入会话失败: {e}", file=sys.stderr)
                    return 2
            if args.command in ("run", "continue", "command", "agent", "fix-build"):
                _maybe_metrics_cli(
                    module=str(args.command),
                    event=f"{args.command}.invoke",
                    latency_ms=float(elapsed_ms),
                    tokens=int(usage.get("total_tokens", 0)),
                    success=(str(task.status) == "completed"),
                )
            _print_hook_status(
                settings,
                event="session_end",
                json_output=bool(args.json_output),
            )
            # 技能自进化钩子：若 CAI_SKILLS_AUTO_SUGGEST=1 且任务已完成，dry-run 落盘草稿
            if (
                str(task.status) == "completed"
                and os.environ.get("CAI_SKILLS_AUTO_SUGGEST", "").strip() in ("1", "true", "yes")
            ):
                _completed_goal = goal if isinstance(goal, str) else ""
                if _completed_goal.strip():
                    try:
                        from cai_agent.skills import build_skill_evolution_suggest as _bsev
                        _auto_sug = _bsev(
                            root=str(Path.cwd().resolve()),
                            goal=_completed_goal[:300],
                            write=True,
                        )
                        if not bool(args.json_output) and _auto_sug.get("written"):
                            print(
                                f"[skills auto] 已落盘进化草稿: {_auto_sug.get('suggested_path')}",
                                file=sys.stderr,
                            )
                    except Exception:
                        pass
            # 任务后自动提炼技能草稿（[skills.auto_extract] 或 CAI_SKILLS_AUTO_EXTRACT）
            if str(task.status) == "completed":
                _cg = goal if isinstance(goal, str) else ""
                if _cg.strip():
                    try:
                        from cai_agent.skills import (
                            auto_extract_skill_after_task as _aext,
                            resolve_auto_extract_for_runner as _arx,
                        )

                        _run_ax, _use_llm_ax = _arx(settings, goal=_cg)
                        if _run_ax:
                            _ev_lines = [f"- tool: {nm}" for nm in (used_tools or [])[:48]]
                            _ext = _aext(
                                root=str(Path.cwd().resolve()),
                                goal=_cg[:2000],
                                answer=str(final.get("answer") or "")[:12000],
                                write=True,
                                settings=settings,
                                use_llm=_use_llm_ax,
                                events_summary="\n".join(_ev_lines),
                            )
                            if not bool(args.json_output) and bool(_ext.get("written")):
                                print(
                                    f"[skills auto-extract] 已落盘: {_ext.get('suggested_path')} "
                                    f"schema={_ext.get('schema_version')}",
                                    file=sys.stderr,
                                )
                    except Exception:
                        pass
            # 本会话曾加载的技能：可选追加「历史改进」（CAI_SKILLS_AUTO_IMPROVE_APPLY 才真正写盘）
            if str(task.status) == "completed":
                try:
                    from cai_agent.skill_evolution import maybe_run_session_auto_improve_after_task as _mimp

                    _imp = _mimp(root=str(Path.cwd().resolve()))
                    if (
                        _imp
                        and not bool(args.json_output)
                        and (_imp.get("touched_skills") or [])
                    ):
                        print(
                            f"[skills auto-improve] skills={_imp.get('touched_skills')} "
                            f"apply={_imp.get('apply')}",
                            file=sys.stderr,
                        )
                except Exception:
                    pass
            return 0
        finally:
            if auto_on:
                if prev_auto is None:
                    os.environ.pop("CAI_AUTO_APPROVE", None)
                else:
                    os.environ["CAI_AUTO_APPROVE"] = prev_auto

    if args.command == "ui":
        from cai_agent.tui import run_tui

        t_ui = time.perf_counter()
        try:
            settings = Settings.from_env(
                config_path=args.config,
                workspace_hint=_settings_workspace_hint(args),
            )
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            _maybe_metrics_cli(
                module="ui",
                event="ui.tui",
                latency_ms=(time.perf_counter() - t_ui) * 1000.0,
                tokens=0,
                success=False,
            )
            return 2
        if args.model:
            settings = replace(settings, model=str(args.model).strip())
        if args.workspace:
            settings = replace(
                settings,
                workspace=os.path.abspath(args.workspace),
            )
        rc_ui = 0
        try:
            run_tui(settings)
        except Exception:
            rc_ui = 2
        finally:
            _maybe_metrics_cli(
                module="ui",
                event="ui.tui",
                latency_ms=(time.perf_counter() - t_ui) * 1000.0,
                tokens=0,
                success=(rc_ui == 0),
            )
        return rc_ui

    # S1-03: should not happen while subparsers stay aligned with dispatch below.
    cmd = getattr(args, "command", None)
    print(
        f"内部错误: CLI 未处理子命令 {cmd!r}（请报告并附带 cai-agent --version 输出）",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
