from __future__ import annotations

import json
from pathlib import Path

from cai_agent.feedback import append_feedback, list_feedback


def test_feedback_roundtrip(tmp_path: Path) -> None:
    append_feedback(tmp_path, text="hello feedback")
    rows = list_feedback(tmp_path, limit=10)
    assert rows
    assert "hello" in str(rows[-1].get("text") or "")
