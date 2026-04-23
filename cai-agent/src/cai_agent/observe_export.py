"""Hermes S7-04：``observe export`` 按 UTC 日历日导出（CSV / JSON / Markdown）。"""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any

from cai_agent.memory import build_memory_health_payload
from cai_agent.schedule import aggregate_schedule_audit_by_calendar_day_utc
from cai_agent.session import list_session_files, load_session


def _aggregate_sessions_for_day(paths: list[Path]) -> dict[str, Any]:
    n = 0
    failed = 0
    total_tokens = 0
    for p in paths:
        try:
            s = load_session(str(p))
        except Exception:
            continue
        n += 1
        ec = int(s.get("error_count") or 0) if isinstance(s.get("error_count"), int) else 0
        if ec > 0:
            failed += 1
        tt = int(s.get("total_tokens") or 0) if isinstance(s.get("total_tokens"), int) else 0
        total_tokens += tt
    fr = (float(failed) / float(n)) if n else 0.0
    sr = (1.0 - fr) if n else 1.0
    return {
        "session_count": n,
        "failed_count": failed,
        "failure_rate": fr,
        "success_rate": sr,
        "token_total": total_tokens,
        "token_avg": (float(total_tokens) / float(n)) if n else 0.0,
    }


def build_observe_export_v1(
    *,
    cwd: str,
    pattern: str,
    limit: int,
    days: int,
    memory_session_pattern: str = ".cai-session*.json",
    memory_session_limit: int = 200,
) -> dict[str, Any]:
    """返回 ``observe_export_v1`` 信封 + ``rows``（按 ``date`` 升序，与调度按日聚合对齐）。"""
    ndays = max(1, min(int(days), 366))
    clock = datetime.now(UTC)
    since_ts = (clock - timedelta(days=ndays)).timestamp()
    cap = min(max(int(limit) * max(ndays, 7), 200), 5000)
    files = list_session_files(cwd=cwd, pattern=pattern, limit=cap)
    by_day: dict[str, list[Path]] = defaultdict(list)
    for p in files:
        try:
            mt = float(p.stat().st_mtime)
        except OSError:
            continue
        if mt < since_ts:
            continue
        dkey = datetime.fromtimestamp(mt, UTC).date().isoformat()
        by_day[dkey].append(p)

    sched = aggregate_schedule_audit_by_calendar_day_utc(cwd=cwd, days=ndays)
    rows: list[dict[str, Any]] = []
    for srow in sched:
        dk = str(srow.get("date") or "")
        if not dk:
            continue
        agg = _aggregate_sessions_for_day(by_day.get(dk, []))
        d0 = date.fromisoformat(dk)
        day_start = datetime(d0.year, d0.month, d0.day, tzinfo=UTC)
        day_end = day_start + timedelta(days=1)
        hp = build_memory_health_payload(
            cwd,
            days=1,
            session_pattern=memory_session_pattern,
            session_limit=memory_session_limit,
            reference_now=day_end,
            session_mtime_start=day_start,
            session_mtime_end_exclusive=day_end,
        )
        sc = int(srow.get("success_count") or 0)
        fc = int(srow.get("fail_count") or 0)
        rows.append(
            {
                "ts": str(srow.get("ts") or day_start.isoformat()),
                "date": dk,
                "session_count": int(agg["session_count"]),
                "success_rate": float(agg["success_rate"]),
                "failure_rate": float(agg["failure_rate"]),
                "token_total": int(agg["token_total"]),
                "token_avg": float(agg["token_avg"]),
                "schedule_tasks_ok": sc,
                "schedule_tasks_failed": fc,
                "schedule_success_rate": srow.get("success_rate"),
                "memory_health_score": float(hp.get("health_score") or 0.0),
                "memory_grade": str(hp.get("grade") or ""),
            },
        )

    return {
        "schema_version": "observe_export_v1",
        "report_kind": "observe_export_daily_v1",
        "generated_at": clock.isoformat(),
        "window_days": ndays,
        "pattern": pattern,
        "limit": limit,
        "scan_cap": cap,
        "rows": rows,
    }


def render_observe_export_csv(doc: dict[str, Any]) -> str:
    rows = doc.get("rows") if isinstance(doc.get("rows"), list) else []
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(
        [
            "date",
            "session_count",
            "success_rate",
            "failure_rate",
            "token_total",
            "token_avg",
            "schedule_tasks_ok",
            "schedule_tasks_failed",
            "schedule_success_rate",
            "memory_health_score",
            "memory_grade",
        ],
    )
    for r in rows:
        if not isinstance(r, dict):
            continue
        w.writerow(
            [
                r.get("date"),
                r.get("session_count"),
                f'{float(r.get("success_rate") or 0):.6f}',
                f'{float(r.get("failure_rate") or 0):.6f}',
                r.get("token_total"),
                f'{float(r.get("token_avg") or 0):.4f}',
                r.get("schedule_tasks_ok"),
                r.get("schedule_tasks_failed"),
                ""
                if r.get("schedule_success_rate") is None
                else f'{float(r.get("schedule_success_rate")):.6f}',
                f'{float(r.get("memory_health_score") or 0):.4f}',
                r.get("memory_grade"),
            ],
        )
    return buf.getvalue()


def render_observe_export_markdown(doc: dict[str, Any]) -> str:
    rows = doc.get("rows") if isinstance(doc.get("rows"), list) else []
    lines = [
        "# Observe 按日导出",
        "",
        f"- 生成：`{doc.get('generated_at')}`",
        f"- 窗口天数：**{doc.get('window_days')}**",
        "",
        "| date | sessions | success_rate | token_avg | sched_ok | sched_fail | memory_score | grade |",
        "|------|----------|-------------|-----------|----------|------------|--------------|-------|",
    ]
    for r in rows:
        if not isinstance(r, dict):
            continue
        lines.append(
            "| {date} | {sc} | {sr:.4f} | {ta:.2f} | {ok} | {fl} | {mh:.4f} | {g} |".format(
                date=r.get("date"),
                sc=int(r.get("session_count") or 0),
                sr=float(r.get("success_rate") or 0),
                ta=float(r.get("token_avg") or 0),
                ok=int(r.get("schedule_tasks_ok") or 0),
                fl=int(r.get("schedule_tasks_failed") or 0),
                mh=float(r.get("memory_health_score") or 0),
                g=str(r.get("memory_grade") or ""),
            ),
        )
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(doc, ensure_ascii=False, indent=2)[:6000])
    lines.append("```")
    lines.append("")
    return "\n".join(lines)
