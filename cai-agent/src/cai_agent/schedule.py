from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEDULE_SCHEMA_VERSION = "1.0"
SCHEDULE_FILE = ".cai-schedule.json"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


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
    item = {
        "id": f"sched-{uuid.uuid4().hex[:10]}",
        "goal": g,
        "every_minutes": int(every_minutes),
        "enabled": True,
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
    out: list[dict[str, Any]] = []
    for row in list_schedule_tasks(cwd):
        enabled = bool(row.get("enabled", True))
        if not enabled:
            continue
        every_raw = row.get("every_minutes")
        if not isinstance(every_raw, int) or every_raw < 1:
            continue
        last_run_raw = row.get("last_run_at")
        due = False
        if isinstance(last_run_raw, str) and last_run_raw.strip():
            try:
                last_ts = datetime.fromisoformat(last_run_raw).timestamp()
            except Exception:
                last_ts = 0.0
            due = (now - last_ts) >= (every_raw * 60)
        else:
            due = True
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
    for row in tasks:
        if not isinstance(row, dict):
            continue
        if str(row.get("id") or "") != tid:
            continue
        row["last_run_at"] = _utc_now_iso()
        row["last_status"] = str(status or "unknown")
        row["last_error"] = (str(error)[:500] if isinstance(error, str) and error else None)
        rc = row.get("run_count")
        row["run_count"] = int(rc) + 1 if isinstance(rc, int) else 1
        changed = True
        break
    if changed:
        save_schedule_doc(doc, cwd)
    return changed
