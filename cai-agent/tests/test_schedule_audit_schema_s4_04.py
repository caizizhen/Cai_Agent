from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cai_agent.schedule import append_schedule_audit_event


REQUIRED_KEYS = frozenset(
    {"schema_version", "ts", "event", "task_id", "goal_preview", "elapsed_ms", "error", "status", "action", "details"},
)


class ScheduleAuditSchemaS404Tests(unittest.TestCase):
    def test_append_audit_has_required_top_level_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            append_schedule_audit_event(
                task_id="sched-x",
                status="completed",
                action="schedule.run_due",
                cwd=str(root),
                event="task.completed",
                goal_preview="hello world",
                elapsed_ms=42,
                details={"attempts": 1},
            )
            p = root / ".cai-schedule-audit.jsonl"
            row = json.loads(p.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("schema_version"), "1.0")
            self.assertTrue(REQUIRED_KEYS.issubset(row.keys()))
            self.assertEqual(row.get("event"), "task.completed")
            self.assertEqual(row.get("task_id"), "sched-x")
            self.assertEqual(row.get("goal_preview"), "hello world")
            self.assertEqual(row.get("elapsed_ms"), 42)
            self.assertIsNone(row.get("error"))


if __name__ == "__main__":
    unittest.main()
