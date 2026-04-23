"""Tests for skill usage logging, session touches, and improve CLI helpers."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from dataclasses import replace

from cai_agent.skill_evolution import (
    aggregate_skill_usage,
    build_default_improve_note,
    build_skills_usage_trend_v1,
    clear_session_skill_touches,
    improve_skill_append_note,
    iter_session_skill_touches,
    record_skill_usage,
    register_session_skill_touch,
    revert_skill_append_by_hist_id,
    run_session_auto_improve,
)
from cai_agent.skill_registry import load_related_skill_texts
from cai_agent.config import Settings

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
        timeout=30,
    )


def test_record_and_aggregate_usage(tmp_path: Path) -> None:
    record_skill_usage(tmp_path, "a.md", goal="g1", outcome="loaded")
    record_skill_usage(tmp_path, "a.md", goal="g2", outcome="loaded")
    record_skill_usage(tmp_path, "b.md", goal="x", outcome="loaded")
    agg = aggregate_skill_usage(tmp_path)
    assert agg["schema_version"] == "skills_usage_aggregate_v1"
    assert agg["total_events"] == 3
    assert agg["by_skill_id"]["a.md"] == 2
    filt = aggregate_skill_usage(tmp_path, skill_id="b.md")
    assert filt["total_events"] == 1


def test_session_touches_and_auto_improve_dry_run(tmp_path: Path) -> None:
    clear_session_skill_touches()
    register_session_skill_touch("demo.md", "goal-a")
    register_session_skill_touch("demo.md", "goal-b")
    (tmp_path / "skills").mkdir(parents=True)
    (tmp_path / "skills" / "demo.md").write_text("# Demo\n\nbody\n", encoding="utf-8")
    record_skill_usage(tmp_path, "demo.md", goal="goal-a")
    out = run_session_auto_improve(root=tmp_path, apply=False)
    assert "demo.md" in (out.get("touched_skills") or [])
    assert out["results"]
    assert out["results"][0].get("written") is False
    assert "## 历史改进" in str(out["results"][0].get("preview_append") or "")
    assert not (out.get("skipped_by_threshold") or [])
    clear_session_skill_touches()


def test_improve_apply_writes(tmp_path: Path) -> None:
    (tmp_path / "skills").mkdir(parents=True)
    p = tmp_path / "skills" / "x.md"
    p.write_text("# X\n", encoding="utf-8")
    out = improve_skill_append_note(
        root=tmp_path,
        skill_id="x.md",
        note_md="**note**",
        apply=True,
    )
    assert out["written"] is True
    assert out.get("hist_id")
    text = p.read_text(encoding="utf-8")
    assert "历史改进" in text
    assert "**note**" in text
    assert "cai:hist id=" in text


def test_run_session_auto_improve_skips_below_threshold(tmp_path: Path) -> None:
    clear_session_skill_touches()
    register_session_skill_touch("low.md", "g")
    (tmp_path / "skills").mkdir(parents=True)
    (tmp_path / "skills" / "low.md").write_text("# L\n\n" + "b" * 50 + "\n", encoding="utf-8")
    record_skill_usage(tmp_path, "low.md", goal="g")
    out = run_session_auto_improve(root=tmp_path, apply=False, min_usage_count=5)
    assert any(x.get("skill_id") == "low.md" for x in (out.get("skipped_by_threshold") or []))
    clear_session_skill_touches()


def test_revert_skill_hist(tmp_path: Path) -> None:
    (tmp_path / "skills").mkdir(parents=True)
    p = tmp_path / "skills" / "rv.md"
    p.write_text("# R\n\n" + "c" * 50 + "\n", encoding="utf-8")
    out = improve_skill_append_note(root=tmp_path, skill_id="rv.md", note_md="n1", apply=True)
    hid = str(out.get("hist_id") or "")
    assert hid
    prev = p.read_text(encoding="utf-8")
    rv = revert_skill_append_by_hist_id(root=tmp_path, skill_id="rv.md", hist_id=hid, apply=True)
    assert rv.get("written") is True
    assert len(p.read_text(encoding="utf-8")) < len(prev)


def test_usage_trend_payload(tmp_path: Path) -> None:
    record_skill_usage(tmp_path, "t.md", goal="g")
    doc = build_skills_usage_trend_v1(tmp_path, days=3)
    assert doc.get("schema_version") == "skills_usage_trend_v1"
    assert len(doc.get("series") or []) == 3


def test_build_default_improve_note(tmp_path: Path) -> None:
    record_skill_usage(tmp_path, "z.md", goal="gz")
    note = build_default_improve_note(tmp_path, "z.md")
    assert "skill-usage" in note or "最近" in note


def test_load_related_records_usage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clear_session_skill_touches()
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "plan.md").write_text("# Plan skill\nhello", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "cai-agent.toml"
    cfg.write_text(
        '[llm]\nbase_url = "http://127.0.0.1:9/v1"\nmodel = "m"\napi_key = "k"\n',
        encoding="utf-8",
    )
    s0 = Settings.from_env(config_path=str(cfg), workspace_hint=str(tmp_path))
    st = replace(s0, workspace=str(tmp_path.resolve()))
    texts = load_related_skill_texts(st, "plan", goal_hint="run tests", limit=3)
    assert texts and "Plan" in texts[0]
    usage_file = tmp_path / ".cai" / "skill-usage.jsonl"
    assert usage_file.is_file()
    line = usage_file.read_text(encoding="utf-8").strip().splitlines()[-1]
    doc = json.loads(line)
    assert doc["skill_id"] == "plan.md"
    assert "run tests" in doc["goal"]
    touches = iter_session_skill_touches()
    assert any(t.get("skill_id") == "plan.md" for t in touches)


def test_auto_extract_v2_llm_stub(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from cai_agent.skills import auto_extract_skill_after_task

    def _fake_chat(_settings: object, _messages: list[dict[str, str]]) -> str:
        return '{"steps":["do a","do b"],"caveats":["watch out"],"followups":["verify"]}'

    monkeypatch.setattr("cai_agent.llm_factory.chat_completion", _fake_chat)
    monkeypatch.delenv("CAI_SKILLS_AUTO_EXTRACT_LLM", raising=False)
    r = auto_extract_skill_after_task(
        root=tmp_path,
        goal="test goal v2",
        answer="final answer",
        write=True,
        settings=object(),
        use_llm=True,
        events_summary="- tool: x",
    )
    assert r["schema_version"] == "skills_auto_extract_v2"
    assert r["llm_used"] is True
    path = tmp_path / str(r["suggested_path"])
    body = path.read_text(encoding="utf-8")
    assert "do a" in body
    assert "watch out" in body


def test_usage_log_disabled_no_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "only.md").write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CAI_SKILLS_USAGE_LOG", "0")
    cfg = tmp_path / "cai-agent.toml"
    cfg.write_text(
        '[llm]\nbase_url = "http://127.0.0.1:9/v1"\nmodel = "m"\napi_key = "k"\n',
        encoding="utf-8",
    )
    s0 = Settings.from_env(config_path=str(cfg), workspace_hint=str(tmp_path))
    st = replace(s0, workspace=str(tmp_path.resolve()))
    load_related_skill_texts(st, "only", goal_hint="g")
    usage = tmp_path / ".cai" / "skill-usage.jsonl"
    assert not usage.is_file()
    monkeypatch.delenv("CAI_SKILLS_USAGE_LOG", raising=False)


def test_skills_usage_and_improve_cli(tmp_path: Path) -> None:
    record_skill_usage(tmp_path, "cli-skill.md", goal="g")
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "cli-skill.md").write_text("# S\n", encoding="utf-8")
    r1 = _cli("skills", "usage", "--json", cwd=tmp_path)
    assert r1.returncode == 0, r1.stderr
    doc = json.loads(r1.stdout)
    assert doc["schema_version"] == "skills_usage_aggregate_v1"
    r2 = _cli("skills", "improve", "cli-skill.md", "--json", cwd=tmp_path)
    assert r2.returncode == 0, r2.stderr
    out = json.loads(r2.stdout)
    assert out.get("schema_version") == "skills_evolution_runtime_v1"
    assert out.get("written") is False
