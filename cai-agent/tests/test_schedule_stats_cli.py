from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cai_agent.__main__ import main
from cai_agent.schedule import append_schedule_audit_event, compute_schedule_stats_from_audit


class ScheduleStatsTests(unittest.TestCase):
    def test_compute_stats_from_audit_window(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            append_schedule_audit_event(
                task_id="t-old",
                status="completed",
                action="schedule.run_due",
                cwd=str(root),
                event="task.completed",
                goal_preview="old",
                elapsed_ms=100,
                details={},
            )
            p = root / ".cai-schedule-audit.jsonl"
            lines = p.read_text(encoding="utf-8").splitlines()
            self.assertTrue(lines)
            obj = json.loads(lines[0])
            obj["ts"] = "2000-01-01T00:00:00+00:00"
            p.write_text(json.dumps(obj, ensure_ascii=False) + "\n", encoding="utf-8")

            append_schedule_audit_event(
                task_id="t-new",
                status="completed",
                action="schedule.run_due",
                cwd=str(root),
                event="task.completed",
                goal_preview="new goal",
                elapsed_ms=200,
                details={},
            )
            append_schedule_audit_event(
                task_id="t-new",
                status="retrying",
                action="schedule.run_due",
                cwd=str(root),
                event="task.retrying",
                goal_preview="new goal",
                elapsed_ms=50,
                details={},
            )
            st = compute_schedule_stats_from_audit(cwd=str(root), days=30)
            self.assertEqual(st.get("schema_version"), "schedule_stats_v1")
            tasks = {str(x.get("task_id")): x for x in (st.get("tasks") or [])}
            self.assertNotIn("t-old", tasks)
            self.assertIn("t-new", tasks)
            tn = tasks["t-new"]
            self.assertEqual(tn.get("run_count"), 2)
            self.assertEqual(tn.get("success_count"), 1)
            self.assertEqual(tn.get("fail_count"), 1)
            self.assertAlmostEqual(float(tn.get("success_rate") or 0), 0.5)
            self.assertEqual(tn.get("avg_elapsed_ms"), 125)
            self.assertEqual(tn.get("p95_elapsed_ms"), 200)

    def test_stats_cli_json(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            append_schedule_audit_event(
                task_id="sched-cli",
                status="completed",
                action="schedule.run_due",
                cwd=str(root),
                event="task.completed",
                goal_preview="g",
                elapsed_ms=10,
                details={},
            )
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["schedule", "stats", "--days", "7", "--json"])
            self.assertEqual(rc, 0)
            out = json.loads(buf.getvalue().strip())
            self.assertEqual(out.get("schema_version"), "schedule_stats_v1")
            self.assertEqual(out.get("days"), 7)
            arr = out.get("tasks") or []
            self.assertTrue(any(str(x.get("task_id")) == "sched-cli" for x in arr))

    def test_stats_accepts_v0_audit_without_schema_version(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            legacy = {
                "ts": "2026-04-22T12:00:00+00:00",
                "task_id": "legacy-1",
                "status": "completed",
                "action": "schedule.run_due",
                "details": {"attempts": 1},
            }
            (root / ".cai-schedule-audit.jsonl").write_text(
                json.dumps(legacy, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            st = compute_schedule_stats_from_audit(cwd=str(root), days=365)
            tasks = {str(x.get("task_id")): x for x in (st.get("tasks") or [])}
            self.assertIn("legacy-1", tasks)


if __name__ == "__main__":
    unittest.main()
