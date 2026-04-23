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


class MetricsJsonlTests(unittest.TestCase):
    def test_observe_summary_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "metrics.jsonl"
            tdir = Path(td) / "ws"
            tdir.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(tdir)):
                    with redirect_stdout(buf):
                        rc = main(["observe", "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            raw = metrics_path.read_text(encoding="utf-8").strip()
            self.assertTrue(raw)
            row = json.loads(raw.splitlines()[-1])
            self.assertEqual(row.get("schema_version"), "metrics_schema_v1")
            self.assertEqual(row.get("module"), "observe")
            self.assertEqual(row.get("event"), "observe.summary")

    def test_observe_report_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "m2.jsonl"
            ws = Path(td) / "ws2"
            ws.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(["observe", "report", "--format", "json", "--days", "1"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("event"), "observe.report")

    def test_memory_health_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "mh.jsonl"
            ws = Path(td) / "wsm"
            (ws / "memory" / "instincts").mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(["memory", "health", "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "memory")
            self.assertEqual(row.get("event"), "memory.health")

    def test_recall_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "rc.jsonl"
            ws = Path(td) / "wsr"
            ws.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(
                            [
                                "recall",
                                "--query",
                                "x",
                                "--days",
                                "7",
                                "--json",
                            ],
                        )
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "recall")
            self.assertEqual(row.get("event"), "recall.query")

    def test_schedule_stats_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "ss.jsonl"
            ws = Path(td) / "wss"
            ws.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(["schedule", "stats", "--json", "--days", "1"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "schedule")
            self.assertEqual(row.get("event"), "schedule.stats")

    def test_gateway_status_appends_metrics_when_env_set(self) -> None:
        with TemporaryDirectory() as td:
            metrics_path = Path(td) / "gw.jsonl"
            ws = Path(td) / "wsg"
            ws.mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch.dict(os.environ, {"CAI_METRICS_JSONL": str(metrics_path)}):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(ws)):
                    with redirect_stdout(buf):
                        rc = main(["gateway", "status", "--json"])
            self.assertEqual(rc, 0)
            json.loads(buf.getvalue().strip())
            row = json.loads(metrics_path.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(row.get("module"), "gateway")
            self.assertEqual(row.get("event"), "gateway.status")


if __name__ == "__main__":
    unittest.main()
