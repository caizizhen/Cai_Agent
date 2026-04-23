"""Hermes S7-03：``insights --cross-domain`` 按 UTC 日历日对齐的趋势序列。"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from cai_agent.memory import build_memory_health_payload
from cai_agent.schedule import aggregate_schedule_audit_by_calendar_day_utc


def _recall_probe_hits(
    content: str,
    *,
    query: str,
    use_regex: bool,
    case_sensitive: bool,
) -> bool:
    if not isinstance(content, str) or not content.strip():
        return False
    if use_regex:
        flags = 0 if case_sensitive else re.IGNORECASE
        return re.search(query, content, flags=flags) is not None
    q = query if case_sensitive else query.lower()
    hay = content if case_sensitive else content.lower()
    return hay.find(q) >= 0


def _recall_index_probe_for_day(
    entries: list[dict[str, Any]],
    *,
    day_start: datetime,
    day_end_exclusive: datetime,
    probe_query: str,
    use_regex: bool,
    case_sensitive: bool,
) -> dict[str, Any]:
    lo = day_start.timestamp()
    hi = day_end_exclusive.timestamp()
    scanned = 0
    with_hit = 0
    for row in entries:
        if not isinstance(row, dict):
            continue
        raw_mt = row.get("mtime")
        if not isinstance(raw_mt, int):
            continue
        if raw_mt < lo or raw_mt >= hi:
            continue
        txt = row.get("content")
        if not isinstance(txt, str) or not txt.strip():
            continue
        scanned += 1
        if _recall_probe_hits(txt, query=probe_query, use_regex=use_regex, case_sensitive=case_sensitive):
            with_hit += 1
    rate = (float(with_hit) / float(scanned)) if scanned else None
    return {
        "indexed_rows": scanned,
        "probe_hits": with_hit,
        "hit_rate": rate,
        "probe_query": probe_query,
        "probe_case_sensitive": case_sensitive,
    }


def build_insights_cross_domain_v1(
    *,
    cwd: str,
    base_insights: dict[str, Any],
    pattern: str,
    limit: int,
    days: int,
    memory_session_pattern: str = ".cai-session*.json",
    memory_session_limit: int = 200,
) -> dict[str, Any]:
    """``insights_cross_domain_v1``：嵌套基础 ``insights``（1.1）+ 三条按日趋势（``ts`` 升序）。"""
    ndays = max(1, int(days))
    clock = datetime.now(UTC)
    end_d = clock.date()
    start_d = end_d - timedelta(days=ndays - 1)
    dates_asc: list[date] = []
    cur = start_d
    while cur <= end_d:
        dates_asc.append(cur)
        cur = cur + timedelta(days=1)

    idx_path = Path(cwd).resolve() / ".cai-recall-index.json"
    index_entries: list[dict[str, Any]] = []
    index_ok = False
    if idx_path.is_file():
        try:
            doc = json.loads(idx_path.read_text(encoding="utf-8"))
            raw = doc.get("entries") if isinstance(doc, dict) else None
            if isinstance(raw, list):
                index_entries = [x for x in raw if isinstance(x, dict)]
                index_ok = True
        except Exception:
            index_entries = []
            index_ok = False

    probe_q = "the"
    recall_trend: list[dict[str, Any]] = []
    memory_trend: list[dict[str, Any]] = []
    for day in dates_asc:
        day_start = datetime(day.year, day.month, day.day, tzinfo=UTC)
        day_end = day_start + timedelta(days=1)
        ts_iso = day_start.isoformat()
        dk = day.isoformat()

        if index_ok:
            rsum = _recall_index_probe_for_day(
                index_entries,
                day_start=day_start,
                day_end_exclusive=day_end,
                probe_query=probe_q,
                use_regex=False,
                case_sensitive=False,
            )
            recall_trend.append(
                {
                    "ts": ts_iso,
                    "date": dk,
                    "hit_rate": rsum.get("hit_rate"),
                    "indexed_rows": int(rsum.get("indexed_rows") or 0),
                    "probe_hits": int(rsum.get("probe_hits") or 0),
                    "probe_query": probe_q,
                    "index_file": str(idx_path),
                },
            )
        else:
            recall_trend.append(
                {
                    "ts": ts_iso,
                    "date": dk,
                    "hit_rate": None,
                    "indexed_rows": 0,
                    "probe_hits": 0,
                    "probe_query": probe_q,
                    "no_index_reason": "index_missing",
                },
            )

        hp = build_memory_health_payload(
            cwd,
            days=1,
            session_pattern=memory_session_pattern,
            session_limit=memory_session_limit,
            reference_now=day_end,
            session_mtime_start=day_start,
            session_mtime_end_exclusive=day_end,
        )
        memory_trend.append(
            {
                "ts": ts_iso,
                "date": dk,
                "health_score": float(hp.get("health_score") or 0.0),
                "grade": str(hp.get("grade") or ""),
                "recent_sessions": int((hp.get("counts") or {}).get("recent_sessions") or 0),
            },
        )

    schedule_trend = aggregate_schedule_audit_by_calendar_day_utc(cwd=cwd, days=ndays)

    return {
        "schema_version": "insights_cross_domain_v1",
        "generated_at": clock.isoformat(),
        "window": {
            "days": ndays,
            "since": datetime(start_d.year, start_d.month, start_d.day, tzinfo=UTC).isoformat(),
            "until_exclusive": (datetime(end_d.year, end_d.month, end_d.day, tzinfo=UTC) + timedelta(days=1)).isoformat(),
            "pattern": pattern,
            "limit": limit,
            "memory_session_pattern": memory_session_pattern,
            "memory_session_limit": memory_session_limit,
        },
        "insights": base_insights,
        "recall_hit_rate_trend": recall_trend,
        "memory_health_trend": memory_trend,
        "schedule_success_trend": schedule_trend,
    }
