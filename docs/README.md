# Documentation Map

This page is the English docs entrypoint.

## Read these first

| Purpose | Document |
|---|---|
| First-run path | [`ONBOARDING.md`](ONBOARDING.md) / [`ONBOARDING.zh-CN.md`](ONBOARDING.zh-CN.md) |
| Current capabilities, completion state, and test baseline | [`PRODUCT_PLAN.md`](PRODUCT_PLAN.md) / [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md) |
| Current product gaps and next-wave priorities | [`PRODUCT_GAP_ANALYSIS.md`](PRODUCT_GAP_ANALYSIS.md) / [`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md) |
| Next-wave developer backlog | Chinese-only: [`DEVELOPER_TODOS.zh-CN.md`](DEVELOPER_TODOS.zh-CN.md) |
| Next-wave test backlog | Chinese-only: [`TEST_TODOS.zh-CN.md`](TEST_TODOS.zh-CN.md) |
| Roadmap / milestone / status mapping | [`ROADMAP_EXECUTION.md`](ROADMAP_EXECUTION.md) / [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md) |
| Execution issue drafts | [`ISSUE_BACKLOG.md`](ISSUE_BACKLOG.md) / [`ISSUE_BACKLOG.zh-CN.md`](ISSUE_BACKLOG.zh-CN.md) |
| Completed task archive | [`COMPLETED_TASKS_ARCHIVE.md`](COMPLETED_TASKS_ARCHIVE.md) / [`COMPLETED_TASKS_ARCHIVE.zh-CN.md`](COMPLETED_TASKS_ARCHIVE.zh-CN.md) |
| Release review matrix | [`PARITY_MATRIX.md`](PARITY_MATRIX.md) / [`PARITY_MATRIX.zh-CN.md`](PARITY_MATRIX.zh-CN.md) |
| Rolling implementation summary | [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md) / [`IMPLEMENTATION_STATUS.zh-CN.md`](IMPLEMENTATION_STATUS.zh-CN.md) |
| Version history | repo-root `CHANGELOG.md` / `CHANGELOG.zh-CN.md` |

## Product target

CAI Agent is now positioned as a **single integrated runtime** that combines strengths from:

- [`anthropics/claude-code`](https://github.com/anthropics/claude-code)
- [`NousResearch/hermes-agent`](https://github.com/NousResearch/hermes-agent)
- [`affaan-m/everything-claude-code`](https://github.com/affaan-m/everything-claude-code)

See [`PRODUCT_VISION_FUSION.zh-CN.md`](PRODUCT_VISION_FUSION.zh-CN.md).

If you only read four files, use this order:

1. [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md)
2. [`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md)
3. [`DEVELOPER_TODOS.zh-CN.md`](DEVELOPER_TODOS.zh-CN.md)
4. [`TEST_TODOS.zh-CN.md`](TEST_TODOS.zh-CN.md)

## Common topics

| Topic | Document |
|---|---|
| Architecture | [`ARCHITECTURE.md`](ARCHITECTURE.md) / [`ARCHITECTURE.zh-CN.md`](ARCHITECTURE.zh-CN.md) |
| JSON schemas / exit conventions | [`schema/README.md`](schema/README.md) / [`schema/README.zh-CN.md`](schema/README.zh-CN.md) |
| Ops dashboard HTTP contract | [`OPS_DYNAMIC_WEB_API.md`](OPS_DYNAMIC_WEB_API.md) / [`OPS_DYNAMIC_WEB_API.zh-CN.md`](OPS_DYNAMIC_WEB_API.zh-CN.md) |
| Model onboarding runbook | Chinese-only: [`MODEL_ONBOARDING_RUNBOOK.zh-CN.md`](MODEL_ONBOARDING_RUNBOOK.zh-CN.md) |
| Model routing | [`MODEL_ROUTING_RULES.md`](MODEL_ROUTING_RULES.md) / [`MODEL_ROUTING_RULES.zh-CN.md`](MODEL_ROUTING_RULES.zh-CN.md) |
| Runtime backends | [`RUNTIME_BACKENDS.md`](RUNTIME_BACKENDS.md) / [`RUNTIME_BACKENDS.zh-CN.md`](RUNTIME_BACKENDS.zh-CN.md) |
| Memory policy | [`MEMORY_TTL_CONFIDENCE_POLICY.md`](MEMORY_TTL_CONFIDENCE_POLICY.md) / [`MEMORY_TTL_CONFIDENCE_POLICY.zh-CN.md`](MEMORY_TTL_CONFIDENCE_POLICY.zh-CN.md) |
| MCP Web recipe | [`MCP_WEB_RECIPE.md`](MCP_WEB_RECIPE.md) / [`MCP_WEB_RECIPE.zh-CN.md`](MCP_WEB_RECIPE.zh-CN.md) |
| Cross-harness export | [`CROSS_HARNESS_COMPATIBILITY.md`](CROSS_HARNESS_COMPATIBILITY.md) / [`CROSS_HARNESS_COMPATIBILITY.zh-CN.md`](CROSS_HARNESS_COMPATIBILITY.zh-CN.md) |
| Plugin compatibility | [`PLUGIN_COMPAT_MATRIX.md`](PLUGIN_COMPAT_MATRIX.md) / [`PLUGIN_COMPAT_MATRIX.zh-CN.md`](PLUGIN_COMPAT_MATRIX.zh-CN.md); CI snapshot: [`schema/plugin_compat_matrix_v1.snapshot.json`](schema/plugin_compat_matrix_v1.snapshot.json) |

## Historical / compatibility docs

Historical docs now live under [`archive/`](archive/). They remain for traceability and should not be updated as active planning sources:

- [`DEVELOPMENT_PROGRESS_TRACKER.zh-CN.md`](archive/legacy/DEVELOPMENT_PROGRESS_TRACKER.zh-CN.md)
- [`HERMES_PARITY_PROGRESS.zh-CN.md`](archive/legacy/HERMES_PARITY_PROGRESS.zh-CN.md)
- [`HERMES_PARITY_SPRINT_PLAN.zh-CN.md`](archive/legacy/HERMES_PARITY_SPRINT_PLAN.zh-CN.md)

## Maintenance Rules

- Keep current-state completion and test baseline in `PRODUCT_PLAN`.
- Keep product gaps, priorities, and OOS boundaries in `PRODUCT_GAP_ANALYSIS`.
- Keep next-wave developer backlog in `DEVELOPER_TODOS`.
- Keep next-wave QA backlog in `TEST_TODOS`.
- Keep milestone / roadmap status in `ROADMAP_EXECUTION`.
- Keep completed evidence in `COMPLETED_TASKS_ARCHIVE`.
- Keep version history in `CHANGELOG`.
- Keep current docs bilingual. English companion summaries are acceptable for large Chinese-primary planning documents, but avoid creating a second independent status matrix.
- Archived docs are frozen except for link repairs.
