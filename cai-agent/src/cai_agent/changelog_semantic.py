"""I2 · ``changelog_semantic_v1``：对比中英文 CHANGELOG 的章节结构（轻量启发式）。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def _h2_titles(text: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"(?m)^##\s+(.+)$", text)]


def build_changelog_semantic_compare(*, repo_root: Path) -> dict[str, Any]:
    en = repo_root / "CHANGELOG.md"
    zh = repo_root / "CHANGELOG.zh-CN.md"
    if not en.is_file() or not zh.is_file():
        return {
            "schema_version": "changelog_semantic_v1",
            "ok": False,
            "reason": "missing_changelog_files",
            "paths": {"en": str(en), "zh": str(zh)},
        }
    try:
        te = en.read_text(encoding="utf-8")
        tz = zh.read_text(encoding="utf-8")
    except OSError as e:
        return {
            "schema_version": "changelog_semantic_v1",
            "ok": False,
            "reason": f"read_error:{e}",
        }
    he = _h2_titles(te)
    hz = _h2_titles(tz)
    if not he and not hz:
        return {
            "schema_version": "changelog_semantic_v1",
            "ok": True,
            "note": "no_h2_headings_found",
            "h2_count_en": 0,
            "h2_count_zh": 0,
            "repo_root": str(repo_root.resolve()),
        }
    ok = len(he) == len(hz) and len(he) > 0
    return {
        "schema_version": "changelog_semantic_v1",
        "ok": ok,
        "h2_count_en": len(he),
        "h2_count_zh": len(hz),
        "h2_head_en": he[:8],
        "h2_head_zh": hz[:8],
        "repo_root": str(repo_root.resolve()),
    }
