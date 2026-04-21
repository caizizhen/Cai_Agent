# QA Test Plan: Recall CLI and Recall Index

This plan validates cross-session recall (`cai-agent recall`) and the optional index workflow (`cai-agent recall-index`), aligned with Hermes-style session recall.

## 1) Scope

**In scope**

- Keyword and regex search over saved session JSON (`.cai-session*.json` by default)
- Time window (`--days`), scan cap (`--limit`), hit cap (`--max-hits` / `--max-matches`)
- JSON output contract (`--json`)
- Parse failure tolerance (`parse_skipped`)
- Index build, incremental refresh, info, clear
- `recall --use-index` path

**Out of scope**

- Vector DB / embeddings
- MCP-backed remote search

## 2) Preconditions

- Repository with `cai-agent` installed (`pip install -e ".[dev]"` from `cai-agent/`)
- Writable temp directory
- Ability to create `.cai-session*.json` files

## 3) Commands (reference)

| Command | Purpose |
|---------|---------|
| `cai-agent recall --query …` | Scan session files on disk |
| `cai-agent recall --use-index --query …` | Search using `.cai-recall-index.json` |
| `cai-agent recall-index build` | Full rebuild of index |
| `cai-agent recall-index refresh` | Incremental merge (skip unchanged mtime) |
| `cai-agent recall-index refresh --prune` | Incremental + remove missing / out-of-window |
| `cai-agent recall-index search --query …` | Search via index only |
| `cai-agent recall-index info` | Index metadata |
| `cai-agent recall-index clear` | Delete index file |

Optional: `--index-path PATH` on all index-related commands and on `recall --use-index`.

## 4) Test cases

### RC-001 Basic keyword hit (scan mode)

1. Create two session files containing `auth`.
2. Run:

```bash
cai-agent recall --query "auth" --json
```

**Expected**

- `schema_version` is `1.0`
- `query` matches
- `hits_total >= 1`
- `results[]` entries include `path`, `mtime`, `hits`

### RC-002 Days window (scan mode)

1. One session older than `--days`, one recent (adjust `touch` / mtime).
2. Run:

```bash
cai-agent recall --query "auth" --days 1 --json
```

**Expected**

- Old session excluded from `sessions_scanned` / results

### RC-003 Limit and max hits (scan mode)

```bash
cai-agent recall --query "auth" --limit 5 --max-hits 2 --json
```

**Expected**

- At most 2 sessions in `results` (per current implementation: `session_limit` = `limit`)

### RC-004 Malformed session tolerance

1. Add invalid JSON matching `.cai-session*.json`.
2. Run:

```bash
cai-agent recall --query "auth" --json
```

**Expected**

- Exit code `0`
- `parse_skipped >= 1`
- Valid files still return hits

### RC-005 Text output smoke (scan mode)

```bash
cai-agent recall --query "auth"
```

**Expected**

- Summary line includes `hits_total`, `scanned`, `parse_skipped`
- Per-result path and snippet preview

### RC-006 Index build and search

1. Create two valid sessions with distinct content.
2. Run:

```bash
cai-agent recall-index build --json
cai-agent recall-index search --query "auth" --json
```

**Expected**

- `build` returns `ok: true`, `sessions_indexed >= 1`
- `search` returns `source: "index"`, `hits_total >= 1` when query matches

### RC-007 Incremental refresh (mtime skip)

1. `recall-index build`
2. Run `recall-index refresh --json` twice without changing session files.

**Expected**

- Second run: `sessions_skipped_unchanged` equals number of scanned in-window files (or high), `sessions_touched` is `0`

3. Modify one session file content (and ensure mtime changes).

**Expected**

- `sessions_touched >= 1`

### RC-008 Refresh with `--prune`

1. Build index including a session file path.
2. Delete that session file from disk.
3. Run:

```bash
cai-agent recall-index refresh --prune --json
```

**Expected**

- `pruned_missing >= 1` (or index no longer lists deleted path)

### RC-009 `recall --use-index`

1. `recall-index build`
2. Run:

```bash
cai-agent recall --use-index --query "auth" --json
```

**Expected**

- `source: "index"` in payload
- If index missing: exit `2` and JSON `error: index_not_found`

### RC-010 Custom `--index-path`

```bash
cai-agent recall-index build --index-path ./tmp-index.json --json
cai-agent recall --use-index --index-path ./tmp-index.json --query "auth" --json
```

**Expected**

- Index written to `./tmp-index.json`
- Recall uses same path

## 5) Regression commands

```bash
cd cai-agent
python3 -m pytest -q \
  tests/test_recall_cli.py \
  tests/test_recall_index_cli.py \
  tests/test_insights_cli.py \
  tests/test_stats_json.py
```

## 6) QA sign-off

- Build / commit:
- Environment:
- Cases executed:
- Pass / fail summary:
- Blocking issues:
- Attachments (logs, JSON):
