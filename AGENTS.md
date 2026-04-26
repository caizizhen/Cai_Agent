# AGENTS.md

This is the low-token entry point for agent development in this repository.

## Read Order

1. Read `docs/NEXT_ACTIONS.zh-CN.md` first.
2. Read only the source file, test file, or doc section named by that task.
3. Use `docs/README.zh-CN.md` only as an index when the task is unclear.
4. Do not read full `README*`, `CHANGELOG*`, or large roadmap docs unless the task is docs, release, or planning.

## Current Source Of Truth

- Current next work: `docs/NEXT_ACTIONS.zh-CN.md`
- Full developer backlog: `docs/DEVELOPER_TODOS.zh-CN.md`
- Full test backlog: `docs/TEST_TODOS.zh-CN.md`
- Product gap rationale: `docs/PRODUCT_GAP_ANALYSIS.zh-CN.md`
- Current capability snapshot: `docs/PRODUCT_PLAN.zh-CN.md`
- Historical completion evidence: `docs/COMPLETED_TASKS_ARCHIVE.zh-CN.md`
- Release history only: `CHANGELOG.md` / `CHANGELOG.zh-CN.md`

## Project Map

- `cai-agent/src/cai_agent/__main__.py`: CLI command wiring and subcommands.
- `cai-agent/src/cai_agent/tui.py`: Textual TUI, slash commands, model/status UI.
- `cai-agent/src/cai_agent/config.py`: TOML/env settings and runtime configuration.
- `cai-agent/src/cai_agent/context.py`: project context and git summary injection.
- `cai-agent/src/cai_agent/doctor.py`: diagnostics and repair recommendations.
- `cai-agent/src/cai_agent/feedback.py`: feedback reports, bundles, sanitization.
- `cai-agent/src/cai_agent/command_registry.py`: command/template discovery.
- `cai-agent/tests/`: pytest coverage; prefer narrow tests for narrow changes.
- `scripts/smoke_new_features.py`: main smoke check for user-visible features.

## Token Discipline

- Prefer `rg` and targeted reads over broad file scans.
- Read headings or tables first, then the relevant section.
- Summarize large docs into the working plan instead of copying them into prompts.
- Keep generated plans short and grounded in file paths plus verification commands.
- If context grows, compact after a milestone, a failed tool loop, or before switching tasks.

## NEXT_ACTIONS Freshness Rule

`docs/NEXT_ACTIONS.zh-CN.md` must be updated in the same change whenever:

- a task moves between `Now`, `Next`, `Blocked`, `Done`, `OOS`, or `Conditional`;
- a new priority is added to `DEVELOPER_TODOS.zh-CN.md` or `TEST_TODOS.zh-CN.md`;
- a change updates product status, release notes, roadmap state, or acceptance evidence;
- a developer finishes work and leaves a different best next step for the next session.

Keep `NEXT_ACTIONS` short. Move detail to the full backlog docs and link it.

## Completion Protocol

When a task is actually finished, run verification, then run:

```powershell
uv run --project cai-agent python scripts/finalize_task.py --task-id <ID> --summary "<what changed>" --verification "<command: PASS>"
```

This removes the task from `NEXT_ACTIONS` current work, appends completion evidence
to `COMPLETED_TASKS_ARCHIVE.zh-CN.md`, and writes a QA run note. Use `--push`
only after the working tree contains the intended files and tests passed.
