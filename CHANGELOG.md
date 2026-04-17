## Changelog

> Version history for `cai-agent`. **This file (`CHANGELOG.md`) is the default English changelog.** For the full Chinese log see **`CHANGELOG.zh-CN.md`**. The root **`README.md`** is English by default; **`README.zh-CN.md`** is the full Chinese readme.

### 0.5.0 (in development)

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
