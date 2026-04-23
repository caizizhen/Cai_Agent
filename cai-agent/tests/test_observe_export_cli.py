from __future__ import annotations

import csv
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cai_agent.__main__ import main
from cai_agent.observe_export import build_observe_export_v1
from cai_agent.session import save_session


class ObserveExportCliTests(unittest.TestCase):
    def test_observe_export_json_empty_workspace(self) -> None:
        with TemporaryDirectory() as td:
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(td)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "observe",
                            "export",
                            "--format",
                            "json",
                            "--days",
                            "2",
                        ],
                    )
            self.assertEqual(rc, 0)
            doc = json.loads(buf.getvalue().strip())
            self.assertEqual(doc.get("schema_version"), "observe_export_v1")
            rows = doc.get("rows") or []
            self.assertEqual(len(rows), 2)

    def test_observe_export_csv_roundtrip_header(self) -> None:
        with TemporaryDirectory() as td:
            out = Path(td) / "e.csv"
            with patch("cai_agent.__main__.os.getcwd", return_value=str(td)):
                rc = main(
                    [
                        "observe",
                        "export",
                        "--format",
                        "csv",
                        "--days",
                        "1",
                        "-o",
                        str(out),
                    ],
                )
            self.assertEqual(rc, 0)
            self.assertTrue(out.is_file())
            raw = out.read_text(encoding="utf-8")
            rdr = csv.reader(io.StringIO(raw))
            header = next(rdr)
            self.assertIn("schedule_tasks_ok", header)
            self.assertIn("memory_health_score", header)

    def test_observe_export_row_with_session(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            save_session(
                str(root / ".cai-session-a.json"),
                {
                    "version": 2,
                    "total_tokens": 100,
                    "error_count": 0,
                    "messages": [],
                },
            )
            doc = build_observe_export_v1(
                cwd=str(root),
                pattern=".cai-session*.json",
                limit=50,
                days=2,
            )
            today = None
            for r in doc.get("rows") or []:
                if not isinstance(r, dict):
                    continue
                if int(r.get("session_count") or 0) > 0:
                    today = r
                    break
            self.assertIsNotNone(today)
            assert today is not None
            self.assertGreaterEqual(int(today.get("session_count") or 0), 1)


if __name__ == "__main__":
    unittest.main()
