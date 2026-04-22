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

    def test_board_fail_on_failed_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = os.getcwd()
            try:
                os.chdir(root)
                good = {
                    "version": 2,
                    "run_schema_version": "1.0",
                    "task": {"task_id": "run-ok", "type": "run", "status": "completed"},
                    "events": [{"event": "run.started"}],
                    "error_count": 0,
                    "total_tokens": 1,
                    "prompt_tokens": 1,
                    "completion_tokens": 0,
                    "elapsed_ms": 1,
                }
                bad = {
                    "version": 2,
                    "run_schema_version": "1.0",
                    "task": {"task_id": "run-bad", "type": "run", "status": "failed"},
                    "events": [{"event": "run.started"}],
                    "error_count": 1,
                    "total_tokens": 2,
                    "prompt_tokens": 1,
                    "completion_tokens": 1,
                    "elapsed_ms": 2,
                }
                (root / ".cai-session-good.json").write_text(json.dumps(good), encoding="utf-8")
                (root / ".cai-session-bad.json").write_text(json.dumps(bad), encoding="utf-8")
                rc_fail = main(["board", "--fail-on-failed-sessions"])
                self.assertEqual(rc_fail, 2)
                rc_ok = main(["board", "--json", "--failed-only", "--task-id", "run-ok", "--fail-on-failed-sessions"])
                self.assertEqual(rc_ok, 0)
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

    def test_board_json_includes_model_and_task_top(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = os.getcwd()
            try:
                os.chdir(root)
                rows = [
                    {
                        "name": ".cai-session-a.json",
                        "task_id": "run-t1",
                        "model": "gpt-x",
                        "error_count": 0,
                    },
                    {
                        "name": ".cai-session-b.json",
                        "task_id": "run-t1",
                        "model": "gpt-x",
                        "error_count": 0,
                    },
                    {
                        "name": ".cai-session-c.json",
                        "task_id": "run-t2",
                        "model": "gpt-y",
                        "error_count": 1,
                    },
                ]
                for r in rows:
                    payload = {
                        "version": 2,
                        "run_schema_version": "1.0",
                        "task": {
                            "task_id": r["task_id"],
                            "type": "run",
                            "status": "failed" if r["error_count"] else "completed",
                        },
                        "model": r["model"],
                        "events": [{"event": "run.started"}, {"event": "run.finished"}],
                        "error_count": r["error_count"],
                        "total_tokens": 1,
                        "prompt_tokens": 1,
                        "completion_tokens": 0,
                        "elapsed_ms": 1,
                    }
                    (root / r["name"]).write_text(json.dumps(payload), encoding="utf-8")

                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = main(["board", "--json", "--group-top", "2"])
                self.assertEqual(rc, 0)
                payload = json.loads(buf.getvalue().strip())
                gs = payload.get("group_summary") or {}
                by_model = gs.get("models_top") or []
                by_task = gs.get("tasks_top") or []
                self.assertGreaterEqual(len(by_model), 2)
                self.assertEqual(by_model[0].get("key"), "gpt-x")
                self.assertEqual(by_model[0].get("count"), 2)
                self.assertGreaterEqual(len(by_task), 2)
                self.assertEqual(by_task[0].get("key"), "run-t1")
                self.assertEqual(by_task[0].get("count"), 2)
            finally:
                os.chdir(old)

    def test_board_json_combined_filters_failed_and_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = os.getcwd()
            try:
                os.chdir(root)
                rows = [
                    {
                        "name": ".cai-session-failed.json",
                        "task": {"task_id": "run-f-1", "type": "run", "status": "failed"},
                        "error_count": 1,
                    },
                    {
                        "name": ".cai-session-running.json",
                        "task": {"task_id": "run-r-1", "type": "run", "status": "running"},
                        "error_count": 0,
                    },
                    {
                        "name": ".cai-session-completed.json",
                        "task": {"task_id": "run-c-1", "type": "run", "status": "completed"},
                        "error_count": 0,
                    },
                ]
                for r in rows:
                    payload = {
                        "version": 2,
                        "run_schema_version": "1.0",
                        "task": r["task"],
                        "events": [{"event": "run.started"}, {"event": "run.finished"}],
                        "error_count": r["error_count"],
                        "total_tokens": 1,
                        "prompt_tokens": 1,
                        "completion_tokens": 0,
                        "elapsed_ms": 1,
                    }
                    (root / r["name"]).write_text(json.dumps(payload), encoding="utf-8")

                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = main(["board", "--json", "--failed-only", "--status", "failed,running"])
                self.assertEqual(rc, 0)
                payload = json.loads(buf.getvalue().strip())
                obs = payload.get("observe") or {}
                sessions = obs.get("sessions") or []
                self.assertEqual(len(sessions), 1)
                self.assertEqual(sessions[0].get("task_id"), "run-f-1")
                filters = payload.get("filters") or {}
                status_values = filters.get("status")
                self.assertTrue(isinstance(status_values, list))
                self.assertIn("failed", status_values)
                self.assertIn("running", status_values)
            finally:
                os.chdir(old)

    def test_board_json_includes_trend_window_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = os.getcwd()
            try:
                os.chdir(root)
                rows = [
                    {
                        "name": ".cai-session-old-pass.json",
                        "task": {"task_id": "run-old-pass", "type": "run", "status": "completed"},
                        "error_count": 0,
                        "total_tokens": 10,
                        "mtime": 1000,
                    },
                    {
                        "name": ".cai-session-old-fail.json",
                        "task": {"task_id": "run-old-fail", "type": "run", "status": "failed"},
                        "error_count": 1,
                        "total_tokens": 40,
                        "mtime": 1100,
                    },
                    {
                        "name": ".cai-session-recent-pass.json",
                        "task": {"task_id": "run-recent-pass", "type": "run", "status": "completed"},
                        "error_count": 0,
                        "total_tokens": 20,
                        "mtime": 3000,
                    },
                    {
                        "name": ".cai-session-recent-fail.json",
                        "task": {"task_id": "run-recent-fail", "type": "run", "status": "failed"},
                        "error_count": 1,
                        "total_tokens": 30,
                        "mtime": 3100,
                    },
                ]
                for r in rows:
                    payload = {
                        "version": 2,
                        "run_schema_version": "1.0",
                        "task": r["task"],
                        "events": [{"event": "run.started"}, {"event": "run.finished"}],
                        "error_count": r["error_count"],
                        "total_tokens": r["total_tokens"],
                        "prompt_tokens": 1,
                        "completion_tokens": 0,
                        "elapsed_ms": 1,
                    }
                    p = root / r["name"]
                    p.write_text(json.dumps(payload), encoding="utf-8")
                    os.utime(p, (r["mtime"], r["mtime"]))

                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = main(["board", "--json", "--trend-window", "2"])
                self.assertEqual(rc, 0)
                payload = json.loads(buf.getvalue().strip())
                tr = payload.get("trend_summary") or {}
                recent = tr.get("recent") or {}
                baseline = tr.get("baseline") or {}
                delta = tr.get("delta") or {}
                self.assertEqual(recent.get("sessions"), 2)
                self.assertEqual(baseline.get("sessions"), 2)
                self.assertAlmostEqual(float(recent.get("failure_rate") or 0.0), 0.5, places=6)
                self.assertAlmostEqual(float(baseline.get("failure_rate") or 0.0), 0.5, places=6)
                self.assertAlmostEqual(float(delta.get("failure_rate") or 0.0), 0.0, places=6)
                self.assertAlmostEqual(float(delta.get("avg_tokens_per_session") or 0.0), 0.0, places=6)
            finally:
                os.chdir(old)


if __name__ == "__main__":
    unittest.main()
