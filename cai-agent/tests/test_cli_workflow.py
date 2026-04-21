from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

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
                self.assertIn("steps", payload)
                self.assertIn("events", payload)
                self.assertTrue(isinstance(payload["events"], list))
                self.assertIn("task", payload)
                self.assertEqual(payload["task"].get("type"), "workflow")
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


if __name__ == "__main__":
    unittest.main()
