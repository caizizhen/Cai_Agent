from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Literal

TaskStatus = Literal["pending", "running", "completed", "failed"]


@dataclass
class TaskState:
    task_id: str
    type: str
    status: TaskStatus
    started_at: float
    ended_at: float | None
    elapsed_ms: int
    error: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "type": self.type,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "elapsed_ms": self.elapsed_ms,
            "error": self.error,
        }


def new_task(task_type: str) -> TaskState:
    now = time.time()
    return TaskState(
        task_id=f"{task_type}-{uuid.uuid4().hex[:10]}",
        type=task_type,
        status="pending",
        started_at=now,
        ended_at=None,
        elapsed_ms=0,
        error=None,
    )
