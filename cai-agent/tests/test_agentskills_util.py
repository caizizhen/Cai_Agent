from __future__ import annotations

from cai_agent.agentskills_util import agentskills_compliant, split_frontmatter_body


def test_split_frontmatter() -> None:
    raw = "---\nname: Demo\ndescription: A demo skill for unit tests\n---\n\nBody " + "x" * 50
    meta, body = split_frontmatter_body(raw)
    assert meta.get("name") == "Demo"
    assert agentskills_compliant(meta, body)


def test_non_compliant_missing_description() -> None:
    raw = "---\nname: X\n---\n\nshort"
    meta, body = split_frontmatter_body(raw)
    assert not agentskills_compliant(meta, body)
