from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def last_workflow_path(root: str | Path | None = None) -> Path:
    base = Path(root or ".").expanduser().resolve()
    return base / ".cai" / "last-workflow.json"


def save_last_workflow_snapshot(
    root: str | Path,
    result: dict[str, Any],
    *,
    workflow_file: str,
) -> Path:
    """将最近一次 workflow 结果写入 `.cai/last-workflow.json`（供 `board` 与 TUI 消费）。"""
    base = Path(root).expanduser().resolve()
    out_dir = base / ".cai"
    out_dir.mkdir(parents=True, exist_ok=True)
    steps_raw = result.get("steps") or []
    slim_steps: list[dict[str, Any]] = []
    if isinstance(steps_raw, list):
        for s in steps_raw:
            if not isinstance(s, dict):
                continue
            goal = str(s.get("goal") or "")
            slim_steps.append(
                {
                    "index": s.get("index"),
                    "name": s.get("name"),
                    "goal": goal[:240],
                    "elapsed_ms": s.get("elapsed_ms"),
                    "finished": s.get("finished"),
                    "error_count": s.get("error_count"),
                    "total_tokens": s.get("total_tokens"),
                },
            )
    doc: dict[str, Any] = {
        "schema_version": "1.0",
        "saved_at": datetime.now(UTC).isoformat(),
        "workflow_file": workflow_file,
        "task": result.get("task"),
        "summary": result.get("summary"),
        "steps": slim_steps,
        "events": result.get("events"),
    }
    target = out_dir / "last-workflow.json"
    target.write_text(
        json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def load_last_workflow_snapshot(root: str | Path | None = None) -> dict[str, Any] | None:
    p = last_workflow_path(root)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def build_board_payload(
    *,
    cwd: str | None = None,
    observe_pattern: str = ".cai-session*.json",
    observe_limit: int = 100,
) -> dict[str, Any]:
    from cai_agent.session import build_observe_payload

    base = Path(cwd or ".").expanduser().resolve()
    obs = build_observe_payload(
        cwd=str(base),
        pattern=observe_pattern,
        limit=observe_limit,
    )
    wf = load_last_workflow_snapshot(base)
    return {
        "schema_version": "board_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(base),
        # 与 `observe --json` 根对象同源：`observe` 键内嵌完整 `build_observe_payload` 结果，
        # 任务看板 / CI 只解析 `board_v1` 时可用本字段快速读取 observe 代际。
        "observe_schema_version": obs.get("schema_version"),
        "observe": obs,
        "last_workflow": wf,
    }


def filter_board_payload(
    payload: dict[str, Any],
    *,
    failed_only: bool = False,
    task_id: str | None = None,
    status_filters: list[str] | None = None,
) -> dict[str, Any]:
    """按最小看板诉求筛选会话行，不改变顶层 schema。"""
    out = dict(payload)
    obs = out.get("observe")
    if not isinstance(obs, dict):
        return out
    sessions = obs.get("sessions")
    if not isinstance(sessions, list):
        return out
    rows = [r for r in sessions if isinstance(r, dict)]
    allowed_status: set[str] = set()
    if isinstance(status_filters, list):
        for st in status_filters:
            s = str(st or "").strip().lower()
            if s in ("pending", "running", "completed", "failed", "unknown"):
                allowed_status.add(s)
    if allowed_status:
        filtered_rows: list[dict[str, Any]] = []
        for r in rows:
            st_raw = str(r.get("task_status") or "").strip().lower()
            ec = int(r.get("error_count") or 0)
            derived = st_raw if st_raw in ("pending", "running", "completed", "failed") else (
                "failed" if ec > 0 else "unknown"
            )
            if derived in allowed_status:
                filtered_rows.append(r)
        rows = filtered_rows
    if failed_only:
        rows = [r for r in rows if int(r.get("error_count") or 0) > 0]
    tid = str(task_id or "").strip()
    if tid:
        rows = [r for r in rows if str(r.get("task_id") or "") == tid]
    obs2 = dict(obs)
    obs2["sessions"] = rows
    obs2["sessions_count"] = len(rows)
    out["observe"] = obs2
    return out


def attach_failed_summary(
    payload: dict[str, Any],
    *,
    limit: int = 5,
) -> dict[str, Any]:
    """附加失败会话摘要，便于快速排障。"""
    out = dict(payload)
    obs = out.get("observe")
    if not isinstance(obs, dict):
        out["failed_summary"] = {"count": 0, "recent": []}
        return out
    sessions = obs.get("sessions")
    if not isinstance(sessions, list):
        out["failed_summary"] = {"count": 0, "recent": []}
        return out
    rows = [r for r in sessions if isinstance(r, dict)]
    failed = [r for r in rows if int(r.get("error_count") or 0) > 0]
    failed.sort(key=lambda r: int(r.get("mtime") or 0), reverse=True)
    recent: list[dict[str, Any]] = []
    for r in failed[: max(limit, 1)]:
        recent.append(
            {
                "path": r.get("path"),
                "task_id": r.get("task_id"),
                "error_count": r.get("error_count"),
                "model": r.get("model"),
                "elapsed_ms": r.get("elapsed_ms"),
            },
        )
    out["failed_summary"] = {
        "count": len(failed),
        "recent": recent,
    }
    return out


def attach_status_summary(payload: dict[str, Any]) -> dict[str, Any]:
    """附加会话状态分布统计，便于看板快速识别运行态。"""
    out = dict(payload)
    obs = out.get("observe")
    if not isinstance(obs, dict):
        empty = {"pending": 0, "running": 0, "completed": 0, "failed": 0}
        out["status_counts"] = dict(empty)
        out["status_summary"] = {"total": 0, "counts": dict(empty)}
        return out
    sessions = obs.get("sessions")
    if not isinstance(sessions, list):
        empty = {"pending": 0, "running": 0, "completed": 0, "failed": 0}
        out["status_counts"] = dict(empty)
        out["status_summary"] = {"total": 0, "counts": dict(empty)}
        return out
    counts = {
        "pending": 0,
        "running": 0,
        "completed": 0,
        "failed": 0,
        "unknown": 0,
    }
    for row in sessions:
        if not isinstance(row, dict):
            continue
        st_raw = str(row.get("task_status") or "").strip().lower()
        ec = int(row.get("error_count") or 0)
        if st_raw in ("pending", "running", "completed", "failed"):
            counts[st_raw] += 1
        elif ec > 0:
            counts["failed"] += 1
        else:
            counts["unknown"] += 1
    out["status_counts"] = dict(counts)
    out["status_summary"] = {
        "total": sum(counts.values()),
        "counts": counts,
    }
    return out


def attach_group_summary(
    payload: dict[str, Any],
    *,
    top_n: int = 5,
) -> dict[str, Any]:
    """附加按模型与任务维度的 TopN 聚合统计。"""
    out = dict(payload)
    obs = out.get("observe")
    if not isinstance(obs, dict):
        out["group_summary"] = {"top_n": max(1, int(top_n)), "models_top": [], "tasks_top": []}
        return out
    sessions = obs.get("sessions")
    if not isinstance(sessions, list):
        out["group_summary"] = {"top_n": max(1, int(top_n)), "models_top": [], "tasks_top": []}
        return out
    rows = [r for r in sessions if isinstance(r, dict)]
    m_counter: Counter[str] = Counter()
    t_counter: Counter[str] = Counter()
    for r in rows:
        model = str(r.get("model") or "").strip() or "unknown"
        task_id = str(r.get("task_id") or "").strip() or "unknown"
        m_counter[model] += 1
        t_counter[task_id] += 1
    n = max(1, int(top_n))
    out["group_summary"] = {
        "top_n": n,
        "models_top": [{"key": k, "count": v} for k, v in m_counter.most_common(n)],
        "tasks_top": [{"key": k, "count": v} for k, v in t_counter.most_common(n)],
    }
    # backward-compatible alias for early adopters
    out["topn_summary"] = {
        "top_n": n,
        "models": list(out["group_summary"]["models_top"]),
        "tasks": list(out["group_summary"]["tasks_top"]),
    }
    return out


def attach_trend_summary(
    payload: dict[str, Any],
    *,
    recent_window: int = 10,
) -> dict[str, Any]:
    """基于最近窗口与历史基线窗口计算趋势对比。"""
    out = dict(payload)
    obs = out.get("observe")
    if not isinstance(obs, dict):
        out["trend_summary"] = {
            "window": max(1, int(recent_window)),
            "recent": {"sessions": 0, "failure_rate": 0.0, "avg_total_tokens": 0.0},
            "baseline": {"sessions": 0, "failure_rate": 0.0, "avg_total_tokens": 0.0},
            "delta": {"failure_rate": 0.0, "avg_total_tokens": 0.0},
        }
        return out
    sessions = obs.get("sessions")
    if not isinstance(sessions, list):
        out["trend_summary"] = {
            "window": max(1, int(recent_window)),
            "recent": {"sessions": 0, "failure_rate": 0.0, "avg_total_tokens": 0.0},
            "baseline": {"sessions": 0, "failure_rate": 0.0, "avg_total_tokens": 0.0},
            "delta": {"failure_rate": 0.0, "avg_total_tokens": 0.0},
        }
        return out
    rows = [r for r in sessions if isinstance(r, dict)]
    rows.sort(key=lambda r: int(r.get("mtime") or 0), reverse=True)
    w = max(1, int(recent_window))
    recent_rows = rows[:w]
    baseline_rows = rows[w : (2 * w)]
    if not baseline_rows:
        baseline_rows = rows[w:]

    def _slice_stats(slice_rows: list[dict[str, Any]]) -> dict[str, float | int]:
        n = len(slice_rows)
        if n <= 0:
            return {"sessions": 0, "failure_rate": 0.0, "avg_total_tokens": 0.0}
        failed = sum(1 for r in slice_rows if int(r.get("error_count") or 0) > 0)
        total_tokens = sum(int(r.get("total_tokens") or 0) for r in slice_rows)
        return {
            "sessions": n,
            "failure_rate": float(failed) / n,
            "avg_total_tokens": float(total_tokens) / n,
        }

    recent = _slice_stats(recent_rows)
    baseline = _slice_stats(baseline_rows)
    out["trend_summary"] = {
        "window": w,
        "recent": recent,
        "baseline": baseline,
        "delta": {
            "failure_rate": float(recent["failure_rate"]) - float(baseline["failure_rate"]),
            "avg_total_tokens": float(recent["avg_total_tokens"]) - float(baseline["avg_total_tokens"]),
        },
    }
    return out
