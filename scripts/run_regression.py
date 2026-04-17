#!/usr/bin/env python3
"""Run a repeatable CLI regression from the repository root.

Usage (from repo root):
  python scripts/run_regression.py

Notes:
  - mcp-check may exit 2 when MCP is disabled or unreachable; that is expected.
  - models may exit 0 or 2 depending on LM_BASE_URL; set REGRESSION_STRICT_MODELS=1
    to require exit 0.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def main() -> int:
    root = _repo_root()
    os.chdir(root)
    exe = "cai-agent"
    strict_models = os.environ.get("REGRESSION_STRICT_MODELS", "").lower() in (
        "1",
        "true",
        "yes",
    )
    models_expected: tuple[int, ...] = (0, 2) if not strict_models else (0,)

    steps: list[tuple[str, list[str], tuple[int, ...]]] = [
        ("compileall", [sys.executable, "-m", "compileall", "cai-agent/src"], (0,)),
        (
            "unittest",
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "cai-agent/tests",
                "-p",
                "test*.py",
                "-q",
            ],
            (0,),
        ),
        ("version", [exe, "--version"], (0,)),
        ("doctor", [exe, "doctor"], (0,)),
        ("plugins", [exe, "plugins", "--json"], (0,)),
        ("commands", [exe, "commands", "--json"], (0,)),
        ("agents", [exe, "agents", "--json"], (0,)),
        ("sessions", [exe, "sessions", "--json"], (0,)),
        ("stats", [exe, "stats", "--json"], (0,)),
        ("observe", [exe, "observe", "--json", "--limit", "20"], (0,)),
        ("cost budget", [exe, "cost", "budget"], (0,)),
        ("security-scan", [exe, "security-scan", "--json"], (0,)),
        ("quality-gate", [exe, "quality-gate", "--json"], (0, 2)),
        ("mcp-check", [exe, "mcp-check", "--json"], (0, 2)),
        ("models", [exe, "models", "--json"], models_expected),
        ("workflow missing", [exe, "workflow", "missing-workflow.json", "--json"], (2,)),
    ]

    all_ok = True
    for label, argv, expected in steps:
        proc = subprocess.run(
            argv,
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        ok = proc.returncode in expected
        if not ok:
            print(
                f"FAIL {label}: exit={proc.returncode} expected={expected}",
                file=sys.stderr,
            )
            if proc.stdout:
                print(proc.stdout[:1500], file=sys.stderr)
            if proc.stderr:
                print(proc.stderr[:1500], file=sys.stderr)
        else:
            print(f"OK   {label} (exit={proc.returncode})")
        all_ok = all_ok and ok

    wf = root / ".regression-workflow.json"
    wf.write_text(
        '{"steps":[{"name":"r1","goal":"regression smoke"}]}',
        encoding="utf-8",
    )
    try:
        env = os.environ.copy()
        env["CAI_MOCK"] = "1"
        proc_wf = subprocess.run(
            [exe, "workflow", str(wf), "--json"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        wf_ok = proc_wf.returncode == 0
        if not wf_ok:
            print(
                f"FAIL workflow mock: exit={proc_wf.returncode}",
                file=sys.stderr,
            )
            if proc_wf.stderr:
                print(proc_wf.stderr[:2000], file=sys.stderr)
        else:
            print("OK   workflow mock (exit=0)")
        all_ok = all_ok and wf_ok
    finally:
        wf.unlink(missing_ok=True)

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
