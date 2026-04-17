from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cai_agent.task_state import new_task


def save_session(path: str, payload: dict[str, Any]) -> None:
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_session(path: str) -> dict[str, Any]:
    p = Path(path).expanduser().resolve()
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("会话文件根对象必须是 JSON object")
    return data


def list_session_files(
    *,
    cwd: str | None = None,
    pattern: str = ".cai-session*.json",
    limit: int = 50,
) -> list[Path]:
    base = Path(cwd or ".").expanduser().resolve()
    files = [p for p in base.glob(pattern) if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[: max(limit, 1)]


def aggregate_sessions(
    *,
    cwd: str | None = None,
    pattern: str = ".cai-session*.json",
    limit: int = 100,
) -> dict[str, Any]:
    files = list_session_files(cwd=cwd, pattern=pattern, limit=limit)
    sessions_count = 0
    total_elapsed = 0
    total_tokens = 0
    prompt_tokens = 0
    completion_tokens = 0
    failed_count = 0
    for p in files:
        try:
            s = load_session(str(p))
        except Exception:
            continue
        sessions_count += 1
        elapsed = s.get("elapsed_ms")
        if isinstance(elapsed, int):
            total_elapsed += elapsed
        tt = s.get("total_tokens")
        if isinstance(tt, int):
            total_tokens += tt
        pt = s.get("prompt_tokens")
        if isinstance(pt, int):
            prompt_tokens += pt
        ct = s.get("completion_tokens")
        if isinstance(ct, int):
            completion_tokens += ct
        if bool(s.get("error_count", 0)):
            failed_count += 1
    return {
        "sessions_count": sessions_count,
        "elapsed_ms_total": total_elapsed,
        "total_tokens": total_tokens,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "failed_count": failed_count,
        "failure_rate": (float(failed_count) / sessions_count) if sessions_count else 0.0,
    }


def build_observe_payload(
    *,
    cwd: str | None = None,
    pattern: str = ".cai-session*.json",
    limit: int = 100,
) -> dict[str, Any]:
    """稳定顶层键集合，供 dashboard / CI 消费。"""
    obs_task = new_task("observe")
    obs_task.status = "running"
    files = list_session_files(cwd=cwd, pattern=pattern, limit=limit)
    base = Path(cwd or ".").expanduser().resolve()
    sessions: list[dict[str, Any]] = []
    total_tokens = 0
    prompt_tokens = 0
    completion_tokens = 0
    failed_count = 0
    total_elapsed = 0
    for p in files:
        try:
            s = load_session(str(p))
        except Exception:
            continue
        tt = int(s["total_tokens"]) if isinstance(s.get("total_tokens"), int) else 0
        pt = int(s["prompt_tokens"]) if isinstance(s.get("prompt_tokens"), int) else 0
        ct = int(s["completion_tokens"]) if isinstance(s.get("completion_tokens"), int) else 0
        ec = int(s["error_count"]) if isinstance(s.get("error_count"), int) else 0
        total_tokens += tt
        prompt_tokens += pt
        completion_tokens += ct
        if ec > 0:
            failed_count += 1
        em = int(s["elapsed_ms"]) if isinstance(s.get("elapsed_ms"), int) else 0
        total_elapsed += em
        model = s.get("model")
        ev = s.get("events")
        events_count = len(ev) if isinstance(ev, list) else 0
        td = s.get("task")
        task_id = str(td.get("task_id", "")) if isinstance(td, dict) else None
        try:
            rel_path = str(p.relative_to(base))
        except ValueError:
            rel_path = str(p)
        sessions.append(
            {
                "path": rel_path,
                "total_tokens": tt,
                "prompt_tokens": pt,
                "completion_tokens": ct,
                "error_count": ec,
                "elapsed_ms": em,
                "model": model if isinstance(model, str) else None,
                "task_id": task_id,
                "events_count": events_count,
                "run_schema_version": s.get("run_schema_version")
                if isinstance(s.get("run_schema_version"), str)
                else None,
            },
        )
    n = len(sessions)
    run_events_total = sum(int(s.get("events_count") or 0) for s in sessions)
    sessions_with_events = sum(
        1 for s in sessions if int(s.get("events_count") or 0) > 0
    )
    ended = time.time()
    obs_task.ended_at = ended
    obs_task.elapsed_ms = int((ended - obs_task.started_at) * 1000)
    obs_task.status = "completed"
    ag = {
        "total_tokens": total_tokens,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "elapsed_ms_total": total_elapsed,
        "failed_count": failed_count,
        "failure_rate": (float(failed_count) / n) if n else 0.0,
        "run_events_total": run_events_total,
        "sessions_with_events": sessions_with_events,
    }
    events: list[dict[str, Any]] = [
        {
            "event": "observe.summarized",
            "task_id": obs_task.task_id,
            "sessions_count": n,
            "workspace": str(base),
            "aggregates": ag,
        },
    ]
    return {
        "schema_version": "1.1",
        "generated_at": datetime.now(UTC).isoformat(),
        "task": obs_task.to_dict(),
        "events": events,
        "workspace": str(base),
        "pattern": pattern,
        "limit": limit,
        "sessions_count": n,
        "sessions": sessions,
        "aggregates": ag,
    }
