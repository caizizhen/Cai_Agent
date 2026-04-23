"""Recall 查询审计（H1-M-04）：写入 ``.cai/recall-audit.jsonl``，供 ``insights --cross-domain`` 使用真实命中率。"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any


RECALL_AUDIT_REL = ".cai/recall-audit.jsonl"
SCHEMA_VERSION = "recall_audit_v1"
SCHEMA_NEGATIVE = "recall_audit_negative_v1"


def recall_audit_path(cwd: str | Path) -> Path:
    return Path(cwd).expanduser().resolve() / RECALL_AUDIT_REL


def append_negative_recall_line(
    cwd: str | Path,
    *,
    query: str,
    reason: str | None = None,
) -> None:
    """记录一次「零命中」recall，供 ``insights --cross-domain`` 分析常见未命中查询。"""
    if os.environ.get("CAI_RECALL_AUDIT_DISABLE", "").strip().lower() in ("1", "true", "yes"):
        return
    p = recall_audit_path(cwd)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = {
        "schema_version": SCHEMA_NEGATIVE,
        "ts": datetime.now(UTC).isoformat(),
        "query": (query or "")[:500],
        "reason": (reason or "")[:200] or None,
    }
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def append_recall_audit_line(
    cwd: str | Path,
    *,
    query: str,
    hits_total: int,
    sessions_scanned: int,
    sessions_with_hits: int,
    task_id: str | None = None,
    use_index: bool = False,
) -> None:
    if os.environ.get("CAI_RECALL_AUDIT_DISABLE", "").strip().lower() in ("1", "true", "yes"):
        return
    p = recall_audit_path(cwd)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = {
        "schema_version": SCHEMA_VERSION,
        "ts": datetime.now(UTC).isoformat(),
        "query": (query or "")[:500],
        "hits_total": int(hits_total),
        "sessions_scanned": int(sessions_scanned),
        "sessions_with_hits": int(sessions_with_hits),
        "hit": bool(int(hits_total or 0) > 0),
        "task_id": task_id,
        "use_index": bool(use_index),
    }
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def _day_bounds_utc(d: date) -> tuple[datetime, datetime]:
    start = datetime(d.year, d.month, d.day, tzinfo=UTC)
    return start, start + timedelta(days=1)


def aggregate_recall_audit_by_calendar_day_utc(
    cwd: str | Path,
    *,
    start_d: date,
    end_d: date,
) -> dict[str, dict[str, Any]]:
    """按 UTC 日历日聚合审计行：``date_iso -> {queries, hits, hit_rate}``。"""
    p = recall_audit_path(cwd)
    if not p.is_file():
        return {}
    by_day: dict[str, list[tuple[bool, int]]] = defaultdict(list)
    try:
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            if str(obj.get("schema_version") or "") != SCHEMA_VERSION:
                continue
            ts_raw = obj.get("ts")
            if not isinstance(ts_raw, str) or not ts_raw.strip():
                continue
            try:
                dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except ValueError:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            d = dt.astimezone(UTC).date()
            if d < start_d or d > end_d:
                continue
            hit = bool(obj.get("hit"))
            hits_total = int(obj.get("hits_total") or 0)
            by_day[d.isoformat()].append((hit, hits_total))
    except OSError:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for dk, rows in by_day.items():
        queries = len(rows)
        hits = sum(1 for h, _ in rows if h)
        out[dk] = {
            "queries": queries,
            "queries_with_hit": hits,
            "hit_rate": (float(hits) / float(queries)) if queries else None,
        }
    return out


def has_recall_audit_data(cwd: str | Path, *, start_d: date, end_d: date) -> bool:
    agg = aggregate_recall_audit_by_calendar_day_utc(cwd, start_d=start_d, end_d=end_d)
    return any((v.get("queries") or 0) > 0 for v in agg.values())


def aggregate_negative_recall_queries(
    cwd: str | Path,
    *,
    start_d: date,
    end_d: date,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """统计 ``recall_audit_negative_v1`` 行：按 query 计数，降序取前 ``limit`` 条。"""
    p = recall_audit_path(cwd)
    if not p.is_file():
        return []
    counts: dict[str, int] = defaultdict(int)
    reasons: dict[str, str] = {}
    try:
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            if str(obj.get("schema_version") or "") != SCHEMA_NEGATIVE:
                continue
            ts_raw = obj.get("ts")
            if not isinstance(ts_raw, str) or not ts_raw.strip():
                continue
            try:
                dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except ValueError:
                continue
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            d = dt.astimezone(UTC).date()
            if d < start_d or d > end_d:
                continue
            q = str(obj.get("query") or "").strip()[:500]
            if not q:
                continue
            counts[q] += 1
            r = obj.get("reason")
            if isinstance(r, str) and r.strip() and q not in reasons:
                reasons[q] = r.strip()[:200]
    except OSError:
        return []
    lim = max(1, min(100, int(limit)))
    ranked = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:lim]
    return [{"query": q, "count": n, "sample_reason": reasons.get(q)} for q, n in ranked]


def build_recall_evaluation_payload(
    cwd: str | Path,
    *,
    days: int = 14,
) -> dict[str, Any]:
    """``recall_evaluation_v1``：基于审计文件的命中率与负样本计数（UTC 日历日窗口）。"""
    ndays = max(1, int(days))
    clock = datetime.now(UTC)
    end_d = clock.date()
    start_d = end_d - timedelta(days=ndays - 1)
    agg = aggregate_recall_audit_by_calendar_day_utc(cwd, start_d=start_d, end_d=end_d)
    total_q = sum(int((v or {}).get("queries") or 0) for v in agg.values())
    total_hit = sum(int((v or {}).get("queries_with_hit") or 0) for v in agg.values())
    neg_top = aggregate_negative_recall_queries(cwd, start_d=start_d, end_d=end_d, limit=15)
    neg_total = 0
    sample: list[dict[str, Any]] = []
    p = recall_audit_path(cwd)
    if p.is_file():
        try:
            for raw in p.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict):
                    continue
                sch = str(obj.get("schema_version") or "")
                if sch not in (SCHEMA_NEGATIVE, SCHEMA_VERSION):
                    continue
                ts_raw = obj.get("ts")
                if not isinstance(ts_raw, str):
                    continue
                try:
                    dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                d = dt.astimezone(UTC).date()
                if not (start_d <= d <= end_d):
                    continue
                if sch == SCHEMA_NEGATIVE:
                    neg_total += 1
                elif sch == SCHEMA_VERSION and len(sample) < 12:
                    q = str(obj.get("query") or "").strip()
                    if q:
                        sample.append(
                            {
                                "query": q[:200],
                                "hits_total": int(obj.get("hits_total") or 0),
                                "hit": bool(obj.get("hit")),
                                "ts": ts_raw,
                            },
                        )
        except OSError:
            pass
    return {
        "schema_version": "recall_evaluation_v1",
        "generated_at": clock.isoformat(),
        "window_days": ndays,
        "audit_file": str(recall_audit_path(cwd)),
        "recall_queries_total": total_q,
        "recall_queries_with_hit": total_hit,
        "recall_hit_rate": (float(total_hit) / float(total_q)) if total_q else None,
        "negative_events_total": neg_total,
        "negative_queries_top": neg_top,
        "recall_evaluation_sample": sample,
        "by_day": agg,
    }
