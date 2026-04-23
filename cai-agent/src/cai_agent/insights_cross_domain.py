"""Hermes S7-03：``insights --cross-domain`` 按 UTC 日历日对齐的趋势序列。

``recall_hit_rate_trend`` 中 ``hit_rate`` 为 **索引子串探测**（固定 ``probe_query``），
与 ``cai-agent recall`` 查询命中率不同；根级 ``recall_hit_rate_metric_kind`` 标明语义。
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from cai_agent.memory import build_memory_health_payload
from cai_agent.recall_audit import (
    aggregate_negative_recall_queries,
    aggregate_recall_audit_by_calendar_day_utc,
)
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
    audit_agg = aggregate_recall_audit_by_calendar_day_utc(cwd, start_d=start_d, end_d=end_d)
    use_audit = any(int((v or {}).get("queries") or 0) > 0 for v in audit_agg.values())
    negative_queries_top = aggregate_negative_recall_queries(
        cwd,
        start_d=start_d,
        end_d=end_d,
        limit=12,
    )
    # 若部分日历日无 audit 行但索引可用，则按日回退 probe → 根级 source 记为 mixed
    use_mixed = False
    if use_audit and index_ok:
        for day in dates_asc:
            dk = day.isoformat()
            st = audit_agg.get(dk) or {}
            if int(st.get("queries") or 0) <= 0:
                use_mixed = True
                break

    recall_trend: list[dict[str, Any]] = []
    memory_trend: list[dict[str, Any]] = []
    for day in dates_asc:
        day_start = datetime(day.year, day.month, day.day, tzinfo=UTC)
        day_end = day_start + timedelta(days=1)
        ts_iso = day_start.isoformat()
        dk = day.isoformat()

        if use_mixed:
            st = audit_agg.get(dk) or {}
            qn = int(st.get("queries") or 0)
            if qn > 0:
                recall_trend.append(
                    {
                        "ts": ts_iso,
                        "date": dk,
                        "metric_kind": "recall_audit",
                        "recall_hit_rate_source": "audit",
                        "hit_rate": st.get("hit_rate"),
                        "queries": qn,
                        "queries_with_hit": int(st.get("queries_with_hit") or 0),
                        "audit_file": str(Path(cwd).resolve() / ".cai" / "recall-audit.jsonl"),
                    },
                )
            elif index_ok:
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
                        "metric_kind": "index_probe",
                        "recall_hit_rate_source": "probe",
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
                        "metric_kind": "unavailable",
                        "recall_hit_rate_source": "mixed",
                        "metric_unavailability_reason": "no_audit_no_index",
                        "hit_rate": None,
                        "indexed_rows": 0,
                        "probe_hits": 0,
                        "probe_query": probe_q,
                        "no_index_reason": "index_missing",
                    },
                )
        elif use_audit:
            st = audit_agg.get(dk) or {}
            qn = int(st.get("queries") or 0)
            recall_trend.append(
                {
                    "ts": ts_iso,
                    "date": dk,
                    "metric_kind": "recall_audit",
                    "recall_hit_rate_source": "audit",
                    "hit_rate": st.get("hit_rate"),
                    "queries": qn,
                    "queries_with_hit": int(st.get("queries_with_hit") or 0),
                    "audit_file": str(Path(cwd).resolve() / ".cai" / "recall-audit.jsonl"),
                },
            )
        elif index_ok:
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
                    "metric_kind": "index_probe",
                    "recall_hit_rate_source": "probe",
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
                    "metric_kind": "unavailable",
                    "recall_hit_rate_source": "probe",
                    "metric_unavailability_reason": "index_missing",
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

    metric_kind_top = "mixed_audit_probe" if use_mixed else ("recall_audit" if use_audit else "index_probe")
    note_audit = (
        "hit_rate is derived from `.cai/recall-audit.jsonl` (one row per `cai-agent recall` run); "
        "see `cai_agent.recall_audit.append_recall_audit_line`."
    )
    note_probe = (
        "hit_rate is derived from recall-index rows and a fixed substring probe_query; "
        "enable audit by running `cai-agent recall` (writes `.cai/recall-audit.jsonl`)."
    )
    note_mixed = (
        "Per-day: UTC days with recall_audit rows use audit hit_rate; "
        "days without audit but with recall index use index_probe; "
        "see `cai_agent.insights_cross_domain.build_insights_cross_domain_v1`."
    )
    src_top = "mixed" if use_mixed else ("audit" if use_audit else "probe")
    return {
        "schema_version": "insights_cross_domain_v1",
        "generated_at": clock.isoformat(),
        "recall_hit_rate_source": src_top,
        "recall_hit_rate_metric_kind": metric_kind_top,
        "recall_hit_rate_metric_note": note_mixed if use_mixed else (note_audit if use_audit else note_probe),
        "negative_queries_top": negative_queries_top,
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
