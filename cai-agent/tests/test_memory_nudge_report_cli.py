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
    def test_report_json_aggregates_history_and_jumps(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            hist = root / "memory" / "nudge-history.jsonl"
            hist.parent.mkdir(parents=True, exist_ok=True)
            rows = [
                {
                    "schema_version": "1.1",
                    "generated_at": "2099-04-20T00:00:00+00:00",
                    "severity": "low",
                    "recent_sessions": 2,
                    "memory_entries": 8,
                },
                {
                    "schema_version": "1.1",
                    "generated_at": "2099-04-20T12:00:00+00:00",
                    "severity": "medium",
                    "recent_sessions": 5,
                    "memory_entries": 3,
                },
                {
                    "schema_version": "1.1",
                    "generated_at": "2099-04-21T00:00:00+00:00",
                    "severity": "high",
                    "recent_sessions": 9,
                    "memory_entries": 1,
                },
            ]
            hist.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["memory", "nudge-report", "--json", "--limit", "50", "--days", "3650"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "1.2")
            self.assertIn("freshness", payload)
            self.assertIn("health_score", payload)
            self.assertEqual(payload.get("history_total"), 3)
            self.assertEqual((payload.get("severity_counts") or {}).get("high"), 1)
            self.assertEqual((payload.get("severity_counts") or {}).get("medium"), 1)
            self.assertEqual((payload.get("severity_counts") or {}).get("low"), 1)
            self.assertEqual(payload.get("latest_severity"), "high")
            jumps = payload.get("severity_jumps") or []
            self.assertGreaterEqual(len(jumps), 2)

    def test_report_json_with_missing_history(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["memory", "nudge-report", "--json"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "1.2")
            self.assertEqual(payload.get("history_total"), 0)
            self.assertEqual(payload.get("latest_severity"), None)
            self.assertIn("freshness", payload)
            self.assertIn("health_score", payload)

    def test_report_freshness_days_matches_health_window(self) -> None:
        from datetime import UTC, datetime, timedelta

        with TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            mem.mkdir(parents=True, exist_ok=True)
            old = (datetime.now(UTC) - timedelta(days=40)).isoformat()
            new = (datetime.now(UTC) - timedelta(days=3)).isoformat()
            lines = [
                json.dumps(
                    {
                        "id": "o1",
                        "category": "session",
                        "text": "old topic one",
                        "confidence": 0.5,
                        "expires_at": None,
                        "created_at": old,
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "id": "n1",
                        "category": "session",
                        "text": "new topic two",
                        "confidence": 0.5,
                        "expires_at": None,
                        "created_at": new,
                    },
                    ensure_ascii=False,
                ),
            ]
            (mem / "entries.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
            hist = mem / "nudge-history.jsonl"
            hist.write_text(
                json.dumps(
                    {
                        "schema_version": "1.1",
                        "generated_at": "2099-04-20T00:00:00+00:00",
                        "severity": "low",
                        "recent_sessions": 1,
                        "memory_entries": 2,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "memory",
                            "nudge-report",
                            "--json",
                            "--days",
                            "3650",
                            "--freshness-days",
                            "14",
                        ],
                    )
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "1.2")
            self.assertEqual(float(payload.get("freshness") or 0), 0.5)
            self.assertEqual(int(payload.get("freshness_days") or 0), 14)


if __name__ == "__main__":
    unittest.main()
