## Changelog

> Version history for `cai-agent`. **This file (`CHANGELOG.md`) is the default English changelog.** For the full Chinese log see **`CHANGELOG.zh-CN.md`**. The root **`README.md`** is English by default; **`README.zh-CN.md`** is the full Chinese readme.

### 0.6.10 (2026-04-23)

- **GA perf gate (Hermes S8-02)**: **[`scripts/perf_ga_gate.py`](scripts/perf_ga_gate.py)** runs the recall **200**-session benchmark thresholds (same logic as **`perf_recall_bench.py`**); optional **`--pytest-daemon`** runs the daemon stability test. **`tests/test_perf_ga_s8_02.py`**: **PERF-GA-001/002** (recall scan + index search) and **PERF-GA-003** (`schedule daemon` **100** cycles with mocked execute + sleep). **AC3** (gateway **500** messages) remains manual / harness-specific per sprint plan.
- **GA security gate (Hermes S8-03)**: **[`scripts/security_ga_gate.py`](scripts/security_ga_gate.py)** runs **`run_security_scan`** over **`cai-agent/src`** plus a quoted **`sk-…`** literal probe. **`tests/test_sec_ga_s8_03.py`**. Allowlist deny path remains **`tests/test_gateway_telegram_cli.py`** (**`not_allowed`** / **SEC-GA-004**).

### 0.6.9 (2026-04-23)

- **Docs (Hermes S8-04)**: Added **[`docs/MIGRATION_GUIDE.md`](docs/MIGRATION_GUIDE.md)** (0.5.x → 0.6.x: JSON envelopes, exit codes, schedule audit, recall). **`README.md` / `README.zh-CN.md`**: version requirements + link to the migration guide. **`CHANGELOG.md` / `CHANGELOG.zh-CN.md`** §**0.6.0**: explicit **Breaking changes**, **New CLI (0.6.x train)**, and **Deprecations** subsections for GA doc gates.
- **Tests**: `tests/test_migration_guide_present.py` guards the migration doc in the monorepo layout.

### 0.6.8 (2026-04-23)

- **Observability (Hermes S7-04)**: **`cai-agent observe export`** (`--days`, **`--format` csv|json|markdown**, **`-o`**) → **`observe_export_v1`** with per-day **`rows`** (sessions, tokens, schedule ok/fail, **memory** score/grade). **`cai_agent.observe_export`**, **`schedule.aggregate_schedule_audit_by_calendar_day_utc`** reuse. **`smoke_new_features`** writes **`observe-export.json`** in the sessions/observe temp dir.
- **Tests**: **`test_observe_export_cli.py`**.

### 0.6.7 (2026-04-23)

- **Observability (Hermes S7-03)**: **`cai-agent insights --json --cross-domain`** → **`insights_cross_domain_v1`** with **`recall_hit_rate_trend`** (`.cai-recall-index.json` substring probe **`the`** / `index_missing`), **`memory_health_trend`** (per-day **`build_memory_health_payload`** via session **mtime** window), **`schedule_success_trend`** (**`aggregate_schedule_audit_by_calendar_day_utc`**). **`build_memory_health_payload`** gains optional **`reference_now` / `session_mtime_start` / `session_mtime_end_exclusive`**. **`smoke_new_features`** covers cross-domain.
- **Tests**: **`test_insights_cross_domain.py`**.

### 0.6.6 (2026-04-23)

- **Observability (Hermes S7-01 / S7-02)**: **`cai_agent.metrics`** (`metrics_schema_v1`) with optional append to **`CAI_METRICS_JSONL`** after **`observe`** / **`observe report`**. **`cai-agent observe report`** (`--days`, **`--format` json|markdown**, **`-o`**) builds **`observe_ops_report_v1`** (root **`schema_version` `1.0`**). **`build_observe_payload`** gains time-window filtering plus **`tool_errors_total` / `tool_errors_top`** in **`aggregates`**.
- **Docs / smoke / tests**: **`docs/schema/METRICS_JSON.zh-CN.md`**; schema index + **`smoke_new_features.py`** **`observe report`**; **`test_observe_ops_report_cli.py`**, **`test_metrics_jsonl.py`**.

### 0.6.5 (2026-04-23)

- **Gateway (Hermes S6-04)**: **`cai-agent gateway telegram continue-hint`** prints JSON (**`gateway_telegram_continue_hint_v1`**) with shell-safe **`continue_cli`** lines for bound **`session_file`** paths (optional **`--chat-id`** + **`--user-id`**, or list all). **`/help`** / **`/new`** slash text points to this command. QA plan **`docs/qa/sprint6-gateway-telegram-testplan.md`** adds **GTW-CONT-001~003**.
- **Tests / smoke**: **`test_gateway_telegram_cli.py`** continue-hint cases; **`smoke_new_features.py`** asserts **`continue-hint --json`**.

### 0.6.4 (2026-04-23)

- **Gateway (Hermes S6-02)**: **`serve-webhook --execute-on-update`** now runs **`_execute_gateway_telegram_goal`**: same load/append/save path as CLI **`run`/`continue`** on the bound **`session_file`** (new file created on first message). **`reply_template`** receives the full **`{answer}`** (Telegram send still chunked). Slash **`/stop`**: default text points to **`gateway stop`**; optional **`CAI_TELEGRAM_STOP_WEBHOOK=1`** plus **`CAI_TELEGRAM_ADMIN_USER_IDS`** (comma-separated Telegram **`user_id`**) allows in-chat **`gateway_lifecycle.stop_webhook_subprocess`**. **`/help`** documents **`/stop`** and run-like execution.
- **Tests**: **`tests/test_gateway_telegram_execute_goal.py`** (session persistence, **`/stop`** paths).

### 0.6.3 (2026-04-23)

- **Gateway lifecycle (Hermes S6-01)**: **`cai-agent gateway setup|start|status|stop`** backed by **`cai_agent.gateway_lifecycle`** (writes **`gateway_telegram_config_v1`** to **`.cai/gateway/telegram-config.json`**, PID **`.cai/gateway/telegram-webhook.pid`**). **`setup`** mirrors **`serve-webhook`** flags and optional **`--allow-chat-id`**. **`start`** spawns **`gateway telegram serve-webhook`** detached (logs under **`.cai/gateway/`**). **`-w`/`--workspace`** on **`telegram`**, **`platforms`**, and lifecycle subcommands sets the workspace root.
- **Gateway (Hermes S6-02 partial)**: Webhook deny / execution replies use **`_telegram_send_text_chunked`** (~3900 chars). Slash-first messages (**`/ping`**, **`/status`**, **`/help`**, **`/start`**, **`/new`**) get inline replies without running **`_execute_scheduled_goal`**.
- **Tests / smoke**: **`tests/test_gateway_lifecycle_cli.py`**; **`scripts/smoke_new_features.py`** asserts **`gateway status --json`** (**`gateway_lifecycle_status_v1`**).

### 0.6.2 (2026-04-23)

- **Gateway (Hermes S6-03)**: Optional root **`allowed_chat_ids`** on **`gateway_telegram_map_v1`** map file. **`gateway telegram allow add|list|rm`**. **`resolve-update`** / **`serve-webhook`** return **`not_allowed`** when the list is non-empty and **`chat_id`** is missing. **`list --json`** adds **`allowed_chat_ids`** and **`allowlist_enabled`**. **`serve-webhook`**: wired missing kwargs (**`--reply-on-execution`**, **`--telegram-bot-token`** / **`CAI_TELEGRAM_BOT_TOKEN`**, **`--reply-template`**), plus **`--reply-on-deny`** / **`--deny-message`** for optional Telegram rejection text.
- **Tests / smoke**: `test_gateway_telegram_cli.py` allowlist cases; smoke asserts **`list`** allowlist fields.

### 0.6.1 (2026-04-23)

- **Gateway (dev item 24 MVP)**: `cai-agent gateway platforms list --json` → **`gateway_platforms_v1`** (Telegram `full`, Discord/Slack `stub`, others `planned`).
- **Skills Hub (dev item 25 MVP)**: `cai-agent skills hub manifest --json` → **`skills_hub_manifest_v1`** (exportable listing from workspace `skills/`). Automatic skill evolution remains out of scope.
- **Ops dashboard (dev item 26 MVP)**: `cai-agent ops dashboard --json` → **`ops_dashboard_v1`** (nested **`board_v1`**, **`schedule_stats_v1`**, **`cost_aggregate`** + top-level **`summary`**). Web UI still separate.
- **Tests / smoke**: `cai-agent/tests/test_ops_gateway_skills_cli.py`; `scripts/smoke_new_features.py` exercises the three JSON paths.

### 0.6.0 (2026-04-23)

#### Breaking changes (upgrade from 0.5.x)

- **Versioned `--json` stdout**: Many commands no longer emit bare JSON arrays/strings; each payload documents **`schema_version`** and stable root keys (e.g. **`sessions_list_v1.sessions`**, **`schedule_list_v1.jobs`**). See **[`docs/schema/README.zh-CN.md`](docs/schema/README.zh-CN.md)** and **[`docs/MIGRATION_GUIDE.md`](docs/MIGRATION_GUIDE.md)**.
- **Exit codes**: `init` failures, `models ping` non-OK, and CLI dispatch fallthrough use **exit `2`** where **`1`** applied before (see schema README **S1-03**).
- **`models fetch --json`**: Wrapped as **`{"schema_version":"models_fetch_v1","models":[…]}`** (not a bare array).

#### New CLI (0.6.x train, high level)

- **In 0.6.0**: Workflow **`on_error`** / **`budget_max_tokens`**; schedule **stats / audit schema / retries / concurrency / `depends_on`**; recall **sort / `no_hit_reason` / doctor`**; **memory health / nudge / nudge-report**; versioned JSON for **sessions, commands, agents, schedule, cost budget, export, plugins**, and memory list/search/instincts (detail bullets below).
- **0.6.1–0.6.5**: **`gateway platforms`**, **`skills hub manifest`**, **`ops dashboard`**, Telegram **lifecycle / allowlist / execute-on-update / continue-hint`**.
- **0.6.6–0.6.8**: **`CAI_METRICS_JSONL`**, **`observe report`**, **`insights --json --cross-domain`**, **`observe export`**.

#### Deprecations

- **None** that remove flags without replacement in 0.6.0. **`models ping --fail-on-any-error`** remains a **no-op alias** matching the new default (exit **`2`** on any error).

- **Workflow (Hermes S5-03)**: JSON root **`on_error`**: **`fail_fast`** (default) or **`continue_on_error`** (alias **`continue-on-error`**). On fail-fast, remaining steps are **`skipped`** with **`skip_reason=fail_fast_prior_batch`** and **`workflow.step.skipped`** events; merge/conflict resolution only considers successfully finished steps when continuing. Summary adds **`on_error`**, **`steps_skipped`**, **`merge_steps_considered`**.
- **Workflow (Hermes S5-04)**: Optional root **`budget_max_tokens`**. Cumulative executed-step **`total_tokens`** gates the next batch; unstarted steps become **`skipped`/`budget_exceeded`**. **`summary`** and **`workflow.finished`** include **`budget_limit`**, **`budget_used`**, **`budget_exceeded`**; **`task.error`** may be **`workflow_budget_exceeded`**. Batches already submitted still run to completion.
- **Workflow status logic**: Fail-fast completion is detected via **`skip_reason=fail_fast_prior_batch`**, so budget-driven skips are not misclassified as fail-fast.
- **Smoke / docs**: `scripts/smoke_new_features.py` asserts **`workflow --json`** **`summary.on_error`** and **`budget_*`**; `docs/PRODUCT_PLAN.zh-CN.md` §3.0 documents the **>20%** sync baseline; `QA_SKIP_LOG=1` on `scripts/run_regression.py` skips writing new `docs/qa/runs/*.md` reports. Parity docs (`docs/schema/README.zh-CN.md`, `docs/HERMES_PARITY_*`, `docs/qa/sprint5-subagents-testplan.md`) updated for S5-03/S5-04.

### 0.5.0 – 0.5.7 (cumulative; see entries below)

- **Docs**: [`docs/PRODUCT_PLAN.zh-CN.md`](docs/PRODUCT_PLAN.zh-CN.md) **§三之二 · 3.0** adds **quantified progress** (weighted §二 items 1–26, Hermes 34 stories, T1); [`docs/schema/README.zh-CN.md`](docs/schema/README.zh-CN.md) documents **`gateway telegram` / `gateway_telegram_map_v1`** and **`schedule stats` / `schedule_stats_v1`** (S1-02; links [`SCHEDULE_STATS_JSON.zh-CN.md`](docs/schema/SCHEDULE_STATS_JSON.zh-CN.md)); [`docs/HERMES_PARITY_PROGRESS.zh-CN.md`](docs/HERMES_PARITY_PROGRESS.zh-CN.md) and [`docs/DEVELOPMENT_PROGRESS_TRACKER.zh-CN.md`](docs/DEVELOPMENT_PROGRESS_TRACKER.zh-CN.md) cross-link the same metrics. **§三之二** also lists dev-item counts (1–26), backlog **21–26**, and the **QA handoff checklist**.
- **`cai-agent init --json`**: Prints a single-line **`init_cli_v1`** payload (`ok`, `config_path`, `preset`, `global` on success; `error` + `message` on `config_exists` / `template_read_failed` / `mkdir_failed`). Default text output unchanged without `--json`. See `docs/schema/README.zh-CN.md`.
- **`cai-agent init` exit codes (S1-03)**: Failure paths (**`config_exists`** without `--force`, **`template_read_failed`**, **`mkdir_failed`**) now return **exit `2`** (previously **`1`**). JSON envelope unchanged (`init_cli_v1`, `ok: false`). See `docs/schema/README.zh-CN.md` breaking-changes section.
- **CLI `main()` defensive fallthrough (S1-03)**: If dispatch does not handle `args.command` (internal inconsistency), the process now returns **exit `2`** and prints one stderr line (previously **`1`** with no message). See `docs/schema/README.zh-CN.md`.
- **`cai-agent memory export --json` / `memory export-entries --json`**: Optional JSON stdout summaries **`memory_instincts_export_v1`** (`output_file`, `snapshots_exported`) and **`memory_entries_export_result_v1`** (`output_file`, `entries_count`, `export_warnings`). Default stdout (path only) unchanged. See `docs/schema/README.zh-CN.md`.
- **`cai-agent models ping` exit codes (S1-03)**: Any result with `status != OK` now returns **exit `2`** by default (previously **`1`**). **`--fail-on-any-error`** remains a **no-op alias** for backward-compatible scripts. See `docs/schema/README.zh-CN.md` breaking-changes section.
- **`cai-agent memory import` / `memory import-entries` stdout**: **`memory_instincts_import_v1`** (**`imported`**), **`memory_entries_import_result_v1`** (**`imported`**), and **`memory import-entries --dry-run`** → **`memory_entries_import_dry_run_v1`** (adds **`schema_version`** alongside existing fields). See `docs/schema/README.zh-CN.md`.
- **`cai-agent memory list|search|instincts --json` / `memory extract` stdout**: **`memory_list_v1`** (**`entries`**, `limit`, `sort`), **`memory_search_v1`** (**`hits`**, `query`, `limit`, `sort`), **`memory_instincts_list_v1`** (**`paths`**, `limit`), and **`memory_extract_v1`** (**`written`**, **`entries_appended`**). **`list`/`search`/`instincts` `--json` is a breaking change** (was a bare JSON array). See `docs/schema/README.zh-CN.md`.
- **CLI tests (empty workspace)**: Added **`test_sessions_list_json_empty_directory`** (`sessions_list_v1`), **`test_observe_report_json_empty_workspace_state_pass`** (`observe_report_v1` / `state=pass`), and **`test_memory_state_json_empty_workspace`** (`memory_state_eval_v1`).
- **`cai-agent insights --json`**: `_build_insights_payload` returns immediately when **no session files fall in the time window**, producing the same **`schema_version` `1.1`** shape as the zero-iteration loop (empty `models_top` / `tools_top`, `sessions_in_window: 0`) without scanning message bodies. Covered by **`test_insights_json_empty_workspace_fast_path`** and **`scripts/smoke_new_features.py`**.
- **`scripts/smoke_new_features.py`**: Also exercises **`mcp-check --json --list-only`** (**`mcp_check_result_v1`**, exit **`0`** or **`2`**), empty-cwd **`sessions --json`** / **`observe-report --json`**, **`hooks run-event … --dry-run --json`** (**`hooks_run_event_result_v1`**), **`memory state --json`** (**`memory_state_eval_v1`**), **`plugins --json`** (**`plugins_surface_v1`**, repo-root **`cai-agent.toml`** via **`--config`**), **`doctor --json`** (**`doctor_v1`**), **`insights --json`** (empty temp cwd), **`board --json`** (**`board_v1`** + nested **`observe`** **`1.1`**), **`hooks list --json`** (**`hooks_catalog_v1`**, minimal temp **`hooks/hooks.json`**), **`memory health --json`** (S2-01 root **`schema_version` `1.0`**), **`init --json`** (**`init_cli_v1`**), a **second `init --json`** in the same temp dir (**`config_exists`**, exit **`2`**), **`schedule add|list|rm --json`**, **`schedule stats --json`** (**`schedule_stats_v1`**), **`gateway telegram list --json`** (**`gateway_telegram_map_v1`**), **`recall --json`** (**`schema_version` `1.3`**, **`no_hit_reason`** on empty workspaces), and **`memory`** JSON paths; it shells **`python -m cai_agent`** with **`cai-agent/src`** on **`PYTHONPATH`** (same as **`run_regression.py`**, no reliance on a **`cai-agent`** script on **`PATH`**).
- **`cai-agent schedule add|list|rm|add-memory-nudge --json`**: Adds **`schema_version`** payloads (**`schedule_add_v1`**, **`schedule_list_v1` + `jobs`**, **`schedule_rm_v1`**, **`schedule_add_memory_nudge_v1`**, and **`schedule_add_invalid_v1`** on validation failure). **`schedule list --json` is a breaking change** (was a bare array). See `docs/schema/README.zh-CN.md`.
- **`cai-agent schedule run-due --json` / `schedule daemon --json`**: Stdout payloads now include **`schema_version`: `schedule_run_due_v1`** / **`schedule_daemon_summary_v1`** (including the daemon lock-conflict JSON). See `docs/schema/README.zh-CN.md`.
- **`cai-agent cost budget`**: The always-JSON stdout payload now includes **`schema_version`: `cost_budget_v1`** (alongside `state` / `total_tokens` / `max_tokens`; still no `--json` flag). See `docs/schema/README.zh-CN.md`.
- **`cai-agent sessions --json`**: Output is now a versioned object **`sessions_list_v1`** with **`sessions`** (plus **`pattern`**, **`limit`**, **`details`**) (**breaking change**: previously a bare JSON array). See `docs/schema/README.zh-CN.md`.
- **`cai-agent commands --json` / `agents --json`**: Output is now versioned objects **`commands_list_v1`** / **`agents_list_v1`** with **`commands`** / **`agents`** arrays (**breaking change**: previously bare JSON string arrays). See `docs/schema/README.zh-CN.md`.
- **`cai-agent export` JSON line**: Adds **`schema_version`: `export_cli_v1`** to the stdout payload from `export_target` (all `--target` modes).
- **`cai-agent plugins --json`**: Payload now includes **`schema_version`: `plugins_surface_v1`** alongside the existing **`plugin_version`** (`list_plugin_surface`).
- **`cai-agent models fetch --json` contract**: Output is now **`{"schema_version":"models_fetch_v1","models":[…]}`** (**breaking change**: previously a bare JSON string array; automation should read **`models`**). See `docs/schema/README.zh-CN.md`.
- **Schedule stats SLA rollup (Hermes S4-05)**: Added **`cai-agent schedule stats`** with **`--json`**, **`--days`** (1–366, default 30), and optional **`--audit-file`**. Output **`schema_version`: `schedule_stats_v1`** and per-task **`success_rate`**, **`avg_elapsed_ms`**, **`p95_elapsed_ms`**, **`run_count`**, **`fail_count`** derived from **`task.completed` / `task.failed` / `task.retrying`** lines in `.cai-schedule-audit.jsonl` (legacy rows without `event` are mapped). See `docs/schema/SCHEDULE_STATS_JSON.zh-CN.md`.
- **Schedule audit JSONL schema (Hermes S4-04)**: `.cai-schedule-audit.jsonl` and `schedule daemon --jsonl-log` now emit **one consistent JSON shape** per line: `schema_version` (**`1.0`**), `event` (`task.started` / `task.completed` / `task.failed` / `task.retrying` / `task.skipped` / `daemon.cycle` / `daemon.started`), plus `task_id`, `goal_preview`, `elapsed_ms`, `error`, `status`, `action`, and `details`. `schedule run-due --execute` logs **`task.started`** before invoking the agent. See `docs/schema/SCHEDULE_AUDIT_JSONL.zh-CN.md`.
- **Schedule dependency validation & list view (Hermes S4-03)**: `add_schedule_task` rejects **`depends_on` cycles** (including self-edges) before persisting. `cai-agent schedule add` surfaces failures as **exit 2** with JSON `{"ok": false, "error": "schedule_add_invalid", "message": ...}`. `cai-agent schedule list` enriches output with **`depends_on_status`**, **`dependency_blocked`**, **`dependents`**, and a readable **`depends_on_chain`** (list JSON only; not stored in `.cai-schedule.json`). Text list adds compact `deps` / `dep_blocked` / `dependents` / `dep_chain` columns.
- **Schedule daemon concurrency cap (Hermes S4-02)**: `cai-agent schedule daemon` adds **`--max-concurrent`** (default **1**; **0** is treated as **1**). Each poll cycle executes at most N due jobs; additional due jobs are skipped for that cycle (not marked failed) and recorded as **`skipped_due_to_concurrency`** in `.cai-schedule-audit.jsonl` and in optional `--jsonl-log` lines. Final JSON adds `max_concurrent`, `total_skipped_due_to_concurrency`, and per-cycle `skipped_due_to_concurrency` / `skipped_due_to_concurrency_count`.
- **Schedule cross-run retries (Hermes S4-01)**: `.cai-schedule.json` tasks now persist `max_retries` (default **3**, CLI `schedule add --max-retries`), `retry_count`, and `next_retry_at`. After a failed `run-due --execute` / `daemon --execute`, `last_status` becomes **`retrying`** until the next backoff window elapses (`60 * 2^(retry_count-1)` seconds), then **`failed_exhausted`** when retries are exhausted; success clears counters. `compute_due_tasks` only surfaces `retrying` jobs when `next_retry_at` is due. JSON / audit lines for failures mirror the persisted status and retry fields.
- **Recall sort modes (Hermes S3-01)**: `cai-agent recall --json` and `recall-index search|benchmark` now accept `--sort recent|density|combined` (default `recent`). Payload includes `sort` plus an explicit `ranking` description; keyword-density scoring uses full matched message bodies (not only snippets) for more stable density ordering.
- **Recall no-hit reasons (Hermes S3-02)**: When a recall query returns zero hits, JSON payloads now include **`no_hit_reason`** (`window_too_narrow` / `pattern_no_match` / `index_empty` / `all_skipped`) and bump **`schema_version` to `1.3`**. Text mode prints a short human-readable hint line. Index search uses full indexed `content` for density scoring.
- **Recall index doctor (Hermes S3-03)**: Added `cai-agent recall-index doctor [--fix] [--json]` with **`schema_version: recall_index_doctor_v1`**, reporting `is_healthy`, `issues`, `stale_paths`, `missing_files`, and `schema_version_ok`. **`--fix`** rewrites the index after pruning missing/stale/invalid rows, then re-checks. Exit **0** when healthy, **2** when problems remain (including missing index file or bad JSON).
- **Recall perf bench (Hermes S3-04)**: Added `scripts/perf_recall_bench.py` to generate synthetic sessions and print a Markdown table with median **scan / index_build / index_search** timings (optional `--include-refresh` for no-op refresh timing). Defaults to writing under `docs/qa/runs/`; includes reference threshold columns for 200-session runs.
- **Memory health (Hermes parity)**: Added `cai-agent memory health --json` with `schema_version=1.0`, composite `health_score` / `grade` (A–D), and sub-metrics `freshness`, `coverage`, `conflict_rate` plus structured observability (`conflict_pairs`, `conflict_pair_count`, `conflict_compared_entries`, `conflict_max_compare_entries`, `conflict_similarity_metric`, coverage denominator helpers under `counts`). CLI flags include `--days`, `--freshness-days`, `--session-pattern`, `--session-limit`, `--conflict-threshold`, `--max-conflict-compare-entries`, and `--fail-on-grade` (exit 2 when the grade is not strictly better than the threshold).
- **Memory nudge recommendations**: Added `cai-agent memory nudge` (Hermes-inspired memory hygiene loop) to evaluate recent session volume and current memory health, then emit actionable reminders. Supports `--days`, `--session-pattern`, `--session-limit`, and `--json` output (`schema_version=1.0`, `severity`, `actions`, `memory_warnings`, `latest_instinct_path`) for automation and scheduled checks. Added `--write-file` to persist the JSON payload for cron/CI handoff, plus `--fail-on-severity medium|high` to return non-zero when severity reaches a configured threshold. When `--write-file` is set, the same JSON line is appended to `memory/nudge-history.jsonl` by default (override with `--history-file`; deduped when paths match).
- **Memory nudge trend report**: Added `cai-agent memory nudge-report` to aggregate `memory/nudge-history.jsonl` into an operator-friendly trend snapshot (`schema_version=1.2`, `history_total`, `severity_counts`, `latest_severity`, `severity_trend`, `severity_jumps`, `avg_recent_sessions`, `avg_memory_entries`, plus `health_score` / `health_grade` / `freshness` aligned with `memory health`). Supports `--history-file`, `--days` (time window filter), `--freshness-days`, `--limit`, and `--json`; useful for QA/ops drift monitoring across runs. `memory nudge --write-file` appends the same JSON line to the default history file (or `--history-file`) unless it points at the same path as `--write-file`.
- **Schedule nudge template shortcut**: Added `cai-agent schedule add-memory-nudge` to create a standard daily memory-governance task in one command. It generates a canonical nudge goal (JSON output + write-file + severity gate), supports overrides (`--every-minutes`, `--output-file`, `--fail-on-severity`, `--workspace`, `--model`, `--disabled`), and reduces manual quoting/flag drift when integrating with schedule daemon.
- **Recall index incremental refresh**: `recall-index refresh` merges into `.cai-recall-index.json` (schema `1.1`): skips re-parsing sessions whose `mtime` is unchanged, preserves entries outside the current `--days` scan window, and optional `--prune` removes missing files or entries older than the window. `recall-index build` remains a full rebuild. `recall --use-index` reads the index via `--index-path`; `recall-index` subcommands use `--index-path` consistently (`dest=index_path`).
- **Cross-session recall search**: Added `cai-agent recall` for Hermes-style session recall with keyword/regex search over saved session JSON files. Supports `--query`, `--regex`, `--days`, `--pattern`, `--limit`, `--json`, and returns ranked snippets with file path, mtime, model, and answer preview.
- **Schedule daemon guardrails**: `cai-agent schedule daemon` now supports a single-instance lock (`.cai-schedule.lock`) to prevent duplicate runners in one workspace, and optional JSONL append logging via `--log-file`. Added startup metadata (`pid`, `started_at`, mode flags) and per-cycle log records suitable for QA/ops tracing.
- **Schedule execute mode**: `cai-agent schedule run-due --execute` now performs real agent runs for due tasks (instead of metadata-only marking), captures per-task answer/error/elapsed metrics, and persists run status (`last_run_at`, `last_status`, `last_error`, `run_count`) back into `.cai-schedule.json`. `schedule list` includes `last_status`/`run_count` in text output; `schedule add --disabled` remains supported.
- **Zhipu AI (BigModel) OpenAI-compatible routing**: `profiles.PRESETS` adds **`zhipu`** (`cai-agent models add --preset zhipu …`); `normalize_openai_chat_base_url` / `project_base_url` **do not append `/v1`** to `https://open.bigmodel.cn/api/paas/v4` so chat hits `…/chat/completions` per [Zhipu’s OpenAI-compat guide](https://docs.bigmodel.cn/cn/guide/develop/openai/introduction). Example templates document **`ZAI_API_KEY`** + **`glm-5.1`**.
- **HTTP proxy vs local LLM**: When `[llm].http_trust_env` is `true`, httpx still uses **`trust_env=false` for loopback** (`localhost`, `127.*`, `::1`) on OpenAI-compat **chat**, **`GET …/models`** / `ping_profile`, and **MCP** HTTP clients so corporate proxies cannot break local LM Studio/Ollama with bogus **503** responses.
- **Sprint 3 — TUI model panel (M4)**: `Ctrl+M` / `/models` opens a richer panel (columns `id | model | provider | base_url | notes | [active]`; `Enter` switches chat profile; `a`/`e`/`d`/`t` add/edit/delete/ping with TOML persistence consistent with `cai-agent models`; empty-state guidance when the list is empty). See `docs/MODEL_SWITCHER_DEVPLAN.zh-CN.md` §4.
- **Sprint 3 — `/use-model` + provider hint (M5)**: When switching profiles changes the **provider**, the TUI appends a short hint suggesting `/compact` or `/clear` if context looks wrong across vendors.
- **Sprint 3 — `/status` + session fields (M7)**: `/status` prints an explicit `profile:` line; TUI `/save` and `run --save-session` JSON now include **`profile`** (active profile id) alongside **`active_profile_id` / `subagent_profile_id` / `planner_profile_id`**; session load accepts **`profile`** as a fallback for the active id.
- **Sprint 3 — docs / parity (M9) + P1 decision**: `docs/PARITY_MATRIX.zh-CN.md` adds a `Done` row for multi-profile + TUI; new `docs/WEBSEARCH_NOTEBOOK_MCP.zh-CN.md` records the **MCP-first** decision for WebSearch/Notebook and how `board --json` relates to `observe`; `board --json` adds top-level **`observe_schema_version`** mirroring the embedded `observe` payload.
- **Init & model presets for local stacks and gateways**: `cai-agent init --preset starter` copies a bundled `cai-agent.starter.toml` with explicit profiles for LM Studio, Ollama, vLLM, OpenRouter, **Zhipu GLM**, and a placeholder self-hosted OpenAI-compatible gateway. `cai-agent models add --preset` now includes **`vllm`**, **`gateway`**, and **`zhipu`** (plus existing presets); `profiles.PRESETS` documents default ports (`8000` / `8080`) and env vars (`VLLM_API_KEY`, `OPENAI_API_KEY`, `ZAI_API_KEY`). README / README.zh-CN / `docs/ONBOARDING.zh-CN.md` describe the flow; `doctor` hints at `init --preset starter` and the new CLI presets.
- **Removed Cursor Cloud API integration**: Dropped `cai-agent cursor`, `cai_agent.cursor_cloud`, TOML `[cursor]` / `CURSOR_*` settings, the TUI `Ctrl+Shift+M` / `/cursor-launch` flow, and the extra `doctor` line. **`cai-agent export --target cursor` is unchanged** — it only copies `rules/` / `skills/` / etc. into `.cursor/cai-agent-export` for IDE portability, not the Cloud Agents HTTP API.
- **TUI text selection & copy**: Dragging the mouse over the chat area now produces a real selection (`ALLOW_SELECT=True` set explicitly on the app so a future default flip won't regress us), and the new `Ctrl+Shift+C` binding calls `Screen.get_selected_text()` + `App.copy_to_clipboard()` to push it to the system clipboard (with a toast showing the copied character count, or a helpful hint when nothing is selected). `Ctrl+Shift+A` selects the entire chat area via `RichLog.text_select_all()` for one-shot copy. `Ctrl+C` stays bound to stop-run per terminal convention; the welcome banner and `/help` advertise the new shortcuts and the Windows-Terminal `Shift+drag` fallback.
- **Config discovery: user-level global fallback**: When `--config` / `CAI_CONFIG` / cwd-walk / `CAI_WORKSPACE` / `-w` hint all fail, `_resolve_config_file` now also tries a user-level config path, so `cai-agent ui` from any directory finds your settings. Order: `%APPDATA%\cai-agent\cai-agent.toml` (Windows) → `$XDG_CONFIG_HOME/cai-agent/cai-agent.toml` (default `~/.config/cai-agent/cai-agent.toml`) → `~/.cai-agent.toml` → `~/cai-agent.toml`. New `cai-agent init --global` seeds the OS-appropriate location (creating parent dirs as needed) from the bundled template. Project-level TOML still wins over the global one; `CAI_CONTEXT_WINDOW` env and per-profile `context_window` still override `[llm].context_window`. The "source=default" welcome hint now explicitly tells users about `init --global`, `CAI_CONFIG`, `--config`, and `-w` as the four concrete escape hatches.
- **Config discovery: workspace hint**: `Settings.from_env` / `from_sources` accept a new `workspace_hint` parameter (wired from every `cai-agent <cmd> -w/--workspace` call site in `__main__.py`). After cwd-walk, the resolver also walks from `CAI_WORKSPACE` and `workspace_hint`, fixing the "`cd` elsewhere, `-w` back to the project, and still read 8192" case.
- **TUI context usage bar**: A new row above the input shows `ctx ███░░ prompt_tokens / context_window (pct%)` — green <70%, yellow 70–89%, red ≥90%. Values come from the server's `prompt_tokens` after each response; before the first call the bar falls back to a **CJK-aware estimator** (`~N`, "估算" — CJK ~1.5 chars/token, ASCII ~4 chars/token so Chinese-heavy prompts aren't under-counted by 2–3×). Configurable via `[llm].context_window` (fallback), `[[models.profile]].context_window` (preferred), or `CAI_CONTEXT_WINDOW`. Default `8192`. `Settings` gains `context_window_source` (`profile|llm|env|default`) and both the TUI welcome banner and `/status` now print the resolved window and its source so users can diagnose "why is my denominator 8k" at a glance. Pressing Enter re-estimates immediately (doesn't wait for the server round-trip). Also exposes `cai_agent.llm.get_last_usage()` / `estimate_tokens_from_messages()` for programmatic use; `graph.llm_node` emits a `phase="usage"` progress event after every LLM call.
- **Empty-completion guard** (Qwen3 / DeepSeek-R1 / LM Studio reasoning models): when the server returns `content=""` plus a large `reasoning_content` (reasoning-budget exhaustion), the OpenAI-compat and Anthropic adapters now synthesise a `{"type":"finish","message":"[empty-completion] ..."}` envelope with an actionable diagnostic instead of crashing on `extract_json_object("")` or spinning to `max_iterations`. `<think>…</think>` prefixes are also stripped transparently. Two old Anthropic "raise on empty" contracts flipped to the new envelope — see `test_llm_empty_content_guard.py`.
- **`plan --json` + missing config**: `--config` pointing at a non-existent file now prints a JSON error (`error: config_not_found`) instead of only stderr.
- **`stats` (text mode)**: One-line summary adds `run_events_total`, `sessions_with_events`, and `parse_skipped`.
- **Hooks**: `observe_start` / `observe_end` wrap `observe`; `cost_budget_start` / `cost_budget_end` wrap `cost budget`; human `observe` line includes `run_events_total`.
- **`stats --json`**: Adds `stats_schema_version` (`1.0`), `run_events_total`, `sessions_with_events`, `parse_skipped`, and `session_summaries` (per-file `events_count`, `task_id`, tokens, tool stats).
- **`plan --json` errors**: Empty goal or LLM failure returns a JSON line with `ok: false`, `error` (`goal_empty` / `llm_error`), and `task` marked `failed` when applicable; success payloads include `ok: true`.
- **Hooks**: `memory_start` / `memory_end` wrap `cai-agent memory`; `export_start` / `export_end` wrap `cai-agent export` (adds `-w` / `--workspace` on export).
- **`plan --json`**: Stable envelope with `plan_schema_version` (`1.0`), `generated_at` (UTC ISO), and `task` (`plan-*` id via `new_task`).
- **`sessions --json`**: Without `--details`, each row still tries to parse the session file and adds `events_count`, `run_schema_version`, `task_id`, `total_tokens`, and `error_count` when possible (`parse_error` on failure). `--details` text lines now include `events=…`.
- **`security-scan` hooks**: `security_scan_start` / `security_scan_end` wrap `cai-agent security-scan` (stderr hook id listing; `security_scan_end` still runs if the scan raises).
- **Session files**: `--save-session` now persists `run_schema_version`, `events`, tool stats (`tool_calls_count`, `used_tools`, `last_tool`, `error_count`), and `post_gate` when applicable—aligned with `run --json`.
- **observe**: Per-session rows include `task_id`, `events_count`, and `run_schema_version`; aggregates add `run_events_total` and `sessions_with_events`.
- **workflow hooks**: `workflow_start` / `workflow_end` hook events (stderr hook id listing, same as session hooks) wrap `cai-agent workflow`.
- **quality-gate hooks**: `quality_gate_start` / `quality_gate_end` wrap the standalone `cai-agent quality-gate` command; `quality-gate` also honors `-w` / `--workspace` when passed via the shared parser.
- **fetch_url**: Block common SSRF hostnames (`localhost`, GCP metadata hosts) before allowlist checks.
- **fetch_url tool**: Opt-in HTTPS GET with host allowlist, size cap, and timeout; gated by `[fetch_url]` and `[permissions].fetch_url` (default deny). See `templates/cai-agent.example.toml` and `docs/MCP_WEB_RECIPE.zh-CN.md`.
- **Run JSON envelope**: `run --json` / `continue --json` (and shared path for `command` / `agent` / `fix-build`) include `run_schema_version` and `events` (`run.started` / `run.finished`) aligned with `workflow` telemetry style.
- **Memory entries**: Validate each `memory/entries.jsonl` row before append (v1 shape; JSON Schema file under `cai_agent/schemas/` for external tooling).
- **Doctor**: Prints `fetch_url` enablement and allowlist count when enabled.
- **QA regression logs**: `scripts/run_regression.py` writes a timestamped Markdown report under `docs/qa/runs/` (see `docs/QA_REGRESSION_LOGGING.md`); CI uploads those files as workflow artifacts.
- **Changelog split**: `CHANGELOG.md` is now English by default; the previous Chinese text lives in `CHANGELOG.zh-CN.md`.
- **Readme split**: `README.md` is English by default; the previous Chinese readme is in `README.zh-CN.md`, with cross-links at the top of each file.
- **JSON diagnostics**: `run --json` / `continue --json` add `last_tool` and `error_count`.
- **Session management**: New `cai-agent sessions` subcommand; TUI adds `/sessions` and `/load latest` for quick restore.
- **Session details**: `cai-agent sessions --details` shows message count, tool calls, error count, and answer preview per file.
- **Session matching fix**: `sessions` and `/load latest` default to `.cai-session*.json`, including `.cai-session.json` and auto-named files.
- **Rules expansion**: New common and Python rule docs (naming/structure, logging/errors, secrets, Git, docs, performance, context/memory, MCP, typing, tests/CI, packaging, CLI/TUI, config evolution).
- **Skills expansion**: New workflow docs (planning, refactors, features+tests, debugging, security scan, performance, deps, API integration, reviews, pre-release, workflows, migrations).
- **Readme sync**: Describes `rules/` and `skills/` as a reusable content library beyond skeleton dirs.
- **Rules round 2**: Hooks, sub-agents, validation, research-first, prompt hygiene, concurrency, HTTP retries.
- **Skills round 2**: search-first, TDD, verification loop, hook design, sub-agent orchestration, memory extraction, coverage audit, hardening, postmortems, doc sync.
- **Readme sync 2**: Governance and execution workflow themes.
- **Runtime skeleton**: `commands/`, `agents/`, `hooks/` with `hooks.json` and session lifecycle guidance.
- **Readme sync 3**: Documents commands/agents/hooks and “library → runtime surface” positioning.
- **Bugfix (tool node)**: `graph` tool node avoids raw `pending` indexing; uses validated `name`/`args` to reduce KeyError risk.
- **CLI command templates**: `cai-agent commands` and `cai-agent command <name> <goal...>` read `commands/*.md` as templates.
- **Hook runtime**: `hook_runtime` reads `hooks/hooks.json` on session start/end for `run`/`continue`/`command` (non-JSON mode prints enabled hook ids).
- **Readme sync 4**: Usage for `commands`/`command` and hook runtime.
- **Bugfix (command save_session)**: `command` subcommand gains safe `save_session` handling.
- **CLI agents**: `cai-agent agents` and `cai-agent agent <name> <goal...>` load `agents/*.md` role templates.
- **Auto skill injection**: `command` / `agent` injects matching `skills/*.md` (same name or prefix).
- **Readme sync 5**: Documents `agent` usage and command/role + skill composition.

### 0.4.1

- **TUI save**: `/save` may omit path; default filename `.cai-session-YYYYMMDD-HHMMSS.json`.

### 0.4.0

- **JSON fields**: `run --json` / `continue --json` add `tool_calls_count` and `used_tools`.
- **TUI load summary**: After `/load <path>`, show assistant rounds, tool calls, last answer preview.

### 0.3.9

- **JSON fields**: `run --json` / `continue --json` add `provider`, `model`, `mcp_enabled`, `elapsed_ms` for scripts/CI.
- **TUI sessions**: `/save <path>` and `/load <path>` in the UI.

### 0.3.8

- **Readme at repo root**: Single top-level readme to avoid duplicating `cai-agent/README.md`.
- **MCP probe**: `mcp-check` adds `--tool` / `--args` for a real tool call after listing tools.

### 0.3.7

- **Cross-platform docs**: macOS/Linux install, config copy, env vars, common commands.
- **MCP ops**: `mcp-check` adds `--force` / `--verbose`; TUI adds `/mcp refresh` and `/mcp call <name> <json_args>`.

### 0.3.6

- **MCP usability**: `cai-agent mcp-check`; `mcp_list_tools` short TTL cache (15s, `force=true` refresh); TUI `/mcp`.

### 0.3.5

- **MCP Bridge**: `mcp_list_tools` / `mcp_call_tool` with config; `doctor` and TUI `/status` show MCP state.

### 0.3.4

- **Git read-only tools**: `git_status` and `git_diff` to scope changes before heavy file reads.

### 0.3.3

- **TUI model management**: `/models` and `/use-model <id>` to list and switch models without restart.

### 0.3.2

- **Copilot model pick**: `cai-agent models` (`/v1/models`) and global `--model` for `run`/`continue`/`ui`/`doctor`/`models`.

### 0.3.1

- **Copilot provider**: `llm.provider` (`openai_compatible` / `copilot`); `doctor` and `/status` show provider; `[copilot]` and `COPILOT_*` env vars.

### 0.3.0

- **Session I/O**: `run` supports `--save-session` / `--load-session` for JSON `messages` round-trip.
- **`cai-agent continue`**: Continue from session JSON (same idea as `run --load-session`).
- **`run_command`**: `cwd` relative to workspace, still sandboxed.

### 0.2.x

- **`cai-agent doctor`**: Resolved config, workspace, doc files, git repo flag; **redacts API key**; `--config`, `-w` / `--workspace`.
- **`Settings.config_loaded_from`**: Absolute path of loaded TOML (or `None`); included in `run --json` for scripts.
- **`run --json`**: One-line JSON to stdout (`answer`, `iteration`, `finished`, `config`, `workspace`); no stderr transcript spam.
- **LLM retries**: Backoff on HTTP **429 / 502 / 503 / 504** (up to 5 attempts).
- **Tools**: `read_file` **`line_start` / `line_end`** (optional read to EOF); **`list_tree`** with depth/entry limits.
- **TUI**: **`/status`** model/workspace; **`/reload`** rebuilds first system message (project + git context).

### 0.1.x and earlier (summary)

- **`cai-agent init`**: Writes `cai-agent.toml` (`--force` overwrite).
- **Config**: `temperature`, `timeout_sec`, `project_context`, `git_context`, etc.; env overrides.
- **System prompt**: Optional `CAI.md` / `AGENTS.md` / `CLAUDE.md` and read-only git summary.
- **Tools**: `glob_search`, `search_text`; `run` / `ui`; bundled example TOML template.
