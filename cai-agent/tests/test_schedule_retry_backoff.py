from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cai_agent.schedule import (
    add_schedule_task,
    compute_due_tasks,
    mark_schedule_task_run,
    schedule_retry_backoff_seconds,
)


class ScheduleRetryBackoffTests(unittest.TestCase):
    def test_backoff_seconds_sequence(self) -> None:
        self.assertEqual(schedule_retry_backoff_seconds(1), 60.0)
        self.assertEqual(schedule_retry_backoff_seconds(2), 120.0)
        self.assertEqual(schedule_retry_backoff_seconds(3), 240.0)

    def test_mark_failure_then_retrying_and_next_retry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            job = add_schedule_task(goal="x", every_minutes=60, max_retries=3, cwd=str(root))
            tid = str(job.get("id") or "")
            ok = mark_schedule_task_run(task_id=tid, status="failed", error="e1", cwd=str(root))
            self.assertTrue(ok)
            doc = json.loads((root / ".cai-schedule.json").read_text(encoding="utf-8"))
            row = next(t for t in doc["tasks"] if str(t.get("id")) == tid)
            self.assertEqual(row.get("last_status"), "retrying")
            self.assertEqual(row.get("retry_count"), 1)
            self.assertIsInstance(row.get("next_retry_at"), str)

    def test_compute_due_retrying_respects_next_retry_at(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            job = add_schedule_task(goal="x", every_minutes=60, max_retries=3, cwd=str(root))
            tid = str(job.get("id") or "")
            mark_schedule_task_run(task_id=tid, status="failed", cwd=str(root))
            doc = json.loads((root / ".cai-schedule.json").read_text(encoding="utf-8"))
            row = next(t for t in doc["tasks"] if str(t.get("id")) == tid)
            future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
            row["next_retry_at"] = future
            (root / ".cai-schedule.json").write_text(
                json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            due = compute_due_tasks(cwd=str(root))
            ids = {str(x.get("id") or "") for x in due}
            self.assertNotIn(tid, ids)

            past = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
            row["next_retry_at"] = past
            doc["tasks"] = [row if str(t.get("id")) == tid else t for t in doc["tasks"]]
            (root / ".cai-schedule.json").write_text(
                json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            due2 = compute_due_tasks(cwd=str(root))
            ids2 = {str(x.get("id") or "") for x in due2}
            self.assertIn(tid, ids2)

    def test_max_retries_zero_exhausts_on_first_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            job = add_schedule_task(goal="x", every_minutes=60, max_retries=0, cwd=str(root))
            tid = str(job.get("id") or "")
            mark_schedule_task_run(task_id=tid, status="failed", cwd=str(root))
            doc = json.loads((root / ".cai-schedule.json").read_text(encoding="utf-8"))
            row = next(t for t in doc["tasks"] if str(t.get("id")) == tid)
            self.assertEqual(row.get("last_status"), "failed_exhausted")
            self.assertEqual(row.get("retry_count"), 1)
            due = compute_due_tasks(cwd=str(root))
            self.assertEqual([x for x in due if str(x.get("id")) == tid], [])

    def test_success_resets_retry_count(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            job = add_schedule_task(goal="x", every_minutes=60, max_retries=3, cwd=str(root))
            tid = str(job.get("id") or "")
            mark_schedule_task_run(task_id=tid, status="failed", cwd=str(root))
            mark_schedule_task_run(task_id=tid, status="completed", cwd=str(root))
            doc = json.loads((root / ".cai-schedule.json").read_text(encoding="utf-8"))
            row = next(t for t in doc["tasks"] if str(t.get("id")) == tid)
            self.assertEqual(row.get("last_status"), "completed")
            self.assertEqual(row.get("retry_count"), 0)
            self.assertIsNone(row.get("next_retry_at"))

    def test_four_failures_exhausted_when_max_retries_three(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            job = add_schedule_task(goal="x", every_minutes=60, max_retries=3, cwd=str(root))
            tid = str(job.get("id") or "")
            for _ in range(3):
                mark_schedule_task_run(task_id=tid, status="failed", cwd=str(root))
            doc = json.loads((root / ".cai-schedule.json").read_text(encoding="utf-8"))
            row = next(t for t in doc["tasks"] if str(t.get("id")) == tid)
            self.assertEqual(row.get("retry_count"), 3)
            self.assertEqual(row.get("last_status"), "retrying")
            mark_schedule_task_run(task_id=tid, status="failed", cwd=str(root))
            doc2 = json.loads((root / ".cai-schedule.json").read_text(encoding="utf-8"))
            row2 = next(t for t in doc2["tasks"] if str(t.get("id")) == tid)
            self.assertEqual(row2.get("last_status"), "failed_exhausted")
            self.assertEqual(row2.get("retry_count"), 4)


if __name__ == "__main__":
    unittest.main()
