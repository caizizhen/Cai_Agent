from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cai_agent.memory import (
    export_memory_entries_bundle,
    import_memory_entries_bundle,
    validate_memory_entries_bundle,
    validate_memory_entry_row,
)


class MemoryEntriesBundleTests(unittest.TestCase):
    def test_import_rejects_invalid_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = {
                "schema_version": "memory_entries_bundle_v1",
                "entries": [
                    {
                        "id": "1",
                        "category": "c",
                        "text": "t",
                        "confidence": 0.5,
                        "expires_at": None,
                        "created_at": "2020-01-01T00:00:00+00:00",
                    },
                    {
                        "id": "2",
                        "category": "",
                        "text": "x",
                        "confidence": 0.5,
                        "expires_at": None,
                        "created_at": "2020-01-01T00:00:00+00:00",
                    },
                ],
            }
            with self.assertRaises(ValueError):
                import_memory_entries_bundle(root, bundle)
            entries_file = root / "memory" / "entries.jsonl"
            self.assertFalse(entries_file.is_file())

    def test_roundtrip_export_import(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = {
                "id": "e1",
                "category": "unit",
                "text": "hello",
                "confidence": 0.7,
                "expires_at": None,
                "created_at": "2021-06-01T12:00:00+00:00",
            }
            self.assertFalse(validate_memory_entry_row(row))
            import_memory_entries_bundle(
                root,
                {"schema_version": "memory_entries_bundle_v1", "entries": [row]},
            )
            bundle = export_memory_entries_bundle(root)
            self.assertEqual(len(bundle.get("entries")), 1)
            self.assertEqual(bundle["entries"][0]["id"], "e1")

    def test_validate_bundle_rows_reports_entry_index_and_field_errors(self) -> None:
        bundle = {
            "schema_version": "memory_entries_bundle_v1",
            "entries": [
                {
                    "id": "ok",
                    "category": "unit",
                    "text": "hello",
                    "confidence": 0.5,
                    "expires_at": None,
                    "created_at": "2021-01-01T00:00:00+00:00",
                },
                {
                    "id": "",
                    "category": "unit",
                    "text": "bad",
                    "confidence": 2,
                    "expires_at": None,
                    "created_at": "",
                },
            ],
        }
        rows, errors = validate_memory_entries_bundle(bundle)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(errors), 1)
        err = errors[0]
        self.assertEqual(err.get("entry_index"), 2)
        self.assertTrue(isinstance(err.get("errors"), list))
        txt = " ".join(str(x) for x in err.get("errors") or [])
        self.assertIn("id", txt)
        self.assertIn("confidence", txt)


if __name__ == "__main__":
    unittest.main()
