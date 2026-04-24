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
            self.assertEqual(payload.get("schema_version"), "1.3")
            self.assertEqual(payload.get("sort"), "recent")
            self.assertIsNone(payload.get("no_hit_reason"))
            results = payload.get("results") or []
            self.assertEqual(len(results), 2)
            # Newest first.
            self.assertTrue(str(results[0].get("path", "")).endswith(".cai-session-new.json"))
            first_hits = results[0].get("hits") or []
            self.assertTrue(first_hits)
            self.assertIn("fix", str(first_hits[0]).lower())
            self.assertIn("ranking", payload)
            self.assertIn("score", results[0])
            self.assertIn("score_breakdown", results[0])

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
            self.assertEqual(payload.get("no_hit_reason"), "window_too_narrow")

    def test_recall_no_hit_pattern_no_match(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            now = int(time.time())
            p = root / ".cai-session-x.json"
            save_session(
                str(p),
                {
                    "version": 2,
                    "model": "m",
                    "answer": "hello world",
                    "messages": [{"role": "assistant", "content": "hello world"}],
                },
            )
            os.utime(p, (now, now))
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "recall",
                            "--query",
                            "notfoundtoken",
                            "--json",
                            "--days",
                            "30",
                            "--limit",
                            "10",
                        ],
                    )
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "1.3")
            self.assertEqual(payload.get("hits_total"), 0)
            self.assertEqual(payload.get("no_hit_reason"), "pattern_no_match")

    def test_recall_no_hit_all_skipped(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            now = int(time.time())
            p = root / ".cai-session-bad.json"
            p.write_text("{not json", encoding="utf-8")
            os.utime(p, (now, now))
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "recall",
                            "--query",
                            "x",
                            "--json",
                            "--days",
                            "30",
                            "--limit",
                            "10",
                        ],
                    )
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("no_hit_reason"), "all_skipped")

    def test_recall_sort_density_differs_from_recent(self) -> None:
        """S3-01: --sort density prioritizes keyword concentration vs default recent blend."""
        with TemporaryDirectory() as td:
            root = Path(td)
            now = int(time.time())
            dense = root / ".cai-session-dense.json"
            fresh = root / ".cai-session-fresh.json"
            save_session(
                str(dense),
                {
                    "version": 2,
                    "model": "m-old",
                    "answer": "x",
                    "messages": [
                        {
                            "role": "assistant",
                            "content": "needle " * 40 + "padding text so length is non-trivial for density",
                        },
                    ],
                },
            )
            save_session(
                str(fresh),
                {
                    "version": 2,
                    "model": "m-new",
                    "answer": "y",
                    "messages": [
                        {
                            "role": "assistant",
                            "content": "needle once " + ("x" * 500),
                        },
                    ],
                },
            )
            os.utime(dense, (now - 500000, now - 500000))
            os.utime(fresh, (now - 1000, now - 1000))

            def run(sort: str) -> list[str]:
                buf = io.StringIO()
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with redirect_stdout(buf):
                        rc = main(
                            [
                                "recall",
                                "--query",
                                "needle",
                                "--json",
                                "--limit",
                                "10",
                                "--max-hits",
                                "10",
                                "--days",
                                "30",
                                "--sort",
                                sort,
                            ],
                        )
                self.assertEqual(rc, 0)
                payload = json.loads(buf.getvalue().strip())
                rows = payload.get("results") or []
                return [str(r.get("path")) for r in rows if isinstance(r, dict)]

            order_recent = run("recent")
            order_density = run("density")
            self.assertEqual(len(order_recent), 2)
            self.assertEqual(len(order_density), 2)
            self.assertNotEqual(order_recent[0], order_density[0])
            self.assertTrue(order_density[0].endswith("dense.json"))

    def test_recall_evaluate_json_without_query(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["recall", "--evaluate", "--json", "--evaluate-days", "3"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "recall_evaluation_v1")
            self.assertEqual(int(payload.get("window_days") or 0), 3)
            self.assertIn("negative_queries_top", payload)
            self.assertIn("audit_file", payload)

    def test_recall_missing_query_errors(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["recall", "--json", "--days", "1", "--limit", "1"])
            self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
