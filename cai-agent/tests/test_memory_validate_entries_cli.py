from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from pathlib import Path

from cai_agent.__main__ import main


class MemoryValidateEntriesCliTests(unittest.TestCase):
    def test_validate_entries_ok_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            mem.mkdir(parents=True)
            (mem / "entries.jsonl").write_text(
                json.dumps(
                    {
                        "id": "a",
                        "category": "c",
                        "text": "t",
                        "confidence": 0.5,
                        "expires_at": None,
                        "created_at": "2020-01-01T00:00:00+00:00",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["memory", "validate-entries", "--json"])
        self.assertEqual(rc, 0)
        doc = json.loads(buf.getvalue().strip())
        self.assertEqual(doc.get("schema_version"), "memory_entries_file_validate_v1")
        self.assertTrue(doc.get("ok"))

    def test_validate_entries_bad_line_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            mem.mkdir(parents=True)
            (mem / "entries.jsonl").write_text('{"not":"valid"}\n', encoding="utf-8")
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["memory", "validate-entries", "--json"])
        self.assertEqual(rc, 2)
        doc = json.loads(buf.getvalue().strip())
        self.assertFalse(doc.get("ok"))
