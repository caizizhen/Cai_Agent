from __future__ import annotations

import unittest

from cai_agent.memory import append_memory_entry, validate_memory_entry_row


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
