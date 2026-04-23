from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cai_agent.memory import (
    append_memory_entry,
    import_memory_entries_bundle,
    validate_memory_entry_row,
)


class MemoryEntryValidateTests(unittest.TestCase):
    def test_validate_extra_field(self) -> None:
        errs = validate_memory_entry_row(
            {
                "id": "a",
                "category": "c",
                "text": "t",
                "confidence": 0.5,
                "expires_at": None,
                "created_at": "2020-01-01T00:00:00+00:00",
                "bad": 1,
            },
        )
        self.assertTrue(any("不允许" in e for e in errs))

    def test_validate_rejects_bool_confidence(self) -> None:
        errs = validate_memory_entry_row(
            {
                "id": "a",
                "category": "c",
                "text": "t",
                "confidence": True,
                "expires_at": None,
                "created_at": "2020-01-01T00:00:00+00:00",
            },
        )
        self.assertTrue(any("confidence" in e for e in errs))

    def test_append_rejects_invalid_row(self) -> None:
        with self.assertRaises(ValueError):
            append_memory_entry(
                ".",
                category="",
                text="x",
                confidence=0.5,
            )

    def test_append_rejects_when_entries_jsonl_has_invalid_line(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            mem.mkdir(parents=True, exist_ok=True)
            (mem / "entries.jsonl").write_text('{"not":"a memory row"}\n', encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                append_memory_entry(root, category="c", text="ok", confidence=0.5)
            self.assertIn("validate-entries", str(ctx.exception))

    def test_append_allowed_when_dirty_guard_env_set(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            mem.mkdir(parents=True, exist_ok=True)
            (mem / "entries.jsonl").write_text('{"not":"a memory row"}\n', encoding="utf-8")
            import os

            prev = os.environ.get("CAI_MEMORY_ALLOW_DIRTY_ENTRIES_JSONL")
            try:
                os.environ["CAI_MEMORY_ALLOW_DIRTY_ENTRIES_JSONL"] = "1"
                append_memory_entry(root, category="c", text="ok", confidence=0.5)
            finally:
                if prev is None:
                    os.environ.pop("CAI_MEMORY_ALLOW_DIRTY_ENTRIES_JSONL", None)
                else:
                    os.environ["CAI_MEMORY_ALLOW_DIRTY_ENTRIES_JSONL"] = prev

    def test_import_rejects_when_existing_entries_jsonl_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem = root / "memory"
            mem.mkdir(parents=True, exist_ok=True)
            (mem / "entries.jsonl").write_text('{"bad":true}\n', encoding="utf-8")
            bundle = {
                "schema_version": "memory_entries_bundle_v1",
                "entries": [
                    {
                        "id": "ok-1",
                        "category": "unit",
                        "text": "row",
                        "confidence": 0.6,
                        "expires_at": None,
                        "created_at": "2022-02-02T00:00:00+00:00",
                    },
                ],
            }
            with self.assertRaises(ValueError):
                import_memory_entries_bundle(root, bundle)
