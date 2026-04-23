"""运营聚合：会话看板 + 调度 SLA + 成本 rollup（CLI `ops dashboard`）。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cai_agent.board_state import attach_failed_summary, attach_status_summary, build_board_payload
from cai_agent.schedule import compute_schedule_stats_from_audit
from cai_agent.session import aggregate_sessions


def build_ops_dashboard_payload(
    *,
    cwd: str | Path | None = None,
    observe_pattern: str = ".cai-session*.json",
    observe_limit: int = 100,
    schedule_days: int = 30,
    audit_path: str | Path | None = None,
    cost_session_limit: int = 200,
) -> dict[str, Any]:
    """``ops_dashboard_v1``：嵌套完整 ``board_v1`` 供既有消费者复用，并附调度与成本摘要。"""
    base = Path(cwd or ".").expanduser().resolve()
    board = build_board_payload(
        cwd=str(base),
        observe_pattern=observe_pattern,
        observe_limit=observe_limit,
    )
    board = attach_status_summary(board)
    board = attach_failed_summary(board, limit=5)
    obs = board.get("observe") if isinstance(board.get("observe"), dict) else {}
    ag = obs.get("aggregates") if isinstance(obs.get("aggregates"), dict) else {}
    schedule_stats = compute_schedule_stats_from_audit(
        cwd=str(base),
        days=int(schedule_days),
        audit_path=audit_path,
    )
    cost_agg = aggregate_sessions(
        cwd=str(base),
        pattern=observe_pattern,
        limit=max(1, int(cost_session_limit)),
    )
    st_tasks = schedule_stats.get("tasks")
    n_sched = len(st_tasks) if isinstance(st_tasks, list) else 0
    return {
        "schema_version": "ops_dashboard_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(base),
        "observe_pattern": observe_pattern,
        "observe_limit": int(observe_limit),
        "schedule_days": int(schedule_days),
        "summary": {
            "sessions_count": int(obs.get("sessions_count", 0) or 0),
            "failure_rate": float(ag.get("failure_rate", 0.0) or 0.0),
            "failed_count": int(ag.get("failed_count", 0) or 0),
            "total_tokens_observe": int(ag.get("total_tokens", 0) or 0),
            "schedule_tasks_in_stats": n_sched,
            "cost_total_tokens": int(cost_agg.get("total_tokens", 0) or 0),
            "cost_failed_count": int(cost_agg.get("failed_count", 0) or 0),
        },
        "board": board,
        "schedule_stats": schedule_stats,
        "cost_aggregate": cost_agg,
    }
