# Documentation Map

This page is the English docs entrypoint.

## Read these first

| Purpose | Document |
|---|---|
| First-run path | [`ONBOARDING.zh-CN.md`](ONBOARDING.zh-CN.md) |
| Current capabilities and test progress | [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md) |
| Current roadmap / todo list | [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md) |
| Execution issue drafts | [`ISSUE_BACKLOG.md`](ISSUE_BACKLOG.md) / [`ISSUE_BACKLOG.zh-CN.md`](ISSUE_BACKLOG.zh-CN.md) |
| Developer start list | [`DEVELOPER_TODOS.zh-CN.md`](DEVELOPER_TODOS.zh-CN.md) |
| Test start list | [`TEST_TODOS.md`](TEST_TODOS.md) / [`TEST_TODOS.zh-CN.md`](TEST_TODOS.zh-CN.md) |
| Gaps, boundaries, release gates | [`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md) |
| Release review matrix | [`PARITY_MATRIX.zh-CN.md`](PARITY_MATRIX.zh-CN.md) |
| Rolling implementation summary | [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md) / [`IMPLEMENTATION_STATUS.zh-CN.md`](IMPLEMENTATION_STATUS.zh-CN.md) |
| Version history | repo-root `CHANGELOG.md` / `CHANGELOG.zh-CN.md` |

## Product target

CAI Agent is now positioned as a **single integrated runtime** that combines strengths from:

- [`anthropics/claude-code`](https://github.com/anthropics/claude-code)
- [`NousResearch/hermes-agent`](https://github.com/NousResearch/hermes-agent)
- [`affaan-m/everything-claude-code`](https://github.com/affaan-m/everything-claude-code)

See [`PRODUCT_VISION_FUSION.zh-CN.md`](PRODUCT_VISION_FUSION.zh-CN.md).

## Common topics

| Topic | Document |
|---|---|
| Architecture | [`ARCHITECTURE.zh-CN.md`](ARCHITECTURE.zh-CN.md) |
| JSON schemas / exit conventions | [`schema/README.zh-CN.md`](schema/README.zh-CN.md) |
| Ops dashboard HTTP contract | [`OPS_DYNAMIC_WEB_API.md`](OPS_DYNAMIC_WEB_API.md) |
| Model routing | [`MODEL_ROUTING_RULES.md`](MODEL_ROUTING_RULES.md) |
| Runtime backends | [`RUNTIME_BACKENDS.md`](RUNTIME_BACKENDS.md) |
| Cross-harness export | [`CROSS_HARNESS_COMPATIBILITY.md`](CROSS_HARNESS_COMPATIBILITY.md) |
| Plugin compatibility | [`PLUGIN_COMPAT_MATRIX.md`](PLUGIN_COMPAT_MATRIX.md); CI snapshot: [`schema/plugin_compat_matrix_v1.snapshot.json`](schema/plugin_compat_matrix_v1.snapshot.json) |

## Historical / compatibility docs

These remain mainly for old links and traceability:

- [`DEVELOPMENT_PROGRESS_TRACKER.zh-CN.md`](DEVELOPMENT_PROGRESS_TRACKER.zh-CN.md)
- [`HERMES_PARITY_PROGRESS.zh-CN.md`](HERMES_PARITY_PROGRESS.zh-CN.md)
- [`HERMES_PARITY_SPRINT_PLAN.zh-CN.md`](HERMES_PARITY_SPRINT_PLAN.zh-CN.md)
