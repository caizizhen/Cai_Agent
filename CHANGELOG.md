## Changelog

> Version history for `cai-agent`. **This file (`CHANGELOG.md`) is the default English changelog.** For the full Chinese log see **`CHANGELOG.zh-CN.md`**. The root **`README.md`** is English by default; **`README.zh-CN.md`** is the full Chinese readme.

### 0.5.0 (in development)

- **Memory nudge recommendations**: Added `cai-agent memory nudge` (Hermes-inspired memory hygiene loop) to evaluate recent session volume and current memory health, then emit actionable reminders. Supports `--days`, `--session-pattern`, `--session-limit`, and `--json` output (`schema_version=1.0`, `severity`, `actions`, `memory_warnings`, `latest_instinct_path`) for automation and scheduled checks. Added `--write-file` to persist the JSON payload for cron/CI handoff, plus `--fail-on-severity medium|high` to return non-zero when severity reaches a configured threshold.
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
