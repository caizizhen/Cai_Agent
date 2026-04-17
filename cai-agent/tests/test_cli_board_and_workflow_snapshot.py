from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from cai_agent.__main__ import main


class BoardAndWorkflowSnapshotTests(unittest.TestCase):
    def test_workflow_writes_last_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            wf_path = root / "workflow.json"
            wf_path.write_text(
                json.dumps({"steps": [{"name": "s1", "goal": "test workflow"}]}),
                encoding="utf-8",
            )
            old_cwd = os.getcwd()
            old_mock = os.environ.get("CAI_MOCK")
            os.environ["CAI_MOCK"] = "1"
            try:
                os.chdir(root)
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = main(["workflow", str(wf_path), "--json"])
                self.assertEqual(rc, 0)
                snap = root / ".cai" / "last-workflow.json"
                self.assertTrue(snap.is_file())
                doc = json.loads(snap.read_text(encoding="utf-8"))
                self.assertEqual(doc.get("schema_version"), "1.0")
                self.assertIn("steps", doc)
            finally:
                os.chdir(old_cwd)
                if old_mock is None:
                    os.environ.pop("CAI_MOCK", None)
                else:
                    os.environ["CAI_MOCK"] = old_mock

    def test_board_text_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = os.getcwd()
            try:
                os.chdir(root)
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = main(["board"])
                self.assertEqual(rc, 0)
                out = buf.getvalue()
                self.assertIn("[observe]", out)
                self.assertIn("[last_workflow]", out)
            finally:
                os.chdir(old)


if __name__ == "__main__":
    unittest.main()
