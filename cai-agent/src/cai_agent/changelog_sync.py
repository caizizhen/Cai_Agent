"""CHANGELOG bilingual sanity check (Hermes H4-QA-02 MVP)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def check_changelog_bilingual(*, repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).expanduser().resolve()
    en = root / "CHANGELOG.md"
    zh = root / "CHANGELOG.zh-CN.md"
    en_ok = en.is_file()
    zh_ok = zh.is_file()
    en_n = len(en.read_text(encoding="utf-8").splitlines()) if en_ok else 0
    zh_n = len(zh.read_text(encoding="utf-8").splitlines()) if zh_ok else 0
    ratio = (min(en_n, zh_n) / max(en_n, zh_n)) if en_n and zh_n else 0.0
    ok = en_ok and zh_ok and ratio >= 0.5
    return {
        "schema_version": "changelog_bilingual_check_v1",
        "ok": ok,
        "changelog_en": str(en),
        "changelog_zh": str(zh),
        "lines_en": en_n,
        "lines_zh": zh_n,
        "line_ratio": round(ratio, 3),
    }
