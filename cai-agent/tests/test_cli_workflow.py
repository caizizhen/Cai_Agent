from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cai_agent.__main__ import main
from cai_agent.config import Settings
from cai_agent.workflow import run_workflow


class WorkflowCliTests(unittest.TestCase):
    def test_workflow_missing_file_returns_error_code(self) -> None:
        """Regression: workflow command should not crash on missing file."""
        with tempfile.TemporaryDirectory() as tmp:
            missing = str(Path(tmp) / "missing-workflow.json")
            rc = main(["workflow", missing, "--json"])

        self.assertEqual(rc, 2)

    def test_workflow_missing_usage_prints_hints(self) -> None:
        err = io.StringIO()
        with redirect_stderr(err):
            rc = main(["workflow"])
        self.assertEqual(rc, 2)
        self.assertIn("hint: cai-agent workflow --list-templates --json", err.getvalue())

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
                self.assertEqual(payload.get("subagent_io_schema_version"), "1.1")
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
                "subagent_io_schema_version": "1.1",
                "subagent_io": {
                    "inputs": {"steps_count": 1, "merge_strategy": "last_wins", "agent_templates": []},
                    "merge": {"conflicts": []},
                    "outputs": [],
                },
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

    def test_workflow_fail_fast_skips_remaining_steps(self) -> None:
        """S5-03 / SAG-ERR-001: default fail_fast stops after first failing batch."""
        with tempfile.TemporaryDirectory() as tmp:
            wf_path = Path(tmp) / "wf.json"
            wf_path.write_text(
                json.dumps(
                    {
                        "steps": [
                            {"name": "a", "goal": "g1"},
                            {"name": "b", "goal": "g2"},
                            {"name": "c", "goal": "g3"},
                        ],
                    },
                ),
                encoding="utf-8",
            )

            def fake_run_step(settings, raw_step, idx):
                name = str(raw_step.get("name") or "")
                ok = name != "b"
                sr = {
                    "index": idx,
                    "name": name,
                    "goal": str(raw_step.get("goal", "")),
                    "workspace": settings.workspace,
                    "provider": settings.provider,
                    "model": settings.model,
                    "elapsed_ms": 1,
                    "answer": "y" if ok else "n",
                    "finished": ok,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "tool_calls_count": 0,
                    "used_tools": [],
                    "error_count": 0 if ok else 3,
                    "role": "default",
                    "parallel_group": None,
                    "protocol": {
                        "input": {"goal": raw_step.get("goal"), "role": "default", "parallel_group": None},
                        "output": {"answer": "y" if ok else "n"},
                        "error": None if ok else "tool_error_detected",
                    },
                }
                ev = {
                    "event": "workflow.step.completed",
                    "step_index": idx,
                    "name": name,
                    "elapsed_ms": 1,
                    "tool_calls_count": 0,
                    "error_count": sr["error_count"],
                    "parallel_group": None,
                }
                return sr, ev, settings.workspace

            old_mock = os.environ.get("CAI_MOCK")
            os.environ["CAI_MOCK"] = "1"
            try:
                with patch("cai_agent.workflow._run_single_step", side_effect=fake_run_step):
                    settings = Settings.from_env(
                        config_path=None,
                        workspace_hint=str(Path(tmp)),
                    )
                    out = run_workflow(settings, str(wf_path))
            finally:
                if old_mock is None:
                    os.environ.pop("CAI_MOCK", None)
                else:
                    os.environ["CAI_MOCK"] = old_mock

        steps = out.get("steps") or []
        self.assertEqual(len(steps), 3)
        names = [str(s.get("name")) for s in steps]
        self.assertEqual(names, ["a", "b", "c"])
        self.assertFalse(steps[0].get("skipped"))
        self.assertTrue(steps[2].get("skipped"))
        self.assertEqual(steps[2].get("skip_reason"), "fail_fast_prior_batch")
        self.assertEqual(out.get("summary", {}).get("on_error"), "fail_fast")
        self.assertEqual(int(out.get("summary", {}).get("steps_skipped") or 0), 1)
        self.assertEqual(out.get("task", {}).get("error"), "workflow_fail_fast")

    def test_workflow_continue_on_error_runs_all_steps(self) -> None:
        """S5-03 / SAG-ERR-002: continue_on_error runs tail steps after a failure."""
        with tempfile.TemporaryDirectory() as tmp:
            wf_path = Path(tmp) / "wf.json"
            wf_path.write_text(
                json.dumps(
                    {
                        "on_error": "continue_on_error",
                        "steps": [
                            {"name": "a", "goal": "g1"},
                            {"name": "b", "goal": "g2"},
                            {"name": "c", "goal": "g3"},
                        ],
                    },
                ),
                encoding="utf-8",
            )

            def fake_run_step(settings, raw_step, idx):
                name = str(raw_step.get("name") or "")
                ok = name != "b"
                sr = {
                    "index": idx,
                    "name": name,
                    "goal": str(raw_step.get("goal", "")),
                    "workspace": settings.workspace,
                    "provider": settings.provider,
                    "model": settings.model,
                    "elapsed_ms": 1,
                    "answer": "y" if ok else "n",
                    "finished": ok,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "tool_calls_count": 0,
                    "used_tools": [],
                    "error_count": 0 if ok else 2,
                    "role": "default",
                    "parallel_group": None,
                    "protocol": {
                        "input": {"goal": raw_step.get("goal"), "role": "default", "parallel_group": None},
                        "output": {"answer": "y" if ok else "n"},
                        "error": None if ok else "tool_error_detected",
                    },
                }
                ev = {
                    "event": "workflow.step.completed",
                    "step_index": idx,
                    "name": name,
                    "elapsed_ms": 1,
                    "tool_calls_count": 0,
                    "error_count": sr["error_count"],
                    "parallel_group": None,
                }
                return sr, ev, settings.workspace

            old_mock = os.environ.get("CAI_MOCK")
            os.environ["CAI_MOCK"] = "1"
            try:
                with patch("cai_agent.workflow._run_single_step", side_effect=fake_run_step):
                    settings = Settings.from_env(
                        config_path=None,
                        workspace_hint=str(Path(tmp)),
                    )
                    out = run_workflow(settings, str(wf_path))
            finally:
                if old_mock is None:
                    os.environ.pop("CAI_MOCK", None)
                else:
                    os.environ["CAI_MOCK"] = old_mock

        steps = out.get("steps") or []
        self.assertEqual(len(steps), 3)
        self.assertFalse(any(s.get("skipped") for s in steps))
        self.assertEqual(out.get("summary", {}).get("on_error"), "continue_on_error")
        self.assertEqual(int(out.get("summary", {}).get("steps_skipped") or 0), 0)
        self.assertEqual(str(out.get("steps", [{}])[2].get("answer")), "y")

    def test_workflow_on_error_normalizes_dashed_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wf_path = Path(tmp) / "wf.json"
            wf_path.write_text(
                json.dumps(
                    {
                        "on_error": "continue-on-error",
                        "steps": [{"name": "only", "goal": "g"}],
                    },
                ),
                encoding="utf-8",
            )
            old_mock = os.environ.get("CAI_MOCK")
            os.environ["CAI_MOCK"] = "1"
            try:
                with patch("cai_agent.workflow._run_single_step") as m:
                    m.return_value = (
                        {
                            "index": 1,
                            "name": "only",
                            "goal": "g",
                            "workspace": tmp,
                            "provider": "x",
                            "model": "y",
                            "elapsed_ms": 0,
                            "answer": "ok",
                            "finished": True,
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0,
                            "tool_calls_count": 0,
                            "used_tools": [],
                            "error_count": 0,
                            "role": "default",
                            "parallel_group": None,
                            "protocol": {
                                "input": {"goal": "g", "role": "default", "parallel_group": None},
                                "output": {"answer": "ok"},
                                "error": None,
                            },
                        },
                        {
                            "event": "workflow.step.completed",
                            "step_index": 1,
                            "name": "only",
                            "elapsed_ms": 0,
                            "tool_calls_count": 0,
                            "error_count": 0,
                            "parallel_group": None,
                        },
                        str(tmp),
                    )
                    settings = Settings.from_env(
                        config_path=None,
                        workspace_hint=str(Path(tmp)),
                    )
                    out = run_workflow(settings, str(wf_path))
            finally:
                if old_mock is None:
                    os.environ.pop("CAI_MOCK", None)
                else:
                    os.environ["CAI_MOCK"] = old_mock

        self.assertEqual(out.get("summary", {}).get("on_error"), "continue_on_error")

    def test_workflow_budget_max_skips_unstarted_tail(self) -> None:
        """S5-04: after a batch, cumulative total_tokens >= budget skips remaining steps."""
        with tempfile.TemporaryDirectory() as tmp:
            wf_path = Path(tmp) / "wf.json"
            wf_path.write_text(
                json.dumps(
                    {
                        "budget_max_tokens": 50,
                        "steps": [
                            {"name": "s1", "goal": "a"},
                            {"name": "s2", "goal": "b"},
                            {"name": "s3", "goal": "c"},
                        ],
                    },
                ),
                encoding="utf-8",
            )

            def fake_run_step(settings, raw_step, idx):
                name = str(raw_step.get("name") or "")
                tokens = {"s1": 40, "s2": 20, "s3": 1}.get(name, 0)
                sr = {
                    "index": idx,
                    "name": name,
                    "goal": str(raw_step.get("goal", "")),
                    "workspace": settings.workspace,
                    "provider": settings.provider,
                    "model": settings.model,
                    "elapsed_ms": 1,
                    "answer": "ok",
                    "finished": True,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": tokens,
                    "tool_calls_count": 0,
                    "used_tools": [],
                    "error_count": 0,
                    "role": "default",
                    "parallel_group": None,
                    "protocol": {
                        "input": {"goal": raw_step.get("goal"), "role": "default", "parallel_group": None},
                        "output": {"answer": "ok"},
                        "error": None,
                    },
                }
                ev = {
                    "event": "workflow.step.completed",
                    "step_index": idx,
                    "name": name,
                    "elapsed_ms": 1,
                    "tool_calls_count": 0,
                    "error_count": 0,
                    "parallel_group": None,
                }
                return sr, ev, settings.workspace

            old_mock = os.environ.get("CAI_MOCK")
            os.environ["CAI_MOCK"] = "1"
            try:
                with patch("cai_agent.workflow._run_single_step", side_effect=fake_run_step):
                    settings = Settings.from_env(
                        config_path=None,
                        workspace_hint=str(Path(tmp)),
                    )
                    out = run_workflow(settings, str(wf_path))
            finally:
                if old_mock is None:
                    os.environ.pop("CAI_MOCK", None)
                else:
                    os.environ["CAI_MOCK"] = old_mock

        steps = out.get("steps") or []
        self.assertEqual(len(steps), 3)
        self.assertFalse(steps[0].get("skipped"))
        self.assertFalse(steps[1].get("skipped"))
        self.assertTrue(steps[2].get("skipped"))
        self.assertEqual(steps[2].get("skip_reason"), "budget_exceeded")
        sm = out.get("summary") or {}
        self.assertEqual(sm.get("budget_limit"), 50)
        self.assertEqual(sm.get("budget_used"), 60)
        self.assertTrue(sm.get("budget_exceeded"))
        self.assertEqual(out.get("task", {}).get("error"), "workflow_budget_exceeded")

    def test_workflow_budget_summary_when_no_cap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wf_path = Path(tmp) / "wf.json"
            wf_path.write_text(
                json.dumps({"steps": [{"name": "only", "goal": "g"}]}),
                encoding="utf-8",
            )
            old_mock = os.environ.get("CAI_MOCK")
            os.environ["CAI_MOCK"] = "1"
            try:
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = main(["workflow", str(wf_path), "--json"])
                out = json.loads(buf.getvalue().strip())
            finally:
                if old_mock is None:
                    os.environ.pop("CAI_MOCK", None)
                else:
                    os.environ["CAI_MOCK"] = old_mock
        self.assertEqual(rc, 0)
        sm = out.get("summary") or {}
        self.assertIsNone(sm.get("budget_limit"))
        self.assertIs(sm.get("budget_exceeded"), False)
        self.assertIn("budget_used", sm)

    def test_workflow_branch_retry_and_aggregate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wf_path = Path(tmp) / "wf.json"
            wf_path.write_text(
                json.dumps(
                    {
                        "on_error": "continue_on_error",
                        "aggregate": True,
                        "steps": [
                            {"name": "prepare", "goal": "prep"},
                            {"name": "repair", "goal": "retry", "retry": {"max_attempts": 2}},
                            {"name": "ship", "goal": "ship", "when": {"step": "repair", "status": "ok"}},
                            {"name": "fallback", "goal": "fallback", "when": {"step": "repair", "status": "failed"}},
                        ],
                    },
                ),
                encoding="utf-8",
            )
            attempts = {"repair": 0}

            def fake_run_step(settings, raw_step, idx):
                name = str(raw_step.get("name") or "")
                ok = True
                if name == "repair":
                    attempts["repair"] += 1
                    ok = attempts["repair"] >= 2
                sr = {
                    "index": idx,
                    "name": name,
                    "goal": str(raw_step.get("goal", "")),
                    "workspace": settings.workspace,
                    "provider": settings.provider,
                    "model": settings.model,
                    "elapsed_ms": 1,
                    "answer": f"{name}-answer" if ok else "failed-once",
                    "finished": ok,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "tool_calls_count": 0,
                    "used_tools": [],
                    "error_count": 0 if ok else 1,
                    "role": "default",
                    "parallel_group": None,
                    "protocol": {
                        "input": {"goal": raw_step.get("goal"), "role": "default", "parallel_group": None},
                        "output": {"answer": f"{name}-answer" if ok else "failed-once"},
                        "error": None if ok else "temporary_error",
                    },
                }
                ev = {
                    "event": "workflow.step.completed",
                    "step_index": idx,
                    "name": name,
                    "elapsed_ms": 1,
                    "tool_calls_count": 0,
                    "error_count": sr["error_count"],
                    "parallel_group": None,
                }
                return sr, ev, settings.workspace

            old_mock = os.environ.get("CAI_MOCK")
            os.environ["CAI_MOCK"] = "1"
            try:
                with patch("cai_agent.workflow._run_single_step", side_effect=fake_run_step):
                    settings = Settings.from_env(
                        config_path=None,
                        workspace_hint=str(Path(tmp)),
                    )
                    out = run_workflow(settings, str(wf_path))
            finally:
                if old_mock is None:
                    os.environ.pop("CAI_MOCK", None)
                else:
                    os.environ["CAI_MOCK"] = old_mock

        steps = {str(s.get("name")): s for s in out.get("steps") or []}
        self.assertEqual(steps["repair"].get("attempts"), 2)
        self.assertFalse(steps["ship"].get("skipped"))
        self.assertTrue(steps["fallback"].get("skipped"))
        self.assertEqual(steps["fallback"].get("skip_reason"), "when_condition_false")
        self.assertTrue(any(ev.get("event") == "workflow.step.retrying" for ev in out.get("events") or []))
        aggregate = out.get("aggregate") or {}
        self.assertEqual(aggregate.get("schema_version"), "workflow_aggregate_v1")
        self.assertEqual((aggregate.get("answers_by_name") or {}).get("ship"), "ship-answer")

    def test_workflow_quality_gate_runs_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wf_path = Path(tmp) / "wf-qg.json"
            wf_path.write_text(
                json.dumps(
                    {
                        "quality_gate": {"lint": True, "report_dir": ".cai/qg-report"},
                        "steps": [{"name": "only", "goal": "g"}],
                    },
                ),
                encoding="utf-8",
            )

            def fake_run_step(settings, raw_step, idx):
                sr = {
                    "index": idx,
                    "name": "only",
                    "goal": "g",
                    "workspace": settings.workspace,
                    "provider": settings.provider,
                    "model": settings.model,
                    "elapsed_ms": 1,
                    "answer": "ok",
                    "finished": True,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 3,
                    "tool_calls_count": 0,
                    "used_tools": [],
                    "error_count": 0,
                    "role": "default",
                    "parallel_group": None,
                    "protocol": {
                        "input": {"goal": "g", "role": "default", "parallel_group": None},
                        "output": {"answer": "ok"},
                        "error": None,
                    },
                }
                ev = {
                    "event": "workflow.step.completed",
                    "step_index": idx,
                    "name": "only",
                    "elapsed_ms": 1,
                    "tool_calls_count": 0,
                    "error_count": 0,
                    "parallel_group": None,
                }
                return sr, ev, settings.workspace

            old_mock = os.environ.get("CAI_MOCK")
            os.environ["CAI_MOCK"] = "1"
            try:
                with (
                    patch("cai_agent.workflow._run_single_step", side_effect=fake_run_step),
                    patch(
                        "cai_agent.workflow.run_quality_gate",
                        return_value={
                            "schema_version": "quality_gate_result_v1",
                            "ok": True,
                            "failed_count": 0,
                            "checks": [],
                        },
                    ) as qg_mock,
                ):
                    settings = Settings.from_env(
                        config_path=None,
                        workspace_hint=str(Path(tmp)),
                    )
                    out = run_workflow(settings, str(wf_path))
            finally:
                if old_mock is None:
                    os.environ.pop("CAI_MOCK", None)
                else:
                    os.environ["CAI_MOCK"] = old_mock

        qg = out.get("quality_gate") or {}
        self.assertTrue(qg.get("requested"))
        self.assertTrue(qg.get("ran"))
        self.assertTrue(qg.get("ok"))
        self.assertEqual(out.get("task", {}).get("status"), "completed")
        self.assertEqual(out.get("post_gate", {}).get("schema_version"), "quality_gate_result_v1")
        self.assertEqual(
            qg.get("report_dir"),
            str((Path(tmp) / ".cai" / "qg-report").resolve()),
        )
        self.assertTrue(any(ev.get("event") == "workflow.quality_gate.completed" for ev in out.get("events") or []))
        self.assertTrue(qg_mock.called)
        self.assertTrue(qg_mock.call_args.kwargs.get("enable_lint"))

    def test_workflow_quality_gate_failure_marks_workflow_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wf_path = Path(tmp) / "wf-qg-fail.json"
            wf_path.write_text(
                json.dumps(
                    {
                        "quality_gate": True,
                        "steps": [{"name": "only", "goal": "g"}],
                    },
                ),
                encoding="utf-8",
            )

            def fake_run_step(settings, raw_step, idx):
                sr = {
                    "index": idx,
                    "name": "only",
                    "goal": "g",
                    "workspace": settings.workspace,
                    "provider": settings.provider,
                    "model": settings.model,
                    "elapsed_ms": 1,
                    "answer": "ok",
                    "finished": True,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 1,
                    "tool_calls_count": 0,
                    "used_tools": [],
                    "error_count": 0,
                    "role": "default",
                    "parallel_group": None,
                    "protocol": {
                        "input": {"goal": "g", "role": "default", "parallel_group": None},
                        "output": {"answer": "ok"},
                        "error": None,
                    },
                }
                ev = {
                    "event": "workflow.step.completed",
                    "step_index": idx,
                    "name": "only",
                    "elapsed_ms": 1,
                    "tool_calls_count": 0,
                    "error_count": 0,
                    "parallel_group": None,
                }
                return sr, ev, settings.workspace

            old_mock = os.environ.get("CAI_MOCK")
            os.environ["CAI_MOCK"] = "1"
            try:
                with (
                    patch("cai_agent.workflow._run_single_step", side_effect=fake_run_step),
                    patch(
                        "cai_agent.workflow.run_quality_gate",
                        return_value={
                            "schema_version": "quality_gate_result_v1",
                            "ok": False,
                            "failed_count": 2,
                            "checks": [{"name": "python -m pytest -q", "exit_code": 1}],
                        },
                    ),
                ):
                    settings = Settings.from_env(
                        config_path=None,
                        workspace_hint=str(Path(tmp)),
                    )
                    out = run_workflow(settings, str(wf_path))
            finally:
                if old_mock is None:
                    os.environ.pop("CAI_MOCK", None)
                else:
                    os.environ["CAI_MOCK"] = old_mock

        self.assertEqual(out.get("task", {}).get("status"), "failed")
        self.assertEqual(out.get("task", {}).get("error"), "workflow_quality_gate_failed")
        self.assertTrue(out.get("quality_gate", {}).get("ran"))
        self.assertFalse(out.get("quality_gate", {}).get("ok"))
        self.assertEqual(out.get("summary", {}).get("quality_gate_failed_count"), 2)

    def test_workflow_quality_gate_skips_when_workflow_failed_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wf_path = Path(tmp) / "wf-qg-skip.json"
            wf_path.write_text(
                json.dumps(
                    {
                        "quality_gate": True,
                        "steps": [{"name": "only", "goal": "g"}],
                    },
                ),
                encoding="utf-8",
            )

            def fake_run_step(settings, raw_step, idx):
                sr = {
                    "index": idx,
                    "name": "only",
                    "goal": "g",
                    "workspace": settings.workspace,
                    "provider": settings.provider,
                    "model": settings.model,
                    "elapsed_ms": 1,
                    "answer": "bad",
                    "finished": False,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "tool_calls_count": 0,
                    "used_tools": [],
                    "error_count": 1,
                    "role": "default",
                    "parallel_group": None,
                    "protocol": {
                        "input": {"goal": "g", "role": "default", "parallel_group": None},
                        "output": {"answer": "bad"},
                        "error": "tool_error_detected",
                    },
                }
                ev = {
                    "event": "workflow.step.completed",
                    "step_index": idx,
                    "name": "only",
                    "elapsed_ms": 1,
                    "tool_calls_count": 0,
                    "error_count": 1,
                    "parallel_group": None,
                }
                return sr, ev, settings.workspace

            old_mock = os.environ.get("CAI_MOCK")
            os.environ["CAI_MOCK"] = "1"
            try:
                with (
                    patch("cai_agent.workflow._run_single_step", side_effect=fake_run_step),
                    patch("cai_agent.workflow.run_quality_gate") as qg_mock,
                ):
                    settings = Settings.from_env(
                        config_path=None,
                        workspace_hint=str(Path(tmp)),
                    )
                    out = run_workflow(settings, str(wf_path))
            finally:
                if old_mock is None:
                    os.environ.pop("CAI_MOCK", None)
                else:
                    os.environ["CAI_MOCK"] = old_mock

        self.assertEqual(out.get("task", {}).get("error"), "workflow_has_step_errors")
        self.assertFalse(out.get("quality_gate", {}).get("ran"))
        self.assertEqual(out.get("quality_gate", {}).get("skip_reason"), "workflow_failed")
        self.assertIsNone(out.get("post_gate"))
        self.assertFalse(qg_mock.called)

    def test_workflow_cli_returns_nonzero_when_quality_gate_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wf_path = Path(tmp) / "wf-cli-qg.json"
            wf_path.write_text(json.dumps({"steps": [{"name": "s1", "goal": "ignored"}]}), encoding="utf-8")
            fake = {
                "schema_version": "workflow_run_v1",
                "task_id": "wf-qg",
                "task": {
                    "task_id": "wf-qg",
                    "type": "workflow",
                    "status": "failed",
                    "error": "workflow_quality_gate_failed",
                },
                "subagent_io_schema_version": "1.1",
                "subagent_io": {
                    "inputs": {"steps_count": 1, "merge_strategy": "last_wins", "agent_templates": []},
                    "merge": {"conflicts": []},
                    "outputs": [],
                },
                "steps": [{"name": "s1", "index": 1, "error_count": 0}],
                "summary": {
                    "steps_count": 1,
                    "tool_errors_total": 0,
                    "elapsed_ms_total": 1,
                    "elapsed_ms_avg": 1,
                    "tool_calls_total": 0,
                    "quality_gate_requested": True,
                    "quality_gate_ran": True,
                    "quality_gate_ok": False,
                    "quality_gate_failed_count": 1,
                    "quality_gate_skip_reason": None,
                },
                "quality_gate": {
                    "requested": True,
                    "ran": True,
                    "ok": False,
                    "failed_count": 1,
                    "skip_reason": None,
                    "report_dir": None,
                },
                "post_gate": {
                    "schema_version": "quality_gate_result_v1",
                    "ok": False,
                    "failed_count": 1,
                    "checks": [],
                },
                "events": [],
            }
            buf = io.StringIO()
            with patch("cai_agent.__main__.run_workflow", return_value=fake):
                with redirect_stdout(buf):
                    rc = main(["workflow", str(wf_path), "--json"])

        self.assertEqual(rc, 2)
        out = json.loads(buf.getvalue().strip())
        self.assertEqual(out.get("post_gate", {}).get("schema_version"), "quality_gate_result_v1")


if __name__ == "__main__":
    unittest.main()
