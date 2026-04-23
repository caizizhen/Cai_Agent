from __future__ import annotations

from cai_agent.agentskills_util import split_frontmatter_body


def test_surfaces_array_in_frontmatter() -> None:
    raw = """---
name: demo
description: demo skill for unit test with enough body text padding xxxxxxxxxxxx
surfaces: [cli, tui, gateway]
---

""" + ("body line " * 10)
    meta, body = split_frontmatter_body(raw)
    assert meta.get("surfaces") == ["cli", "tui", "gateway"]
    assert len(body.strip()) >= 40
