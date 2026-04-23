#!/usr/bin/env python3
"""List Markdown files under docs/ that still contain unchecked `- [ ]` items.

Usage (from repo root):
  python scripts/list_markdown_open_checkboxes.py

Use this to triage "many open todos" in documentation vs code work. Does not
modify files.
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    docs = root / "docs"
    if not docs.is_dir():
        print("no docs/ directory", file=sys.stderr)
        return 1
    rows: list[tuple[int, Path]] = []
    for p in sorted(docs.rglob("*.md")):
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        n = sum(1 for line in text.splitlines() if line.lstrip().startswith("- [ ]"))
        if n:
            rows.append((n, p.relative_to(root)))
    rows.sort(key=lambda x: (-x[0], str(x[1])))
    total = sum(n for n, _ in rows)
    print(f"files_with_open_checkboxes={len(rows)} total_open_lines={total}\n")
    for n, rel in rows[:80]:
        print(f"{n:4d}  {rel}")
    if len(rows) > 80:
        print(f"\n... and {len(rows) - 80} more files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
