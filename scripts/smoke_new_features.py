#!/usr/bin/env python3
"""Smoke tests for newer CLI JSON envelopes (CHANGELOG 0.5.x).

Run from repository root:
  python scripts/smoke_new_features.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def _run(argv: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(_root()),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env or os.environ.copy(),
    )


def main() -> int:
    root = _root()
    exe = "cai-agent"
    errs: list[str] = []

    p = _run(
        [
            exe,
            "plan",
            "--config",
            str(root / ".__no_such_config__.toml"),
            "--json",
            "x",
        ],
    )
    if p.returncode != 2:
        errs.append(f"plan missing config: want exit 2 got {p.returncode}")
    try:
        o = json.loads((p.stdout or "").strip())
        if not (o.get("ok") is False and o.get("error") == "config_not_found"):
            errs.append(f"plan missing config JSON: {o!r}")
    except json.JSONDecodeError as e:
        errs.append(f"plan missing config parse: {e}")

    p = _run([exe, "plan", "--json", "  ", "  "])
    if p.returncode != 2:
        errs.append(f"plan empty goal: want exit 2 got {p.returncode}")
    try:
        o = json.loads((p.stdout or "").strip())
        if o.get("error") != "goal_empty":
            errs.append(f"plan empty goal JSON: {o!r}")
    except json.JSONDecodeError as e:
        errs.append(f"plan empty goal parse: {e}")

    env = os.environ.copy()
    env["CAI_MOCK"] = "1"
    p = _run([exe, "plan", "--json", "schema smoke"], env=env)
    if p.returncode != 0:
        errs.append(f"plan mock exit {p.returncode} stderr={p.stderr!r}")
    else:
        o = json.loads((p.stdout or "").strip())
        if not (o.get("ok") is True and o.get("plan_schema_version") == "1.0" and o.get("task")):
            errs.append(f"plan mock payload: {list(o.keys())}")

    p = _run([exe, "run", "--json", "run envelope"], env=env)
    if p.returncode != 0:
        errs.append(f"run mock exit {p.returncode}")
    else:
        o = json.loads((p.stdout or "").strip())
        if o.get("run_schema_version") != "1.0":
            errs.append(f"run_schema_version: {o.get('run_schema_version')!r}")
        ev = o.get("events")
        if not isinstance(ev, list) or len(ev) < 1:
            errs.append(f"run events: {ev!r}")

    p = _run([exe, "stats", "--json"])
    if p.returncode != 0:
        errs.append(f"stats exit {p.returncode}")
    else:
        o = json.loads((p.stdout or "").strip())
        if o.get("stats_schema_version") != "1.0":
            errs.append(f"stats_schema_version {o.get('stats_schema_version')!r}")
        for k in ("run_events_total", "sessions_with_events", "parse_skipped"):
            if k not in o:
                errs.append(f"stats missing {k}")

    p = _run([exe, "sessions", "--json"])
    if p.returncode != 0:
        errs.append(f"sessions exit {p.returncode}")
    else:
        arr = json.loads((p.stdout or "").strip())
        if not isinstance(arr, list):
            errs.append("sessions not array")

    p = _run([exe, "observe", "--json", "--limit", "5"])
    if p.returncode != 0:
        errs.append(f"observe exit {p.returncode}")
    else:
        o = json.loads((p.stdout or "").strip())
        ag = o.get("aggregates") or {}
        if "run_events_total" not in ag:
            errs.append("observe aggregates missing run_events_total")
        if "sessions_with_events" not in ag:
            errs.append("observe aggregates missing sessions_with_events")

    p = _run([exe, "commands", "--json"])
    if p.returncode != 0:
        errs.append(f"commands json exit {p.returncode}")
    else:
        o = json.loads((p.stdout or "").strip())
        if o.get("schema_version") != "commands_list_v1":
            errs.append(f"commands json schema_version {o.get('schema_version')!r}")
        if "commands" not in o or not isinstance(o.get("commands"), list):
            errs.append(f"commands json envelope: {o!r}")

    p = _run([exe, "agents", "--json"])
    if p.returncode != 0:
        errs.append(f"agents json exit {p.returncode}")
    else:
        o = json.loads((p.stdout or "").strip())
        if o.get("schema_version") != "agents_list_v1":
            errs.append(f"agents json schema_version {o.get('schema_version')!r}")
        if "agents" not in o or not isinstance(o.get("agents"), list):
            errs.append(f"agents json envelope: {o!r}")

    if errs:
        print("NEW_FEATURE_CHECKS_FAILED:", file=sys.stderr)
        for e in errs:
            print(" -", e, file=sys.stderr)
        return 1
    print("NEW_FEATURE_CHECKS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
