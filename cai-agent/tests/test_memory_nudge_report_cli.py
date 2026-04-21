from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cai_agent.__main__ import main


class MemoryNudgeReportCliTests(unittest.TestCase):
    def test_report_json_aggregates_history(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            hist = root / "memory" / "nudge-history.jsonl"
            hist.parent.mkdir(parents=True, exist_ok=True)
            rows = [
                {
                    "schema_version": "1.0",
                    "generated_at": "2026-04-20T00:00:00+00:00",
                    "severity": "low",
                    "recent_sessions": 2,
                    "memory_entries": 8,
                },
                {
                    "schema_version": "1.0",
                    "generated_at": "2026-04-20T12:00:00+00:00",
                    "severity": "medium",
                    "recent_sessions": 5,
                    "memory_entries": 3,
                },
                {
                    "schema_version": "1.0",
                    "generated_at": "2026-04-21T00:00:00+00:00",
                    "severity": "high",
                    "recent_sessions": 9,
                    "memory_entries": 1,
                },
            ]
            hist.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["memory", "nudge-report", "--json", "--limit", "50"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "1.0")
            self.assertEqual(payload.get("history_total"), 3)
            self.assertEqual((payload.get("severity_counts") or {}).get("high"), 1)
            self.assertEqual((payload.get("severity_counts") or {}).get("medium"), 1)
            self.assertEqual((payload.get("severity_counts") or {}).get("low"), 1)
            self.assertEqual(payload.get("latest_severity"), "high")

    def test_report_json_with_missing_history(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["memory", "nudge-report", "--json"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("history_total"), 0)
            self.assertEqual(payload.get("latest_severity"), None)

