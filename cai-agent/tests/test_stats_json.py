from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cai_agent.__main__ import main
from cai_agent.session import save_session


class StatsJsonTests(unittest.TestCase):
    def test_stats_json_schema_and_summaries(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            save_session(
                str(root / ".cai-session-stats.json"),
                {
                    "version": 2,
                    "run_schema_version": "1.0",
                    "goal": "g",
                    "workspace": td,
                    "elapsed_ms": 5,
                    "total_tokens": 10,
                    "prompt_tokens": 6,
                    "completion_tokens": 4,
                    "error_count": 0,
                    "task": {
                        "task_id": "run-stats1234",
                        "type": "run",
                        "status": "completed",
                        "started_at": 0.0,
                        "ended_at": 1.0,
                        "elapsed_ms": 5,
                        "error": None,
                    },
                    "events": [{"e": 1}, {"e": 2}],
                },
            )
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "stats",
                            "--pattern",
                            ".cai-session*.json",
                            "--limit",
                            "10",
                            "--json",
                        ],
                    )
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("stats_schema_version"), "1.0")
            self.assertEqual(payload.get("sessions_count"), 1)
            self.assertEqual(payload.get("run_events_total"), 2)
            self.assertEqual(payload.get("sessions_with_events"), 1)
            self.assertEqual(payload.get("parse_skipped"), 0)
            summ = payload.get("session_summaries") or []
            self.assertEqual(len(summ), 1)
            self.assertEqual(summ[0].get("events_count"), 2)
            self.assertEqual(summ[0].get("task_id"), "run-stats1234")

    def test_stats_json_normalizes_blank_task_id_to_none(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            save_session(
                str(root / ".cai-session-stats-blank-task.json"),
                {
                    "version": 2,
                    "run_schema_version": "1.0",
                    "goal": "g",
                    "workspace": td,
                    "elapsed_ms": 5,
                    "total_tokens": 10,
                    "prompt_tokens": 6,
                    "completion_tokens": 4,
                    "error_count": 0,
                    "task": {
                        "task_id": "   ",
                        "type": "run",
                        "status": "completed",
                        "started_at": 0.0,
                        "ended_at": 1.0,
                        "elapsed_ms": 5,
                        "error": None,
                    },
                    "events": [{"e": 1}],
                },
            )
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "stats",
                            "--pattern",
                            ".cai-session*.json",
                            "--limit",
                            "10",
                            "--json",
                        ],
                    )
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            summ = payload.get("session_summaries") or []
            self.assertEqual(len(summ), 1)
            self.assertIsNone(summ[0].get("task_id"))
