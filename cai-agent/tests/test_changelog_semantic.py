from __future__ import annotations

from cai_agent.changelog_semantic import build_changelog_semantic_compare


def test_changelog_semantic_aligned(tmp_path) -> None:
    (tmp_path / "CHANGELOG.md").write_text("## 1.0.0\n\nen\n", encoding="utf-8")
    (tmp_path / "CHANGELOG.zh-CN.md").write_text("## 1.0.0\n\nzh\n", encoding="utf-8")
    r = build_changelog_semantic_compare(repo_root=tmp_path)
    assert r.get("schema_version") == "changelog_semantic_v1"
    assert r.get("ok") is True
