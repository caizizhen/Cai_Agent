from __future__ import annotations

from pathlib import Path

from cai_agent.feedback import append_feedback, export_feedback_jsonl


def test_export_feedback_jsonl(tmp_path: Path) -> None:
    append_feedback(tmp_path, text="hello export")
    dest = tmp_path / "out.jsonl"
    doc = export_feedback_jsonl(tmp_path, dest=dest)
    assert doc.get("schema_version") == "feedback_export_v1"
    assert int(doc.get("rows") or 0) >= 1
    assert dest.is_file()
    txt = dest.read_text(encoding="utf-8")
    assert "hello export" in txt
