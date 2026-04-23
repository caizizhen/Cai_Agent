from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cai_agent.__main__ import main


class ObserveOpsReportCliTests(unittest.TestCase):
    def test_observe_report_json_empty_workspace(self) -> None:
        with TemporaryDirectory() as td:
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(td)):
                with redirect_stdout(buf):
                    rc = main(["observe", "report", "--format", "json", "--days", "1"])
            self.assertEqual(rc, 0)
            doc = json.loads(buf.getvalue().strip())
            self.assertEqual(doc.get("schema_version"), "1.0")
            self.assertEqual(doc.get("report_kind"), "observe_ops_report_v1")
            self.assertEqual(int(doc.get("session_count", -1)), 0)
            self.assertAlmostEqual(float(doc.get("success_rate") or 0), 1.0)

    def test_observe_report_markdown_empty_workspace(self) -> None:
        with TemporaryDirectory() as td:
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(td)):
                with redirect_stdout(buf):
                    rc = main(["observe", "report", "--format", "markdown", "--days", "2"])
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("# Observe", out)
            self.assertIn("```json", out)

    def test_observe_report_output_file(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            outp = root / "sub" / "r.json"
            with patch("cai_agent.__main__.os.getcwd", return_value=str(td)):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "observe",
                            "report",
                            "--format",
                            "json",
                            "-o",
                            str(outp),
                        ],
                    )
            self.assertEqual(rc, 0)
            self.assertTrue(outp.is_file())
            doc = json.loads(outp.read_text(encoding="utf-8"))
            self.assertEqual(doc.get("schema_version"), "1.0")
            self.assertIn("{", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
