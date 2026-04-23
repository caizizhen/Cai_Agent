"""Guard S8-04 migration doc in monorepo checkout (repo root = parents[2])."""

from __future__ import annotations

from pathlib import Path


def test_migration_guide_exists_with_upgrade_anchors() -> None:
    root = Path(__file__).resolve().parents[2]
    path = root / "docs" / "MIGRATION_GUIDE.md"
    assert path.is_file(), "docs/MIGRATION_GUIDE.md must exist at repository root"
    text = path.read_text(encoding="utf-8")
    assert "0.5" in text and "0.6" in text
    assert "sessions_list_v1" in text
    assert "Breaking changes" in text or "breaking" in text.lower()
