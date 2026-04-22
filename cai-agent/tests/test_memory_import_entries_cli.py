from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cai_agent.__main__ import main


class MemoryImportEntriesCliTests(unittest.TestCase):
    def test_dry_run_writes_error_report_and_human_summary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bad_bundle = {
                "schema_version": "memory_entries_bundle_v1",
                "entries": [
                    {
                        "id": "ok-1",
                        "category": "unit",
                        "text": "good",
                        "confidence": 0.9,
                        "expires_at": None,
                        "created_at": "2021-01-01T00:00:00+00:00",
                    },
                    {
                        "id": "",
                        "category": "unit",
                        "text": "bad",
                        "confidence": 2.0,
                        "expires_at": None,
                        "created_at": "",
                    },
                ],
            }
            bundle_path = root / "bundle.json"
            bundle_path.write_text(
                json.dumps(bad_bundle, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            report_path = root / "reports" / "invalid.json"
            out = io.StringIO()
            err = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(out), redirect_stderr(err):
                    rc = main(
                        [
                            "memory",
                            "import-entries",
                            str(bundle_path),
                            "--dry-run",
                            "--error-report",
                            str(report_path),
                        ],
                    )
            self.assertEqual(rc, 2)
            payload = json.loads(out.getvalue().strip())
            self.assertTrue(payload.get("dry_run"))
            self.assertEqual(payload.get("validated"), 1)
            self.assertEqual(payload.get("errors_count"), 1)
            self.assertEqual(payload.get("error_report"), str(report_path))
            self.assertTrue(report_path.is_file())
            report_doc = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report_doc.get("schema_version"), "memory_entries_import_errors_v1")
            self.assertEqual(report_doc.get("errors_count"), 1)
            stderr_txt = err.getvalue()
            self.assertIn("导入校验失败", stderr_txt)
            self.assertIn("首个错误", stderr_txt)
            entries_file = root / "memory" / "entries.jsonl"
            self.assertFalse(entries_file.is_file())

    def test_import_entries_rejects_invalid_with_error_report(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bad_bundle = {
                "schema_version": "memory_entries_bundle_v1",
                "entries": [
                    {
                        "id": "ok-1",
                        "category": "unit",
                        "text": "good",
                        "confidence": 0.9,
                        "expires_at": None,
                        "created_at": "2021-01-01T00:00:00+00:00",
                    },
                    {"id": "broken", "category": "unit", "text": "x", "confidence": "nan"},
                ],
            }
            bundle_path = root / "bundle.json"
            bundle_path.write_text(
                json.dumps(bad_bundle, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            report_path = root / "invalid-rows.json"
            out = io.StringIO()
            err = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(out), redirect_stderr(err):
                    rc = main(
                        [
                            "memory",
                            "import-entries",
                            str(bundle_path),
                            "--error-report",
                            str(report_path),
                        ],
                    )
            self.assertEqual(rc, 2)
            self.assertEqual(out.getvalue().strip(), "")
            self.assertTrue(report_path.is_file())
            stderr_txt = err.getvalue()
            self.assertIn("导入校验失败", stderr_txt)
            self.assertIn("详细错误报告已写入", stderr_txt)
            entries_file = root / "memory" / "entries.jsonl"
            self.assertFalse(entries_file.is_file())


if __name__ == "__main__":
    unittest.main()
