#!/usr/bin/env python3
"""Smoke tests for newer CLI JSON envelopes (CHANGELOG 0.5.x).

Covers plan/run/stats/sessions/observe/commands/agents/cost budget, gateway
platforms + ops dashboard + skills hub manifest, repo-root
``plugins``/``doctor``/``mcp-check``/``security-scan --json``, empty cwd ``sessions`` +
``observe-report --json``, ``hooks list`` + ``run-event --dry-run --json``,
``insights``/``board --json``, ``memory health`` + ``memory state --json``, plus
init --json, schedule add + list + rm + stats --json, gateway telegram list
--json, recall --json, ``recall-index doctor --json`` (missing index → exit 2),
``recall-index info --json`` (missing index → ok false / index_not_found, exit 0),
``workflow --json`` (``CAI_MOCK=1``, root ``task_id`` vs ``task.task_id``;
``summary.on_error`` + ``budget_limit``/``budget_used``/``budget_exceeded``),
memory list/search/export-entries/export --json envelopes.

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

# Minimal TOML for isolated hook smoke dirs (no network; satisfies Settings).
_MINIMAL_LLM_TOML = (
    '[llm]\nbase_url = "http://127.0.0.1:1/v1"\nmodel = "m"\napi_key = "k"\n'
)


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
        tid = str(o.get("task_id") or "").strip()
        td = o.get("task") if isinstance(o.get("task"), dict) else {}
        ntid = str((td or {}).get("task_id") or "").strip()
        if not tid or tid != ntid:
            errs.append(f"run json task_id mismatch top={tid!r} nested={ntid!r}")

    with tempfile.TemporaryDirectory(prefix="cai-smoke-wf-") as wf_td:
        wfp = Path(wf_td) / "smoke-workflow.json"
        wfp.write_text(
            json.dumps({"steps": [{"name": "smoke-wf", "goal": "smoke workflow task_id"}]}),
            encoding="utf-8",
        )
        pw = _run([*cli, "workflow", str(wfp), "--json"], cwd=wf_td, env=env)
        if pw.returncode != 0:
            errs.append(f"workflow mock exit {pw.returncode} stderr={pw.stderr!r}")
        else:
            wo = json.loads((pw.stdout or "").strip())
            if wo.get("schema_version") != "workflow_run_v1":
                errs.append(f"workflow schema_version {wo.get('schema_version')!r}")
            wtid = str(wo.get("task_id") or "").strip()
            wtd = wo.get("task") if isinstance(wo.get("task"), dict) else {}
            wnt = str((wtd or {}).get("task_id") or "").strip()
            if not wtid or wtid != wnt:
                errs.append(f"workflow json task_id mismatch top={wtid!r} nested={wnt!r}")
            sm = wo.get("summary") if isinstance(wo.get("summary"), dict) else {}
            if sm.get("on_error") != "fail_fast":
                errs.append(f"workflow summary.on_error {sm.get('on_error')!r}")
            for bk in ("budget_limit", "budget_used", "budget_exceeded"):
                if bk not in sm:
                    errs.append(f"workflow summary missing {bk}")
            if sm.get("budget_limit") is not None:
                errs.append(f"workflow budget_limit expected None got {sm.get('budget_limit')!r}")
            if sm.get("budget_exceeded") is not False:
                errs.append(f"workflow budget_exceeded expected False got {sm.get('budget_exceeded')!r}")

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

    cfg_repo = root / "cai-agent.toml"
    if not cfg_repo.is_file():
        errs.append("smoke expects repo-root cai-agent.toml for plugins/doctor --json")
    else:
        pp = _run(
            [*cli, "plugins", "--json", "--config", str(cfg_repo)],
            cwd=str(root),
        )
        if pp.returncode != 0:
            errs.append(f"plugins json exit {pp.returncode} stderr={pp.stderr!r}")
        else:
            po = json.loads((pp.stdout or "").strip())
            if po.get("schema_version") != "plugins_surface_v1":
                errs.append(f"plugins schema_version {po.get('schema_version')!r}")
            comps = po.get("components")
            if not isinstance(comps, dict):
                errs.append("plugins components not object")
        pd = _run(
            [*cli, "doctor", "--json", "--config", str(cfg_repo)],
            cwd=str(root),
        )
        if pd.returncode != 0:
            errs.append(f"doctor json exit {pd.returncode} stderr={pd.stderr!r}")
        else:
            do = json.loads((pd.stdout or "").strip())
            if do.get("schema_version") != "doctor_v1":
                errs.append(f"doctor schema_version {do.get('schema_version')!r}")
            if not isinstance(do.get("workspace"), str) or not str(do.get("workspace")).strip():
                errs.append("doctor workspace missing")
        pmcp = _run(
            [*cli, "mcp-check", "--json", "--list-only", "--config", str(cfg_repo)],
            cwd=str(root),
        )
        if pmcp.returncode not in (0, 2):
            errs.append(f"mcp-check json exit {pmcp.returncode} stderr={pmcp.stderr!r}")
        else:
            try:
                mco = json.loads((pmcp.stdout or "").strip())
            except json.JSONDecodeError as e:
                errs.append(f"mcp-check json parse: {e}")
            else:
                if mco.get("schema_version") != "mcp_check_result_v1":
                    errs.append(f"mcp-check schema_version {mco.get('schema_version')!r}")
                if "mcp_enabled" not in mco:
                    errs.append("mcp-check missing mcp_enabled")

        with tempfile.TemporaryDirectory(prefix="cai-smoke-secscan-") as sec_td:
            psec = _run(
                [
                    *cli,
                    "security-scan",
                    "--json",
                    "--config",
                    str(cfg_repo),
                    "-w",
                    sec_td,
                ],
                cwd=str(root),
            )
            if psec.returncode not in (0, 2):
                errs.append(f"security-scan json exit {psec.returncode} stderr={psec.stderr!r}")
            else:
                try:
                    so = json.loads((psec.stdout or "").strip())
                except json.JSONDecodeError as e:
                    errs.append(f"security-scan json parse: {e}")
                else:
                    if so.get("schema_version") != "security_scan_result_v1":
                        errs.append(
                            f"security-scan schema_version {so.get('schema_version')!r}",
                        )
                    if not isinstance(so.get("scanned_files"), int):
                        errs.append("security-scan scanned_files not int")

    with tempfile.TemporaryDirectory(prefix="cai-smoke-insights-") as ins_td:
        pi = _run(
            [*cli, "insights", "--json", "--days", "7", "--limit", "5"],
            cwd=ins_td,
        )
        if pi.returncode != 0:
            errs.append(f"insights json exit {pi.returncode} stderr={pi.stderr!r}")
        else:
            io = json.loads((pi.stdout or "").strip())
            if io.get("schema_version") != "1.1":
                errs.append(f"insights schema_version {io.get('schema_version')!r}")
            siw = io.get("sessions_in_window")
            if type(siw) is not int or siw != 0:
                errs.append(f"insights sessions_in_window want 0 got {siw!r}")

    with tempfile.TemporaryDirectory(prefix="cai-smoke-board-") as brd_td:
        pb = _run([*cli, "board", "--json"], cwd=brd_td)
        if pb.returncode != 0:
            errs.append(f"board json exit {pb.returncode} stderr={pb.stderr!r}")
        else:
            bo = json.loads((pb.stdout or "").strip())
            if bo.get("schema_version") != "board_v1":
                errs.append(f"board schema_version {bo.get('schema_version')!r}")
            if bo.get("observe_schema_version") != "1.1":
                errs.append(f"board observe_schema_version {bo.get('observe_schema_version')!r}")
            obs = bo.get("observe")
            if not isinstance(obs, dict) or obs.get("schema_version") != "1.1":
                errs.append(f"board observe envelope: {bo!r}")

    with tempfile.TemporaryDirectory(prefix="cai-smoke-sessions-obsrpt-") as so_td:
        pss = _run([*cli, "sessions", "--json", "--limit", "3"], cwd=so_td)
        if pss.returncode != 0:
            errs.append(f"sessions json (empty cwd) exit {pss.returncode} stderr={pss.stderr!r}")
        else:
            sobj = json.loads((pss.stdout or "").strip())
            if sobj.get("schema_version") != "sessions_list_v1":
                errs.append(f"sessions schema_version {sobj.get('schema_version')!r}")
            if not isinstance(sobj.get("sessions"), list):
                errs.append("sessions.sessions not list")
        por = _run([*cli, "observe-report", "--json"], cwd=so_td)
        if por.returncode != 0:
            errs.append(f"observe-report json exit {por.returncode} stderr={por.stderr!r}")
        else:
            rep = json.loads((por.stdout or "").strip())
            if rep.get("schema_version") != "observe_report_v1":
                errs.append(f"observe-report schema_version {rep.get('schema_version')!r}")
            if rep.get("state") != "pass":
                errs.append(f"observe-report state want pass got {rep.get('state')!r}")
            obn = rep.get("observe")
            if not isinstance(obn, dict):
                errs.append("observe-report observe not object")

    with tempfile.TemporaryDirectory(prefix="cai-smoke-hooks-") as hk_td:
        hp = Path(hk_td)
        (hp / "hooks").mkdir(parents=True, exist_ok=True)
        (hp / "cai-agent.toml").write_text(_MINIMAL_LLM_TOML, encoding="utf-8")
        (hp / "hooks" / "hooks.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "hooks": [
                        {
                            "id": "smoke-hook-1",
                            "event": "observe_start",
                            "enabled": True,
                            "command": [sys.executable, "-c", "print(1)"],
                        },
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        ph = _run(
            [
                *cli,
                "hooks",
                "--config",
                str(hp / "cai-agent.toml"),
                "list",
                "--json",
            ],
            cwd=str(hp),
        )
        if ph.returncode != 0:
            errs.append(f"hooks list json exit {ph.returncode} stderr={ph.stderr!r}")
        else:
            ho = json.loads((ph.stdout or "").strip())
            if ho.get("schema_version") != "hooks_catalog_v1":
                errs.append(f"hooks list schema_version {ho.get('schema_version')!r}")
            rows = ho.get("hooks")
            if not isinstance(rows, list) or not rows:
                errs.append("hooks list hooks not non-empty list")
            pru = _run(
                [
                    *cli,
                    "hooks",
                    "--config",
                    str(hp / "cai-agent.toml"),
                    "run-event",
                    "observe_start",
                    "--dry-run",
                    "--json",
                ],
                cwd=str(hp),
            )
            if pru.returncode != 0:
                errs.append(f"hooks run-event dry-run json exit {pru.returncode} stderr={pru.stderr!r}")
            else:
                ru = json.loads((pru.stdout or "").strip())
                if ru.get("schema_version") != "hooks_run_event_result_v1":
                    errs.append(f"hooks run-event schema_version {ru.get('schema_version')!r}")
                if ru.get("dry_run") is not True:
                    errs.append(f"hooks run-event dry_run flag: {ru!r}")
                if not isinstance(ru.get("results"), list):
                    errs.append("hooks run-event results not list")

    with tempfile.TemporaryDirectory(prefix="cai-smoke-memhealth-") as mh_td:
        pmh = _run([*cli, "memory", "health", "--json"], cwd=mh_td)
        if pmh.returncode != 0:
            errs.append(f"memory health json exit {pmh.returncode} stderr={pmh.stderr!r}")
        else:
            mh = json.loads((pmh.stdout or "").strip())
            if mh.get("schema_version") != "1.0":
                errs.append(f"memory health schema_version {mh.get('schema_version')!r}")
            gr = mh.get("grade")
            if gr not in ("A", "B", "C", "D"):
                errs.append(f"memory health grade {gr!r}")
            hs = mh.get("health_score")
            if not isinstance(hs, int | float):
                errs.append(f"memory health health_score not numeric: {hs!r}")
        pst = _run([*cli, "memory", "state", "--json"], cwd=mh_td)
        if pst.returncode != 0:
            errs.append(f"memory state json exit {pst.returncode} stderr={pst.stderr!r}")
        else:
            st = json.loads((pst.stdout or "").strip())
            if st.get("schema_version") != "memory_state_eval_v1":
                errs.append(f"memory state schema_version {st.get('schema_version')!r}")
            if not isinstance(st.get("counts"), dict):
                errs.append("memory state counts not object")

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
        pp = _run([*cli, "gateway", "platforms", "list", "--json"], cwd=gw_td)
        if pp.returncode != 0:
            errs.append(f"gateway platforms list exit {pp.returncode} stderr={pp.stderr!r}")
        else:
            po = json.loads((pp.stdout or "").strip())
            if po.get("schema_version") != "gateway_platforms_v1":
                errs.append(f"gateway platforms schema {po.get('schema_version')!r}")
            if not isinstance(po.get("platforms"), list):
                errs.append("gateway platforms not list")
        od = _run([*cli, "ops", "dashboard", "--json"], cwd=gw_td)
        if od.returncode != 0:
            errs.append(f"ops dashboard exit {od.returncode} stderr={od.stderr!r}")
        else:
            oo = json.loads((od.stdout or "").strip())
            if oo.get("schema_version") != "ops_dashboard_v1":
                errs.append(f"ops dashboard schema {oo.get('schema_version')!r}")
            if not isinstance(oo.get("board"), dict):
                errs.append("ops dashboard board missing")
        (Path(gw_td) / "skills").mkdir()
        (Path(gw_td) / "skills" / "smoke-skill.md").write_text("# s\n", encoding="utf-8")
        sk = _run([*cli, "skills", "hub", "manifest", "--json"], cwd=gw_td)
        if sk.returncode != 0:
            errs.append(f"skills hub manifest exit {sk.returncode} stderr={sk.stderr!r}")
        else:
            so = json.loads((sk.stdout or "").strip())
            if so.get("schema_version") != "skills_hub_manifest_v1":
                errs.append(f"skills manifest schema {so.get('schema_version')!r}")

    with tempfile.TemporaryDirectory(prefix="cai-smoke-recall-") as rec_td:
        pr = _run(
            [
                *cli,
                "recall",
                "--query",
                "smoke-recall-envelope",
                "--json",
                "--limit",
                "5",
                "--days",
                "7",
            ],
            cwd=rec_td,
        )
        if pr.returncode != 0:
            errs.append(f"recall json exit {pr.returncode} stderr={pr.stderr!r}")
        else:
            ro = json.loads((pr.stdout or "").strip())
            if ro.get("schema_version") != "1.3":
                errs.append(f"recall schema_version {ro.get('schema_version')!r}")
            ht = ro.get("hits_total")
            if type(ht) is not int:
                errs.append(f"recall hits_total not int: {ht!r}")
            elif ht != 0:
                errs.append(f"recall hits_total want 0 got {ht}")
            nhr = ro.get("no_hit_reason")
            if not isinstance(nhr, str) or not nhr.strip():
                errs.append(f"recall no_hit_reason missing: {ro!r}")
            if not isinstance(ro.get("results"), list):
                errs.append("recall results not list")

    with tempfile.TemporaryDirectory(prefix="cai-smoke-recall-idx-doc-") as rid_td:
        prd = _run(
            [*cli, "recall-index", "doctor", "--json"],
            cwd=rid_td,
        )
        if prd.returncode != 2:
            errs.append(f"recall-index doctor (no index) exit {prd.returncode} want 2")
        else:
            try:
                djo = json.loads((prd.stdout or "").strip())
            except json.JSONDecodeError as e:
                errs.append(f"recall-index doctor json parse: {e}")
            else:
                if djo.get("schema_version") != "recall_index_doctor_v1":
                    errs.append(
                        f"recall-index doctor schema_version {djo.get('schema_version')!r}",
                    )
                if djo.get("is_healthy") is not False:
                    errs.append(f"recall-index doctor is_healthy: {djo!r}")
                issues = djo.get("issues") or []
                if not isinstance(issues, list) or "index_file_missing" not in issues:
                    errs.append(f"recall-index doctor issues want index_file_missing: {issues!r}")

    with tempfile.TemporaryDirectory(prefix="cai-smoke-recall-idx-info-") as rii_td:
        pri = _run([*cli, "recall-index", "info", "--json"], cwd=rii_td)
        if pri.returncode != 0:
            errs.append(f"recall-index info (no index) exit {pri.returncode} want 0")
        else:
            try:
                inf = json.loads((pri.stdout or "").strip())
            except json.JSONDecodeError as e:
                errs.append(f"recall-index info json parse: {e}")
            else:
                if inf.get("ok") is not False:
                    errs.append(f"recall-index info ok want false: {inf!r}")
                if inf.get("error") != "index_not_found":
                    errs.append(f"recall-index info error want index_not_found: {inf!r}")
                if not isinstance(inf.get("index_file"), str) or not str(inf.get("index_file")).strip():
                    errs.append(f"recall-index info index_file missing: {inf!r}")

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
