from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cai_agent.session import build_observe_payload, save_session


class SessionObserveAggregationTests(unittest.TestCase):
    def test_observe_aggregates_run_events_from_saved_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            save_session(
                str(root / ".cai-session-a.json"),
                {
                    "version": 2,
                    "run_schema_version": "1.0",
                    "goal": "one",
                    "workspace": td,
                    "elapsed_ms": 10,
                    "total_tokens": 100,
                    "prompt_tokens": 60,
                    "completion_tokens": 40,
                    "error_count": 0,
                    "task": {
                        "task_id": "run-aaaaaaaaaa",
                        "type": "run",
                        "status": "completed",
                        "started_at": 0.0,
                        "ended_at": 1.0,
                        "elapsed_ms": 10,
                        "error": None,
                    },
                    "events": [
                        {"event": "run.started", "task_id": "run-aaaaaaaaaa"},
                        {"event": "run.finished", "task_id": "run-aaaaaaaaaa"},
                    ],
                },
            )
            obs = build_observe_payload(cwd=td, pattern=".cai-session*.json", limit=10)
            self.assertEqual(obs.get("sessions_count"), 1)
            ag = obs.get("aggregates") or {}
            self.assertEqual(ag.get("run_events_total"), 2)
            self.assertEqual(ag.get("sessions_with_events"), 1)
            sess = (obs.get("sessions") or [])[0]
            self.assertEqual(sess.get("events_count"), 2)
            self.assertEqual(sess.get("task_id"), "run-aaaaaaaaaa")
            self.assertEqual(sess.get("run_schema_version"), "1.0")

    def test_observe_normalizes_blank_task_id_to_none(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            save_session(
                str(root / ".cai-session-blank-task.json"),
                {
                    "version": 2,
                    "run_schema_version": "1.0",
                    "goal": "blank task id",
                    "workspace": td,
                    "elapsed_ms": 1,
                    "total_tokens": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "error_count": 0,
                    "task": {
                        "task_id": "   ",
                        "type": "run",
                        "status": "completed",
                        "started_at": 0.0,
                        "ended_at": 1.0,
                        "elapsed_ms": 1,
                        "error": None,
                    },
                    "events": [],
                },
            )
            obs = build_observe_payload(cwd=td, pattern=".cai-session*.json", limit=10)
            sess = (obs.get("sessions") or [])[0]
            self.assertIsNone(sess.get("task_id"))
