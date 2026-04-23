#!/usr/bin/env python3
"""Generate docs/TOOLS_REGISTRY.zh-CN.md from cai_agent.tools_registry_doc."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _ensure_pkg_path() -> None:
    root = _repo_root()
    src = root / "cai-agent" / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def main(argv: list[str] | None = None) -> int:
    _ensure_pkg_path()
    from cai_agent.tools import DISPATCH_TOOL_NAMES
    from cai_agent.tools_registry_doc import (
        BUILTIN_TOOLS_DOC_ROWS,
        render_tools_registry_markdown_zh_cn,
    )

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check",
        action="store_true",
        help="Exit 2 if docs/TOOLS_REGISTRY.zh-CN.md differs from generated output",
    )
    args = ap.parse_args(argv)

    reg_names = {r.name for r in BUILTIN_TOOLS_DOC_ROWS}
    if reg_names != DISPATCH_TOOL_NAMES:
        only_reg = sorted(reg_names - DISPATCH_TOOL_NAMES)
        only_disp = sorted(DISPATCH_TOOL_NAMES - reg_names)
        print(
            "BUILTIN_TOOLS_DOC_ROWS and DISPATCH_TOOL_NAMES differ:\n"
            f"  only in registry doc: {only_reg}\n"
            f"  only in dispatch: {only_disp}",
            file=sys.stderr,
        )
        return 1

    out = _repo_root() / "docs" / "TOOLS_REGISTRY.zh-CN.md"
    body = render_tools_registry_markdown_zh_cn()
    if args.check:
        if not out.is_file():
            print(f"Missing {out}", file=sys.stderr)
            return 2
        existing = out.read_text(encoding="utf-8").replace("\r\n", "\n")
        if existing != body:
            print(
                f"{out} is out of date; run: python scripts/gen_tools_registry_zh.py",
                file=sys.stderr,
            )
            return 2
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8", newline="\n")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
