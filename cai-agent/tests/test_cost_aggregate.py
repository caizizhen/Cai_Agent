from __future__ import annotations

import json
from pathlib import Path

from cai_agent.cost_aggregate import build_compact_policy_explain_v1, build_cost_by_profile_v1


def test_cost_by_profile_empty_workspace(tmp_path: Path) -> None:
    doc = build_cost_by_profile_v1(tmp_path)
    assert doc.get("schema_version") == "cost_by_profile_v1"
    assert doc.get("empty") is True


def test_cost_by_profile_reads_metrics(tmp_path: Path) -> None:
    cai = tmp_path / ".cai"
    cai.mkdir(parents=True)
    mp = cai / "metrics.jsonl"
    mp.write_text(
        json.dumps(
            {
                "schema_version": "metrics_schema_v1",
                "module": "llm",
                "event": "chat",
                "tokens": 100,
                "active_profile_id": "p1",
                "provider": "openai_compatible",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    doc = build_cost_by_profile_v1(tmp_path, metrics_path=mp)
    assert doc.get("empty") is False
    profs = doc.get("profiles") or []
    assert any(p.get("id") == "p1" for p in profs if isinstance(p, dict))


def test_cost_by_tenant_and_per_day(tmp_path: Path) -> None:
    cai = tmp_path / ".cai"
    cai.mkdir(parents=True)
    mp = cai / "metrics.jsonl"
    line = {
        "schema_version": "metrics_schema_v1",
        "ts": "2026-04-24T12:00:00+00:00",
        "module": "llm",
        "event": "chat",
        "tokens": 50,
        "active_profile_id": "p2",
        "tenant_id": "tenant-a",
    }
    mp.write_text(json.dumps(line, ensure_ascii=False) + "\n", encoding="utf-8")
    doc = build_cost_by_profile_v1(
        tmp_path,
        metrics_path=mp,
        include_by_tenant=True,
        include_by_calendar_day=True,
    )
    bt = doc.get("by_tenant") or []
    assert any(isinstance(x, dict) and x.get("tenant_id") == "tenant-a" for x in bt)
    days = doc.get("by_calendar_day") or {}
    assert days.get("2026-04-24", 0) >= 50


def test_compact_policy_explain_v1() -> None:
    doc = build_compact_policy_explain_v1(
        cost_budget_max_tokens=1000,
        context_compact_after_iterations=4,
        context_compact_min_messages=12,
        context_compact_on_tool_error=True,
        context_compact_after_tool_calls=6,
    )
    assert doc.get("schema_version") == "compact_policy_explain_v1"
    assert doc.get("cost_hint_ratio") == 0.85
    lines = doc.get("lines_zh") or []
    assert isinstance(lines, list) and len(lines) >= 3
    assert any("850" in str(x) or "0.85" in str(x) for x in lines)
