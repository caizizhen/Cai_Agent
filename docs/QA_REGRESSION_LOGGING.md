# QA regression test logging

Every full CLI regression run should leave a **machine-generated** record under `docs/qa/runs/`, plus any **manual** notes you add after investigating failures.

## Automatic log (recommended)

From the repository root:

```bash
python scripts/run_regression.py
```

The script also runs **`scripts/smoke_new_features.py`**, which invokes **`python -m cai_agent`** with **`cai-agent/src`** on **`PYTHONPATH`** (same pattern as the main regression steps), for JSON envelopes: `plan` / `run` / `stats` / `sessions` / `observe` / `commands` / `agents` / `cost budget`, plus `mcp-check --json`, empty-cwd `sessions` / `observe-report --json`, `hooks list` + `hooks run-event --dry-run --json`, `plugins --json`, `doctor --json`, `insights --json`, `board --json`, `memory health` + `memory state --json`, `init --json`, `schedule add|list|rm|stats --json`, `gateway telegram list --json`, `recall --json`, `memory list --json`, `memory search --json`, `memory export-entries --json`, and `memory export --json` in temp cwds (and repo-root **`mcp-check`/`plugins`/`doctor`** where noted).

On completion, the script writes:

- `docs/qa/runs/regression-YYYYMMDD-HHmmss.md` — timestamp in **local** time (filename prefix).

Set **`QA_LOG_DIR`** to override the directory (path relative to repo root or absolute).

Set **`QA_SKIP_LOG=1`** to disable writing the Markdown file (stdout/stderr only).

## What each log file contains

1. **Metadata** — date/time, repository root, `git rev-parse HEAD` (if available), Python version, platform, relevant env vars (`REGRESSION_STRICT_MODELS`, `QA_LOG_DIR`, `CAI_MOCK` is *not* set globally; mock is only injected for subprocess steps that need it).
2. **Summary** — overall pass/fail and exit code of the script.
3. **Step table** — human-readable step name, full command line, expected exit code(s), actual exit code, pass/fail.
4. **Failure details** — for failed steps, truncated `stdout` / `stderr` from the subprocess (capped to keep files readable).

## Manual follow-up

When a step fails:

1. Open the latest `docs/qa/runs/regression-*.md`.
2. Re-run the failing command locally with the same cwd (repo root).
3. Optionally append a subsection **“Analyst notes”** at the bottom of that file (root cause, ticket id, fix PR).

## Chinese mirror

See **`docs/QA_REGRESSION_LOGGING.zh-CN.md`** for the same policy in Chinese.
