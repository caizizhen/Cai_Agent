from __future__ import annotations

import io
import json
import os
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cai_agent.__main__ import main
from cai_agent.session import save_session


class RecallCliTests(unittest.TestCase):
    def test_recall_json_matches_keyword_and_sorts_recent_first(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            older = root / ".cai-session-old.json"
            newer = root / ".cai-session-new.json"
            save_session(
                str(older),
                {
                    "version": 2,
                    "model": "m1",
                    "answer": "legacy fix done",
                    "messages": [
                        {"role": "assistant", "content": "legacy fix done in module A"},
                    ],
                },
            )
            save_session(
                str(newer),
                {
                    "version": 2,
                    "model": "m2",
                    "answer": "recent fix applied",
                    "messages": [
                        {"role": "assistant", "content": "recent fix applied in module B"},
                    ],
                },
            )
            # Force deterministic recency ordering while staying inside days window.
            now = int(time.time())
            os.utime(older, (now - 120, now - 120))
            os.utime(newer, (now - 60, now - 60))

            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "recall",
                            "--query",
                            "fix",
                            "--json",
                            "--limit",
                            "10",
                            "--max-hits",
                            "10",
                        ],
                    )
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "1.0")
            results = payload.get("results") or []
            self.assertEqual(len(results), 2)
            # Newest first.
            self.assertTrue(str(results[0].get("path", "")).endswith(".cai-session-new.json"))
            first_hits = results[0].get("hits") or []
            self.assertTrue(first_hits)
            self.assertIn("fix", str(first_hits[0]).lower())

    def test_recall_regex_mode_and_days_filter(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            target = root / ".cai-session-regex.json"
            save_session(
                str(target),
                {
                    "version": 2,
                    "model": "m3",
                    "answer": "deploy: status=ok",
                    "messages": [
                        {"role": "assistant", "content": "deploy: status=ok"},
                    ],
                },
            )
            # Make file too old for days=1.
            now = int(time.time())
            old_ts = now - (60 * 60 * 24 * 10)
            os.utime(target, (old_ts, old_ts))

            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "recall",
                            "--query",
                            r"status=(ok|fail)",
                            "--regex",
                            "--json",
                            "--days",
                            "1",
                        ],
                    )
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("hits_total"), 0)
            self.assertEqual(payload.get("sessions_scanned"), 0)

