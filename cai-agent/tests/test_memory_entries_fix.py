from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from cai_agent.memory import build_memory_entries_jsonl_validate_report, fix_memory_entries_jsonl


def test_fix_memory_entries_drops_invalid() -> None:
    with TemporaryDirectory() as td:
        root = Path(td)
        mem = root / "memory"
        mem.mkdir(parents=True)
        p = mem / "entries.jsonl"
        good = {
            "id": "a1",
            "category": "fact",
            "text": "valid entry text here",
            "confidence": 0.5,
            "expires_at": None,
            "created_at": "2020-01-01T00:00:00+00:00",
        }
        bad = {"id": "", "category": "x", "text": "y", "confidence": 2.0, "created_at": "2020-01-01T00:00:00+00:00"}
        p.write_text(
            json.dumps(good, ensure_ascii=False)
            + "\n"
            + "not json\n"
            + json.dumps(bad, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        rep0 = build_memory_entries_jsonl_validate_report(root)
        assert rep0.get("ok") is False
        fx = fix_memory_entries_jsonl(root, dry_run=False)
        assert fx.get("rewritten") is True
        rep1 = build_memory_entries_jsonl_validate_report(root)
        assert rep1.get("ok") is True
        assert int(rep1.get("valid_lines") or 0) == 1
