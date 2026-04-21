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

    def test_board_json_filters_failed_only_and_task_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = os.getcwd()
            try:
                os.chdir(root)
                good = {
                    "version": 2,
                    "run_schema_version": "1.0",
                    "task": {"task_id": "run-ok-123", "type": "run", "status": "completed"},
                    "events": [{"event": "run.started"}, {"event": "run.finished"}],
                    "error_count": 0,
                    "total_tokens": 1,
                    "prompt_tokens": 1,
                    "completion_tokens": 0,
                    "elapsed_ms": 1,
                }
                bad = {
                    "version": 2,
                    "run_schema_version": "1.0",
                    "task": {"task_id": "run-bad-999", "type": "run", "status": "failed"},
                    "events": [{"event": "run.started"}, {"event": "run.finished"}],
                    "error_count": 1,
                    "total_tokens": 2,
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "elapsed_ms": 2,
                }
                (root / ".cai-session-good.json").write_text(json.dumps(good), encoding="utf-8")
                (root / ".cai-session-bad.json").write_text(json.dumps(bad), encoding="utf-8")

                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = main(["board", "--json", "--failed-only", "--task-id", "run-bad-999"])
                self.assertEqual(rc, 0)
                payload = json.loads(buf.getvalue().strip())
                obs = payload.get("observe") or {}
                sessions = obs.get("sessions") or []
                self.assertEqual(len(sessions), 1)
                self.assertEqual(sessions[0].get("task_id"), "run-bad-999")
                ag = obs.get("aggregates") or {}
                self.assertEqual(ag.get("failed_count"), 1)
                fs = payload.get("failed_summary") or {}
                self.assertEqual(fs.get("count"), 1)
                recent = fs.get("recent") or []
                self.assertEqual(len(recent), 1)
                self.assertEqual(recent[0].get("task_id"), "run-bad-999")
                self.assertTrue(isinstance(recent[0].get("path"), str))
                self.assertIn("error_count", recent[0])
            finally:
                os.chdir(old)

    def test_board_failed_summary_sorts_by_mtime_and_honors_topn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = os.getcwd()
            try:
                os.chdir(root)
                older = {
                    "version": 2,
                    "run_schema_version": "1.0",
                    "task": {"task_id": "run-fail-old", "type": "run", "status": "failed"},
                    "events": [{"event": "run.started"}, {"event": "run.finished"}],
                    "error_count": 1,
                    "total_tokens": 2,
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "elapsed_ms": 2,
                }
                newer = {
                    "version": 2,
                    "run_schema_version": "1.0",
                    "task": {"task_id": "run-fail-new", "type": "run", "status": "failed"},
                    "events": [{"event": "run.started"}, {"event": "run.finished"}],
                    "error_count": 1,
                    "total_tokens": 3,
                    "prompt_tokens": 2,
                    "completion_tokens": 1,
                    "elapsed_ms": 3,
                }
                old_path = root / ".cai-session-old.json"
                new_path = root / ".cai-session-new.json"
                old_path.write_text(json.dumps(older), encoding="utf-8")
                new_path.write_text(json.dumps(newer), encoding="utf-8")
                os.utime(old_path, (1000, 1000))
                os.utime(new_path, (2000, 2000))

                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = main(["board", "--json", "--failed-top", "1"])
                self.assertEqual(rc, 0)
                payload = json.loads(buf.getvalue().strip())
                fs = payload.get("failed_summary") or {}
                recent = fs.get("recent") or []
                self.assertEqual(len(recent), 1)
                self.assertEqual(recent[0].get("task_id"), "run-fail-new")
            finally:
                os.chdir(old)

    def test_board_json_includes_status_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = os.getcwd()
            try:
                os.chdir(root)
                running = {
                    "version": 2,
                    "run_schema_version": "1.0",
                    "task": {"task_id": "run-running-1", "type": "run", "status": "running"},
                    "events": [{"event": "run.started"}],
                    "error_count": 0,
                    "total_tokens": 1,
                    "prompt_tokens": 1,
                    "completion_tokens": 0,
                    "elapsed_ms": 1,
                }
                completed = {
                    "version": 2,
                    "run_schema_version": "1.0",
                    "task": {"task_id": "run-completed-1", "type": "run", "status": "completed"},
                    "events": [{"event": "run.started"}, {"event": "run.finished"}],
                    "error_count": 0,
                    "total_tokens": 1,
                    "prompt_tokens": 1,
                    "completion_tokens": 0,
                    "elapsed_ms": 1,
                }
                failed = {
                    "version": 2,
                    "run_schema_version": "1.0",
                    "task": {"task_id": "run-failed-1", "type": "run", "status": "failed"},
                    "events": [{"event": "run.started"}, {"event": "run.finished"}],
                    "error_count": 1,
                    "total_tokens": 2,
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "elapsed_ms": 2,
                }
                unknown = {
                    "version": 2,
                    "run_schema_version": "1.0",
                    "events": [{"event": "run.started"}],
                    "error_count": 0,
                    "total_tokens": 1,
                    "prompt_tokens": 1,
                    "completion_tokens": 0,
                    "elapsed_ms": 1,
                }
                (root / ".cai-session-running.json").write_text(json.dumps(running), encoding="utf-8")
                (root / ".cai-session-completed.json").write_text(json.dumps(completed), encoding="utf-8")
                (root / ".cai-session-failed.json").write_text(json.dumps(failed), encoding="utf-8")
                (root / ".cai-session-unknown.json").write_text(json.dumps(unknown), encoding="utf-8")

                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = main(["board", "--json"])
                self.assertEqual(rc, 0)
                payload = json.loads(buf.getvalue().strip())
                status_summary = payload.get("status_summary") or {}
                self.assertEqual(status_summary.get("total"), 4)
                counts = status_summary.get("counts") or {}
                self.assertEqual(counts.get("running"), 1)
                self.assertEqual(counts.get("completed"), 1)
                self.assertEqual(counts.get("failed"), 1)
                self.assertEqual(counts.get("pending"), 0)
                self.assertEqual(counts.get("unknown"), 1)
            finally:
                os.chdir(old)


if __name__ == "__main__":
    unittest.main()
