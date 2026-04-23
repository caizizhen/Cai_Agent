from __future__ import annotations

from cai_agent.agentskills_util import split_frontmatter_body


def test_nested_metadata_block() -> None:
    raw = """---
name: nested-demo
description: demo skill for unit test with enough body text padding xxxxxxxxxxxx
metadata:
  version: "2"
  license: mit
---

""" + ("body line " * 10)
    meta, body = split_frontmatter_body(raw)
    assert meta.get("name") == "nested-demo"
    md = meta.get("metadata")
    assert isinstance(md, dict)
    assert md.get("version") == "2"
    assert md.get("license") == "mit"
    assert len(body.strip()) >= 40
