# QA Test Plan: Recall CLI (Cross-Session Search)

This plan validates the new `cai-agent recall` command (Hermes-style cross-session recall).

## 1) Scope

In scope:
- keyword search across saved session files
- time-window filtering (`--days`)
- result limits (`--limit`)
- JSON schema stability (`--json`)
- parser-failure tolerance (`parse_skipped`)

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

### RC-001 Basic keyword hit

1. Create at least 2 session files with content containing keyword `auth`.
2. Run:

```bash
cai-agent recall "auth" --json
```

Expected:
- `schema_version == "1.0"`
- `query == "auth"`
- `hits_total >= 1`
- each hit contains `file`, `line`, `snippet`, `timestamp`

### RC-002 Days window filter

1. Ensure one session is older than 1 day, one is current.
2. Run:

```bash
cai-agent recall "auth" --days 1 --json
```

Expected:
- old session is excluded
- `scanned_sessions` only counts in-window files

### RC-003 Limit behavior

1. Create multiple matching lines.
2. Run:

```bash
cai-agent recall "auth" --limit 2 --json
```

Expected:
- returned `hits` length is `<= 2`

### RC-004 Parse skip tolerance

1. Add one invalid JSON session file matching pattern.
2. Run:

```bash
cai-agent recall "auth" --json
```

Expected:
- command exits 0
- `parse_skipped >= 1`
- valid files still produce results

### RC-005 Text output smoke

Run:

```bash
cai-agent recall "auth"
```

Expected:
- human-readable summary line with `hits_total` / `scanned_sessions`
- matching lines are printed as `file:line snippet`

## 4) Regression command

```bash
cd cai-agent
python3 -m pytest -q tests/test_recall_cli.py tests/test_insights_cli.py tests/test_stats_json.py
```
