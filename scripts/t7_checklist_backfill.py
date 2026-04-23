#!/usr/bin/env python3
"""I1 · Scan Markdown checklists and emit ``t7_checklist_scan_v1`` JSON (CI-friendly).

Usage (repo root):
  python scripts/t7_checklist_backfill.py
  python scripts/t7_checklist_backfill.py --root docs --max-open 200

Exit 1 when open ``- [ ]`` count exceeds ``--fail-over`` (default: disabled).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _scan(root: Path, *, glob_pat: str) -> dict[str, object]:
    files: list[dict[str, object]] = []
    total = 0
    for p in sorted(root.rglob(glob_pat)):
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        lines = [i + 1 for i, ln in enumerate(text.splitlines()) if ln.lstrip().startswith("- [ ]")]
        if not lines:
            continue
        n = len(lines)
        total += n
        try:
            rel = str(p.relative_to(root))
        except ValueError:
            rel = str(p)
        files.append({"path": rel, "open_count": n, "lines": lines[:40]})
    return {
        "schema_version": "t7_checklist_scan_v1",
        "root": str(root.resolve()),
        "open_total": total,
        "files": files,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="T7 checklist scanner (I1)")
    ap.add_argument(
        "--root",
        default="docs",
        help="Directory to scan (relative to repo root)",
    )
    ap.add_argument(
        "--glob",
        default="*.md",
        dest="glob_pat",
        help="Glob under root (default *.md)",
    )
    ap.add_argument(
        "--fail-over",
        type=int,
        default=None,
        metavar="N",
        help="Exit 1 if open_total > N",
    )
    args = ap.parse_args()
    repo = Path(__file__).resolve().parent.parent
    root = (repo / str(args.root)).resolve()
    if not root.is_dir():
        print(json.dumps({"error": "root_not_dir", "path": str(root)}), file=sys.stderr)
        return 2
    doc = _scan(root, glob_pat=str(args.glob_pat))
    print(json.dumps(doc, ensure_ascii=False, indent=2))
    lim = args.fail_over
    if isinstance(lim, int) and int(doc.get("open_total") or 0) > lim:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
