#!/usr/bin/env python3
"""Smoke tests for newer CLI JSON envelopes (CHANGELOG 0.5.x).

Covers plan/run/stats/sessions/observe/commands/agents/cost budget and, in a
temporary cwd, init --json, schedule add + list + rm + stats --json envelopes,
gateway telegram list --json, memory list/search/export-entries/export --json
envelopes.

Run from repository root:
  python scripts/smoke_new_features.py

Uses ``python -m cai_agent`` (and prepends ``cai-agent/src`` on ``PYTHONPATH``)
so the checkout is exercised even when the ``cai-agent`` console script is
absent or shadowed on ``PATH`` — same idea as ``scripts/run_regression.py``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def _ensure_repo_pythonpath(root: Path) -> None:
    """Prepend cai-agent/src so `python -m cai_agent` uses this checkout."""
    src = str((root / "cai-agent" / "src").resolve())
    prev = os.environ.get("PYTHONPATH", "").strip()
    os.environ["PYTHONPATH"] = src if not prev else f"{src}{os.pathsep}{prev}"


def _run(
    argv: list[str],
    *,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd if cwd is not None else str(_root()),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env or os.environ.copy(),
    )


def main() -> int:
    root = _root()
    _ensure_repo_pythonpath(root)
    cli = [sys.executable, "-m", "cai_agent"]
    errs: list[str] = []

    p = _run(
        [
            *cli,
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

    p = _run([*cli, "plan", "--json", "  ", "  "])
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
    p = _run([*cli, "plan", "--json", "schema smoke"], env=env)
    if p.returncode != 0:
        errs.append(f"plan mock exit {p.returncode} stderr={p.stderr!r}")
    else:
        o = json.loads((p.stdout or "").strip())
        if not (o.get("ok") is True and o.get("plan_schema_version") == "1.0" and o.get("task")):
            errs.append(f"plan mock payload: {list(o.keys())}")

    p = _run([*cli, "run", "--json", "run envelope"], env=env)
    if p.returncode != 0:
        errs.append(f"run mock exit {p.returncode}")
    else:
        o = json.loads((p.stdout or "").strip())
        if o.get("run_schema_version") != "1.0":
            errs.append(f"run_schema_version: {o.get('run_schema_version')!r}")
        ev = o.get("events")
        if not isinstance(ev, list) or len(ev) < 1:
            errs.append(f"run events: {ev!r}")

    p = _run([*cli, "cost", "budget"])
    if p.returncode not in (0, 2):
        errs.append(f"cost budget exit {p.returncode}")
    else:
        o = json.loads((p.stdout or "").strip())
        if o.get("schema_version") != "cost_budget_v1":
            errs.append(f"cost budget schema_version {o.get('schema_version')!r}")
        for k in ("state", "total_tokens", "max_tokens"):
            if k not in o:
                errs.append(f"cost budget missing {k}")

    p = _run([*cli, "stats", "--json"])
    if p.returncode != 0:
        errs.append(f"stats exit {p.returncode}")
    else:
        o = json.loads((p.stdout or "").strip())
        if o.get("stats_schema_version") != "1.0":
            errs.append(f"stats_schema_version {o.get('stats_schema_version')!r}")
        for k in ("run_events_total", "sessions_with_events", "parse_skipped"):
            if k not in o:
                errs.append(f"stats missing {k}")

    p = _run([*cli, "sessions", "--json"])
    if p.returncode != 0:
        errs.append(f"sessions exit {p.returncode}")
    else:
        o = json.loads((p.stdout or "").strip())
        if o.get("schema_version") != "sessions_list_v1":
            errs.append(f"sessions schema_version {o.get('schema_version')!r}")
        arr = o.get("sessions")
        if not isinstance(arr, list):
            errs.append("sessions.sessions not array")

    p = _run([*cli, "observe", "--json", "--limit", "5"])
    if p.returncode != 0:
        errs.append(f"observe exit {p.returncode}")
    else:
        o = json.loads((p.stdout or "").strip())
        ag = o.get("aggregates") or {}
        if "run_events_total" not in ag:
            errs.append("observe aggregates missing run_events_total")
        if "sessions_with_events" not in ag:
            errs.append("observe aggregates missing sessions_with_events")

    p = _run([*cli, "commands", "--json"])
    if p.returncode != 0:
        errs.append(f"commands json exit {p.returncode}")
    else:
        o = json.loads((p.stdout or "").strip())
        if o.get("schema_version") != "commands_list_v1":
            errs.append(f"commands json schema_version {o.get('schema_version')!r}")
        if "commands" not in o or not isinstance(o.get("commands"), list):
            errs.append(f"commands json envelope: {o!r}")

    p = _run([*cli, "agents", "--json"])
    if p.returncode != 0:
        errs.append(f"agents json exit {p.returncode}")
    else:
        o = json.loads((p.stdout or "").strip())
        if o.get("schema_version") != "agents_list_v1":
            errs.append(f"agents json schema_version {o.get('schema_version')!r}")
        if "agents" not in o or not isinstance(o.get("agents"), list):
            errs.append(f"agents json envelope: {o!r}")

    with tempfile.TemporaryDirectory(prefix="cai-smoke-init-") as ini_td:
        pi = _run([*cli, "init", "--json"], cwd=ini_td)
        if pi.returncode != 0:
            errs.append(f"init json exit {pi.returncode} stderr={pi.stderr!r}")
        else:
            init_o = json.loads((pi.stdout or "").strip())
            if init_o.get("schema_version") != "init_cli_v1":
                errs.append(f"init schema_version {init_o.get('schema_version')!r}")
            if init_o.get("ok") is not True:
                errs.append(f"init ok not true: {init_o!r}")
            if not (Path(ini_td) / "cai-agent.toml").is_file():
                errs.append("init json did not create cai-agent.toml")
        if (Path(ini_td) / "cai-agent.toml").is_file():
            pi2 = _run([*cli, "init", "--json"], cwd=ini_td)
            if pi2.returncode != 2:
                errs.append(f"init second run (config_exists) exit {pi2.returncode} want 2")
            else:
                dup = json.loads((pi2.stdout or "").strip())
                if dup.get("schema_version") != "init_cli_v1":
                    errs.append(f"init dup schema_version {dup.get('schema_version')!r}")
                if dup.get("ok") is not False or dup.get("error") != "config_exists":
                    errs.append(f"init dup payload: {dup!r}")

    with tempfile.TemporaryDirectory(prefix="cai-smoke-schedule-") as sched_td:
        tid = ""
        p = _run(
            [*cli, "schedule", "add", "--goal", "smoke", "--every-minutes", "1440", "--json"],
            cwd=sched_td,
        )
        if p.returncode != 0:
            errs.append(f"schedule add exit {p.returncode} stderr={p.stderr!r}")
        else:
            add_o = json.loads((p.stdout or "").strip())
            if add_o.get("schema_version") != "schedule_add_v1":
                errs.append(f"schedule add schema_version {add_o.get('schema_version')!r}")
            tid = str(add_o.get("id") or "").strip()
            if not tid:
                errs.append("schedule add missing id")
        if tid:
            p2 = _run([*cli, "schedule", "list", "--json"], cwd=sched_td)
            if p2.returncode != 0:
                errs.append(f"schedule list exit {p2.returncode}")
            else:
                list_o = json.loads((p2.stdout or "").strip())
                if list_o.get("schema_version") != "schedule_list_v1":
                    errs.append(f"schedule list schema_version {list_o.get('schema_version')!r}")
                jobs = list_o.get("jobs")
                if not isinstance(jobs, list) or not jobs:
                    errs.append("schedule list jobs not non-empty list")
            p3 = _run([*cli, "schedule", "rm", tid, "--json"], cwd=sched_td)
            if p3.returncode != 0:
                errs.append(f"schedule rm exit {p3.returncode}")
            else:
                rm_o = json.loads((p3.stdout or "").strip())
                if rm_o.get("schema_version") != "schedule_rm_v1":
                    errs.append(f"schedule rm schema_version {rm_o.get('schema_version')!r}")
                if rm_o.get("removed") is not True:
                    errs.append(f"schedule rm removed: {rm_o!r}")
            pst = _run(
                [*cli, "schedule", "stats", "--json", "--days", "7"],
                cwd=sched_td,
            )
            if pst.returncode != 0:
                errs.append(f"schedule stats exit {pst.returncode} stderr={pst.stderr!r}")
            else:
                st_o = json.loads((pst.stdout or "").strip())
                if st_o.get("schema_version") != "schedule_stats_v1":
                    errs.append(f"schedule stats schema_version {st_o.get('schema_version')!r}")
                if not isinstance(st_o.get("tasks"), list):
                    errs.append("schedule stats tasks not list")

    with tempfile.TemporaryDirectory(prefix="cai-smoke-gateway-") as gw_td:
        pg = _run([*cli, "gateway", "telegram", "list", "--json"], cwd=gw_td)
        if pg.returncode != 0:
            errs.append(f"gateway telegram list exit {pg.returncode} stderr={pg.stderr!r}")
        else:
            go = json.loads((pg.stdout or "").strip())
            if go.get("schema_version") != "gateway_telegram_map_v1":
                errs.append(f"gateway list schema_version {go.get('schema_version')!r}")
            if go.get("action") != "list":
                errs.append(f"gateway list action {go.get('action')!r}")
            if not isinstance(go.get("bindings"), list):
                errs.append("gateway list bindings not list")

    with tempfile.TemporaryDirectory(prefix="cai-smoke-memory-") as mem_td:
        pm = _run([*cli, "memory", "list", "--json", "--limit", "5"], cwd=mem_td)
        if pm.returncode != 0:
            errs.append(f"memory list json exit {pm.returncode}")
        else:
            mo = json.loads((pm.stdout or "").strip())
            if mo.get("schema_version") != "memory_list_v1":
                errs.append(f"memory list schema_version {mo.get('schema_version')!r}")
            if not isinstance(mo.get("entries"), list):
                errs.append("memory list entries not list")

    with tempfile.TemporaryDirectory(prefix="cai-smoke-memexp-") as exp_td:
        (Path(exp_td) / "memory" / "instincts").mkdir(parents=True, exist_ok=True)
        pe = _run([*cli, "memory", "export", "smoke-inst.json", "--json"], cwd=exp_td)
        if pe.returncode != 0:
            errs.append(f"memory export json exit {pe.returncode}")
        else:
            eo = json.loads((pe.stdout or "").strip())
            if eo.get("schema_version") != "memory_instincts_export_v1":
                errs.append(f"memory export schema_version {eo.get('schema_version')!r}")
            if not isinstance(eo.get("snapshots_exported"), int):
                errs.append("memory export snapshots_exported not int")

    with tempfile.TemporaryDirectory(prefix="cai-smoke-memory2-") as m2:
        memd = Path(m2) / "memory"
        memd.mkdir(parents=True, exist_ok=True)
        token = "smoke-token-unique-xyz"
        row = {
            "id": "smoke-entry-1",
            "category": "session",
            "text": f"hello {token} needle",
            "confidence": 0.8,
            "expires_at": None,
            "created_at": "2099-01-01T00:00:00+00:00",
        }
        (memd / "entries.jsonl").write_text(
            json.dumps(row, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        pl2 = _run([*cli, "memory", "list", "--json", "--limit", "5"], cwd=m2)
        if pl2.returncode != 0:
            errs.append(f"memory list (seeded) exit {pl2.returncode}")
        else:
            lo = json.loads((pl2.stdout or "").strip())
            if lo.get("schema_version") != "memory_list_v1":
                errs.append(f"memory list seeded schema_version {lo.get('schema_version')!r}")
            if not any(str((e or {}).get("id")) == "smoke-entry-1" for e in (lo.get("entries") or [])):
                errs.append("memory list seeded missing smoke-entry-1")
        ps2 = _run([*cli, "memory", "search", token, "--json", "--limit", "5"], cwd=m2)
        if ps2.returncode != 0:
            errs.append(f"memory search json exit {ps2.returncode}")
        else:
            so = json.loads((ps2.stdout or "").strip())
            if so.get("schema_version") != "memory_search_v1":
                errs.append(f"memory search schema_version {so.get('schema_version')!r}")
            hits = so.get("hits") or []
            if not hits:
                errs.append("memory search hits empty")
        pe2 = _run([*cli, "memory", "export-entries", "bundle.json", "--json"], cwd=m2)
        if pe2.returncode != 0:
            errs.append(f"memory export-entries json exit {pe2.returncode}")
        else:
            xo = json.loads((pe2.stdout or "").strip())
            if xo.get("schema_version") != "memory_entries_export_result_v1":
                errs.append(f"memory export-entries schema_version {xo.get('schema_version')!r}")
            if int(xo.get("entries_count") or 0) < 1:
                errs.append(f"memory export-entries entries_count {xo.get('entries_count')!r}")
        if not (Path(m2) / "bundle.json").is_file():
            errs.append("memory export-entries bundle.json missing")

    if errs:
        print("NEW_FEATURE_CHECKS_FAILED:", file=sys.stderr)
        for e in errs:
            print(" -", e, file=sys.stderr)
        return 1
    print("NEW_FEATURE_CHECKS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
