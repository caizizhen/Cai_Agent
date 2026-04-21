from __future__ import annotations

import json
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
