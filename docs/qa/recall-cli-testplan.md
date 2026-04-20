# QA Test Plan: Recall CLI (Cross-Session Search)

This plan validates `cai-agent recall` in both scan mode and index mode.

## 1) Scope

In scope:
- keyword search across saved session files
- time-window filtering (`--days`)
- result limits (`--limit`)
- JSON schema stability (`--json`)
- parser-failure tolerance (`parse_skipped`)
- index build/update workflow (`recall index`)
- indexed query mode (`--use-index`)

Out of scope:
- external vector DB / embeddings
- MCP-backed search engines

## 2) Preconditions

- repo root with `cai-agent` installed
- writable temp workspace
- ability to create `.cai-session*.json` files

Setup:

```bash
cd cai-agent
python3 -m pip install -e ".[dev]"
cd ..
```

## 3) Cases

### RC-001 Basic keyword hit (scan mode)

1. Create at least 2 session files with content containing keyword `auth`.
2. Run:

```bash
cai-agent recall --query "auth" --json
```

Expected:
- `schema_version == "1.0"`
- `query == "auth"`
- `hits_total >= 1`
- each result row contains `path`, `hits`, `hits_count`

### RC-002 Days window filter

1. Ensure one session is older than 1 day, one is current.
2. Run:

```bash
cai-agent recall --query "auth" --days 1 --json
```

Expected:
- old session is excluded
- `sessions_scanned` only counts in-window files

### RC-003 Limit behavior

1. Create multiple matching lines.
2. Run:

```bash
cai-agent recall --query "auth" --limit 2 --max-hits 2 --json
```

Expected:
- returned `results` length is `<= 2`

### RC-004 Parse skip tolerance

1. Add one invalid JSON session file matching pattern.
2. Run:

```bash
cai-agent recall --query "auth" --json
```

Expected:
- command exits 0
- `parse_skipped >= 1`
- valid files still produce results

### RC-005 Text output smoke

Run:

```bash
cai-agent recall --query "auth"
```

Expected:
- human-readable summary line with `hits_total` / `sessions_scanned`
- matched sessions are printed with snippets

### RC-006 Index build smoke

Run:

```bash
cai-agent recall index --json
```

Expected:
- `ok == true`
- has index metadata (`files_scanned`, `rows_indexed`, `index_path`)

### RC-007 Indexed query parity

1. Build index:

```bash
cai-agent recall index --json
```

2. Query with index:

```bash
cai-agent recall --query "auth" --use-index --json
```

Expected:
- `index_used == true`
- returns same or fewer (window-filtered) sessions compared to scan mode
- command exits 0 and schema remains stable

## 4) Regression command

```bash
cd cai-agent
python3 -m pytest -q \
  tests/test_recall_cli.py \
  tests/test_recall_index_cli.py \
  tests/test_insights_cli.py \
  tests/test_stats_json.py
```
