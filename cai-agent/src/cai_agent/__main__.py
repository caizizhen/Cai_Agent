from __future__ import annotations

import argparse
from collections import Counter
import json
import os
import signal
import sys

import threading
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from importlib import resources
from pathlib import Path
from typing import Any

from cai_agent import __version__
from cai_agent.agent_registry import list_agent_names, load_agent_text
from cai_agent.command_registry import list_command_names, load_command_text
from cai_agent.config import Settings
from cai_agent.doctor import run_doctor
from cai_agent.graph import build_app, initial_state
from cai_agent.board_state import build_board_payload, save_last_workflow_snapshot
from cai_agent.hook_runtime import enabled_hook_ids, run_project_hooks
from cai_agent.llm import get_usage_counters, reset_usage_counters
from cai_agent.llm_factory import chat_completion_by_role
from cai_agent.models import fetch_models, ping_profile
from cai_agent.profiles import (
    Profile,
    ProfilesError,
    add_profile,
    apply_preset,
    build_profile,
    edit_profile,
    profile_to_public_dict,
    remove_profile,
    write_models_to_toml,
)
from cai_agent.exporter import export_target
from cai_agent.memory import (
    export_memory_entries_bundle,
    extract_basic_instincts_from_session,
    extract_memory_entries_from_session,
    import_memory_entries_bundle,
    load_memory_entries,
    load_memory_entries_validated,
    prune_expired_memory_entries,
    save_instincts,
    search_memory_entries,
    sort_memory_rows,
)
from cai_agent.plugin_registry import list_plugin_surface
from cai_agent.quality_gate import run_quality_gate
from cai_agent.rules import load_rule_text
from cai_agent.security_scan import run_security_scan
from cai_agent.schedule import (
    add_schedule_task,
    compute_due_tasks,
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
from cai_agent.skill_registry import load_related_skill_texts
from cai_agent.task_state import new_task
from cai_agent.tools import dispatch, tools_spec_markdown
from cai_agent.workflow import run_workflow


def _session_file_json_extra(sess: dict[str, Any]) -> dict[str, Any]:
    """从已解析的会话 JSON 提取稳定字段（供 `sessions --json` 等使用）。"""
    ev = sess.get("events")
    events_count = len(ev) if isinstance(ev, list) else 0
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
    files = list_session_files(cwd=cwd, pattern=pattern, limit=limit)
    window_files = [p for p in files if datetime.fromtimestamp(p.stat().st_mtime, UTC) >= since]

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
        "schema_version": "1.0",
        "generated_at": now.isoformat(),
        "window": {
            "days": max(days, 1),
            "since": since.isoformat(),
            "pattern": pattern,
            "limit": limit,
        },
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
    severity = "low"
    if len(recent_sessions) >= 8 and not entries:
        severity = "high"
        actions.append(
            "近期会话较多但暂无结构化记忆，建议立即执行 `cai-agent memory extract --limit 20`",
        )
    elif len(recent_sessions) >= 4 and len(entries) < 3:
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

    return {
        "schema_version": "1.0",
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
        "actions": actions,
    }


def _build_memory_nudge_report_payload(
    *,
    cwd: str,
    history_file: str | None,
    limit: int,
    days: int,
) -> dict[str, Any]:
    root = Path(cwd).resolve()
    history_path = Path(history_file).expanduser() if isinstance(history_file, str) and history_file.strip() else (root / "memory" / "nudge-history.jsonl")
    if not history_path.is_absolute():
        history_path = (root / history_path).resolve()
    since = datetime.now(UTC) - timedelta(days=max(1, int(days)))
    if not history_path.is_file():
        return {
            "schema_version": "1.1",
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
        "schema_version": "1.1",
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
) -> dict[str, Any]:
    now = datetime.now(UTC)
    since = now - timedelta(days=max(days, 1))
    files = list_session_files(cwd=cwd, pattern=pattern, limit=limit)
    parse_skipped = 0
    sessions_scanned = 0
    sessions_with_hits = 0
    hits_total = 0
    result_rows: list[dict[str, Any]] = []
    for p in files:
        mtime = datetime.fromtimestamp(p.stat().st_mtime, UTC)
        if mtime < since:
            continue
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
            },
        )
    result_rows.sort(key=lambda x: int(x.get("mtime") or 0), reverse=True)
    trimmed = result_rows[: max(1, session_limit)]
    return {
        "schema_version": "1.0",
        "generated_at": now.isoformat(),
        "query": query,
        "regex": use_regex,
        "case_sensitive": case_sensitive,
        "window": {
            "days": max(days, 1),
            "since": since.isoformat(),
            "pattern": pattern,
            "limit": limit,
            "hits_per_session": max(1, hits_per_session),
            "session_limit": max(1, session_limit),
        },
        "sessions_scanned": sessions_scanned,
        "sessions_with_hits": len(trimmed),
        "hits_total": sum(int(x.get("hits_count") or 0) for x in trimmed),
        "parse_skipped": parse_skipped,
        "results": trimmed,
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
) -> dict[str, Any]:
    doc = json.loads(Path(index_file).expanduser().resolve().read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("index file root must be object")
    entries = doc.get("entries")
    if not isinstance(entries, list):
        entries = []
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
        rows.append(
            {
                "path": row.get("path"),
                "mtime": row.get("mtime"),
                "model": row.get("model"),
                "task_id": row.get("task_id"),
                "answer_preview": row.get("answer_preview"),
                "hits_count": len(hits),
                "hits": hits[:3],
            },
        )
    rows.sort(key=lambda x: int(x.get("mtime") or 0), reverse=True)
    trimmed = rows[: max(1, session_limit)]
    return {
        "schema_version": "1.1",
        "query": query,
        "regex": use_regex,
        "case_sensitive": case_sensitive,
        "source": "index",
        "index_file": str(Path(index_file).expanduser().resolve()),
        "sessions_scanned": len(entries),
        "sessions_with_hits": len(trimmed),
        "hits_total": sum(int(x.get("hits_count") or 0) for x in trimmed),
        "parse_skipped": 0,
        "results": trimmed,
    }


def _search_recall_index(
    *,
    cwd: str,
    query: str,
    regex: bool,
    case_sensitive: bool,
    max_hits: int,
    index_path: str | None = None,
) -> dict[str, Any]:
    idx_path = _resolve_recall_index_path(cwd=cwd, index_path=index_path)
    return _build_recall_payload_from_index(
        index_file=str(idx_path),
        query=query,
        use_regex=regex,
        case_sensitive=case_sensitive,
        session_limit=max(1, max_hits),
    )


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


def _resolve_schedule_path(root: Path, raw_path: str | None, default_name: str) -> Path:
    if isinstance(raw_path, str) and raw_path.strip():
        p = Path(raw_path.strip()).expanduser()
        if not p.is_absolute():
            p = (root / p).resolve()
        else:
            p = p.resolve()
        return p
    return (root / default_name).resolve()


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


def _print_hook_status(
    settings: Settings,
    *,
    event: str,
    json_output: bool,
    hook_payload: dict[str, Any] | None = None,
) -> None:
    run_project_hooks(settings, event, hook_payload)
    if json_output:
        return
    ids = enabled_hook_ids(settings, event)
    if not ids:
        return
    print(f"[hook:{event}] " + ", ".join(ids), file=sys.stderr)


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


def _cmd_models_list(settings: Settings, *, json_output: bool) -> int:
    rows = [profile_to_public_dict(p) for p in settings.profiles]
    active = settings.active_profile_id
    if json_output:
        payload = {
            "active": active,
            "subagent": settings.subagent_profile_id,
            "planner": settings.planner_profile_id,
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
        return _cmd_models_list(settings, json_output=bool(getattr(args, "json_output", False)))

    if action == "fetch":
        try:
            models = fetch_models(settings)
        except Exception as e:
            print(f"获取模型列表失败: {e}", file=sys.stderr)
            return 2
        if getattr(args, "json_output", False):
            print(json.dumps(models, ensure_ascii=False))
        else:
            if not models:
                print("(无模型)")
            else:
                for m in models:
                    print(m)
        return 0

    if action == "ping":
        pid = getattr(args, "id", None)
        timeout_sec = float(getattr(args, "timeout_sec", 10.0) or 10.0)
        targets = (
            [p for p in settings.profiles if p.id == pid] if pid else list(settings.profiles)
        )
        if pid and not targets:
            print(f"profile 不存在: {pid}", file=sys.stderr)
            return 2
        results = [
            ping_profile(p, trust_env=settings.http_trust_env, timeout_sec=timeout_sec)
            for p in targets
        ]
        if getattr(args, "json_output", False):
            print(json.dumps({"results": results}, ensure_ascii=False))
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
                print(f"{r.get('profile_id')}: {status}{extra}")
        fail = any(r.get("status") != "OK" for r in results)
        return 1 if fail else 0

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

    # 以下动作会改写 TOML：先算新的 profiles 集合，再写回。
    target = _resolve_config_target(settings)
    # 合成 default 不应持久化：仅显式配置才作为写入基线。
    base_profiles: tuple[Profile, ...] = (
        settings.profiles if settings.profiles_explicit else ()
    )
    base_active = settings.active_profile_id if settings.profiles_explicit else None

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
            subagent=settings.subagent_profile_id,
            planner=settings.planner_profile_id,
        )
    except Exception as e:
        print(f"写入 {target} 失败: {e}", file=sys.stderr)
        return 2
    print(
        f"[models] {action} ok | active={next_active} "
        f"profiles={len(new_profiles)} file={target}",
    )
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


def _cmd_init(*, force: bool, is_global: bool = False, preset: str = "default") -> int:
    if is_global:
        dest = _default_global_config_path()
    else:
        dest = Path.cwd() / "cai-agent.toml"
    if dest.exists() and not force:
        label = "用户级全局" if is_global else "当前目录"
        print(
            f"{label} 配置已存在: {dest}；若需覆盖请添加 --force",
            file=sys.stderr,
        )
        return 1
    tpl_name = (
        "templates/cai-agent.starter.toml"
        if (preset or "").strip().lower() == "starter"
        else "templates/cai-agent.example.toml"
    )
    try:
        tpl = resources.files("cai_agent").joinpath(tpl_name)
        data = tpl.read_bytes()
    except Exception as e:
        print(f"读取内置配置模板失败: {e}", file=sys.stderr)
        return 1
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"创建目录失败 {dest.parent}: {e}", file=sys.stderr)
        return 1
    dest.write_bytes(data)
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
    print(
        "多模型: cai-agent models list；新增条目: "
        "cai-agent models add --preset lmstudio|ollama|vllm|openrouter|gateway|zhipu …",
    )
    if (preset or "").strip().lower() == "starter":
        print(
            "starter 模板已启用多条 profile；设置密钥后可用 "
            "`cai-agent models use local-lmstudio`（或其它 id）切换。",
        )
    print("说明: docs/ONBOARDING.zh-CN.md（含 CI / CAI_AUTO_APPROVE）。")
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
        help="模型 profile 管理：list/use/add/edit/rm/ping/fetch/route",
    )
    models_sub = models_p.add_subparsers(dest="models_action", required=False)

    _ml = models_sub.add_parser("list", help="列出已配置的模型 profile")
    _ml.add_argument("--json", action="store_true", dest="json_output")

    _mu = models_sub.add_parser("use", help="切换激活 profile 并写回配置")
    _mu.add_argument("id", help="profile id")

    _ma = models_sub.add_parser("add", help="新增一个 profile")
    _ma.add_argument("--id", required=True, dest="pid")
    _ma.add_argument(
        "--preset", default=None,
        choices=sorted(
            [
                "openai",
                "anthropic",
                "openrouter",
                "lmstudio",
                "ollama",
                "vllm",
                "gateway",
                "zhipu",
            ],
        ),
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
    _mp.add_argument("--json", action="store_true", dest="json_output")
    _mp.add_argument("--timeout-sec", type=float, default=10.0, dest="timeout_sec")

    _mf = models_sub.add_parser(
        "fetch",
        help="调用当前激活 profile 的 /v1/models 端点列出模型（原 `cai-agent models` 行为）",
    )
    _mf.add_argument("--json", action="store_true", dest="json_output")

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

    # 顶层兼容：不带子命令时等价于 list。
    models_p.add_argument("--json", action="store_true", dest="json_output")
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
    recall_p = sub.add_parser(
        "recall",
        help="跨会话检索：按关键词/正则匹配历史会话内容（Hermes-style recall）",
    )
    recall_p.add_argument(
        "--query",
        required=True,
        help="检索关键词（默认子串匹配）或正则表达式（--regex）",
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
    recall_idx_p = sub.add_parser(
        "recall-index",
        help="构建/管理 recall 索引（加速跨会话检索）",
    )
    recall_idx_sub = recall_idx_p.add_subparsers(dest="recall_index_action", required=True)

    recall_idx_build = recall_idx_sub.add_parser("build", help="重建索引文件")
    recall_idx_build.add_argument("--pattern", default=".cai-session*.json")
    recall_idx_build.add_argument("--limit", type=int, default=200)
    recall_idx_build.add_argument("--days", type=int, default=30)
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
    recall_idx_search.add_argument("--json", action="store_true", dest="json_output")
    recall_idx_search.add_argument("--index-path", default=None, dest="index_path")

    recall_idx_info = recall_idx_sub.add_parser("info", help="查看索引信息")
    recall_idx_info.add_argument("--json", action="store_true", dest="json_output")
    recall_idx_info.add_argument("--index-path", default=None, dest="index_path")

    recall_idx_clear = recall_idx_sub.add_parser("clear", help="删除索引文件")
    recall_idx_clear.add_argument("--json", action="store_true", dest="json_output")
    recall_idx_clear.add_argument("--index-path", default=None, dest="index_path")
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

    memory_p = sub.add_parser("memory", help="记忆管理命令")
    memory_sub = memory_p.add_subparsers(dest="memory_action", required=True)
    memory_extract = memory_sub.add_parser("extract", help="从会话提取记忆")
    memory_extract.add_argument("--pattern", default=".cai-session*.json")
    memory_extract.add_argument("--limit", type=int, default=10)
    memory_list = memory_sub.add_parser("list", help="列出结构化记忆条目（entries.jsonl）")
    memory_list.add_argument("--limit", type=int, default=50)
    memory_list.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="输出 JSON 数组（含 id/category/confidence/expires_at）",
    )
    memory_list.add_argument(
        "--sort",
        default="none",
        choices=("none", "confidence", "created_at"),
        help="list 结果排序（默认按文件顺序；无效行会被校验过滤）",
    )
    memory_instincts = memory_sub.add_parser("instincts", help="列出 instinct Markdown 快照路径")
    memory_instincts.add_argument("--limit", type=int, default=20)
    memory_instincts.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="以 JSON 数组输出路径",
    )
    memory_search = memory_sub.add_parser("search", help="按子串搜索记忆条目")
    memory_search.add_argument("query", help="搜索子串")
    memory_search.add_argument("--limit", type=int, default=50)
    memory_search.add_argument(
        "--sort",
        default="",
        help="confidence 或 created_at（命中后排序再截断）",
    )
    memory_search.add_argument("--json", action="store_true", dest="json_output")
    memory_prune = memory_sub.add_parser("prune", help="删除已过期的记忆条目")
    memory_prune.add_argument("--json", action="store_true", dest="json_output")
    memory_export = memory_sub.add_parser("export", help="导出记忆目录")
    memory_export.add_argument("file")
    memory_import = memory_sub.add_parser("import", help="导入记忆文件")
    memory_import.add_argument("file")
    memory_export_entries = memory_sub.add_parser(
        "export-entries",
        help="导出校验后的 memory/entries.jsonl 为 JSON bundle（schema: memory_entries_bundle_v1）",
    )
    memory_export_entries.add_argument("file")
    memory_import_entries = memory_sub.add_parser(
        "import-entries",
        help="从 bundle 导入条目（任一行无效则整批失败，不写入）",
    )
    memory_import_entries.add_argument("file")
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
    memory_nudge_report.add_argument("--json", action="store_true", dest="json_output")

    schedule_p = sub.add_parser(
        "schedule",
        help="定时任务管理（add/list/rm/run-due/daemon）",
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
    schedule_daemon.add_argument("--json", action="store_true", dest="json_output")

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

    export_p = sub.add_parser("export", parents=[common], help="导出到跨工具目录")
    export_p.add_argument("--target", required=True, choices=["cursor", "codex", "opencode"])
    export_p.add_argument(
        "-w",
        "--workspace",
        default=None,
        help="工作区根目录（默认当前目录或环境变量 CAI_WORKSPACE）",
    )

    obs_p = sub.add_parser("observe", help="输出可观测聚合 JSON")
    obs_p.add_argument("--pattern", default=".cai-session*.json")
    obs_p.add_argument("--limit", type=int, default=100)
    obs_p.add_argument("--json", action="store_true", dest="json_output")

    board_p = sub.add_parser(
        "board",
        help="任务/会话运营最小看板（observe + .cai/last-workflow.json）",
    )
    board_p.add_argument("--pattern", default=".cai-session*.json")
    board_p.add_argument("--limit", type=int, default=100)
    board_p.add_argument("--json", action="store_true", dest="json_output")

    wf_p = sub.add_parser(
        "workflow",
        parents=[common],
        help="根据 JSON workflow 文件依次运行多个步骤任务",
    )
    wf_p.add_argument(
        "file",
        help="workflow JSON 文件路径（包含 steps 数组）",
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
        return _cmd_init(
            force=args.force,
            is_global=bool(getattr(args, "global_flag", False)),
            preset=str(getattr(args, "init_preset", "default") or "default"),
        )

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
        return run_doctor(settings)

    if args.command == "plan":
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
                        },
                        ensure_ascii=False,
                    ),
                )
            else:
                print("goal 不能为空", file=sys.stderr)
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
        return 0

    if args.command == "models":
        return _cmd_models(args)

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
        surface = list_plugin_surface(settings)
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
        names = list_command_names(settings)
        if args.json_output:
            print(json.dumps(names, ensure_ascii=False))
        else:
            if not names:
                print("(无命令模板)")
            for n in names:
                print(f"/{n}")
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
        names = list_agent_names(settings)
        if args.json_output:
            print(json.dumps(names, ensure_ascii=False))
        else:
            if not names:
                print("(无子代理模板)")
            for n in names:
                print(n)
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
        probe_result = None
        if ok and args.tool:
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
        if args.json_output:
            payload = {
                "ok": ok,
                "provider": settings.provider,
                "model": settings.model,
                "mcp_enabled": settings.mcp_enabled,
                "mcp_base_url": settings.mcp_base_url,
                "force": bool(args.force),
                "tool": args.tool,
                "elapsed_ms": elapsed_ms,
                "result": txt,
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
            if probe_result is not None:
                print("--- tool probe ---")
                print(probe_result)
        return 0 if ok else 2

    if args.command == "sessions":
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
            print(json.dumps(arr, ensure_ascii=False))
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
        return 0

    if args.command == "stats":
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
        return 0

    if args.command == "insights":
        payload = _build_insights_payload(
            cwd=os.getcwd(),
            pattern=str(args.pattern),
            limit=int(args.limit),
            days=int(args.days),
        )
        if bool(args.json_output):
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
        return 0

    if args.command == "recall":
        idx_arg = getattr(args, "index_path", None)
        idx_path = (
            str(idx_arg).strip()
            if isinstance(idx_arg, str) and str(idx_arg).strip()
            else None
        )
        if bool(getattr(args, "use_index", False)):
            try:
                payload = _build_recall_payload_from_index(
                    index_file=str(_resolve_recall_index_path(cwd=os.getcwd(), index_path=idx_path)),
                    query=str(args.query),
                    use_regex=bool(args.regex),
                    case_sensitive=bool(getattr(args, "case_sensitive", False)),
                    session_limit=int(args.limit),
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
            )
        if bool(args.json_output):
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(
                f"hits_total={payload.get('hits_total')} scanned={payload.get('sessions_scanned')} "
                f"matched_sessions={payload.get('sessions_with_hits')} "
                f"parse_skipped={payload.get('parse_skipped')}",
            )
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
            payload = _build_recall_index(
                cwd=cwd,
                pattern=str(args.pattern),
                limit=int(args.limit),
                days=int(args.days),
                index_path=str(index_path_arg) if isinstance(index_path_arg, str) else None,
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
            payload = _refresh_recall_index(
                cwd=cwd,
                pattern=str(args.pattern),
                limit=int(args.limit),
                days=int(args.days),
                index_path=str(index_path_arg) if isinstance(index_path_arg, str) else None,
                prune_missing=bool(getattr(args, "prune", False)),
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
            payload = _search_recall_index(
                cwd=cwd,
                query=str(args.query),
                regex=bool(args.regex),
                case_sensitive=bool(getattr(args, "case_sensitive", False)),
                max_hits=int(args.max_hits),
                index_path=str(index_path_arg) if isinstance(index_path_arg, str) else None,
            )
            if bool(args.json_output):
                print(json.dumps(payload, ensure_ascii=False))
            else:
                print(
                    f"hits_total={payload.get('hits_total')} sessions_scanned={payload.get('sessions_scanned')} "
                    f"index_file={payload.get('index_file')}",
                )
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
        if action == "info":
            payload = _recall_index_info(
                cwd=cwd,
                index_path=str(index_path_arg) if isinstance(index_path_arg, str) else None,
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
            payload = _clear_recall_index(
                cwd=cwd,
                index_path=str(index_path_arg) if isinstance(index_path_arg, str) else None,
            )
            if bool(args.json_output):
                print(json.dumps(payload, ensure_ascii=False))
            else:
                print(f"removed={payload.get('removed')} index_file={payload.get('index_file')}")
            return 0
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
        return 0 if bool(result.get("ok")) else 2

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
                files = list_session_files(
                    cwd=str(root),
                    pattern=str(args.pattern),
                    limit=int(args.limit),
                )
                written: list[str] = []
                entries_appended = 0
                for p in files:
                    try:
                        sess = load_session(str(p))
                    except Exception:
                        continue
                    instincts = extract_basic_instincts_from_session(sess)
                    out = save_instincts(root, instincts)
                    if out:
                        written.append(str(out))
                    if extract_memory_entries_from_session(root, sess) is not None:
                        entries_appended += 1
                print(
                    json.dumps(
                        {"written": written, "entries_appended": entries_appended},
                        ensure_ascii=False,
                    ),
                )
                return 0
            if args.memory_action == "list":
                rows, vwarn = load_memory_entries_validated(root)
                for w in vwarn:
                    print(f"[memory] {w}", file=sys.stderr)
                sort_key = str(getattr(args, "sort", "none") or "none")
                sort_memory_rows(rows, sort_key)
                rows = rows[: int(args.limit)]
                if args.json_output:
                    print(json.dumps(rows, ensure_ascii=False))
                else:
                    for row in rows:
                        tid = row.get("id", "")
                        cat = row.get("category", "")
                        snippet = str(row.get("text", ""))[:120].replace("\n", " ")
                        print(f"{tid}\t{cat}\t{snippet}")
                return 0
            if args.memory_action == "instincts":
                files = sorted(
                    mem_dir.glob("instincts-*.md"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                arr = [str(p) for p in files[: int(args.limit)]]
                if args.json_output:
                    print(json.dumps(arr, ensure_ascii=False))
                else:
                    for p in arr:
                        print(p)
                return 0
            if args.memory_action == "search":
                sk = str(getattr(args, "sort", "") or "").strip() or None
                hits = search_memory_entries(
                    root,
                    str(args.query),
                    limit=int(args.limit),
                    sort=sk,
                )
                if args.json_output:
                    print(json.dumps(hits, ensure_ascii=False))
                else:
                    for row in hits:
                        print(
                            f"{row.get('id')}\t{row.get('category')}\t{row.get('text', '')[:200]}",
                        )
                return 0
            if args.memory_action == "prune":
                n = prune_expired_memory_entries(root)
                if args.json_output:
                    print(json.dumps({"removed": n}, ensure_ascii=False))
                else:
                    print(f"removed={n}")
                return 0
            if args.memory_action == "export":
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
                print(str(target))
                return 0
            if args.memory_action == "import":
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
                print(json.dumps({"imported": count}, ensure_ascii=False))
                return 0
            if args.memory_action == "export-entries":
                target = Path(args.file).expanduser().resolve()
                bundle = export_memory_entries_bundle(root)
                target.write_text(
                    json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                warns = bundle.get("export_warnings") or []
                for w in warns:
                    print(f"[memory] {w}", file=sys.stderr)
                print(str(target))
                return 0
            if args.memory_action == "import-entries":
                src = Path(args.file).expanduser().resolve()
                doc = json.loads(src.read_text(encoding="utf-8"))
                n = import_memory_entries_bundle(root, doc)
                print(json.dumps({"imported": n}, ensure_ascii=False))
                return 0
            if args.memory_action == "nudge":
                payload = _build_memory_nudge_payload(
                    cwd=str(root),
                    days=int(getattr(args, "days", 7)),
                    session_pattern=str(getattr(args, "session_pattern", ".cai-session*.json")),
                    session_limit=int(getattr(args, "session_limit", 50)),
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
                payload = _build_memory_nudge_report_payload(
                    cwd=str(root),
                    history_file=getattr(args, "history_file", None),
                    limit=int(getattr(args, "limit", 200)),
                    days=int(getattr(args, "days", 30)),
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
        finally:
            _print_hook_status(
                settings_mem,
                event="memory_end",
                json_output=mem_json,
            )

    if args.command == "schedule":
        root = Path.cwd().resolve()
        if args.schedule_action == "add":
            job = add_schedule_task(
                goal=str(args.goal),
                every_minutes=int(args.every_minutes),
                workspace=str(args.workspace) if getattr(args, "workspace", None) else None,
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
            if bool(args.json_output):
                print(json.dumps(job, ensure_ascii=False))
            else:
                print(
                    f"added id={job.get('id')} every_minutes={job.get('every_minutes')} "
                    f"enabled={job.get('enabled')}",
                )
            return 0
        if args.schedule_action == "add-memory-nudge":
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
            return 0
        if args.schedule_action == "list":
            jobs = list_schedule_tasks(str(root))
            if bool(args.json_output):
                print(json.dumps(jobs, ensure_ascii=False))
            else:
                if not jobs:
                    print("(无定时任务)")
                for j in jobs:
                    print(
                        f"{j.get('id')}\tevery={j.get('every_minutes')}m\tenabled={j.get('enabled')}\t"
                        f"run_count={j.get('run_count', 0)} last_status={j.get('last_status')}\t"
                        f"goal={(str(j.get('goal') or '')[:80])}",
                    )
            return 0
        if args.schedule_action == "rm":
            ok = remove_schedule_task(str(args.id), str(root))
            if bool(args.json_output):
                print(json.dumps({"removed": ok}, ensure_ascii=False))
            else:
                print("removed=1" if ok else "removed=0")
            return 0 if ok else 2
        if args.schedule_action == "run-due":
            due = compute_due_tasks(cwd=str(root))
            if not bool(args.execute):
                payload = {"mode": "dry-run", "due_jobs": due, "executed": []}
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
                    executed.append(
                        {
                            "id": tid,
                            "ok": False,
                            "status": "failed",
                            "error": "empty_goal",
                        },
                    )
                    continue
                ok, out = _execute_scheduled_goal(
                    config_path=None,
                    workspace_hint=workspace_override,
                    workspace_override=workspace_override,
                    model_override=model_override,
                    goal=goal,
                )
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
                        },
                    )
                else:
                    mark_schedule_task_run(
                        task_id=tid,
                        status="failed",
                        error=out,
                        cwd=str(root),
                    )
                    executed.append(
                        {
                            "id": tid,
                            "ok": False,
                            "status": "failed",
                            "error": out,
                            "workspace": workspace_override,
                            "model": model_override,
                        },
                    )
            payload = {"mode": "execute", "due_jobs": due, "executed": executed}
            if bool(args.json_output):
                print(json.dumps(payload, ensure_ascii=False))
            else:
                print(f"executed={len(executed)} due_jobs={len(due)}")
            return 0
        if args.schedule_action == "daemon":
            interval_sec = max(0.2, float(args.interval_sec))
            max_cycles = int(args.max_cycles)
            execute = bool(args.execute)
            lock_path = _resolve_schedule_path(root, getattr(args, "lock_file", None), ".cai-schedule-daemon.lock")
            stale_lock_sec = max(0.0, float(getattr(args, "stale_lock_sec", 0.0) or 0.0))
            ok_lock, lock_msg = _acquire_schedule_daemon_lock(lock_path=lock_path, stale_lock_sec=stale_lock_sec)
            if not ok_lock:
                payload = {"mode": "daemon", "ok": False, "error": "lock_conflict", "message": lock_msg}
                if bool(args.json_output):
                    print(json.dumps(payload, ensure_ascii=False))
                else:
                    print(f"[schedule-daemon] lock conflict: {lock_msg}", file=sys.stderr)
                return 2

            log_path_raw = getattr(args, "jsonl_log", None)
            log_path = _resolve_schedule_path(root, log_path_raw, ".cai-schedule-daemon.jsonl") if log_path_raw else None

            cycles = 0
            total_due = 0
            total_executed = 0
            results: list[dict[str, Any]] = []
            interrupted = False
            try:
                while True:
                    cycles += 1
                    due = compute_due_tasks(cwd=str(root))
                    total_due += len(due)
                    cycle_exec: list[dict[str, Any]] = []
                    if execute:
                        for j in due:
                            tid = str(j.get("id") or "").strip()
                            if not tid:
                                continue
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
                                cycle_exec.append(
                                    {"id": tid, "ok": False, "status": "failed", "error": "empty_goal"},
                                )
                                continue
                            ok, out = _execute_scheduled_goal(
                                config_path=None,
                                workspace_hint=workspace_override,
                                workspace_override=workspace_override,
                                model_override=model_override,
                                goal=goal,
                            )
                            if ok:
                                mark_schedule_task_run(task_id=tid, status="completed", cwd=str(root))
                                preview = out[:160] + ("…" if len(out) > 160 else "")
                                cycle_exec.append(
                                    {
                                        "id": tid,
                                        "ok": True,
                                        "status": "completed",
                                        "answer_preview": preview,
                                    },
                                )
                            else:
                                mark_schedule_task_run(
                                    task_id=tid,
                                    status="failed",
                                    error=out,
                                    cwd=str(root),
                                )
                                cycle_exec.append(
                                    {"id": tid, "ok": False, "status": "failed", "error": out},
                                )
                    total_executed += len(cycle_exec)
                    cycle_row = {
                        "cycle": cycles,
                        "due_count": len(due),
                        "executed_count": len(cycle_exec),
                        "execute": execute,
                        "executed": cycle_exec,
                    }
                    results.append(cycle_row)
                    if log_path is not None:
                        _append_schedule_daemon_log(
                            log_path,
                            {
                                "event": "schedule.daemon.cycle",
                                "ts": datetime.now(UTC).isoformat(),
                                **cycle_row,
                            },
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
                "mode": "daemon",
                "execute": execute,
                "interval_sec": interval_sec,
                "max_cycles": max_cycles,
                "cycles": cycles,
                "total_due": total_due,
                "total_executed": total_executed,
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
                    f"execute={execute} interrupted={interrupted}",
                )
            return 0

    if args.command == "cost":
        if args.cost_action == "budget":
            settings_cost = Settings.from_env(config_path=None)
            _print_hook_status(
                settings_cost,
                event="cost_budget_start",
                json_output=True,
            )
            try:
                cfg_max = int(settings_cost.cost_budget_max_tokens)
                max_tokens = (
                    int(args.max_tokens) if args.max_tokens is not None else cfg_max
                )
                agg = aggregate_sessions(cwd=os.getcwd(), limit=200)
                total_tokens = int(agg.get("total_tokens", 0))
                state = "pass"
                if total_tokens > max_tokens:
                    state = "fail"
                elif total_tokens > int(max_tokens * 0.8):
                    state = "warn"
                payload = {
                    "state": state,
                    "total_tokens": total_tokens,
                    "max_tokens": max_tokens,
                }
                print(json.dumps(payload, ensure_ascii=False))
                rc = 0 if state != "fail" else 2
            finally:
                _print_hook_status(
                    settings_cost,
                    event="cost_budget_end",
                    json_output=True,
                )
            return rc

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
        try:
            result = export_target(settings, str(args.target))
        finally:
            _print_hook_status(
                settings,
                event="export_end",
                json_output=True,
            )
        print(json.dumps(result, ensure_ascii=False))
        return 0

    if args.command == "observe":
        settings_obs = Settings.from_env(config_path=None)
        obs_json = bool(getattr(args, "json_output", False))
        _print_hook_status(
            settings_obs,
            event="observe_start",
            json_output=obs_json,
            hook_payload={
                "pattern": str(args.pattern),
                "limit": int(args.limit),
            },
        )
        try:
            obs = build_observe_payload(
                cwd=os.getcwd(),
                pattern=str(args.pattern),
                limit=int(args.limit),
            )
            if args.json_output:
                print(json.dumps(obs, ensure_ascii=False))
            else:
                ag = obs.get("aggregates") if isinstance(obs.get("aggregates"), dict) else {}
                print(
                    f"schema={obs.get('schema_version')} sessions={obs.get('sessions_count')} "
                    f"failed={ag.get('failed_count')} tokens={ag.get('total_tokens')} "
                    f"run_events_total={ag.get('run_events_total', 0)}",
                )
        finally:
            _print_hook_status(
                settings_obs,
                event="observe_end",
                json_output=obs_json,
                hook_payload={
                    "pattern": str(args.pattern),
                    "limit": int(args.limit),
                },
            )
        return 0

    if args.command == "board":
        settings_board = Settings.from_env(config_path=None)
        board_json = bool(getattr(args, "json_output", False))
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
            if board_json:
                print(json.dumps(payload, ensure_ascii=False))
            else:
                obs = payload.get("observe") if isinstance(payload.get("observe"), dict) else {}
                ag = obs.get("aggregates") if isinstance(obs.get("aggregates"), dict) else {}
                print(
                    f"[observe] schema={obs.get('schema_version')} "
                    f"sessions={obs.get('sessions_count')} "
                    f"failed={ag.get('failed_count')} tokens={ag.get('total_tokens')} "
                    f"run_events_total={ag.get('run_events_total', 0)}",
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
        return 0

    if args.command == "workflow":
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
        return 0

    if args.command in ("run", "continue", "command", "agent", "fix-build"):
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
        goal = " ".join(args.goal).strip()
        if not goal:
            print("goal 不能为空", file=sys.stderr)
            return 2
        if args.command in ("command", "fix-build"):
            if args.command == "fix-build":
                cmd_name = "fix-build"
            else:
                cmd_name = str(args.name).strip().lstrip("/")
            cmd_text = load_command_text(settings, cmd_name)
            if not cmd_text:
                print(f"命令模板不存在: /{cmd_name}", file=sys.stderr)
                return 2
            skill_texts = load_related_skill_texts(settings, cmd_name)
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
                print(f"子代理模板不存在: {agent_name}", file=sys.stderr)
                return 2
            skill_texts = load_related_skill_texts(settings, agent_name)
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
                print(f"读取计划文件失败: {e}", file=sys.stderr)
                return 2

        auto_on = bool(getattr(args, "auto_approve", False))
        prev_auto = os.environ.get("CAI_AUTO_APPROVE")
        if auto_on:
            os.environ["CAI_AUTO_APPROVE"] = "1"
        try:
            reset_usage_counters()
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
                    print(f"读取会话失败: {e}", file=sys.stderr)
                    return 2
                messages = sess.get("messages")
                if not isinstance(messages, list) or not messages:
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
                    payload = {
                        "run_schema_version": "1.0",
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
                        "events": [
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
                        ],
                        "error": "interrupted",
                        "message": "用户已手动停止",
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
                    "run_schema_version": "1.0",
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
                    "events": run_events,
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
                    "run_schema_version": "1.0",
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
                    "events": run_events,
                    "post_gate": gate_result,
                }
                try:
                    save_session(str(save_session_path), payload)
                except Exception as e:
                    print(f"写入会话失败: {e}", file=sys.stderr)
                    return 2
            _print_hook_status(
                settings,
                event="session_end",
                json_output=bool(args.json_output),
            )
            return 0
        finally:
            if auto_on:
                if prev_auto is None:
                    os.environ.pop("CAI_AUTO_APPROVE", None)
                else:
                    os.environ["CAI_AUTO_APPROVE"] = prev_auto

    if args.command == "ui":
        from cai_agent.tui import run_tui

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
        run_tui(settings)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
