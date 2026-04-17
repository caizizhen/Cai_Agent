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
        "observe": obs,
        "last_workflow": wf,
    }
