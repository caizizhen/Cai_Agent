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


class RecallIndexCliTests(unittest.TestCase):
    def test_recall_index_build_and_search(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            save_session(
                str(root / ".cai-session-a.json"),
                {
                    "version": 2,
                    "model": "idx-a",
                    "answer": "auth token rotated",
                    "messages": [
                        {"role": "assistant", "content": "auth token rotated for service A"},
                    ],
                },
            )
            save_session(
                str(root / ".cai-session-b.json"),
                {
                    "version": 2,
                    "model": "idx-b",
                    "answer": "build passed",
                    "messages": [
                        {"role": "assistant", "content": "release build passed on CI"},
                    ],
                },
            )
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                buf_build = io.StringIO()
                with redirect_stdout(buf_build):
                    rc_build = main(["recall-index", "build", "--json"])
            self.assertEqual(rc_build, 0)
            build_payload = json.loads(buf_build.getvalue().strip())
            self.assertEqual(build_payload.get("ok"), True)
            self.assertGreaterEqual(int(build_payload.get("sessions_indexed") or 0), 2)

            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                buf_search = io.StringIO()
                with redirect_stdout(buf_search):
                    rc_search = main(["recall-index", "search", "--query", "auth", "--json"])
            self.assertEqual(rc_search, 0)
            search_payload = json.loads(buf_search.getvalue().strip())
            self.assertEqual(search_payload.get("schema_version"), "1.3")
            self.assertEqual(search_payload.get("source"), "index")
            self.assertGreaterEqual(int(search_payload.get("hits_total") or 0), 1)
            self.assertIsNone(search_payload.get("no_hit_reason"))
            self.assertIn("ranking", search_payload)
            rows = search_payload.get("results") or []
            self.assertTrue(rows)
            self.assertIn("score", rows[0])

    def test_recall_index_refresh_skips_unchanged_mtime(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            p = root / ".cai-session-refresh.json"
            save_session(
                str(p),
                {
                    "version": 2,
                    "model": "r1",
                    "messages": [{"role": "assistant", "content": "alpha token"}],
                },
            )
            now = int(time.time())
            os.utime(p, (now - 300, now - 300))
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                main(["recall-index", "build", "--json"])
            buf1 = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf1):
                    main(["recall-index", "refresh", "--json"])
            pl1 = json.loads(buf1.getvalue().strip())
            self.assertEqual(pl1.get("mode"), "incremental")
            self.assertGreaterEqual(int(pl1.get("sessions_skipped_unchanged") or 0), 1)
            self.assertEqual(int(pl1.get("sessions_touched") or 0), 0)

            # Touch file to bump mtime and change content.
            save_session(
                str(p),
                {
                    "version": 2,
                    "model": "r1",
                    "messages": [{"role": "assistant", "content": "beta token"}],
                },
            )
            os.utime(p, (now, now))
            buf2 = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf2):
                    main(["recall-index", "refresh", "--json"])
            pl2 = json.loads(buf2.getvalue().strip())
            self.assertGreaterEqual(int(pl2.get("sessions_touched") or 0), 1)

    def test_recall_index_info_and_clear(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            save_session(
                str(root / ".cai-session-c.json"),
                {
                    "version": 2,
                    "model": "idx-c",
                    "messages": [
                        {"role": "assistant", "content": "deploy completed"},
                    ],
                },
            )
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                main(["recall-index", "build", "--json"])

            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                buf_info = io.StringIO()
                with redirect_stdout(buf_info):
                    rc_info = main(["recall-index", "info", "--json"])
            self.assertEqual(rc_info, 0)
            info_payload = json.loads(buf_info.getvalue().strip())
            self.assertEqual(info_payload.get("ok"), True)
            self.assertIn("index_file", info_payload)
            self.assertIn("recall_index_schema_version", info_payload)

            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                buf_clear = io.StringIO()
                with redirect_stdout(buf_clear):
                    rc_clear = main(["recall-index", "clear", "--json"])
            self.assertEqual(rc_clear, 0)
            clear_payload = json.loads(buf_clear.getvalue().strip())
            self.assertEqual(clear_payload.get("ok"), True)
            self.assertEqual(clear_payload.get("removed"), True)

    def test_recall_index_benchmark_outputs_metrics(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            save_session(
                str(root / ".cai-session-bench.json"),
                {
                    "version": 2,
                    "model": "bench",
                    "answer": "token refresh complete",
                    "messages": [
                        {"role": "assistant", "content": "token refresh complete on env A"},
                    ],
                },
            )
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                main(["recall-index", "build", "--json"])

            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "recall-index",
                            "benchmark",
                            "--query",
                            "token",
                            "--json",
                            "--runs",
                            "2",
                        ],
                    )
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "recall_benchmark_v1")
            self.assertIn("scan", payload)
            self.assertIn("index", payload)
            self.assertIn("comparison", payload)
            comp = payload.get("comparison") or {}
            self.assertIn("speedup_scan_over_index", comp)

    def test_recall_index_search_no_hit_index_empty(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            idx = root / ".cai-recall-index.json"
            idx.write_text(
                json.dumps(
                    {"recall_index_schema_version": "1.1", "entries": []},
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["recall-index", "search", "--query", "x", "--json"])
            self.assertEqual(rc, 0)
            pl = json.loads(buf.getvalue().strip())
            self.assertEqual(pl.get("schema_version"), "1.3")
            self.assertEqual(pl.get("hits_total"), 0)
            self.assertEqual(pl.get("no_hit_reason"), "index_empty")

    def test_recall_index_search_no_hit_pattern(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            save_session(
                str(root / ".cai-session-only.json"),
                {
                    "version": 2,
                    "model": "m",
                    "messages": [{"role": "assistant", "content": "alpha beta"}],
                },
            )
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                main(["recall-index", "build", "--json"])
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["recall-index", "search", "--query", "zzznomatch", "--json"])
            self.assertEqual(rc, 0)
            pl = json.loads(buf.getvalue().strip())
            self.assertEqual(pl.get("no_hit_reason"), "pattern_no_match")
