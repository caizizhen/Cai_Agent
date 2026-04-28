#!/usr/bin/env python3
"""Recall / recall-index performance benchmark (Hermes S3-04).

Generates N synthetic session files under a temp workspace, then measures:
  - scan: ``_build_recall_payload`` (full session scan + match)
  - index_build: ``_build_recall_index``
  - index_search: ``_build_recall_payload_from_index`` (same query)

Usage (from repo root):
  python3 scripts/perf_recall_bench.py --sessions 200
  python3 scripts/perf_recall_bench.py --sessions 10 --sessions 50 --sessions 200
  python3 scripts/perf_recall_bench.py --sessions 200 --output docs/qa/runs/perf-recall.md

Default writes Markdown under docs/qa/runs/ unless --output=- (stdout only).
Exit 0 always (report includes pass/fail vs reference thresholds); use CI to grep.

Reference thresholds (backlog PERF-RCL, adjustable):
  - 200 sessions: scan_ms < 5000, index_search_ms < 500
"""

from __future__ import annotations

import argparse
import os
import shutil
import statistics
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _ensure_src_on_path(root: Path) -> None:
    src = root / "cai-agent" / "src"
    if not src.is_dir():
        print(f"error: missing {src}", file=sys.stderr)
        sys.exit(2)
    sys.path.insert(0, str(src))


def _median_ms(samples: list[float]) -> float:
    if not samples:
        return 0.0
    return float(statistics.median(samples))


def _generate_sessions(root: Path, count: int, *, query_token: str) -> None:
    from cai_agent.session import save_session

    now = int(time.time())
    for i in range(count):
        p = root / f".cai-session-bench-{i:04d}.json"
        save_session(
            str(p),
            {
                "version": 2,
                "model": "bench-model",
                "answer": f"bench answer {i} {query_token}",
                "messages": [
                    {
                        "role": "assistant",
                        "content": f"session {i} contains keyword {query_token} for recall bench",
                    },
                ],
            },
        )
        os.utime(p, (now, now))


@contextmanager
def _temporary_workspace(root: Path):
    base = root / ".tmp"
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"perf-recall-bench-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    path.mkdir(mode=0o777)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _bench_once(
    root: Path,
    *,
    sessions: int,
    runs: int,
    query: str,
    days: int,
    limit: int,
    max_hits: int,
    include_refresh: bool,
) -> dict[str, float | int | bool | None]:
    from cai_agent.__main__ import (
        _build_recall_index,
        _build_recall_payload,
        _build_recall_payload_from_index,
        _refresh_recall_index,
        _resolve_recall_index_path,
    )

    for p in root.glob(".cai-session-bench-*.json"):
        p.unlink(missing_ok=True)
    idx = _resolve_recall_index_path(cwd=str(root), index_path=None)
    idx.unlink(missing_ok=True)

    _generate_sessions(root, sessions, query_token=query)

    scan_samples: list[float] = []
    build_samples: list[float] = []
    search_samples: list[float] = []
    refresh_samples: list[float] = []

    pattern = ".cai-session-bench-*.json"
    for _ in range(max(1, runs)):
        t0 = time.perf_counter()
        _build_recall_payload(
            cwd=str(root),
            pattern=pattern,
            limit=max(limit, sessions + 5),
            days=days,
            query=query,
            use_regex=False,
            case_sensitive=False,
            hits_per_session=3,
            session_limit=max_hits,
            sort="recent",
        )
        scan_samples.append((time.perf_counter() - t0) * 1000.0)

        t1 = time.perf_counter()
        _build_recall_index(
            cwd=str(root),
            pattern=pattern,
            limit=max(limit, sessions + 5),
            days=days,
            index_path=None,
        )
        build_samples.append((time.perf_counter() - t1) * 1000.0)

        t2 = time.perf_counter()
        _build_recall_payload_from_index(
            index_file=str(idx),
            query=query,
            use_regex=False,
            case_sensitive=False,
            session_limit=max_hits,
            sort="recent",
        )
        search_samples.append((time.perf_counter() - t2) * 1000.0)

        if include_refresh:
            t3 = time.perf_counter()
            _refresh_recall_index(
                cwd=str(root),
                pattern=pattern,
                limit=max(limit, sessions + 5),
                days=days,
                index_path=None,
                prune_missing=False,
            )
            refresh_samples.append((time.perf_counter() - t3) * 1000.0)

    scan_ms = _median_ms(scan_samples)
    index_build_ms = _median_ms(build_samples)
    index_search_ms = _median_ms(search_samples)
    refresh_ms = _median_ms(refresh_samples) if include_refresh else None

    scan_ok = scan_ms < 5000.0 if sessions >= 200 else True
    search_ok = index_search_ms < 500.0 if sessions >= 200 else True
    refresh_ok = True
    if include_refresh and sessions >= 200 and refresh_ms is not None:
        refresh_ok = refresh_ms < 200.0

    out: dict[str, float | int | bool | None] = {
        "sessions": sessions,
        "runs": max(1, runs),
        "scan_median_ms": round(scan_ms, 2),
        "index_build_median_ms": round(index_build_ms, 2),
        "index_search_median_ms": round(index_search_ms, 2),
        "threshold_scan_ms_max": 5000.0,
        "threshold_search_ms_max": 500.0,
        "scan_under_threshold": bool(scan_ok),
        "search_under_threshold": bool(search_ok),
    }
    if include_refresh:
        out["index_refresh_median_ms"] = round(refresh_ms or 0.0, 2)  # type: ignore[arg-type]
        out["threshold_refresh_ms_max"] = 200.0
        out["refresh_under_threshold"] = bool(refresh_ok)
    return out


def _markdown_table(rows: list[dict[str, float | int | bool | None]]) -> str:
    has_refresh = any(r.get("index_refresh_median_ms") is not None for r in rows)
    lines = [
        "# Recall performance benchmark",
        "",
        f"- generated_at: {datetime.now(UTC).isoformat()}",
        "- tool: `scripts/perf_recall_bench.py` (Hermes S3-04)",
        "",
    ]
    if has_refresh:
        lines.extend(
            [
                "| sessions | scan_median_ms | index_build_median_ms | index_search_median_ms | index_refresh_median_ms | scan<5s (200) | search<500ms (200) | refresh<200ms (200) |",
                "|----------|----------------|------------------------|-------------------------|-------------------------|---------------|---------------------|----------------------|",
            ],
        )
        for r in rows:
            rm = r.get("index_refresh_median_ms")
            rf_ok = r.get("refresh_under_threshold", True)
            lines.append(
                f"| {int(r['sessions'])} | {r['scan_median_ms']} | {r['index_build_median_ms']} | "
                f"{r['index_search_median_ms']} | {rm if rm is not None else '-'} | "
                f"{r['scan_under_threshold']} | {r['search_under_threshold']} | {rf_ok} |",
            )
    else:
        lines.extend(
            [
                "| sessions | scan_median_ms | index_build_median_ms | index_search_median_ms | scan<5s (200) | search<500ms (200) |",
                "|----------|----------------|------------------------|-------------------------|---------------|---------------------|",
            ],
        )
        for r in rows:
            lines.append(
                f"| {int(r['sessions'])} | {r['scan_median_ms']} | {r['index_build_median_ms']} | "
                f"{r['index_search_median_ms']} | {r['scan_under_threshold']} | {r['search_under_threshold']} |",
            )
    lines.extend(
        [
            "",
            "## Reference thresholds",
            "",
            "- For **200** sessions: `scan_median_ms` < 5000 ms; `index_search_median_ms` < 500 ms.",
            "- With `--include-refresh`: for **200** sessions, `index_refresh_median_ms` < 200 ms (no file changes → all skipped).",
            "- Smaller N rows: thresholds not enforced (always `True` in table).",
            "",
        ],
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Benchmark recall scan vs recall-index (S3-04).")
    ap.add_argument(
        "--sessions",
        action="append",
        type=int,
        default=[],
        help="Session count to benchmark (repeatable). Default: 10 50 200",
    )
    ap.add_argument("--runs", type=int, default=3, help="Repeat each phase per size (median taken). Default 3")
    ap.add_argument("--query", default="keyword", help="Substring to search (embedded in generated sessions)")
    ap.add_argument("--days", type=int, default=365, help="Recall window days (default wide)")
    ap.add_argument("--limit", type=int, default=500, help="Max session files to scan / index")
    ap.add_argument("--max-hits", type=int, default=50, help="recall session_limit / index search cap")
    ap.add_argument(
        "--output",
        default="",
        help="Markdown output path, or `-` for stdout only, or empty to auto-write under docs/qa/runs/",
    )
    ap.add_argument(
        "--include-refresh",
        action="store_true",
        default=False,
        help="Also benchmark recall-index refresh (mtime-unchanged skip path; PERF-RCL-005)",
    )
    args = ap.parse_args()
    sizes = args.sessions if args.sessions else [10, 50, 200]

    root = _repo_root()
    _ensure_src_on_path(root)

    rows: list[dict[str, float | int | bool]] = []
    with _temporary_workspace(root) as w:
        for n in sizes:
            if n < 1:
                continue
            row = _bench_once(
                w,
                sessions=n,
                runs=int(args.runs),
                query=str(args.query),
                days=int(args.days),
                limit=int(args.limit),
                max_hits=int(args.max_hits),
                include_refresh=bool(args.include_refresh),
            )
            rows.append(row)

    md = _markdown_table(rows)
    out = str(args.output or "").strip()
    if out == "-":
        sys.stdout.write(md)
        return 0

    if out:
        outp = Path(out).expanduser()
    else:
        ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        outp = root / "docs" / "qa" / "runs" / f"perf-recall-bench-{ts}.md"
    outp.parent.mkdir(parents=True, exist_ok=True)
    outp.write_text(md, encoding="utf-8")
    print(str(outp))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
