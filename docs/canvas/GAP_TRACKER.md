# Canvas gap tracker (aligned with the current roadmap)

This file is no longer a separate planning source. It only mirrors the active backlog in [`../ROADMAP_EXECUTION.zh-CN.md`](../ROADMAP_EXECUTION.zh-CN.md) so the old canvas rows do not drift away from the current three-repo product plan.

## 1. Mapping: old canvas rows -> current roadmap IDs

| Old row | Current roadmap ID | Meaning now |
|----|----|----|
| `A1` / `A3` / `E1` | `HM-05` | Memory providers, user model, recall evaluation, memory policy gates |
| `B1` / `B2` / `B3` / `B4` | `HM-03` | Discord, Slack, gateway ops, gateway perf/productization |
| `D1` / `D2` | `HM-04` | Ops dashboard and dynamic read-only operations UI |
| `F1` / `F2` | `ECC-02` | Cost dashboard, model routing, compact triggers |
| `G3` | `ECC-01` | Rules / skills / hooks assetization and install flow |
| `G4` / `I1` / `I2` | `REL-01` | Feedback loop, release checklist, semantic changelog |
| `H1` | `HM-06` | Runtime backends productization |
| `J1` / `J2` | `HM-07` or `OOS` | Voice / native WebSearch-Notebook style boundaries |

## 2. Active tracker

Status vocabulary:

- `Done`: already closed in the current doc consolidation / roadmap pass
- `Ready`: can be opened as a development issue now
- `Design`: needs a schema or contract decision first
- `Explore`: research or boundary-setting only, not default delivery this cycle

| ID | Status | Suggested next issue | Pointer |
|----|--------|----------------------|---------|
| `DOC-01` | `Done` | **`DOC-01a`/`DOC-01b`/`DOC-01c` Done** — entry docs and bilingual pointers stable | `ROADMAP_EXECUTION` §10 |
| `REL-01` | `Done` | **`REL-01a`/`REL-01b` Done** — release runbook + feedback 同源 | `ROADMAP_EXECUTION` §10 |
| `CC-01` | `Done` | **`CC-01b` Done** — `/mcp-presets` + task board/help/status quickstart + `mcp-check` epilog | `ROADMAP_EXECUTION` §10 |
| `CC-02` | `Done` | **`CC-02b` Done** — `feedback bug` + `feedback_bug_report_v1` | `ROADMAP_EXECUTION` §10 |
| `CC-03` | `Done` | **`CC-03a`/`CC-03b` Done**（`tui_session_strip` + RFC **CC-03b**） | `ROADMAP_EXECUTION` §10 |
| `MODEL-P0` | `Done` | **`MODEL-P0a`/`MODEL-P0b`/`MODEL-P0c` Done** — Model Gateway、capabilities、health/chat-smoke、`doctor_model_gateway_v1`、routing explain / `model_fallback_candidates_v1`、`models onboarding` runbook | `ROADMAP_EXECUTION` §10 |
| `HM-01` | `Done` | **`HM-01a`/`HM-01b` Done** — profile contract + management CLI/fixture/smoke | `ROADMAP_EXECUTION` §10 |
| `HM-02` | `Done` | **`HM-02a`/`HM-02b`/`HM-02c`/`HM-02d-openai` Done**（RFC + `api serve` + 只读扩展 `models/plugins/release` + OpenAI-compatible `/v1/models` 与非流式/SSE `/v1/chat/completions`） | `ROADMAP_EXECUTION` §10 |
| `HM-03` | `Done` | **`HM-03a`/`HM-03b`/`HM-03c`/`HM-03d-teams`/`HM-03e-prod` Done**；生产状态摘要已收口为 `gateway_production_summary_v1` | `ROADMAP_EXECUTION` §10 |
| `HM-04` | `Done` | **`HM-04a`/`HM-04b`/`HM-04c` Done**；高级交互先以 `ops_dashboard_interactions_v1` dry-run 预览契约落地 | `ROADMAP_EXECUTION` §10 |
| `HM-05` | `Done` | **`HM-05a`/`HM-05b`/`HM-05c`/`HM-05d` Done**；provider 边界已收口为 `memory_provider_contract_v1` | `ROADMAP_EXECUTION` §10 |
| `HM-06` | `Done` | **`HM-06a`/`HM-06b-docker`/`HM-06c-ssh` Done**；云 runtime 仍按 OOS/条件立项处理 | `ROADMAP_EXECUTION` §10 |
| `HM-07` | `Done` | **`HM-07a` Done**（Voice **OOS** 边界 RFC；默认不实现） | `ROADMAP_EXECUTION` §10 |
| `ECC-01` | `Done` | **`ECC-01a`/`ECC-01b` Done**（`ecc` CLI + 安装/导出/共享文档） | `ROADMAP_EXECUTION` §10 |
| `ECC-02` | `Done` | **`ECC-02a`/`ECC-02b` Done**（routing-test / cost report + compact explain） | `ROADMAP_EXECUTION` §10 |
| `ECC-03` | `Done` | **`ECC-03a`/`ECC-03b`/`ECC-03c` Done**（治理 RFC + compat check + CI snapshot） | `ROADMAP_EXECUTION` §10 |

## 3. Usage rule

When a roadmap item changes status:

1. Update [`../ROADMAP_EXECUTION.zh-CN.md`](../ROADMAP_EXECUTION.zh-CN.md) first.
2. Mirror the status here.
3. Move completed task details to [`../COMPLETED_TASKS_ARCHIVE.zh-CN.md`](../COMPLETED_TASKS_ARCHIVE.zh-CN.md); move **Done** TODO table rows to [`../TODOS_DONE_ARCHIVE.zh-CN.md`](../TODOS_DONE_ARCHIVE.zh-CN.md); keep [`../DEVELOPER_TODOS.zh-CN.md`](../DEVELOPER_TODOS.zh-CN.md) / [`../TEST_TODOS.zh-CN.md`](../TEST_TODOS.zh-CN.md) focused on **unfinished** work and future directions.
4. If an old canvas row becomes irrelevant, map it to `OOS` instead of inventing a new parallel bucket.
