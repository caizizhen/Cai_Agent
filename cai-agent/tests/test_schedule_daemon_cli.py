from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cai_agent.__main__ import main


class ScheduleDaemonCliTests(unittest.TestCase):
    def test_daemon_runs_due_once_with_max_cycles(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                rc_add = main(
                    [
                        "schedule",
                        "add",
                        "--goal",
                        "daemon check",
                        "--every-minutes",
                        "1",
                        "--json",
                    ],
                )
            self.assertEqual(rc_add, 0)

            def fake_sleep(_seconds: float) -> None:
                return None

            with (
                patch("cai_agent.__main__.os.getcwd", return_value=str(root)),
                patch(
                    "cai_agent.__main__._execute_scheduled_goal",
                    return_value=(True, "daemon-ok"),
                ) as exec_goal,
                patch("cai_agent.__main__.time.sleep", side_effect=fake_sleep),
            ):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "schedule",
                            "daemon",
                            "--interval-sec",
                            "1",
                            "--max-cycles",
                            "1",
                            "--execute",
                            "--json",
                        ],
                    )
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("mode"), "daemon")
            self.assertEqual(payload.get("cycles"), 1)
            self.assertEqual(payload.get("total_executed"), 1)
            self.assertEqual(exec_goal.call_count, 1)

    def test_daemon_dry_run_does_not_execute(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                main(
                    [
                        "schedule",
                        "add",
                        "--goal",
                        "dry-run daemon",
                        "--every-minutes",
                        "1",
                        "--json",
                    ],
                )

            with (
                patch("cai_agent.__main__.os.getcwd", return_value=str(root)),
                patch("cai_agent.__main__._execute_scheduled_goal") as exec_goal,
            ):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "schedule",
                            "daemon",
                            "--interval-sec",
                            "1",
                            "--max-cycles",
                            "1",
                            "--json",
                        ],
                    )
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("total_executed"), 0)
            self.assertEqual(exec_goal.call_count, 0)

    def test_daemon_execute_honors_retry_and_writes_audit(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                rc_add = main(
                    [
                        "schedule",
                        "add",
                        "--goal",
                        "retry daemon",
                        "--every-minutes",
                        "1",
                        "--retry-max-attempts",
                        "2",
                        "--retry-backoff-sec",
                        "0",
                        "--json",
                    ],
                )
            self.assertEqual(rc_add, 0)

            calls: list[int] = []

            def _flaky_execute(**_kwargs):
                calls.append(1)
                if len(calls) == 1:
                    return (False, "boom")
                return (True, "ok-after-retry")

            with (
                patch("cai_agent.__main__.os.getcwd", return_value=str(root)),
                patch("cai_agent.__main__._execute_scheduled_goal", side_effect=_flaky_execute),
            ):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "schedule",
                            "daemon",
                            "--interval-sec",
                            "0.2",
                            "--max-cycles",
                            "1",
                            "--execute",
                            "--json",
                        ],
                    )
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("total_executed"), 1)
            results = payload.get("results") or []
            self.assertTrue(results)
            executed = results[0].get("executed") or []
            self.assertTrue(executed)
            self.assertEqual(executed[0].get("ok"), True)
            self.assertEqual(executed[0].get("attempts"), 2)
            self.assertEqual(len(calls), 2)

            audit = root / ".cai-schedule-audit.jsonl"
            self.assertTrue(audit.is_file())
            rows = [
                json.loads(line)
                for line in audit.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertTrue(any(str(r.get("action")) == "schedule.daemon" for r in rows))

