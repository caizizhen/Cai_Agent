# 已完成任务归档

> 本页归档已经完成的开发 / 设计 / 文档任务，避免 [`DEVELOPER_TODOS.zh-CN.md`](DEVELOPER_TODOS.zh-CN.md) 继续堆积历史完成项。
>
> 当前状态源仍以 [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md) §10 为准；本页只做完成项回溯与交付摘要。

## 2026-04-25 从 TODO 迁移的 Done 项

为保证 `DEVELOPER_TODOS` 只保留未完成事项，以下已完成条目已从 TODO 正文移除并在本页留档：

- `MODEL-P0-01`～`MODEL-P0-07`（能力级）；
- `MODEL-P0-D01`～`MODEL-P0-D14`（原子级）；
- `HM-N02`（能力级）与 `HM-N02-D01`～`HM-N02-D05`（原子级）。

对应交付与验证证据见本页 `MODEL-P0a` / `MODEL-P0b` / `MODEL-P0c` / `HM-02d-openai` 等归档条目，以及 `ROADMAP_EXECUTION.zh-CN.md` §10。

## DOC / REL

| Issue ID | 父 To-do | 交付摘要 | 验证 | 来源 / 备注 |
|---|---|---|---|---|
| `DOC-01a` | `DOC-01` | 统一根 README 与 docs 入口 | 手工检查 + 链接检查 | roadmap §10 |
| `DOC-01b` | `DOC-01` | 删除重复 roadmap / backlog 文档并清理引用 | `rg` 无残链 | roadmap §10 |
| `DOC-01c` | `DOC-01` | 中英文入口补 Teams/runtime/plugin snapshot 指针，README/docs README 互指 | 手工 + `rg` | 2026-04-25 批次 |
| `REL-01a` | `REL-01` | 收口 `release-ga` / `doctor` / changelog 回写流程 | `doctor` + smoke + checklist | roadmap §10 |
| `REL-01b` | `REL-01` | `feedback stats`；`doctor --json.feedback` 与 `release_runbook.feedback` 同源 | pytest + smoke | roadmap §10 |

## Claude Code 线

| Issue ID | 父 To-do | 交付摘要 | 验证 | 来源 / 备注 |
|---|---|---|---|---|
| `CC-01a` | `CC-01` | `mcp-check` preset、模板、WebSearch/Notebook onboarding 入口 | 预设探测 + 文档示例 | roadmap §10 |
| `CC-01b` | `CC-01` | `/mcp-presets`、任务看板/help/status quickstart、`mcp-check --help` epilog | pytest | roadmap §10 |
| `CC-02a` | `CC-02` | 安装、更新、版本提示与 onboarding 文档链路 | walkthrough | roadmap §10 |
| `CC-02b` | `CC-02` | `feedback bug`、`feedback_bug_report_v1`、`sanitize_feedback_text` | pytest `test_feedback_cli` | roadmap §10 |
| `CC-03a` | `CC-03` | `tui_session_strip` 单源文案、会话继续与任务板体验统一 | pytest | roadmap §10 |
| `CC-03b` | `CC-03` | 模型切换与 `/status` 提示 RFC | RFC 评审 | `docs/rfc/CC_03B_MODEL_STATUS_UX.zh-CN.md` |
| `CC-03c` | `CC-03` | TUI `#context-label` route/migration 提示；CLI/TUI 共享 `profile_switched: <id>` | pytest | 2026-04-25 批次 |

## Hermes 线

| Issue ID | 父 To-do | 交付摘要 | 验证 | 来源 / 备注 |
|---|---|---|---|---|
| `MODEL-P0a` | `MODEL-P0` | Model Gateway contract、`ModelResponse`、`model_capabilities_list_v1`、CLI/API capabilities、OpenAI-compatible API 复用 response envelope | pytest `test_model_gateway` / `test_model_profiles_cli` / `test_api_http_server` | 2026-04-25 MODEL-P0 批次 |
| `MODEL-P0b` | `MODEL-P0` | `models ping --chat-smoke`、健康状态枚举、`doctor_model_gateway_v1`、模型接入 runbook | pytest `test_model_profiles_cli` / `test_doctor_cli` + smoke | 2026-04-25 MODEL-P0 批次 |
| `MODEL-P0c` | `MODEL-P0` | `routing_explain_v1`、base/effective capabilities、`model_fallback_candidates_v1` explain-only fallback、成本/metrics 口径 | pytest `test_model_routing` + smoke | 2026-04-25 MODEL-P0 批次 |
| `HM-01a` | `HM-01` | profile schema、切换规则、默认项、迁移策略 | schema review | roadmap §10 |
| `HM-01b` | `HM-01` | `models add/edit/rm/use/route/list` 闭环、`profile_contract_v1`、fixture / smoke 回归 | pytest + smoke | roadmap §10 |
| `HM-02a` | `HM-02` | 最小 API / server 契约 RFC | RFC 合入 | `docs/rfc/HM_02_MINIMAL_SERVER_CONTRACT.zh-CN.md` |
| `HM-02b` | `HM-02` | `api serve`：`/healthz`、`/v1/status`、`/v1/doctor/summary`、`/v1/tasks/run-due` dry-run | pytest + smoke | roadmap §10 |
| `HM-02c` | `HM-02` | API 只读扩展：models summary、plugins surface、release runbook | pytest | 2026-04-25 批次 |
| `HM-02d-openai` | `HM-02` | OpenAI-compatible `/v1/models` 与 `/v1/chat/completions`（非流式 + `stream=true` SSE），复用 `model_response_v1` 并记录 `api.chat_completions` metrics | pytest `test_api_http_server` + smoke | 2026-04-25 MODEL-P0 批次 |
| `HM-03a` | `HM-03` | Discord gateway 生产路径：mapping、health、排障 | gateway smoke + `doctor` | roadmap §10 |
| `HM-03b` | `HM-03` | Slack gateway：health、Slash/Interactivity、mapping metadata、`--execute-on-slash` | gateway smoke + `doctor` | roadmap §10 |
| `HM-03c` | `HM-03` | 下一批 gateway 平台评估 RFC | 文档评审 | `docs/rfc/HM_03C_NEXT_GATEWAY_PLATFORMS.zh-CN.md` |
| `HM-03d-teams` | `HM-03` | `gateway teams`：bind/get/list/unbind/allow/health/manifest/serve-webhook；纳入 platforms/maps | pytest + smoke | 2026-04-25 批次 |
| `HM-03e-prod` | `HM-03` | `gateway prod-status --json`；`gateway_production_summary_v1` 汇总四平台状态 | pytest + smoke | 2026-04-25 批次 |
| `HM-04a` | `HM-04` | `board` / `ops dashboard` / `gateway status` 同源 `gateway_summary_v1` | JSON snapshot | roadmap §10 |
| `HM-04b` | `HM-04` | `ops serve` 只读 dashboard JSON/HTML/SSE | 浏览器手测 + pytest | roadmap §10 |
| `HM-04c` | `HM-04` | `ops_dashboard_interactions_v1`；schedule reorder / gateway bind-edit dry-run 预览 | pytest `test_ops_http_server` | 2026-04-25 批次 |
| `HM-05a` | `HM-05` | user-model store/query/learn 主链路 | pytest + smoke | roadmap §10 |
| `HM-05b` | `HM-05` | `recall --evaluate` 与负样本审计 | pytest + smoke | roadmap §10 |
| `HM-05c` | `HM-05` | memory policy 接入 doctor / release gate | doctor + release-ga pytest | roadmap §10 |
| `HM-05d` | `HM-05` | `memory provider --json`；`memory_provider_contract_v1` 固定 local/provider 边界 | pytest + smoke | 2026-04-25 批次 |
| `HM-06a` | `HM-06` | Runtime backend 产品化评估 RFC | 文档评审 | `docs/rfc/HM_06A_RUNTIME_BACKEND_ASSESSMENT.zh-CN.md` |
| `HM-06b-docker` | `HM-06` | Docker runtime `container` / `image` 双模式、workdir、volumes、limits、doctor describe | pytest + smoke | 2026-04-25 批次 |
| `HM-06c-ssh` | `HM-06` | SSH runtime 诊断、timeout、key/known_hosts、`runtime_ssh_audit_v1` | pytest + smoke | 2026-04-25 批次 |
| `HM-07a` | `HM-07` | Voice 边界与 OOS RFC | 文档评审 | `docs/rfc/HM_07A_VOICE_BOUNDARY.zh-CN.md` |

## ECC 线

| Issue ID | 父 To-do | 交付摘要 | 验证 | 来源 / 备注 |
|---|---|---|---|---|
| `ECC-01a` | `ECC-01` | rules/skills/hooks 资产目录、模板、安装说明 | 文档 + sample asset | roadmap §10 |
| `ECC-01b` | `ECC-01` | 导出 / 安装 / 共享流转文档统一 | 文档走查 | roadmap §10 |
| `ECC-02a` | `ECC-02` | routing/profile/budget 产品路径，`models routing-test` 与 wizard | CLI smoke | roadmap §10 |
| `ECC-02b` | `ECC-02` | `cost report` 嵌 `compact_policy_explain_v1`，文本摘要 | pytest + smoke | roadmap §10 |
| `ECC-03a` | `ECC-03` | 插件矩阵与版本治理 RFC | 文档评审 | `docs/rfc/ECC_03A_PLUGIN_VERSION_GOVERNANCE.zh-CN.md` |
| `ECC-03b` | `ECC-03` | `plugin_compat_matrix_v1.maintenance_checklist` 与 `plugins --compat-check` | pytest | 2026-04-25 批次 |
| `ECC-03c` | `ECC-03` | `scripts/gen_plugin_compat_snapshot.py --check` 与 checked-in snapshot | pytest + smoke | 2026-04-25 批次 |

## 最新验证基线

2026-04-25 本地验证：

| 检查项 | 命令 | 结果 |
|---|---|---|
| 全量单测 | `python -m pytest -q cai-agent/tests` | **742 passed**, **3 subtests passed** |
| 冒烟 | `python scripts/smoke_new_features.py` | **PASS**，输出 `NEW_FEATURE_CHECKS_OK` |
| 回归 | `QA_SKIP_LOG=1 python scripts/run_regression.py` | **PASS** |
