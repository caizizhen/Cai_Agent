from __future__ import annotations

import shutil
import subprocess
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


def run_quality_gate(
    settings: Settings,
    *,
    enable_compile: bool = True,
    enable_test: bool = True,
    enable_lint: bool = False,
    enable_security_scan: bool = False,
) -> dict[str, object]:
    task = new_task("quality-gate")
    task.status = "running"
    root = Path(settings.workspace).resolve()
    timeout_sec = min(max(settings.command_timeout_sec, 5.0), 300.0)
    results: list[dict[str, object]] = []

    if enable_compile:
        results.append(_run(["python", "-m", "compileall", "-q", "cai-agent/src"], root, timeout_sec))
    else:
        results.append(_skipped("python -m compileall -q cai-agent/src", "disabled_by_flag"))

    if enable_test:
        if shutil.which("pytest") is None:
            results.append(_skipped("python -m pytest -q", "pytest_not_installed"))
        else:
            results.append(_run(["python", "-m", "pytest", "-q"], root, timeout_sec))
    else:
        results.append(_skipped("python -m pytest -q", "disabled_by_flag"))

    if enable_lint:
        if shutil.which("ruff") is None:
            results.append(_skipped("python -m ruff check .", "ruff_not_installed"))
        else:
            results.append(_run(["python", "-m", "ruff", "check", "."], root, timeout_sec))
    else:
        results.append(_skipped("python -m ruff check .", "disabled_by_flag"))

    if enable_security_scan:
        sec = run_security_scan(settings)
        findings_count = int(sec.get("findings_count", 0))
        results.append(
            {
                "name": "security-scan",
                "exit_code": 0 if findings_count == 0 else 2,
                "elapsed_ms": 0,
                "stdout": "",
                "stderr": "",
                "skipped": False,
                "findings_count": findings_count,
            },
        )
    else:
        results.append(_skipped("security-scan", "disabled_by_flag"))

    failed = [r for r in results if int(r.get("exit_code", 1)) != 0]
    task.ended_at = time.time()
    task.elapsed_ms = int((task.ended_at - task.started_at) * 1000)
    task.status = "completed" if not failed else "failed"
    task.error = None if not failed else "one_or_more_checks_failed"
    return {
        "task": task.to_dict(),
        "workspace": str(root),
        "config": {
            "compile": enable_compile,
            "test": enable_test,
            "lint": enable_lint,
            "security_scan": enable_security_scan,
        },
        "checks": results,
        "ok": not failed,
        "failed_count": len(failed),
    }
