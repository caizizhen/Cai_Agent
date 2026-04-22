from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from cai_agent.config import Settings
from cai_agent.security_scan import run_security_scan
from cai_agent.task_state import new_task


def _run(argv: list[str], cwd: Path, timeout_sec: float) -> dict[str, object]:
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
            shell=False,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "name": " ".join(argv),
            "exit_code": int(proc.returncode),
            "elapsed_ms": elapsed_ms,
            "stdout": (proc.stdout or "").strip(),
            "stderr": (proc.stderr or "").strip(),
        }
    except (subprocess.TimeoutExpired, OSError) as e:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "name": " ".join(argv),
            "exit_code": 124,
            "elapsed_ms": elapsed_ms,
            "stdout": "",
            "stderr": str(e),
        }


def _skipped(name: str, reason: str) -> dict[str, object]:
    return {
        "name": name,
        "exit_code": 0,
        "elapsed_ms": 0,
        "stdout": "",
        "stderr": "",
        "skipped": True,
        "skip_reason": reason,
    }


def _mypy_cli_available() -> bool:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "mypy", "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15.0,
            shell=False,
        )
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _fail_missing(name: str, detail: str) -> dict[str, object]:
    return {
        "name": name,
        "exit_code": 1,
        "elapsed_ms": 0,
        "stdout": "",
        "stderr": detail,
        "skipped": False,
        "skip_reason": "tool_missing",
    }


def _write_reports(report_dir: Path | None, result: dict[str, object]) -> None:
    if report_dir is None:
        return
    report_dir = report_dir.expanduser().resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    summary_path = report_dir / "quality-gate.json"
    summary_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    jl_path = report_dir / "quality-gate.jsonl"
    with jl_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")
    checks = result.get("checks")
    if not isinstance(checks, list):
        checks = []
    failures = sum(1 for c in checks if isinstance(c, dict) and int(c.get("exit_code", 0)) != 0)
    tests = len(checks)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<testsuite name="quality-gate" tests="{tests}" failures="{failures}" skipped="0">',
    ]
    for c in checks:
        if not isinstance(c, dict):
            continue
        nm = str(c.get("name", "check")).replace("&", "&amp;").replace('"', "&quot;")
        ec = int(c.get("exit_code", 0))
        skipped = bool(c.get("skipped"))
        lines.append(f'  <testcase name="{nm}" classname="cai_agent.quality_gate">')
        if skipped:
            reason = str(c.get("skip_reason", "")).replace("&", "&amp;").replace('"', "&quot;")
            lines.append(f'    <skipped message="{reason}"/>')
        elif ec != 0:
            err = str(c.get("stderr", "") or c.get("stdout", ""))[:2000]
            err = err.replace("&", "&amp;").replace("<", "&lt;").replace("]]>", "]]&gt;")
            lines.append(f"    <failure message=\"exit {ec}\"><![CDATA[{err}]]></failure>")
        lines.append("  </testcase>")
    lines.append("</testsuite>")
    (report_dir / "quality-gate-junit.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_quality_gate(
    settings: Settings,
    *,
    enable_compile: bool = True,
    enable_test: bool = True,
    enable_lint: bool = False,
    enable_typecheck: bool = False,
    enable_security_scan: bool = False,
    report_dir: Path | str | None = None,
) -> dict[str, object]:
    task = new_task("quality-gate")
    task.status = "running"
    root = Path(settings.workspace).resolve()
    timeout_sec = min(max(settings.command_timeout_sec, 5.0), 300.0)
    results: list[dict[str, object]] = []
    test_pol = settings.quality_gate_test_policy
    lint_pol = settings.quality_gate_lint_policy
    rd = Path(report_dir) if report_dir else None

    if enable_compile:
        results.append(_run(["python", "-m", "compileall", "-q", "cai-agent/src"], root, timeout_sec))
    else:
        results.append(_skipped("python -m compileall -q cai-agent/src", "disabled_by_flag"))

    if enable_test:
        if shutil.which("pytest") is None:
            if test_pol == "fail_if_missing":
                results.append(
                    _fail_missing(
                        "python -m pytest -q",
                        "pytest 未安装且 quality_gate.test_policy=fail_if_missing",
                    ),
                )
            else:
                results.append(_skipped("python -m pytest -q", "pytest_not_installed"))
        else:
            results.append(_run(["python", "-m", "pytest", "-q"], root, timeout_sec))
    else:
        results.append(_skipped("python -m pytest -q", "disabled_by_flag"))

    if enable_lint:
        if shutil.which("ruff") is None:
            if lint_pol == "fail_if_missing":
                results.append(
                    _fail_missing(
                        "python -m ruff check .",
                        "ruff 未安装且 quality_gate.lint_policy=fail_if_missing",
                    ),
                )
            else:
                results.append(_skipped("python -m ruff check .", "ruff_not_installed"))
        else:
            results.append(_run(["python", "-m", "ruff", "check", "."], root, timeout_sec))
    else:
        results.append(_skipped("python -m ruff check .", "disabled_by_flag"))

    if enable_typecheck:
        paths = [p for p in settings.quality_gate_typecheck_paths if p.strip()]
        if not paths:
            results.append(_skipped("python -m mypy", "no_typecheck_paths"))
        elif not _mypy_cli_available():
            if settings.quality_gate_typecheck_policy == "fail_if_missing":
                results.append(
                    _fail_missing(
                        "python -m mypy",
                        "mypy 未就绪且 quality_gate.typecheck_policy=fail_if_missing",
                    ),
                )
            else:
                results.append(_skipped("python -m mypy", "mypy_not_available"))
        else:
            argv = [sys.executable, "-m", "mypy", *paths]
            results.append(_run(argv, root, timeout_sec))
    else:
        results.append(_skipped("python -m mypy", "disabled_by_flag"))

    for extra in settings.quality_gate_extra_commands:
        if not extra:
            continue
        label = " ".join(extra)
        results.append(_run(list(extra), root, timeout_sec))

    if enable_security_scan:
        sec = run_security_scan(settings)
        sec_ok = bool(sec.get("ok"))
        results.append(
            {
                "name": "security-scan",
                "exit_code": 0 if sec_ok else 2,
                "elapsed_ms": 0,
                "stdout": "",
                "stderr": "",
                "skipped": False,
                "findings_count": int(sec.get("findings_count", 0)),
            },
        )
    else:
        results.append(_skipped("security-scan", "disabled_by_flag"))

    failed = [r for r in results if int(r.get("exit_code", 1)) != 0]
    task.ended_at = time.time()
    task.elapsed_ms = int((task.ended_at - task.started_at) * 1000)
    task.status = "completed" if not failed else "failed"
    task.error = None if not failed else "one_or_more_checks_failed"
    result: dict[str, object] = {
        "schema_version": "quality_gate_result_v1",
        "task": task.to_dict(),
        "workspace": str(root),
        "config": {
            "compile": enable_compile,
            "test": enable_test,
            "lint": enable_lint,
            "typecheck": enable_typecheck,
            "typecheck_paths": list(settings.quality_gate_typecheck_paths),
            "extra_commands": [list(x) for x in settings.quality_gate_extra_commands],
            "security_scan": enable_security_scan,
            "test_policy": test_pol,
            "lint_policy": lint_pol,
            "typecheck_policy": settings.quality_gate_typecheck_policy,
        },
        "checks": results,
        "ok": not failed,
        "failed_count": len(failed),
    }
    _write_reports(rd, result)
    return result
