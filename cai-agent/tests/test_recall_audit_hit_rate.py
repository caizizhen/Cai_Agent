"""H1-M-04：recall 审计与 insights cross-domain audit 路径。"""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cai_agent.insights_cross_domain import build_insights_cross_domain_v1
from cai_agent.recall_audit import (
    append_negative_recall_line,
    append_recall_audit_line,
    aggregate_recall_audit_by_calendar_day_utc,
    aggregate_negative_recall_queries,
    build_recall_evaluation_payload,
)


def test_append_and_aggregate_audit() -> None:
    with tempfile.TemporaryDirectory() as td:
        cwd = Path(td)
        append_recall_audit_line(cwd, query="foo", hits_total=2, sessions_scanned=5, sessions_with_hits=1)
        append_recall_audit_line(cwd, query="bar", hits_total=0, sessions_scanned=3, sessions_with_hits=0)
        d = datetime.now(UTC).date()
        agg = aggregate_recall_audit_by_calendar_day_utc(cwd, start_d=d, end_d=d)
        dk = d.isoformat()
        assert dk in agg
        assert agg[dk]["queries"] == 2


def test_insights_prefers_audit_when_present() -> None:
    with tempfile.TemporaryDirectory() as td:
        cwd = Path(td)
        today = datetime.now(UTC).date()
        for _ in range(3):
            append_recall_audit_line(
                cwd,
                query="q",
                hits_total=1,
                sessions_scanned=1,
                sessions_with_hits=1,
            )
        base = {
            "schema_version": "1.1",
            "sessions_in_window": 1,
            "failure_rate": 0.0,
            "total_tokens": 0,
            "tool_calls_total": 0,
        }
        doc = build_insights_cross_domain_v1(
            cwd=str(cwd),
            base_insights=base,
            pattern=".cai-session*.json",
            limit=10,
            days=4,
        )
        assert doc.get("recall_hit_rate_source") == "audit"
        assert doc.get("recall_hit_rate_metric_kind") == "recall_audit"
        trend = doc.get("recall_hit_rate_trend") or []
        assert trend
        assert trend[0].get("metric_kind") == "recall_audit"
        assert isinstance(doc.get("negative_queries_top"), list)


def test_negative_recall_and_evaluation() -> None:
    with tempfile.TemporaryDirectory() as td:
        cwd = Path(td)
        append_recall_audit_line(cwd, query="hitq", hits_total=1, sessions_scanned=2, sessions_with_hits=1)
        append_negative_recall_line(cwd, query="missq", reason="index_empty")
        append_negative_recall_line(cwd, query="missq", reason="index_empty")
        d = datetime.now(UTC).date()
        top = aggregate_negative_recall_queries(cwd, start_d=d, end_d=d, limit=5)
        assert any(x.get("query") == "missq" and int(x.get("count") or 0) >= 2 for x in top)
        ev = build_recall_evaluation_payload(cwd, days=7)
        assert ev.get("schema_version") == "recall_evaluation_v1"
        assert int(ev.get("negative_events_total") or 0) >= 2
        samp = ev.get("recall_evaluation_sample") or []
        assert isinstance(samp, list)
        assert any(isinstance(x, dict) and x.get("query") == "hitq" for x in samp)
