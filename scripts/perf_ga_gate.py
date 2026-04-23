#!/usr/bin/env python3
"""Hermes S8-02 GA perf gate (repo checkout).

Runs recall 200-session benchmark thresholds (PERF-GA-001 / PERF-GA-002) in-process.
Schedule daemon 100-cycle stability (PERF-GA-003) is covered by
``cai-agent/tests/test_perf_ga_s8_02.py`` (mocked execute + zero sleep).

Usage (from repository root)::

  python scripts/perf_ga_gate.py
  python scripts/perf_ga_gate.py --pytest-daemon  # also run daemon stability test

Exit codes: ``0`` pass, ``2`` recall thresholds failed or pytest failure.
"""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _ensure_src_on_path(root: Path) -> None:
    src = root / "cai-agent" / "src"
    if not src.is_dir():
        print(f"error: missing {src}", file=sys.stderr)
        sys.exit(2)
    sys.path.insert(0, str(src))


def _load_perf_recall_bench(root: Path):
    path = root / "scripts" / "perf_recall_bench.py"
    spec = importlib.util.spec_from_file_location("perf_recall_bench", path)
    if spec is None or spec.loader is None:
        print(f"error: cannot load {path}", file=sys.stderr)
        sys.exit(2)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser(description="S8-02 GA perf gate (recall 200 + optional daemon test).")
    ap.add_argument(
        "--pytest-daemon",
        action="store_true",
        help="Run pytest on test_perf_ga_s8_02.py::test_schedule_daemon_100_cycles_execute_stability",
    )
    args = ap.parse_args()

    root = _repo_root()
    _ensure_src_on_path(root)

    import tempfile

    mod = _load_perf_recall_bench(root)
    with tempfile.TemporaryDirectory() as td:
        row = mod._bench_once(
            Path(td),
            sessions=200,
            runs=3,
            query="keyword",
            days=365,
            limit=500,
            max_hits=50,
            include_refresh=False,
        )

    scan_ok = bool(row.get("scan_under_threshold"))
    search_ok = bool(row.get("search_under_threshold"))
    print(
        "perf_ga_gate recall200:",
        f"scan_median_ms={row.get('scan_median_ms')} search_median_ms={row.get('index_search_median_ms')}",
        f"scan_ok={scan_ok} search_ok={search_ok}",
    )
    if not scan_ok or not search_ok:
        print("error: recall 200 thresholds not met (see scripts/perf_recall_bench.py)", file=sys.stderr)
        return 2

    if args.pytest_daemon:
        node = "tests/test_perf_ga_s8_02.py::PerfGaS802Tests::test_schedule_daemon_100_cycles_execute_stability"
        r = subprocess.run(
            [sys.executable, "-m", "pytest", node, "-q", "--tb=short"],
            cwd=str(root / "cai-agent"),
            check=False,
        )
        if r.returncode != 0:
            return 2

    print("PERF_GA_GATE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
