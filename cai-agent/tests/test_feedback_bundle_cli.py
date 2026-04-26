from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cai_agent.__main__ import main
from cai_agent.feedback import append_feedback


def test_feedback_bundle_cli_exports_redacted_diagnostic_bundle(tmp_path: Path) -> None:
    append_feedback(
        tmp_path,
        text=(
            "token sk-proj-abcdefghijklmnopqrst "
            "email person@example.com "
            f"path {tmp_path}"
        ),
    )
    dest = tmp_path / "dist" / "feedback-bundle.json"
    buf = io.StringIO()
    with patch("cai_agent.__main__.os.getcwd", return_value=str(tmp_path)):
        with redirect_stdout(buf):
            rc = main(["feedback", "bundle", "--dest", str(dest), "--json"])
    assert rc == 0
    out = json.loads(buf.getvalue().strip())
    assert out.get("schema_version") == "feedback_bundle_export_v1"
    assert out.get("bundle_schema_version") == "feedback_bundle_v1"
    assert dest.is_file()
    bundle = json.loads(dest.read_text(encoding="utf-8"))
    assert bundle.get("schema_version") == "feedback_bundle_v1"
    assert bundle.get("workspace") == "<workspace>"
    assert (bundle.get("doctor_summary") or {}).get("schema_version") == "api_doctor_summary_v1"
    assert (bundle.get("repair_plan") or {}).get("schema_version") == "repair_plan_v1"
    blob = json.dumps(bundle, ensure_ascii=False)
    assert "sk-proj-" not in blob
    assert "person@example.com" not in blob
    assert str(tmp_path) not in blob
    assert "<workspace>" in blob


def test_feedback_bundle_warns_when_dest_outside_workspace(tmp_path: Path) -> None:
    append_feedback(tmp_path, text="outside dest probe")
    outside = tmp_path.parent / f"_fb_bundle_{tmp_path.name}.json"
    buf = io.StringIO()
    with patch("cai_agent.__main__.os.getcwd", return_value=str(tmp_path)):
        with redirect_stdout(buf):
            rc = main(["feedback", "bundle", "--dest", str(outside), "--json"])
    assert rc == 0
    out = json.loads(buf.getvalue().strip())
    assert out.get("dest_placement") == "external"
    assert out.get("workspace") == "<workspace>"
    bundle = json.loads(outside.read_text(encoding="utf-8"))
    warns = ((bundle.get("redaction") or {}).get("warnings")) or []
    assert any("bundle_dest_outside_workspace" in str(w) for w in warns)


def test_doctor_json_includes_feedback_triage(tmp_path: Path) -> None:
    buf = io.StringIO()
    with patch("cai_agent.__main__.os.getcwd", return_value=str(tmp_path)):
        with redirect_stdout(buf):
            rc = main(["doctor", "--json"])
    assert rc == 0
    payload = json.loads(buf.getvalue().strip())
    triage = payload.get("feedback_triage")
    assert isinstance(triage, dict)
    assert triage.get("schema_version") == "doctor_feedback_triage_v1"
    flow = triage.get("recommended_flow") or []
    assert any("feedback bundle" in str(item) for item in flow)
