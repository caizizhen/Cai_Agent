from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEDULE_SCHEMA_VERSION = "1.1"
SCHEDULE_FILE = ".cai-schedule.json"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def schedule_retry_backoff_seconds(retry_count: int) -> float:
    """S4-01 / SCH-RETRY-004：第 ``retry_count`` 次失败后的退避秒数 ``60 * 2**(retry_count-1)``（retry_count >= 1）。"""
    rc = max(1, int(retry_count))
    return 60.0 * float(2 ** (rc - 1))


def _parse_iso_timestamp(ts_raw: str | None) -> float | None:
    if not isinstance(ts_raw, str) or not ts_raw.strip():
        return None
    try:
        dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return float(dt.timestamp())
    except Exception:
        return None


def _schedule_path(cwd: str | None = None) -> Path:
    base = Path(cwd or ".").expanduser().resolve()
    return base / SCHEDULE_FILE


def load_schedule_doc(cwd: str | None = None) -> dict[str, Any]:
    p = _schedule_path(cwd)
    if not p.is_file():
        return {"schema_version": SCHEDULE_SCHEMA_VERSION, "tasks": []}
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"schema_version": SCHEDULE_SCHEMA_VERSION, "tasks": []}
    tasks = data.get("tasks")
    if not isinstance(tasks, list):
        tasks = []
    return {
        "schema_version": str(data.get("schema_version") or SCHEDULE_SCHEMA_VERSION),
        "tasks": tasks,
    }


def save_schedule_doc(doc: dict[str, Any], cwd: str | None = None) -> None:
    p = _schedule_path(cwd)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def list_schedule_tasks(cwd: str | None = None) -> list[dict[str, Any]]:
    doc = load_schedule_doc(cwd)
    rows = doc.get("tasks")
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            out.append(dict(row))
    return out


def add_schedule_task(
    *,
    goal: str,
    every_minutes: int,
    workspace: str | None = None,
    model: str | None = None,
    depends_on: list[str] | None = None,
    retry_max_attempts: int | None = None,
    retry_backoff_sec: float | None = None,
    max_retries: int | None = None,
    cwd: str | None = None,
) -> dict[str, Any]:
    if every_minutes < 1:
        raise ValueError("every_minutes must be >= 1")
    g = goal.strip()
    if not g:
        raise ValueError("goal 不能为空")
    doc = load_schedule_doc(cwd)
    tasks = doc.get("tasks")
    if not isinstance(tasks, list):
        tasks = []
    deps_clean: list[str] = []
    for dep in (depends_on or []):
        d = str(dep or "").strip()
        if d and d not in deps_clean:
            deps_clean.append(d)
    retry_attempts = int(retry_max_attempts if retry_max_attempts is not None else 1)
    retry_attempts = max(1, min(retry_attempts, 20))
    backoff = float(retry_backoff_sec if retry_backoff_sec is not None else 0.0)
    backoff = max(0.0, min(backoff, 600.0))
    mr = int(max_retries if max_retries is not None else 3)
    mr = max(0, min(mr, 50))
    item = {
        "id": f"sched-{uuid.uuid4().hex[:10]}",
        "goal": g,
        "every_minutes": int(every_minutes),
        "enabled": True,
        "workspace": str(workspace).strip() if isinstance(workspace, str) and workspace.strip() else None,
        "model": str(model).strip() if isinstance(model, str) and model.strip() else None,
        "depends_on": deps_clean,
        "retry_max_attempts": retry_attempts,
        "retry_backoff_sec": backoff,
        "max_retries": mr,
        "retry_count": 0,
        "next_retry_at": None,
        "created_at": _utc_now_iso(),
        "last_run_at": None,
        "last_status": None,
        "last_error": None,
        "run_count": 0,
    }
    tasks.append(item)
    doc["tasks"] = tasks
    doc["schema_version"] = SCHEDULE_SCHEMA_VERSION
    save_schedule_doc(doc, cwd)
    return item


def remove_schedule_task(task_id: str, cwd: str | None = None) -> bool:
    tid = task_id.strip()
    if not tid:
        return False
    doc = load_schedule_doc(cwd)
    tasks = doc.get("tasks")
    if not isinstance(tasks, list):
        return False
    kept = [t for t in tasks if not (isinstance(t, dict) and str(t.get("id") or "") == tid)]
    changed = len(kept) != len(tasks)
    if changed:
        doc["tasks"] = kept
        save_schedule_doc(doc, cwd)
    return changed


def compute_due_tasks(
    *,
    cwd: str | None = None,
    now_ts: float | None = None,
) -> list[dict[str, Any]]:
    now = float(now_ts) if now_ts is not None else time.time()
    rows = list_schedule_tasks(cwd)
    status_by_id: dict[str, str | None] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("id") or "").strip()
        if rid:
            st = row.get("last_status")
            status_by_id[rid] = str(st).strip() if isinstance(st, str) and st.strip() else None
    out: list[dict[str, Any]] = []
    for row in rows:
        enabled = bool(row.get("enabled", True))
        if not enabled:
            continue
        deps = row.get("depends_on")
        if isinstance(deps, list) and deps:
            blocked = False
            for dep in deps:
                dep_id = str(dep or "").strip()
                if not dep_id:
                    continue
                if status_by_id.get(dep_id) != "completed":
                    blocked = True
                    break
            if blocked:
                continue
        every_raw = row.get("every_minutes")
        if not isinstance(every_raw, int) or every_raw < 1:
            continue
        last_status_lc = str(row.get("last_status") or "").strip().lower()
        if last_status_lc == "failed_exhausted":
            continue

        last_run_raw = row.get("last_run_at")
        due_interval = False
        last_ts = _parse_iso_timestamp(last_run_raw if isinstance(last_run_raw, str) else None)
        if last_ts is not None:
            due_interval = (now - last_ts) >= (every_raw * 60)
        else:
            due_interval = True

        nra_ts = _parse_iso_timestamp(str(row.get("next_retry_at") or "").strip() or None)
        due_retry = False
        if last_status_lc == "retrying":
            if nra_ts is None:
                due_retry = True
            else:
                due_retry = now >= nra_ts

        if last_status_lc == "retrying":
            due = due_retry
        elif last_status_lc == "failed":
            # 兼容旧版：仅写入 last_status=failed 的任务仍按周期重新尝试
            due = due_interval
        else:
            due = due_interval or due_retry
        if due:
            out.append(row)
    return out


def mark_schedule_task_run(
    *,
    task_id: str,
    status: str,
    error: str | None = None,
    cwd: str | None = None,
) -> bool:
    tid = task_id.strip()
    if not tid:
        return False
    doc = load_schedule_doc(cwd)
    tasks = doc.get("tasks")
    if not isinstance(tasks, list):
        return False
    changed = False
    raw_status = str(status or "unknown").strip()
    raw_lc = raw_status.lower()
    ok_completed = raw_lc in ("completed", "success", "ok")
    for row in tasks:
        if not isinstance(row, dict):
            continue
        if str(row.get("id") or "") != tid:
            continue
        row["last_run_at"] = _utc_now_iso()
        row["last_error"] = (str(error)[:500] if isinstance(error, str) and error else None)
        rc_run = row.get("run_count")
        row["run_count"] = int(rc_run) + 1 if isinstance(rc_run, int) else 1
        if ok_completed:
            row["last_status"] = "completed"
            row["retry_count"] = 0
            row["next_retry_at"] = None
        else:
            mr = row.get("max_retries")
            max_retries = int(mr) if isinstance(mr, int) else 3
            max_retries = max(0, min(max_retries, 50))
            rco = row.get("retry_count")
            retry_count = int(rco) if isinstance(rco, int) else 0
            retry_count = max(0, retry_count + 1)
            row["retry_count"] = retry_count
            if retry_count > max_retries:
                row["last_status"] = "failed_exhausted"
                row["next_retry_at"] = None
            else:
                row["last_status"] = "retrying"
                delay = schedule_retry_backoff_seconds(retry_count)
                row["next_retry_at"] = datetime.fromtimestamp(time.time() + delay, tz=UTC).isoformat()
        changed = True
        break
    if changed:
        save_schedule_doc(doc, cwd)
    return changed


def append_schedule_audit_event(
    *,
    task_id: str,
    status: str,
    action: str,
    cwd: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """向 `.cai-schedule-audit.jsonl` 追加审计记录。"""
    base = Path(cwd or ".").expanduser().resolve()
    p = base / ".cai-schedule-audit.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": _utc_now_iso(),
        "task_id": str(task_id).strip(),
        "status": str(status).strip(),
        "action": str(action).strip(),
        "details": details or {},
    }
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
