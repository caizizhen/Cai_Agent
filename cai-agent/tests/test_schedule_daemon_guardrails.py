from __future__ import annotations

import io
import json
import os
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cai_agent.__main__ import main


class ScheduleDaemonGuardrailTests(unittest.TestCase):
    def test_daemon_lock_prevents_second_instance(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            lock = root / ".cai-schedule-daemon.lock"
            lock.write_text("12345\n", encoding="utf-8")
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = main(["schedule", "daemon", "--max-cycles", "1", "--json"])
            self.assertEqual(rc, 2)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("ok"), False)
            self.assertEqual(payload.get("error"), "lock_conflict")

    def test_daemon_jsonl_log_written(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                main(
                    [
                        "schedule",
                        "add",
                        "--goal",
                        "log test",
                        "--every-minutes",
                        "1",
                        "--json",
                    ],
                )
            log_path = root / "daemon-events.jsonl"
            with (
                patch("cai_agent.__main__.os.getcwd", return_value=str(root)),
                patch("cai_agent.__main__._execute_scheduled_goal", return_value=(True, "ok")),
            ):
                rc = main(
                    [
                        "schedule",
                        "daemon",
                        "--execute",
                        "--max-cycles",
                        "1",
                        "--json",
                        "--jsonl-log",
                        str(log_path),
                    ],
                )
            self.assertEqual(rc, 0)
            self.assertTrue(log_path.is_file())
            lines = [ln.strip() for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            self.assertTrue(lines)
            events = [json.loads(ln).get("event") for ln in lines]
            self.assertIn("daemon.started", events)
            self.assertTrue(any(e == "task.started" for e in events))
            self.assertTrue(any(e == "task.completed" for e in events))
            self.assertIn("daemon.cycle", events)
            for row in map(json.loads, lines):
                self.assertEqual(row.get("schema_version"), "1.0")
                for k in ("ts", "event", "task_id", "goal_preview", "elapsed_ms", "error", "details"):
                    self.assertIn(k, row)

