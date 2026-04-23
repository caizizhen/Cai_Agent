"""H1-M-01：写入前 memory_entry_v1 校验与 MemoryEntryInvalid。"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from cai_agent.memory import (
    MemoryEntryInvalid,
    append_memory_entry,
    validate_memory_entry_row,
)


def test_validate_rejects_bad_confidence() -> None:
    row = {
        "id": "x",
        "category": "c",
        "text": "t",
        "confidence": 2.0,
        "expires_at": None,
        "created_at": "2020-01-01T00:00:00+00:00",
    }
    errs = validate_memory_entry_row(row)
    assert errs


def test_validate_optional_source_must_be_non_empty_str() -> None:
    row = {
        "id": "x",
        "category": "c",
        "text": "t",
        "confidence": 0.5,
        "expires_at": None,
        "created_at": "2020-01-01T00:00:00+00:00",
        "source": "",
    }
    errs = validate_memory_entry_row(row)
    assert errs


def test_append_raises_memory_entry_invalid() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "memory").mkdir(parents=True, exist_ok=True)
        with pytest.raises(MemoryEntryInvalid):
            append_memory_entry(
                root,
                category="",
                text="hello",
                confidence=0.5,
            )


def test_append_with_source_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        e = append_memory_entry(
            root,
            category="test",
            text="hello world",
            confidence=0.88,
            source="unit_test",
        )
        assert e.id
        raw = (root / "memory" / "entries.jsonl").read_text(encoding="utf-8").strip()
        obj = json.loads(raw)
        assert obj.get("source") == "unit_test"
