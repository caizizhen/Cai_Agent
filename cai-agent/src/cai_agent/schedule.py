from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEDULE_SCHEMA_VERSION = "1.1"
SCHEDULE_FILE = ".cai-schedule.json"
SCHEDULE_AUDIT_SCHEMA_VERSION = "1.0"
SCHEDULE_AUDIT_EVENT_NAMES = frozenset(
    {
        "task.started",
        "task.completed",
        "task.failed",
        "task.retrying",
        "task.skipped",
        "daemon.cycle",
        "daemon.started",
    },
)


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


def _task_dep_ids(row: dict[str, Any]) -> list[str]:
    raw = row.get("depends_on")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for dep in raw:
        d = str(dep or "").strip()
        if d and d not in out:
            out.append(d)
    return out


def schedule_tasks_dependency_adjacency(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Directed edges task_id -> dependency_id (task waits for dependency)."""
    adj: dict[str, list[str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        tid = str(row.get("id") or "").strip()
        if not tid:
            continue
        adj[tid] = _task_dep_ids(row)
    return adj


def schedule_dependency_graph_has_cycle(rows: list[dict[str, Any]]) -> bool:
    """True if the depends_on graph contains any directed cycle."""
    adj = schedule_tasks_dependency_adjacency(rows)
    visited: set[str] = set()
    stack: set[str] = set()

    def dfs(u: str) -> bool:
        if u in stack:
            return True
        if u in visited:
            return False
        visited.add(u)
        stack.add(u)
        for v in adj.get(u, []):
            if dfs(v):
                return True
        stack.remove(u)
        return False

    for node in list(adj.keys()):
        if node not in visited:
            if dfs(node):
                return True
    return False


def enrich_schedule_tasks_for_display(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """S4-03：为 list / JSON 输出补充依赖链与阻塞摘要（不写入磁盘）。"""
    known: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        tid = str(row.get("id") or "").strip()
        if tid:
            known[tid] = row
    rev: dict[str, list[str]] = {tid: [] for tid in known}
    for tid, row in known.items():
        for dep in _task_dep_ids(row):
            if dep in known:
                rev[dep].append(tid)
    for k in rev:
        rev[k] = sorted(rev[k])
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        r = dict(row)
        tid = str(r.get("id") or "").strip()
        deps = _task_dep_ids(r)
        dep_statuses: list[dict[str, Any]] = []
        blocked = False
        for dep_id in deps:
            if dep_id not in known:
                dep_statuses.append({"id": dep_id, "last_status": None, "known": False})
                blocked = True
                continue
            st = known[dep_id].get("last_status")
            st_s = str(st).strip() if isinstance(st, str) and st.strip() else None
            dep_statuses.append({"id": dep_id, "last_status": st_s, "known": True})
            if st_s != "completed":
                blocked = True
        r["depends_on_status"] = dep_statuses
        r["dependency_blocked"] = bool(deps) and blocked
        r["dependents"] = sorted(rev.get(tid, [])) if tid else []
        if dep_statuses:
            parts: list[str] = []
            for ds in dep_statuses:
                did = str(ds.get("id") or "")
                if not ds.get("known"):
                    parts.append(f"{did}?")
                else:
                    st = ds.get("last_status") or "none"
                    parts.append(f"{did}({st})")
            r["depends_on_chain"] = " -> ".join(parts)
        else:
            r["depends_on_chain"] = ""
        out.append(r)
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
    item_id = f"sched-{uuid.uuid4().hex[:10]}"
    if item_id in deps_clean:
        raise ValueError("任务不能依赖自身（depends_on 含本任务 id）")
    preview = {
        "id": item_id,
        "goal": g,
        "every_minutes": int(every_minutes),
        "enabled": True,
        "workspace": str(workspace).strip() if isinstance(workspace, str) and workspace.strip() else None,
        "model": str(model).strip() if isinstance(model, str) and model.strip() else None,
        "depends_on": deps_clean,
        "retry_max_attempts": int(retry_max_attempts if retry_max_attempts is not None else 1),
        "retry_backoff_sec": float(retry_backoff_sec if retry_backoff_sec is not None else 0.0),
        "max_retries": int(max_retries if max_retries is not None else 3),
    }
    combined = [t for t in tasks if isinstance(t, dict)] + [preview]
    if schedule_dependency_graph_has_cycle(combined):
        raise ValueError("循环依赖：depends_on 会形成有向环，已拒绝写入")
    retry_attempts = int(retry_max_attempts if retry_max_attempts is not None else 1)
    retry_attempts = max(1, min(retry_attempts, 20))
    backoff = float(retry_backoff_sec if retry_backoff_sec is not None else 0.0)
    backoff = max(0.0, min(backoff, 600.0))
    mr = int(max_retries if max_retries is not None else 3)
    mr = max(0, min(mr, 50))
    item = {
        "id": item_id,
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


def _goal_preview(goal: str | None, limit: int = 120) -> str:
    g = str(goal or "").strip()
    if not g:
        return ""
    if len(g) <= limit:
        return g
    return g[: limit - 1] + "…"


def build_schedule_audit_row(
    *,
    task_id: str,
    status: str,
    action: str,
    details: dict[str, Any] | None = None,
    event: str | None = None,
    goal_preview: str | None = None,
    elapsed_ms: int | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """构建单行审计 JSON（与 ``append_schedule_audit_event`` 写入内容一致）。"""
    det = dict(details or {})
    if isinstance(event, str) and event.strip():
        ev = str(event).strip()
    else:
        ev = _schedule_audit_event_from_legacy(
            action=str(action).strip(),
            status=str(status).strip(),
            details=det,
        )
    if ev not in SCHEDULE_AUDIT_EVENT_NAMES:
        ev = "task.failed"
    tid = str(task_id).strip()
    gp = str(goal_preview).strip() if isinstance(goal_preview, str) else ""
    if not gp and isinstance(det.get("goal_preview"), str):
        gp = str(det.get("goal_preview") or "").strip()
    em = int(elapsed_ms) if isinstance(elapsed_ms, int) and elapsed_ms >= 0 else None
    if em is None and isinstance(det.get("elapsed_ms"), int) and det["elapsed_ms"] >= 0:
        em = int(det["elapsed_ms"])
    err = str(error).strip() if isinstance(error, str) and error.strip() else None
    if err is None and isinstance(det.get("error"), str) and det["error"].strip():
        err = str(det["error"]).strip()[:500]
    return {
        "schema_version": SCHEDULE_AUDIT_SCHEMA_VERSION,
        "ts": _utc_now_iso(),
        "event": ev,
        "task_id": tid,
        "goal_preview": gp,
        "elapsed_ms": em if em is not None else 0,
        "error": err,
        "status": str(status).strip(),
        "action": str(action).strip(),
        "details": det,
    }


def append_schedule_audit_event(
    *,
    task_id: str,
    status: str,
    action: str,
    cwd: str | None = None,
    details: dict[str, Any] | None = None,
    event: str | None = None,
    goal_preview: str | None = None,
    elapsed_ms: int | None = None,
    error: str | None = None,
    mirror_jsonl_path: Path | str | None = None,
) -> None:
    """向 `.cai-schedule-audit.jsonl` 追加一行 **S4-04** 统一 schema（`schema_version`=`SCHEDULE_AUDIT_SCHEMA_VERSION`）。"""
    base = Path(cwd or ".").expanduser().resolve()
    p = base / ".cai-schedule-audit.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    row = build_schedule_audit_row(
        task_id=task_id,
        status=status,
        action=action,
        details=details,
        event=event,
        goal_preview=goal_preview,
        elapsed_ms=elapsed_ms,
        error=error,
    )
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    if mirror_jsonl_path is not None:
        mp = Path(mirror_jsonl_path).expanduser().resolve()
        mp.parent.mkdir(parents=True, exist_ok=True)
        with mp.open("a", encoding="utf-8") as f2:
            f2.write(json.dumps(row, ensure_ascii=False) + "\n")


def _schedule_audit_event_from_legacy(*, action: str, status: str, details: dict[str, Any]) -> str:
    """由旧 action/status 推导 S4-04 `event` 名称。"""
    st = str(status or "").strip().lower()
    act = str(action or "").strip().lower()
    reason = str(details.get("reason") or "").strip().lower()
    if act == "schedule.add":
        return "task.completed"
    if reason == "skipped_due_to_concurrency" or st == "skipped":
        return "task.skipped"
    if st == "retrying":
        return "task.retrying"
    if st == "failed_exhausted":
        return "task.failed"
    if st == "completed":
        return "task.completed"
    if st == "failed":
        return "task.failed"
    if act.startswith("schedule.daemon"):
        return "daemon.started"
    if act.startswith("schedule."):
        return "task.failed"
    return "task.failed"
