from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cai_agent.schedule import (
    add_schedule_task,
    append_schedule_audit_event,
    compute_due_tasks,
    mark_schedule_task_run,
)


class ScheduleDependencyAndAuditTests(unittest.TestCase):
    def test_due_tasks_respect_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            a = add_schedule_task(goal="job-a", every_minutes=1, cwd=str(root))
            b = add_schedule_task(
                goal="job-b",
                every_minutes=1,
                depends_on=[str(a.get("id") or "")],
                cwd=str(root),
            )
            due1 = compute_due_tasks(cwd=str(root))
            ids1 = {str(x.get("id") or "") for x in due1}
            self.assertIn(str(a.get("id") or ""), ids1)
            self.assertNotIn(str(b.get("id") or ""), ids1)

            mark_schedule_task_run(
                task_id=str(a.get("id") or ""),
                status="completed",
                cwd=str(root),
            )
            due2 = compute_due_tasks(cwd=str(root), now_ts=0.0)
            ids2 = {str(x.get("id") or "") for x in due2}
            self.assertIn(str(b.get("id") or ""), ids2)

    def test_append_audit_event_writes_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            append_schedule_audit_event(
                task_id="sched-1",
                status="completed",
                action="schedule.run_due",
                cwd=str(root),
                details={"attempts": 1},
            )
            p = root / ".cai-schedule-audit.jsonl"
            self.assertTrue(p.is_file())
            rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].get("task_id"), "sched-1")
            self.assertEqual(rows[0].get("status"), "completed")
            self.assertEqual(rows[0].get("action"), "schedule.run_due")


if __name__ == "__main__":
    unittest.main()
