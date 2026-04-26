from __future__ import annotations

from pathlib import Path

from cai_agent.feedback import append_feedback, export_feedback_jsonl


def test_export_feedback_jsonl(tmp_path: Path) -> None:
    append_feedback(tmp_path, text="hello export")
    dest = tmp_path / "out.jsonl"
    doc = export_feedback_jsonl(tmp_path, dest=dest)
    assert doc.get("schema_version") == "feedback_export_v1"
    assert doc.get("workspace") == "<workspace>"
    assert int(doc.get("rows") or 0) >= 1
    assert dest.is_file()
    txt = dest.read_text(encoding="utf-8")
    assert "hello export" in txt


def test_export_feedback_jsonl_redacts_secrets_in_rows(tmp_path: Path) -> None:
    append_feedback(tmp_path, text="token sk-proj-abcdefghijklmnopqrst in export")
    dest = tmp_path / "out.jsonl"
    export_feedback_jsonl(tmp_path, dest=dest)
    blob = dest.read_text(encoding="utf-8")
    assert "sk-proj-" not in blob
    assert "sk-<redacted>" in blob
