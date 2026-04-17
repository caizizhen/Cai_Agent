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
            finally:
                if old_mock is None:
                    os.environ.pop("CAI_MOCK", None)
                else:
                    os.environ["CAI_MOCK"] = old_mock

        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
