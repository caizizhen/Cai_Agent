# Memory Nudge QA Test Plan

## Scope

Validate Hermes-style memory nudges added via:

- `cai-agent memory nudge`
- `cai-agent memory nudge --json`

The command should analyze recent sessions and current memory health, then return actionable reminders for memory extraction/cleanup.

## Preconditions

1. In repo root, install dev dependencies if needed:
   - `cd cai-agent`
   - `python3 -m pip install -e ".[dev]"`
2. Ensure writable temporary workspace for test fixtures.

## Test Cases

### MN-001: High severity when many recent sessions and no memory entries

Steps:

1. Create at least 8 recent `.cai-session*.json` files.
2. Ensure `memory/entries.jsonl` does not exist.
3. Run:
   - `cai-agent memory nudge --json --days 7 --session-limit 20`

Expected:

- Exit code `0`.
- JSON contains:
  - `schema_version = "1.0"`
  - `severity = "high"`
  - `recent_sessions >= 8`
  - `memory_entries = 0`
- `actions` includes guidance to run `cai-agent memory extract`.

### MN-002: Low severity when memory appears healthy

Steps:

1. Create recent session file(s).
2. Create valid `memory/entries.jsonl` with at least 1 entry.
3. Create at least one `memory/instincts/instincts-*.md`.
4. Run:
   - `cai-agent memory nudge --json`

Expected:

- Exit code `0`.
- JSON contains:
  - `severity = "low"`
  - non-empty `latest_instinct_path`
  - `actions` includes health-maintenance suggestion.

### MN-003: Text output mode

Steps:

1. Run:
   - `cai-agent memory nudge`

Expected:

- Exit code `0`.
- Human-readable text includes:
  - severity line
  - recent sessions count
  - memory entries count
  - action list.

### MN-004: Validation warnings escalate recommendation

Steps:

1. Create malformed line(s) in `memory/entries.jsonl`.
2. Run:
   - `cai-agent memory nudge --json`

Expected:

- Exit code `0`.
- `memory_warnings` is non-empty.
- `actions` includes instruction to fix invalid lines.
- `severity` is at least `medium`.

## Automated Regression

Run:

- `python3 -m pytest -q tests/test_memory_nudge_cli.py`
- `python3 -m pytest -q tests/test_memory_entries_bundle.py tests/test_memory_entry_validate.py`

Expected:

- All tests pass.

## Notes

- `memory nudge` is read-only: it must not mutate session files or memory files.
- JSON schema should remain stable for scheduling/automation consumption.
