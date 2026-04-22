from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cai_agent.__main__ import main


class WorkflowCliTests(unittest.TestCase):
    def test_workflow_missing_file_returns_error_code(self) -> None:
        """Regression: workflow command should not crash on missing file."""
        with tempfile.TemporaryDirectory() as tmp:
            missing = str(Path(tmp) / "missing-workflow.json")
            rc = main(["workflow", missing, "--json"])

        self.assertEqual(rc, 2)

    def test_workflow_json_happy_path_in_mock_mode(self) -> None:
        """Workflow should succeed and emit JSON in mock mode."""
        with tempfile.TemporaryDirectory() as tmp:
            wf_path = Path(tmp) / "workflow.json"
            wf_path.write_text(
                json.dumps({"steps": [{"name": "s1", "goal": "test workflow"}]}),
                encoding="utf-8",
            )
            old_mock = os.environ.get("CAI_MOCK")
            os.environ["CAI_MOCK"] = "1"
            try:
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = main(["workflow", str(wf_path), "--json"])
                payload = json.loads(buf.getvalue().strip())
                self.assertEqual(payload.get("schema_version"), "workflow_run_v1")
                self.assertIn("steps", payload)
                self.assertIn("events", payload)
                self.assertTrue(isinstance(payload["events"], list))
                self.assertIn("task", payload)
                self.assertEqual(
                    str(payload.get("task_id") or "").strip(),
                    str((payload.get("task") or {}).get("task_id") or "").strip(),
                )
                self.assertEqual(payload["task"].get("type"), "workflow")
                for ev in payload.get("events") or []:
                    self.assertEqual(ev.get("task_id"), payload["task"].get("task_id"))
                self.assertEqual(payload.get("subagent_io_schema_version"), "1.0")
                self.assertIn("subagent_io", payload)
                self.assertIn("merge", payload.get("subagent_io") or {})
                self.assertTrue(isinstance((payload.get("subagent_io") or {}).get("merge"), dict))
            finally:
                if old_mock is None:
                    os.environ.pop("CAI_MOCK", None)
                else:
                    os.environ["CAI_MOCK"] = old_mock

        self.assertEqual(rc, 0)

    def test_workflow_parallel_group_emits_group_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wf_path = Path(tmp) / "workflow-parallel.json"
            wf_path.write_text(
                json.dumps(
                    {
                        "steps": [
                            {"name": "p1", "goal": "parallel one", "parallel_group": "g1"},
                            {"name": "p2", "goal": "parallel two", "parallel_group": "g1"},
                            {"name": "s1", "goal": "serial tail"},
                        ],
                    },
                ),
                encoding="utf-8",
            )
            old_mock = os.environ.get("CAI_MOCK")
            os.environ["CAI_MOCK"] = "1"
            try:
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = main(["workflow", str(wf_path), "--json"])
                payload = json.loads(buf.getvalue().strip())
            finally:
                if old_mock is None:
                    os.environ.pop("CAI_MOCK", None)
                else:
                    os.environ["CAI_MOCK"] = old_mock
        self.assertEqual(rc, 0)
        summary = payload.get("summary") or {}
        self.assertGreaterEqual(int(summary.get("parallel_groups_count") or 0), 1)
        self.assertGreaterEqual(int(summary.get("parallel_steps_count") or 0), 2)
        self.assertIn("merge_confidence", summary)
        subio = payload.get("subagent_io") or {}
        merge = subio.get("merge") if isinstance(subio, dict) else {}
        self.assertIn("decision", merge)
        self.assertIn("confidence", merge)
        self.assertIn("conflicts", merge)

    def test_workflow_fail_on_step_errors_after_successful_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wf_path = Path(tmp) / "wf.json"
            wf_path.write_text(
                json.dumps({"steps": [{"name": "s1", "goal": "ignored under patch"}]}),
                encoding="utf-8",
            )
            fake = {
                "schema_version": "workflow_run_v1",
                "task": {
                    "task_id": "wf-test",
                    "type": "workflow",
                    "status": "completed",
                },
                "subagent_io_schema_version": "1.0",
                "subagent_io": {"inputs": {}, "merge": {"conflicts": []}, "outputs": []},
                "steps": [{"name": "s1", "index": 1, "error_count": 2}],
                "summary": {
                    "steps_count": 1,
                    "tool_errors_total": 2,
                    "elapsed_ms_total": 1,
                    "elapsed_ms_avg": 1,
                    "tool_calls_total": 0,
                },
                "events": [],
            }
            buf = io.StringIO()
            with patch("cai_agent.__main__.run_workflow", return_value=fake):
                with redirect_stdout(buf):
                    rc = main(["workflow", str(wf_path), "--json", "--fail-on-step-errors"])
            self.assertEqual(rc, 2)
            out = json.loads(buf.getvalue().strip())
            self.assertEqual(out.get("schema_version"), "workflow_run_v1")


if __name__ == "__main__":
    unittest.main()
