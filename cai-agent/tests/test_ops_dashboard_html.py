"""Tests for §26: ops dashboard HTML export."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from cai_agent.ops_dashboard import build_ops_dashboard_html, build_ops_dashboard_payload

_SRC = Path(__file__).resolve().parents[1] / "src"


def _cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_SRC)
    return subprocess.run(
        [sys.executable, "-m", "cai_agent", *args],
        cwd=str(cwd or Path.cwd()),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


# ---------------------------------------------------------------------------
# build_ops_dashboard_html
# ---------------------------------------------------------------------------


def _sample_payload() -> dict:
    return {
        "schema_version": "ops_dashboard_v1",
        "generated_at": "2026-04-23T10:00:00+00:00",
        "workspace": "/tmp/test",
        "summary": {
            "sessions_count": 42,
            "failure_rate": 0.12,
            "failed_count": 5,
            "cost_total_tokens": 1000000,
            "schedule_tasks_in_stats": 8,
        },
        "schedule_stats": {
            "tasks": [
                {
                    "task_id": "t1",
                    "goal_preview": "每日摘要",
                    "run_count": 10,
                    "success_count": 9,
                    "success_rate": 0.9,
                    "avg_elapsed_ms": 1200,
                }
            ]
        },
        "board": {
            "observe": {
                "aggregates": {
                    "top_tools": [["read_file", 50], ["run_command", 30]],
                    "failure_rate": 0.12,
                    "failed_count": 5,
                }
            }
        },
        "cost_aggregate": {},
    }


def test_html_output_is_valid_html() -> None:
    payload = _sample_payload()
    html_out = build_ops_dashboard_html(payload)
    assert "<!DOCTYPE html>" in html_out
    assert "<html" in html_out
    assert "</html>" in html_out


def test_html_contains_key_metrics() -> None:
    payload = _sample_payload()
    html_out = build_ops_dashboard_html(payload)
    assert "42" in html_out          # sessions_count
    assert "12.0%" in html_out       # failure_rate 12%
    assert "1,000,000" in html_out   # total tokens formatted


def test_html_contains_workspace() -> None:
    payload = _sample_payload()
    html_out = build_ops_dashboard_html(payload)
    assert "/tmp/test" in html_out


def test_html_schedule_table() -> None:
    payload = _sample_payload()
    html_out = build_ops_dashboard_html(payload)
    assert "每日摘要" in html_out
    assert "90%" in html_out


def test_html_tool_table() -> None:
    payload = _sample_payload()
    html_out = build_ops_dashboard_html(payload)
    assert "read_file" in html_out


def test_html_xss_escaped() -> None:
    payload = _sample_payload()
    payload["workspace"] = "<script>alert(1)</script>"
    html_out = build_ops_dashboard_html(payload)
    assert "<script>alert(1)</script>" not in html_out
    assert "&lt;script&gt;" in html_out


def test_html_empty_payload() -> None:
    """空载荷不应抛出异常。"""
    html_out = build_ops_dashboard_html({})
    assert "<!DOCTYPE html>" in html_out


# ---------------------------------------------------------------------------
# CLI 集成测试
# ---------------------------------------------------------------------------


def test_ops_dashboard_html_format_stdout(tmp_path: Path) -> None:
    result = _cli("ops", "dashboard", "--format", "html", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "<!DOCTYPE html>" in result.stdout


def test_ops_dashboard_html_format_to_file(tmp_path: Path) -> None:
    out_file = tmp_path / "dashboard.html"
    result = _cli("ops", "dashboard", "--format", "html", "-o", str(out_file), cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert out_file.is_file()
    content = out_file.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "<html" in content


def test_ops_dashboard_json_format_still_works(tmp_path: Path) -> None:
    result = _cli("ops", "dashboard", "--format", "json", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout)
    assert out["schema_version"] == "ops_dashboard_v1"
