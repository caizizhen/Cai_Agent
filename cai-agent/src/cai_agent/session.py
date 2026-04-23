from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cai_agent.session_events import normalize_session_run_events
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


def _tool_error_stats_from_messages(messages: list[Any]) -> tuple[int, dict[str, int]]:
    """从会话 ``messages`` 统计工具调用失败次数（与 ``__main__._collect_tool_stats`` 口径一致）。"""
    err_tools: dict[str, int] = {}
    errors = 0
    for m in messages:
        if not isinstance(m, dict) or m.get("role") != "user":
            continue
        content = m.get("content")
        if not isinstance(content, str):
            continue
        try:
            obj = json.loads(content)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        tn = obj.get("tool")
        if not isinstance(tn, str) or not tn.strip():
            continue
        name = tn.strip()
        result = obj.get("result")
        if isinstance(result, str):
            r = result.lower()
            if (
                "失败" in result
                or "error" in r
                or "exception" in r
                or "traceback" in r
            ):
                errors += 1
                err_tools[name] = err_tools.get(name, 0) + 1
    return errors, err_tools


def build_observe_payload(
    *,
    cwd: str | None = None,
    pattern: str = ".cai-session*.json",
    limit: int = 100,
    since_ts: int | None = None,
    scan_cap: int | None = None,
) -> dict[str, Any]:
    """稳定顶层键集合，供 dashboard / CI 消费。

    ``since_ts``：仅保留会话文件 ``mtime >= since_ts`` 的条目（用于 ``observe report`` 时间窗）。
    ``scan_cap``：当 ``since_ts`` 非空时，从磁盘至多扫描的文件数（默认 ``max(limit*20,200)`` 上限 2000）。
    """
    obs_task = new_task("observe")
    obs_task.status = "running"
    base = Path(cwd or ".").expanduser().resolve()
    if since_ts is not None:
        cap = scan_cap if scan_cap is not None else min(max(limit * 20, 200), 2000)
        raw_files = list_session_files(cwd=cwd, pattern=pattern, limit=cap)
        files = [p for p in raw_files if int(p.stat().st_mtime) >= int(since_ts)][: max(limit, 1)]
    else:
        files = list_session_files(cwd=cwd, pattern=pattern, limit=limit)
    sessions: list[dict[str, Any]] = []
    total_tokens = 0
    prompt_tokens = 0
    completion_tokens = 0
    failed_count = 0
    total_elapsed = 0
    tool_errors_total = 0
    tool_err_acc: dict[str, int] = {}
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
        events_count = len(normalize_session_run_events(ev))
        td = s.get("task")
        task_id: str | None = None
        task_status: str | None = None
        if isinstance(td, dict):
            tid = str(td.get("task_id") or "").strip()
            task_id = tid or None
            st = str(td.get("status") or "").strip().lower()
            task_status = st or None
        try:
            rel_path = str(p.relative_to(base))
        except ValueError:
            rel_path = str(p)
        msgs = s.get("messages")
        if isinstance(msgs, list):
            te, byn = _tool_error_stats_from_messages(msgs)
            tool_errors_total += te
            for k, v in byn.items():
                tool_err_acc[k] = tool_err_acc.get(k, 0) + v
        sessions.append(
            {
                "path": rel_path,
                "mtime": int(p.stat().st_mtime),
                "total_tokens": tt,
                "prompt_tokens": pt,
                "completion_tokens": ct,
                "error_count": ec,
                "elapsed_ms": em,
                "model": model if isinstance(model, str) else None,
                "task_id": task_id,
                "task_status": task_status,
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
    top_err = sorted(tool_err_acc.items(), key=lambda x: -x[1])[:10]
    ag = {
        "total_tokens": total_tokens,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "elapsed_ms_total": total_elapsed,
        "failed_count": failed_count,
        "failure_rate": (float(failed_count) / n) if n else 0.0,
        "run_events_total": run_events_total,
        "sessions_with_events": sessions_with_events,
        "tool_errors_total": int(tool_errors_total),
        "tool_errors_top": [{"tool": k, "errors": v} for k, v in top_err],
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
