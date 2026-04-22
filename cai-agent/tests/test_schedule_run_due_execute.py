from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cai_agent.__main__ import main


class ScheduleExecuteTests(unittest.TestCase):
    def test_run_due_execute_runs_goal_via_graph(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                rc_add = main(
                    [
                        "schedule",
                        "add",
                        "--goal",
                        "scheduled check",
                        "--every-minutes",
                        "1",
                        "--json",
                    ],
                )
            self.assertEqual(rc_add, 0)

            def fake_build_app(_settings, should_stop=None, progress=None, role="active"):
                class _App:
                    def invoke(self, state):
                        return {
                            "answer": "scheduled-ok",
                            "iteration": 1,
                            "finished": True,
                            "messages": list(state.get("messages") or []),
                        }

                return _App()

            out = io.StringIO()
            with (
                patch("cai_agent.__main__.os.getcwd", return_value=str(root)),
                patch("cai_agent.__main__.build_app", side_effect=fake_build_app),
                patch("cai_agent.__main__.Settings.from_env", return_value=__import__(
                    "cai_agent.config", fromlist=["Settings"],
                ).Settings.from_env(config_path=None)),
                patch("cai_agent.__main__.initial_state", side_effect=lambda _s, goal: {
                    "messages": [
                        {"role": "system", "content": "s"},
                        {"role": "user", "content": goal},
                    ],
                    "iteration": 0,
                    "pending": None,
                    "finished": False,
                }),
            ):
                with redirect_stdout(out):
                    rc = main(["schedule", "run-due", "--execute", "--json"])
            self.assertEqual(rc, 0)
            payload = json.loads(out.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "schedule_run_due_v1")
            self.assertEqual(payload.get("mode"), "execute")
            executed = payload.get("executed") or []
            self.assertTrue(executed)
            self.assertEqual(executed[0].get("ok"), True)
            self.assertEqual(executed[0].get("answer_preview"), "scheduled-ok")
