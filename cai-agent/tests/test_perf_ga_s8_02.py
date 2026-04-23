"""Hermes S8-02: GA perf gates (recall 200 thresholds, schedule daemon cycle stability)."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_perf_recall_bench():
    root = _repo_root()
    path = root / "scripts" / "perf_recall_bench.py"
    spec = importlib.util.spec_from_file_location("perf_recall_bench", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load perf_recall_bench")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["perf_recall_bench"] = mod
    spec.loader.exec_module(mod)
    return mod


class PerfGaS802Tests(unittest.TestCase):
    def test_recall_200_scan_and_index_search_under_thresholds(self) -> None:
        mod = _load_perf_recall_bench()
        with TemporaryDirectory() as td:
            row = mod._bench_once(
                Path(td),
                sessions=200,
                runs=3,
                query="keyword",
                days=365,
                limit=500,
                max_hits=50,
                include_refresh=False,
            )
        self.assertTrue(row.get("scan_under_threshold"), row)
        self.assertTrue(row.get("search_under_threshold"), row)

    def test_schedule_daemon_100_cycles_execute_stability(self) -> None:
        from cai_agent.__main__ import main

        with TemporaryDirectory() as td:
            root = Path(td)
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                rc_add = main(
                    [
                        "schedule",
                        "add",
                        "--goal",
                        "perf-ga",
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
                patch("cai_agent.__main__._execute_scheduled_goal", return_value=(True, "ok")),
                patch("cai_agent.__main__.time.sleep", side_effect=fake_sleep),
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
                            "100",
                            "--execute",
                            "--json",
                        ],
                    )
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "schedule_daemon_summary_v1")
            self.assertEqual(payload.get("cycles"), 100)
            self.assertFalse(payload.get("interrupted"))
