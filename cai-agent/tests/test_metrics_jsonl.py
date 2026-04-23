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


if __name__ == "__main__":
    unittest.main()
