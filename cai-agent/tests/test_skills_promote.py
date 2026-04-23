from __future__ import annotations

import json
from pathlib import Path

import pytest

from cai_agent.skill_evolution import count_skill_usage_events, record_skill_usage
from cai_agent.skills import auto_promote_evolution_skills, promote_evolution_skill


def test_promote_evolution_moves_and_lints(tmp_path: Path) -> None:
    skills = tmp_path / "skills"
    skills.mkdir(parents=True)
    draft = skills / "_evolution_demo-xyz.md"
    draft.write_text(
        "# Demo\n\n"
        + "x" * 50
        + "\n\n## Section\n\n"
        + ("body padding for lint rules. " * 5)
        + "\n",
        encoding="utf-8",
    )
    out = promote_evolution_skill(root=tmp_path, src_rel="_evolution_demo-xyz.md", dest_name="demo-promoted.md")
    assert out.get("schema_version") == "skills_promote_v1"
    assert out.get("ok") is True
    assert not draft.is_file()
    assert (skills / "demo-promoted.md").is_file()


def test_auto_promote_respects_threshold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAI_SKILLS_PROMOTE_THRESHOLD", "2")
    skills = tmp_path / "skills"
    skills.mkdir(parents=True)
    draft = skills / "_evolution_auto-case.md"
    draft.write_text(
        "# Auto\n\n" + ("y" * 50) + "\n\n" + ("more body for lint. " * 5) + "\n",
        encoding="utf-8",
    )
    record_skill_usage(tmp_path, "_evolution_auto-case.md", goal="g1")
    record_skill_usage(tmp_path, "_evolution_auto-case.md", goal="g2")
    assert count_skill_usage_events(tmp_path, "_evolution_auto-case.md") >= 2
    out = auto_promote_evolution_skills(root=tmp_path, threshold=2)
    assert out.get("schema_version") == "skills_promote_auto_v1"
    assert len(out.get("promoted") or []) == 1


def test_skills_extract_golden_parse() -> None:
    from cai_agent.skill_evolution import parse_skill_extract_llm_json

    p = Path(__file__).resolve().parent / "fixtures" / "skills_extract_goldens" / "case01.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    raw = str(doc.get("llm_raw") or "")
    parsed = parse_skill_extract_llm_json(raw)
    assert isinstance(parsed, dict)
    steps = parsed.get("steps")
    assert isinstance(steps, list)
    assert len(steps) == int(doc.get("expected_step_count") or 0)
