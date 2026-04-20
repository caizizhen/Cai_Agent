# QA Test Plan: Schedule Daemon and Execute Path

This document defines manual QA scenarios for the new scheduling runtime additions:

- `cai-agent schedule run-due --execute` real execution path
- `cai-agent schedule daemon` polling loop runner

## 1) Scope

### In scope

- Schedule CRUD behavior still works (`add/list/rm`)
- Due detection and dry-run preview behavior
- Execute path runs real tasks and updates schedule metadata
- Daemon loop polling behavior with `--interval-sec`, `--max-cycles`
- JSON output shape and core fields
- Failure handling and non-crashing behavior

### Out of scope

- External provider SLA/performance validation
- Long-term stability soak beyond quick functional checks
- Full MCP integration matrix

---

## 2) Environment and prerequisites

- Repository root available
- Python environment with project installed (`pip install -e ".[dev]"`)
- A valid `cai-agent.toml` in current workspace
- Optional: mock-compatible model endpoint for deterministic answers

Recommended prep:

```bash
cd cai-agent
python3 -m pip install -e ".[dev]"
cd ..
```

Ensure no stale schedule file for isolated runs:

```bash
rm -f .cai-schedule.json
```

---

## 3) Test matrix

| ID | Title | Priority |
|---|---|---|
| SCH-DAEMON-001 | Add/List/Remove baseline | P0 |
| SCH-DAEMON-002 | `run-due` dry-run preview | P0 |
| SCH-DAEMON-003 | `run-due --execute` real execution | P0 |
| SCH-DAEMON-004 | Execute failure path metadata | P0 |
| SCH-DAEMON-005 | `daemon` dry-run cycle summary | P1 |
| SCH-DAEMON-006 | `daemon --execute` executes due tasks | P1 |
| SCH-DAEMON-007 | `daemon --max-cycles` stops correctly | P1 |
| SCH-DAEMON-008 | Backward compatibility with older schedule task rows | P1 |

---

## 4) Detailed cases

### SCH-DAEMON-001 Add/List/Remove baseline (P0)

1. Add a task:

```bash
cai-agent schedule add --goal "qa baseline check" --every-minutes 1 --json
```

2. List tasks:

```bash
cai-agent schedule list --json
```

3. Remove returned `id`:

```bash
cai-agent schedule rm <id> --json
```

Expected:

- `add` returns object with `id`, `goal`, `every_minutes`, `enabled`
- `list` includes the task
- `rm` returns `{"removed": true}`

---

### SCH-DAEMON-002 `run-due` dry-run preview (P0)

1. Add task with `every-minutes=1`
2. Run:

```bash
cai-agent schedule run-due --json
```

Expected:

- `mode` is `"dry-run"`
- `due_jobs` includes at least one row
- `executed` is `[]`
- No task metadata (`run_count`, `last_run_at`) should change

---

### SCH-DAEMON-003 `run-due --execute` real execution (P0)

1. Add task:

```bash
cai-agent schedule add --goal "summarize current repository layout in 2 bullets" --every-minutes 1 --json
```

2. Execute:

```bash
cai-agent schedule run-due --execute --json
```

3. List:

```bash
cai-agent schedule list --json
```

Expected:

- `executed[0].ok == true`
- `executed[0].status == "completed"`
- `executed[0].answer_preview` is non-empty
- In list output, corresponding task has:
  - `run_count >= 1`
  - `last_status == "completed"`
  - `last_run_at` non-null

---

### SCH-DAEMON-004 Execute failure path metadata (P0)

1. Make config invalid temporarily (e.g., wrong model endpoint), or run where model call fails.
2. Execute:

```bash
cai-agent schedule run-due --execute --json
```

Expected:

- Command returns JSON without crashing
- Failed task row has:
  - `ok == false`
  - `status == "failed"`
  - non-empty `error`
- `schedule list --json` shows `last_status == "failed"` and `last_error` updated

---

### SCH-DAEMON-005 `daemon` dry-run cycle summary (P1)

Run one short cycle:

```bash
cai-agent schedule daemon --interval-sec 1 --max-cycles 1 --json
```

Expected:

- payload has `mode == "dry-run"` by default
- `cycles_completed == 1`
- `cycle_results` length is 1
- each cycle row includes `due_jobs` and `executed` fields

---

### SCH-DAEMON-006 `daemon --execute` executes due tasks (P1)

1. Add due task (`every-minutes=1`)
2. Run daemon execute:

```bash
cai-agent schedule daemon --interval-sec 1 --max-cycles 1 --execute --json
```

Expected:

- `mode == "execute"`
- cycle result includes executed entries
- at least one executed entry has `ok == true` (in healthy config)
- schedule metadata updated as in SCH-DAEMON-003

---

### SCH-DAEMON-007 `daemon --max-cycles` stop behavior (P1)

Run:

```bash
cai-agent schedule daemon --interval-sec 1 --max-cycles 2 --json
```

Expected:

- process exits automatically after 2 cycles
- `cycles_completed == 2`
- no hang

---

### SCH-DAEMON-008 Backward compatibility with old rows (P1)

1. Manually create `.cai-schedule.json` with a task missing new optional keys (e.g., no `workspace`, `model`, maybe no `enabled`).
2. Run:

```bash
cai-agent schedule run-due --json
```

Expected:

- No crash / parse exception
- Task still considered valid if core fields exist (`id`, `goal`, `every_minutes`)
- Default behavior: missing `enabled` treated as enabled

---

## 5) Suggested regression commands

```bash
cd cai-agent
python3 -m pytest -q \
  tests/test_schedule_cli.py \
  tests/test_schedule_run_due_execute.py \
  tests/test_schedule_daemon_cli.py
```

---

## 6) QA sign-off template

- Build/commit:
- Environment:
- Cases executed:
- Pass/Fail summary:
- Blocking issues:
- Attachments (logs/screenshots/json):

