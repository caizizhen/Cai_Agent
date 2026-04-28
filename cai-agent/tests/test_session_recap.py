from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cai_agent.__main__ import main
from cai_agent.context import build_session_recap_v1
from cai_agent.session import save_session


class SessionRecapTests(unittest.TestCase):
    def test_build_session_recap_v1_schema(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            save_session(
                str(root / ".cai-session-a.json"),
                {
                    "version": 2,
                    "goal": "recap one",
                    "total_tokens": 12,
                    "error_count": 0,
                    "answer": "hello world",
                    "task": {"task_id": "run-abc"},
                },
            )
            payload = build_session_recap_v1(workspace=str(root), limit=10)
            self.assertEqual(payload.get("schema_version"), "session_recap_v1")
            self.assertEqual(payload.get("workspace"), str(root.resolve()))
            self.assertIsInstance(payload.get("sessions"), list)
            self.assertIsInstance(payload.get("summary"), dict)
            self.assertIsInstance(payload.get("replay_commands"), list)
            self.assertTrue(payload.get("replay_commands"))

    def test_sessions_recap_cli_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            save_session(
                str(root / ".cai-session-a.json"),
                {
                    "version": 2,
                    "goal": "cli recap",
                    "total_tokens": 30,
                    "error_count": 1,
                    "answer": "some answer",
                    "task": {"task_id": "run-cli"},
                },
            )
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["sessions", "--recap", "--json", "--limit", "5"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "session_recap_v1")
            summary = payload.get("summary") or {}
            self.assertGreaterEqual(int(summary.get("sessions_parsed") or 0), 1)
            self.assertEqual(int(summary.get("tokens_total") or 0), 30)
