from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cai_agent.__main__ import main
from cai_agent.feedback import (
    append_bug_report,
    append_feedback,
    list_feedback,
    sanitize_feedback_text,
)


def test_feedback_roundtrip(tmp_path: Path) -> None:
    append_feedback(tmp_path, text="hello feedback")
    rows = list_feedback(tmp_path, limit=10)
    assert rows
    assert "hello" in str(rows[-1].get("text") or "")


def test_feedback_stats_json_matches_doctor_feedback(tmp_path: Path) -> None:
    append_feedback(tmp_path, text="stats probe", source="cli")
    buf = io.StringIO()
    with patch("cai_agent.__main__.os.getcwd", return_value=str(tmp_path)):
        with redirect_stdout(buf):
            rc = main(["feedback", "stats", "--json"])
    assert rc == 0
    st = json.loads(buf.getvalue().strip())
    assert st.get("schema_version") == "feedback_stats_v1"
    assert int(st.get("total") or 0) >= 1


def test_feedback_stats_text(tmp_path: Path) -> None:
    buf = io.StringIO()
    with patch("cai_agent.__main__.os.getcwd", return_value=str(tmp_path)):
        with redirect_stdout(buf):
            rc = main(["feedback", "stats"])
    assert rc == 0
    out = buf.getvalue()
    assert "total=0" in out


def test_sanitize_feedback_text_masks_secrets() -> None:
    raw = "token sk-proj-abcdefghijklmnopqrst token2 Bearer abcdefghijklmnop"
    out = sanitize_feedback_text(raw)
    assert "sk-proj-" not in out
    assert "sk-<redacted>" in out
    assert "Bearer <redacted>" in out


def test_feedback_bug_cli_json(tmp_path: Path) -> None:
    buf = io.StringIO()
    with patch("cai_agent.__main__.os.getcwd", return_value=str(tmp_path)):
        with redirect_stdout(buf):
            rc = main(
                [
                    "feedback",
                    "bug",
                    "CLI",
                    "smoke",
                    "case",
                    "--detail",
                    "repro: sk-proj-SECRETKEYHERE",
                    "--category",
                    "ux",
                    "--json",
                ],
            )
    assert rc == 0
    row = json.loads(buf.getvalue().strip())
    assert row.get("schema_version") == "feedback_bug_report_v1"
    assert row.get("category") == "ux"
    assert "sk-proj-" not in str(row.get("detail") or "")
    rows = list_feedback(tmp_path, limit=5)
    assert any(r.get("schema_version") == "feedback_bug_report_v1" for r in rows)


def test_feedback_bug_detail_file(tmp_path: Path) -> None:
    df = tmp_path / "detail.txt"
    df.write_text("steps\nline2", encoding="utf-8")
    buf = io.StringIO()
    with patch("cai_agent.__main__.os.getcwd", return_value=str(tmp_path)):
        with redirect_stdout(buf):
            rc = main(
                [
                    "feedback",
                    "bug",
                    "from",
                    "file",
                    "--detail-file",
                    str(df),
                    "--json",
                ],
            )
    assert rc == 0
    row = json.loads(buf.getvalue().strip())
    assert "steps" in str(row.get("detail") or "")


def test_append_bug_report_invalid_category_falls_back(tmp_path: Path) -> None:
    row = append_bug_report(
        tmp_path,
        summary="x",
        detail="",
        category="not-a-real-category",
        cai_agent_version="9.9.9",
    )
    assert row.get("category") == "other"
