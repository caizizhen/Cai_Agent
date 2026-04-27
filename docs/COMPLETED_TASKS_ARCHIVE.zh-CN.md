# 已完成任务归档

> 本页归档已经完成的开发 / 设计 / 文档任务（叙述摘要与按主题留档）。从开发 TODO / 测试 TODO 拆出的 Done 行另见 [`TODOS_DONE_ARCHIVE.zh-CN.md`](TODOS_DONE_ARCHIVE.zh-CN.md)。
>
> 当前状态源仍以 [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md) §10 为准；本页只做完成项回溯与交付摘要。

## 2026-04-25 从 TODO 迁移的 Done 项

为保证 `DEVELOPER_TODOS` 只保留未完成事项，叙述型完成项在本页留档；**表格级 Done 行**另集中在 [`TODOS_DONE_ARCHIVE.zh-CN.md`](TODOS_DONE_ARCHIVE.zh-CN.md)。以下为历史迁移说明中曾列出的条目：

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
| `CC-N01-D04` | `CC-N01` | `doctor_upgrade_hints_v1`：统一 repair / ecc / export 与文档指针 | pytest `test_doctor_cli` | 2026-04-26 批次 |
| `CC-N03-D02` | `CC-N03` | `plugins sync-home` → `plugins_sync_home_plan_v1`（与 export/ecc 同源） | pytest `test_plugin_compat_matrix` + smoke | 2026-04-26 批次 |
| `CC-N03-D03` | `CC-N03` | `plugins_home_sync_drift_v1`（doctor/repair/API，与 ecc drift 同源） | pytest 多套件 + smoke | 2026-04-26 批次 |
| `CC-N02-D04` | `CC-N02` | feedback bundle/export 脱敏强化、`dest_placement`、工作区外 dest 警告、runbook `feedback bundle` 步骤 | pytest `test_feedback_*` + `test_doctor_cli` + smoke | 2026-04-26 批次 |

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
| `HM-N11-D01` | `HM-N11` | 云后端条件立项门槛文档（`CLOUD_RUNTIME_OOS` 中英同步） | 文档一致性校对 + smoke | 2026-04-25 批次 |
| `HM-N11-D02` | `HM-N11` | `runtime_backend_interface_v1` 接入 `runtime_registry_v1.interface`，对齐 `local/docker/ssh` 接口与配置键 | pytest + smoke | 2026-04-25 批次 |
| `HM-N01-D03` | `HM-N01` | `load_agent_settings_for_workspace`；gateway **discord/slack** **`--config`** 与执行链路同源加载 | pytest 全量 + smoke | 2026-04-26 批次 |
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
| `ECC-N04-D01` | `ECC-N04` | `ecc_asset_registry_v1` 草案快照（source/license/signature/version/trust） | schema snapshot 校对 + smoke | 2026-04-25 批次 |
| `ECC-N04-D02` | `ECC-N04` | ingest sanitizer 策略草案与 `ecc_ingest_sanitizer_policy_v1` 快照（危险 hook 隔离） | 文档审查 + schema snapshot + smoke | 2026-04-25 批次 |
| `ECC-N04-D03` | `ECC-N04` | provenance/signature/trust 中英策略 + `ecc_ingest_provenance_trust_v1` 快照；registry `boundaries` 标注 provenance 已覆盖 | pytest `test_ecc_ingest_schema_snapshots` + smoke | 2026-04-26 批次 |
| `ECC-N01-D02` | `ECC-N01` | `ecc sync-home`、`export --dry-run`（home sync 计划/结果契约） | pytest `test_ecc_layout_cli` + smoke | 2026-04-26 批次 |
| `ECC-N01-D03` | `ECC-N01` | `ecc_home_sync_drift_v1`；`export_ecc_dir_diff_v1` 扩展 codex/opencode | pytest `test_ecc_layout_cli` + `test_doctor_cli` | 2026-04-26 批次 |
| `ECC-N01-D04` | `ECC-N01` | `repair_plan_v1.ecc_sync_commands` | pytest `test_repair_cli` | 2026-04-26 批次 |
| `ECC-N02-D01` | `ECC-N02` | `ecc pack-manifest` → `ecc_asset_pack_manifest_v1` | pytest `test_ecc_layout_cli` + smoke | 2026-04-26 批次 |
| `ECC-N02-D02` | `ECC-N02` | export/ecc dry-run 与 D01 同源 checksum 出口 | pytest + smoke | 2026-04-26 批次 |
| `ECC-N03-D03` | `ECC-N03` | **`ecc_harness_target_inventory_v1`**、`cai-agent ecc inventory --json`、**`doctor_v1.ecc_harness_target_inventory`**（各 harness 导出根 + workspace 源 assets 摘要） | pytest `test_ecc_layout_cli` + `test_doctor_cli` + smoke | 2026-04-28 |
| `ECC-N03-D04` | `ECC-N03` | **`ecc_structured_home_diff_v1`** / **`ecc_structured_home_diff_bundle_v1`**、**`cai-agent ecc home-diff`**、**`doctor_v1.ecc_structured_home_diff`**、**`repair_plan_v1`** 增补 home-diff 预览与 pending targets | pytest `test_export_sync_diff` + `test_doctor_cli` + `test_repair_cli` + smoke | 2026-04-28 |

## 最新验证基线

2026-04-26 本地验证：

| 检查项 | 命令 | 结果 |
|---|---|---|
| 全量单测 | `python -m pytest -q cai-agent/tests` | **830 passed**, **3 subtests passed** |
| 冒烟 | `python scripts/smoke_new_features.py` | **PASS**，输出 `NEW_FEATURE_CHECKS_OK` |
| 回归 | `QA_SKIP_LOG=1 python scripts/run_regression.py` | **PASS** |

## 自动完成归档

| Issue ID | 完成日期 | 交付摘要 | 验证 | 来源 / 备注 |
|---|---|---|---|---|
| `DOC-AUTO-FINALIZE` | 2026-04-26 | 建立任务完成后的自动文档同步脚本和低 token 完成协议 | pytest -q -p no:cacheprovider cai-agent/tests/test_finalize_task_script.py: 1 passed | finalize_task |
| `ECC-N04-D03` | 2026-04-26 | Deliver ECC-N04-D03 provenance/trust bilingual policy, ecc_ingest_provenance_trust_v1 snapshot, schema README and roadmap; add regression test for ingest draft JSON. | python -m pytest -q cai-agent/tests: 817 passed, 3 subtests passed<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | finalize_task |
| `CC-N02-D04` | 2026-04-26 | Harden feedback bundle and JSONL export redaction: sanitize_feedback_text workspace/home paths and Slack tokens, sanitize append_feedback, redact export rows, feedback_bundle_export_v1 dest_placement and warnings for external --dest, release runbook bundle step. | python -m pytest -q cai-agent/tests/test_feedback_cli.py cai-agent/tests/test_feedback_export.py cai-agent/tests/test_feedback_bundle_cli.py cai-agent/tests/test_doctor_cli.py: PASS<br>python -m pytest -q cai-agent/tests: 820 passed, 3 subtests passed<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | finalize_task |
| `HM-N01-D02`/`D04`/`D05` | 2026-04-26 | 交付 `models clone` / `clone-all` / `alias` 与 doctor **`profile_home_migration`**。 | python -m pytest -q cai-agent/tests: PASS (825 passed, 3 subtests)<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | finalize_task |
| `ECC-N01`/`ECC-N02`/`CC-N01-D04`/`HM-N01-D03` | 2026-04-26 | 交付 `ecc sync-home`/`pack-manifest`、`export --dry-run`、doctor drift+repair ecc 提示、`doctor_upgrade_hints_v1`、`load_agent_settings_for_workspace` 与 gateway discord/slack `--config`。 | python -m pytest -q cai-agent/tests: PASS (830 passed, 3 subtests)<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | 本轮合入 |
| `CC-N03-D04` | 2026-04-27 | Harden plugins sync-home apply flow with strict force/no-backup gating and conflict hint parity for text output; add regression tests for CLI flag contracts and conflict hint rendering. | python -m pytest -q cai-agent/tests: PASS (841 passed, 3 subtests passed); python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | finalize_task |
| `HM-N01-D01` | 2026-04-27 | Deepen profile home schema with config_dir, enforce legal profile IDs for home layout/clone to prevent path traversal, and add isolation regression tests. | python -m pytest -q cai-agent/tests: PASS (841 passed, 3 subtests passed); python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | finalize_task |
| `ECC-N03-D03` | 2026-04-28 | Add `ecc_harness_target_inventory_v1`, `cai-agent ecc inventory --json`, and `doctor --json.ecc_harness_target_inventory` for cross-harness export roots and workspace source asset counts. | python -m pytest -q cai-agent/tests/test_ecc_layout_cli.py cai-agent/tests/test_doctor_cli.py: PASS (20 passed)<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | 会话合入 |
| `ECC-N03-D04` | 2026-04-28 | Add structured home diff schemas (`ecc_structured_home_diff_v1` / bundle / multi), `ecc home-diff` CLI, doctor and repair_plan preview fields, SHA256-based add/update/skip/conflict per file. | python -m pytest -q cai-agent/tests/test_export_sync_diff.py cai-agent/tests/test_doctor_cli.py cai-agent/tests/test_repair_cli.py: PASS<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | 会话合入 |
