#!/usr/bin/env python3
"""Run a repeatable CLI regression from the repository root.

Usage (from repo root):
  python scripts/run_regression.py

Writes a Markdown report under docs/qa/runs/ unless QA_SKIP_LOG=1.
See docs/QA_REGRESSION_LOGGING.md (EN) and docs/QA_REGRESSION_LOGGING.zh-CN.md (ZH).

Notes:
  - mcp-check may exit 2 when MCP is disabled or unreachable; that is expected.
  - models may exit 0 or 2 depending on LM_BASE_URL; set REGRESSION_STRICT_MODELS=1
    to require exit 0.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _git_head(root: Path) -> str:
    try:
        p = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "(unavailable)"


def _log_dir(root: Path) -> Path:
    raw = os.environ.get("QA_LOG_DIR", "").strip()
    if raw:
        p = Path(raw).expanduser()
        if not p.is_absolute():
            p = (root / p).resolve()
        return p
    return (root / "docs" / "qa" / "runs").resolve()


def _truncate(s: str, limit: int = 4000) -> str:
    s = s or ""
    if len(s) <= limit:
        return s
    return s[: limit - 20] + "\n…[truncated]…\n"


@dataclass
class StepRecord:
    name: str
    argv: list[str]
    expected: tuple[int, ...]
    exit_code: int
    passed: bool
    stdout_tail: str = ""
    stderr_tail: str = ""
    notes: str = ""


def _write_markdown_report(
    *,
    root: Path,
    out_path: Path,
    started_at: datetime,
    finished_at: datetime,
    overall_ok: bool,
    script_exit: int,
    records: list[StepRecord],
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "# CLI regression run",
        "",
        "## Metadata",
        "",
        f"- **Started**: {started_at.isoformat(timespec='seconds')}",
        f"- **Finished**: {finished_at.isoformat(timespec='seconds')}",
        f"- **Repository root**: `{root}`",
        f"- **Git HEAD**: `{_git_head(root)}`",
        f"- **Python**: `{sys.version.splitlines()[0]}`",
        f"- **Platform**: `{platform.platform()}`",
        f"- **REGRESSION_STRICT_MODELS**: `{os.environ.get('REGRESSION_STRICT_MODELS', '')!r}`",
        f"- **QA_LOG_DIR**: `{os.environ.get('QA_LOG_DIR', '')!r}`",
        f"- **QA_SKIP_LOG**: `{os.environ.get('QA_SKIP_LOG', '')!r}`",
        "",
        "## Summary",
        "",
        f"- **Overall**: {'PASS' if overall_ok else 'FAIL'}",
        f"- **Script exit code**: {script_exit}",
        "",
        "## Steps",
        "",
        "| Step | Command | Expected exit(s) | Actual | Result |",
        "|------|---------|------------------|--------|--------|",
    ]
    for r in records:
        cmd = " ".join(_shell_quote(a) for a in r.argv)
        exp = ", ".join(str(x) for x in r.expected)
        res = "PASS" if r.passed else "FAIL"
        note = f" ({r.notes})" if r.notes else ""
        lines.append(
            f"| {r.name} | `{cmd}` | `{exp}` | `{r.exit_code}` | {res}{note} |",
        )
    lines.extend(["", "## Failure details", ""])
    failures = [r for r in records if not r.passed]
    if not failures:
        lines.append("_No failed steps._")
    else:
        for r in failures:
            lines.extend(
                [
                    f"### {r.name}",
                    "",
                    f"Exit `{r.exit_code}`, expected `{r.expected}`.",
                    "",
                    "**stdout (truncated):**",
                    "",
                    "```text",
                    _truncate(r.stdout_tail, 6000),
                    "```",
                    "",
                    "**stderr (truncated):**",
                    "",
                    "```text",
                    _truncate(r.stderr_tail, 6000),
                    "```",
                    "",
                ],
            )
    lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def _shell_quote(arg: str) -> str:
    if not arg:
        return "''"
    if all(c.isalnum() or c in "._+/-:" for c in arg):
        return arg
    return repr(arg)


def _run_step(
    root: Path,
    label: str,
    argv: list[str],
    expected: tuple[int, ...],
    *,
    env: dict[str, str] | None = None,
    records: list[StepRecord],
) -> bool:
    proc = subprocess.run(
        argv,
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    ok = proc.returncode in expected
    rec = StepRecord(
        name=label,
        argv=list(argv),
        expected=expected,
        exit_code=int(proc.returncode),
        passed=ok,
        stdout_tail=proc.stdout or "",
        stderr_tail=proc.stderr or "",
    )
    records.append(rec)
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
    return ok


def main() -> int:
    started_at = datetime.now()
    root = _repo_root()
    os.chdir(root)
    exe = "cai-agent"
    records: list[StepRecord] = []

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
        all_ok = _run_step(root, label, argv, expected, records=records) and all_ok

    wf = root / ".regression-workflow.json"
    wf.write_text(
        '{"steps":[{"name":"r1","goal":"regression smoke"}]}',
        encoding="utf-8",
    )
    try:
        env = os.environ.copy()
        env["CAI_MOCK"] = "1"
        wf_ok = _run_step(
            root,
            "workflow mock",
            [exe, "workflow", str(wf), "--json"],
            (0,),
            env=env,
            records=records,
        )
        all_ok = all_ok and wf_ok
    finally:
        wf.unlink(missing_ok=True)

    tmp = Path(tempfile.mkdtemp(prefix="cai-regression-"))
    plan_file = tmp / "PLAN.md"
    sess_file = tmp / "session.json"
    rep_dir = tmp / "qg-reports"
    try:
        env_mock = os.environ.copy()
        env_mock["CAI_MOCK"] = "1"
        proc_plan = subprocess.run(
            [
                exe,
                "plan",
                "regression write-plan",
                "--write-plan",
                str(plan_file),
                "--json",
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env_mock,
        )
        plan_ok = proc_plan.returncode == 0 and plan_file.is_file() and plan_file.stat().st_size > 0
        plan_argv = [
            exe,
            "plan",
            "regression write-plan",
            "--write-plan",
            str(plan_file),
            "--json",
        ]
        records.append(
            StepRecord(
                name="plan --write-plan",
                argv=plan_argv,
                expected=(0,),
                exit_code=int(proc_plan.returncode),
                passed=plan_ok,
                stdout_tail=proc_plan.stdout or "",
                stderr_tail=proc_plan.stderr or "",
                notes="" if plan_ok else f"file_ok={plan_file.is_file()} size={plan_file.stat().st_size if plan_file.is_file() else 0}",
            ),
        )
        if not plan_ok:
            print(
                f"FAIL plan --write-plan: exit={proc_plan.returncode} "
                f"file_exists={plan_file.is_file()}",
                file=sys.stderr,
            )
            if proc_plan.stderr:
                print(proc_plan.stderr[:1500], file=sys.stderr)
        else:
            print("OK   plan --write-plan")
        all_ok = all_ok and plan_ok

        proc_run_pf = subprocess.run(
            [
                exe,
                "run",
                "--plan-file",
                str(plan_file),
                "--json",
                "regression run with plan",
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env_mock,
        )
        run_pf_ok = proc_run_pf.returncode == 0
        records.append(
            StepRecord(
                name="run --plan-file",
                argv=[
                    exe,
                    "run",
                    "--plan-file",
                    str(plan_file),
                    "--json",
                    "regression run with plan",
                ],
                expected=(0,),
                exit_code=int(proc_run_pf.returncode),
                passed=run_pf_ok,
                stdout_tail=proc_run_pf.stdout or "",
                stderr_tail=proc_run_pf.stderr or "",
            ),
        )
        if not run_pf_ok:
            print(
                f"FAIL run --plan-file: exit={proc_run_pf.returncode}",
                file=sys.stderr,
            )
            if proc_run_pf.stderr:
                print(proc_run_pf.stderr[:1500], file=sys.stderr)
        else:
            print("OK   run --plan-file")
        all_ok = all_ok and run_pf_ok

        proc_seed = subprocess.run(
            [
                exe,
                "run",
                "--json",
                "--save-session",
                str(sess_file),
                "regression seed session",
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env_mock,
        )
        seed_ok = proc_seed.returncode == 0 and sess_file.is_file()
        records.append(
            StepRecord(
                name="run --save-session (seed)",
                argv=[
                    exe,
                    "run",
                    "--json",
                    "--save-session",
                    str(sess_file),
                    "regression seed session",
                ],
                expected=(0,),
                exit_code=int(proc_seed.returncode),
                passed=seed_ok,
                stdout_tail=proc_seed.stdout or "",
                stderr_tail=proc_seed.stderr or "",
                notes="" if seed_ok else "session file missing",
            ),
        )
        if not seed_ok:
            print(
                f"FAIL run --save-session: exit={proc_seed.returncode}",
                file=sys.stderr,
            )
        else:
            proc_cont = subprocess.run(
                [
                    exe,
                    "continue",
                    str(sess_file),
                    "--plan-file",
                    str(plan_file),
                    "--auto-approve",
                    "--json",
                    "regression continue with plan",
                ],
                cwd=str(root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env_mock,
            )
            cont_ok = proc_cont.returncode == 0
            records.append(
                StepRecord(
                    name="continue --plan-file --auto-approve",
                    argv=[
                        exe,
                        "continue",
                        str(sess_file),
                        "--plan-file",
                        str(plan_file),
                        "--auto-approve",
                        "--json",
                        "regression continue with plan",
                    ],
                    expected=(0,),
                    exit_code=int(proc_cont.returncode),
                    passed=cont_ok,
                    stdout_tail=proc_cont.stdout or "",
                    stderr_tail=proc_cont.stderr or "",
                ),
            )
            if not cont_ok:
                print(
                    f"FAIL continue --plan-file --auto-approve: "
                    f"exit={proc_cont.returncode}",
                    file=sys.stderr,
                )
                if proc_cont.stderr:
                    print(proc_cont.stderr[:1500], file=sys.stderr)
            else:
                print("OK   continue --plan-file --auto-approve")
            all_ok = all_ok and cont_ok

        all_ok = all_ok and seed_ok

        proc_cost = subprocess.run(
            [exe, "cost", "budget", "--check"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        cost_ok = proc_cost.returncode in (0, 2)
        records.append(
            StepRecord(
                name="cost budget --check",
                argv=[exe, "cost", "budget", "--check"],
                expected=(0, 2),
                exit_code=int(proc_cost.returncode),
                passed=cost_ok,
                stdout_tail=proc_cost.stdout or "",
                stderr_tail=proc_cost.stderr or "",
            ),
        )
        if not cost_ok:
            print(
                f"FAIL cost budget --check: exit={proc_cost.returncode}",
                file=sys.stderr,
            )
        else:
            print(f"OK   cost budget --check (exit={proc_cost.returncode})")
        all_ok = all_ok and cost_ok
        try:
            line = (proc_cost.stdout or "").strip().splitlines()[-1]
            cost_payload = json.loads(line)
            if "state" not in cost_payload:
                print("FAIL cost budget JSON missing state", file=sys.stderr)
                all_ok = False
        except (IndexError, json.JSONDecodeError) as e:
            print(f"FAIL cost budget JSON: {e}", file=sys.stderr)
            all_ok = False

        rep_dir.mkdir(parents=True, exist_ok=True)
        proc_qg = subprocess.run(
            [
                exe,
                "quality-gate",
                "--json",
                "--report-dir",
                str(rep_dir),
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        qg_rep_ok = proc_qg.returncode in (0, 2) and (rep_dir / "quality-gate.json").is_file()
        records.append(
            StepRecord(
                name="quality-gate --report-dir",
                argv=[
                    exe,
                    "quality-gate",
                    "--json",
                    "--report-dir",
                    str(rep_dir),
                ],
                expected=(0, 2),
                exit_code=int(proc_qg.returncode),
                passed=qg_rep_ok,
                stdout_tail=proc_qg.stdout or "",
                stderr_tail=proc_qg.stderr or "",
                notes=f"report_exists={(rep_dir / 'quality-gate.json').is_file()}",
            ),
        )
        if not qg_rep_ok:
            print(
                f"FAIL quality-gate --report-dir: exit={proc_qg.returncode} "
                f"report={(rep_dir / 'quality-gate.json').is_file()}",
                file=sys.stderr,
            )
        else:
            print("OK   quality-gate --report-dir")
        all_ok = all_ok and qg_rep_ok

        proc_mem = subprocess.run(
            [exe, "memory", "list", "--json", "--limit", "3"],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        mem_ok = proc_mem.returncode == 0
        records.append(
            StepRecord(
                name="memory list --json",
                argv=[exe, "memory", "list", "--json", "--limit", "3"],
                expected=(0,),
                exit_code=int(proc_mem.returncode),
                passed=mem_ok,
                stdout_tail=proc_mem.stdout or "",
                stderr_tail=proc_mem.stderr or "",
            ),
        )
        if not mem_ok:
            print(
                f"FAIL memory list --json: exit={proc_mem.returncode}",
                file=sys.stderr,
            )
        else:
            print("OK   memory list --json")
        all_ok = all_ok and mem_ok
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    finished_at = datetime.now()
    script_exit = 0 if all_ok else 1

    if os.environ.get("QA_SKIP_LOG", "").lower() not in ("1", "true", "yes"):
        log_dir = _log_dir(root)
        stamp = started_at.strftime("%Y%m%d-%H%M%S")
        report_path = log_dir / f"regression-{stamp}.md"
        _write_markdown_report(
            root=root,
            out_path=report_path,
            started_at=started_at,
            finished_at=finished_at,
            overall_ok=all_ok,
            script_exit=script_exit,
            records=records,
        )
        print(f"\n[qa-log] Wrote {report_path.relative_to(root)}")

    return script_exit


if __name__ == "__main__":
    raise SystemExit(main())
