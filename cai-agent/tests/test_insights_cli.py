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


class InsightsCliTests(unittest.TestCase):
    def test_insights_json_aggregates_recent_sessions(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            save_session(
                str(root / ".cai-session-a.json"),
                {
                    "version": 2,
                    "model": "model-a",
                    "total_tokens": 100,
                    "error_count": 0,
                    "messages": [
                        {
                            "role": "user",
                            "content": json.dumps({"tool": "read_file", "result": "ok"}),
                        },
                    ],
                },
            )
            save_session(
                str(root / ".cai-session-b.json"),
                {
                    "version": 2,
                    "model": "model-b",
                    "total_tokens": 50,
                    "error_count": 2,
                    "messages": [
                        {
                            "role": "user",
                            "content": json.dumps({"tool": "search_text", "result": "error: failed"}),
                        },
                    ],
                },
            )
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["insights", "--json", "--days", "7", "--limit", "10"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "1.1")
            self.assertEqual(payload.get("sessions_in_window"), 2)
            self.assertEqual(payload.get("total_tokens"), 150)
            self.assertEqual(payload.get("tool_calls_total"), 2)
            self.assertEqual(payload.get("parse_skipped"), 0)
            self.assertAlmostEqual(float(payload.get("failure_rate", 0.0)), 0.5, places=3)
            models_top = payload.get("models_top") or []
            tools_top = payload.get("tools_top") or []
            self.assertTrue(any(row.get("model") == "model-a" for row in models_top))
            self.assertTrue(any(row.get("tool") == "read_file" for row in tools_top))
            self.assertTrue(any(row.get("tool") == "search_text" for row in tools_top))

    def test_insights_fail_on_max_failure_rate(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            save_session(
                str(root / ".cai-session-a.json"),
                {
                    "version": 2,
                    "model": "model-a",
                    "total_tokens": 100,
                    "error_count": 0,
                    "messages": [],
                },
            )
            save_session(
                str(root / ".cai-session-b.json"),
                {
                    "version": 2,
                    "model": "model-b",
                    "total_tokens": 50,
                    "error_count": 2,
                    "messages": [],
                },
            )
            buf_ok = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf_ok):
                    rc0 = main(
                        ["insights", "--json", "--days", "7", "--limit", "10", "--fail-on-max-failure-rate", "0.6"],
                    )
            self.assertEqual(rc0, 0)

            buf_bad = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf_bad):
                    rc2 = main(
                        ["insights", "--json", "--days", "7", "--limit", "10", "--fail-on-max-failure-rate", "0.5"],
                    )
            self.assertEqual(rc2, 2)

