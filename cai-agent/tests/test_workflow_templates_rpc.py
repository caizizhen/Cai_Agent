"""Tests for §23: workflow RPC IO TypedDict + 内置模板."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"


def _cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_SRC)
    return subprocess.run(
        [sys.executable, "-m", "cai_agent", *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

from cai_agent.workflow import (
    build_rpc_step_input,
    build_rpc_step_output,
    get_workflow_template,
    list_workflow_templates,
)


# ---------------------------------------------------------------------------
# RPC IO TypedDict
# ---------------------------------------------------------------------------


def test_build_rpc_step_input_schema() -> None:
    inp = build_rpc_step_input(
        task_id="t1",
        workflow_task_id="wf1",
        step_index=1,
        name="explore",
        goal="分析代码库",
        role="explorer",
        workspace="/tmp",
        upstream_results=None,
    )
    assert inp["schema_version"] == "rpc_step_input_v1"
    assert inp["step_index"] == 1
    assert inp["role"] == "explorer"
    assert isinstance(inp["context"], dict)


def test_build_rpc_step_input_context_from_upstream() -> None:
    upstream = [{"name": "step1", "answer": "A" * 600}]
    inp = build_rpc_step_input(
        task_id="t1",
        workflow_task_id="wf1",
        step_index=2,
        name="implement",
        goal="实现",
        workspace="/tmp",
        upstream_results=upstream,
    )
    assert "step1" in inp["context"]
    assert len(inp["context"]["step1"]) <= 500


def test_build_rpc_step_output_ok() -> None:
    step_result = {
        "index": 1,
        "name": "explore",
        "finished": True,
        "error_count": 0,
        "answer": "done",
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "total_tokens": 30,
        "elapsed_ms": 500,
        "tool_calls_count": 2,
        "used_tools": ["read_file"],
        "protocol": {"input": {}, "output": {}, "error": None},
    }
    out = build_rpc_step_output(step_result)
    assert out["schema_version"] == "rpc_step_output_v1"
    assert out["ok"] is True
    assert out["error"] is None


def test_build_rpc_step_output_error() -> None:
    step_result = {
        "index": 1,
        "name": "explore",
        "finished": True,
        "error_count": 1,
        "answer": "",
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "elapsed_ms": 0,
        "tool_calls_count": 0,
        "used_tools": [],
        "protocol": {"input": {}, "output": {}, "error": "tool_error_detected"},
    }
    out = build_rpc_step_output(step_result)
    assert out["ok"] is False
    assert out["error"] == "tool_error_detected"


# ---------------------------------------------------------------------------
# 内置模板
# ---------------------------------------------------------------------------


def test_list_workflow_templates() -> None:
    templates = list_workflow_templates()
    assert len(templates) >= 3
    ids = [t["id"] for t in templates]
    assert "explore-implement-review" in ids
    assert "security-audit" in ids
    assert "parallel-research" in ids


def test_get_workflow_template_explore_implement_review() -> None:
    tpl = get_workflow_template("explore-implement-review")
    assert tpl["on_error"] == "fail_fast"
    steps = tpl["steps"]
    assert len(steps) == 3
    roles = [s["role"] for s in steps]
    assert "explorer" in roles
    assert "reviewer" in roles


def test_get_workflow_template_goal_substitution() -> None:
    tpl = get_workflow_template("explore-implement-review", goal="添加用户认证")
    for step in tpl["steps"]:
        assert "添加用户认证" in step["goal"]
    assert "{{GOAL}}" not in str(tpl)


def test_get_workflow_template_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_workflow_template("nonexistent-template")


def test_get_workflow_template_security_audit() -> None:
    tpl = get_workflow_template("security-audit")
    assert tpl["on_error"] == "continue_on_error"
    assert len(tpl["steps"]) == 3


def test_get_workflow_template_parallel_research() -> None:
    tpl = get_workflow_template("parallel-research")
    parallel = [s for s in tpl["steps"] if s.get("parallel_group")]
    assert len(parallel) >= 2


# ---------------------------------------------------------------------------
# CLI 集成测试
# ---------------------------------------------------------------------------


def test_workflow_templates_cli_json() -> None:
    result = _cli("workflow", "--templates", "--json")
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["schema_version"] == "workflow_templates_v1"
    assert len(out["templates"]) >= 3


def test_workflow_templates_cli_with_template_json() -> None:
    result = _cli(
        "workflow", "--templates",
        "--template", "explore-implement-review",
        "--goal", "测试目标",
        "--json",
    )
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert "steps" in out
    assert "测试目标" in result.stdout


def test_workflow_templates_cli_invalid_template() -> None:
    result = _cli(
        "workflow", "--templates",
        "--template", "nonexistent-xyz",
        "--json",
    )
    assert result.returncode == 2
