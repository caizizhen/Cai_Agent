from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cai_agent.__main__ import main
from cai_agent.config import Settings


class ScheduleCliTests(unittest.TestCase):
    def test_add_with_retry_and_dependency_fields(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "schedule",
                            "add",
                            "--goal",
                            "task A",
                            "--every-minutes",
                            "10",
                            "--depends-on",
                            "sched-upstream",
                            "--retry-max-attempts",
                            "3",
                            "--retry-backoff-sec",
                            "2.5",
                            "--json",
                        ],
                    )
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("depends_on"), ["sched-upstream"])
            self.assertEqual(payload.get("retry_max_attempts"), 3)
            self.assertEqual(payload.get("retry_backoff_sec"), 2.5)
            self.assertEqual(payload.get("max_retries"), 3)
            self.assertEqual(payload.get("retry_count"), 0)
            self.assertIsNone(payload.get("next_retry_at"))

    def test_add_memory_nudge_template(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            out_file = root / "reports" / "memory-nudge.json"
            buf_add = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf_add):
                    rc_add = main(
                        [
                            "schedule",
                            "add-memory-nudge",
                            "--every-minutes",
                            "60",
                            "--days",
                            "14",
                            "--session-limit",
                            "120",
                            "--output-file",
                            str(out_file),
                            "--fail-on-severity",
                            "high",
                            "--json",
                        ],
                    )
            self.assertEqual(rc_add, 0)
            created = json.loads(buf_add.getvalue().strip())
            self.assertEqual(created.get("template"), "memory-nudge")
            job = created.get("job") or {}
            goal = str(created.get("goal") or "")
            self.assertIn("memory nudge", goal)
            self.assertIn("--days 14", goal)
            self.assertIn("--session-limit 120", goal)
            self.assertIn("--write-file", goal)
            self.assertIn("--fail-on-severity high", goal)
            self.assertEqual(job.get("every_minutes"), 60)

    def test_add_list_rm_cycle(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            buf_add = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf_add):
                    rc_add = main(
                        [
                            "schedule",
                            "add",
                            "--goal",
                            "daily audit",
                            "--every-minutes",
                            "5",
                            "--depends-on",
                            "sched-prev",
                            "--retry-max-attempts",
                            "3",
                            "--retry-backoff-sec",
                            "0",
                            "--disabled",
                            "--json",
                        ],
                    )
            self.assertEqual(rc_add, 0)
            created = json.loads(buf_add.getvalue().strip())
            self.assertEqual(created.get("goal"), "daily audit")
            self.assertEqual(created.get("enabled"), False)
            self.assertEqual(created.get("depends_on"), ["sched-prev"])
            self.assertEqual(created.get("retry_max_attempts"), 3)

            buf_list = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf_list):
                    rc_list = main(["schedule", "list", "--json"])
            self.assertEqual(rc_list, 0)
            arr = json.loads(buf_list.getvalue().strip())
            self.assertEqual(len(arr), 1)
            sid = arr[0]["id"]

            buf_rm = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf_rm):
                    rc_rm = main(["schedule", "rm", sid, "--json"])
            self.assertEqual(rc_rm, 0)
            payload = json.loads(buf_rm.getvalue().strip())
            self.assertEqual(payload.get("removed"), True)

    def test_run_due_dry_run_and_execute(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            # Due every minute.
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                main(
                    [
                        "schedule",
                        "add",
                            "--goal",
                            "echo hello",
                            "--every-minutes",
                            "1",
                            "--json",
                        ],
                    )

            buf_dry = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf_dry):
                    rc_dry = main(["schedule", "run-due", "--json"])
            self.assertEqual(rc_dry, 0)
            dry = json.loads(buf_dry.getvalue().strip())
            self.assertEqual(dry.get("schema_version"), "schedule_run_due_v1")
            self.assertEqual(dry.get("mode"), "dry-run")
            self.assertTrue((dry.get("due_jobs") or []))
            self.assertEqual((dry.get("executed") or []), [])

            # Execute mode currently only marks schedule records.
            buf_exec = io.StringIO()
            with (
                patch("cai_agent.__main__.os.getcwd", return_value=str(root)),
                patch("cai_agent.__main__.Settings.from_env", return_value=Settings.from_env(config_path=None)),
                patch("cai_agent.__main__.build_app") as mock_build_app,
                patch("cai_agent.__main__.initial_state") as mock_initial_state,
                patch("cai_agent.__main__.get_usage_counters", return_value={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}),
                patch("cai_agent.__main__.reset_usage_counters"),
            ):
                class _FakeApp:
                    def invoke(self, state):
                        return {
                            "messages": list(state.get("messages") or []),
                            "answer": "ok",
                            "finished": True,
                            "iteration": 1,
                        }

                mock_build_app.return_value = _FakeApp()
                mock_initial_state.side_effect = (
                    lambda _settings, goal: {
                        "messages": [
                            {"role": "system", "content": "s"},
                            {"role": "user", "content": goal},
                        ],
                        "iteration": 0,
                        "pending": None,
                        "finished": False,
                    }
                )
                with redirect_stdout(buf_exec):
                    rc_exec = main(["schedule", "run-due", "--json", "--execute"])
            self.assertEqual(rc_exec, 0)
            ex = json.loads(buf_exec.getvalue().strip())
            self.assertEqual(ex.get("schema_version"), "schedule_run_due_v1")
            self.assertEqual(ex.get("mode"), "execute")
            executed = ex.get("executed") or []
            self.assertTrue(executed)
            self.assertEqual(executed[0].get("ok"), True)
            self.assertEqual(executed[0].get("status"), "completed")
            self.assertEqual(executed[0].get("answer_preview"), "ok")

