#!/usr/bin/env python3
"""Hermes S8-03 GA security gate (repo checkout).

- Runs ``run_security_scan`` over ``cai-agent/src`` (SEC-GA-001 style: no **high** findings).
- Optional quoted ``sk-…`` literal probe (SEC-GA-002 helper).

Gateway allowlist bypass (SEC-GA-004) remains in automated tests:
``cai-agent/tests/test_gateway_telegram_cli.py``.

Usage::

  python scripts/security_ga_gate.py

Exit ``0`` on success, ``2`` on failure.
"""

from __future__ import annotations

import re
import sys
import tempfile
from dataclasses import replace
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _ensure_src_on_path(root: Path) -> None:
    src = root / "cai-agent" / "src"
    if not src.is_dir():
        print(f"error: missing {src}", file=sys.stderr)
        sys.exit(2)
    sys.path.insert(0, str(src))


def main() -> int:
    root = _repo_root()
    _ensure_src_on_path(root)

    from cai_agent.config import Settings
    from cai_agent.security_scan import run_security_scan

    src = root / "cai-agent" / "src"
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        (tdp / "cai-agent.toml").write_text(
            '[llm]\nbase_url = "http://127.0.0.1:1/v1"\nmodel = "m"\napi_key = "k"\n',
            encoding="utf-8",
        )
        s = Settings.from_env(config_path=str(tdp / "cai-agent.toml"))
        s = replace(s, workspace=str(src))
        out = run_security_scan(s)

    if not bool(out.get("ok")):
        print("security_scan ok=false", file=sys.stderr)
        for f in (out.get("findings") or [])[:20]:
            print(f, file=sys.stderr)
        return 2

    bad = re.compile(r"""['"]sk-[a-zA-Z0-9]{36,}['"]""")
    hits: list[str] = []
    for path in sorted(src.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), start=1):
            if bad.search(line):
                hits.append(f"{path.relative_to(src)}:{i}")

    if hits:
        print("error: quoted sk-… literals:", file=sys.stderr)
        print("\n".join(hits[:30]), file=sys.stderr)
        return 2

    print("SECURITY_GA_GATE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
