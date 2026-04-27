# TODOS 已完成项归档

> 本页承接已从 [`DEVELOPER_TODOS.zh-CN.md`](DEVELOPER_TODOS.zh-CN.md) 与 [`TEST_TODOS.zh-CN.md`](TEST_TODOS.zh-CN.md) 移除的 **Done** 表格行与批次留档。  
> **交付与里程碑真源**仍以 [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md) §10、[`COMPLETED_TASKS_ARCHIVE.zh-CN.md`](COMPLETED_TASKS_ARCHIVE.zh-CN.md)、`CHANGELOG.zh-CN.md` 为准；本页为拆页后的**可追溯快照**。

迁移日期：**2026-04-26**。

---

## 1. 开发：批次留档（原 `DEVELOPER_TODOS` §1.2）

| ID | 状态 | 任务 | 验收 |
|---|---|---|---|
| `CC-N01-D05a` | `Done（2026-04-26）` | 建立 `command_discovery_v1`，统一 CLI/TUI/doctor 的命令模板发现视图 | 已覆盖搜索路径、命令列表、数量和 repair hint |
| `CC-N01-D05b` | `Done（2026-04-26）` | TUI `/` 下拉菜单显示所有原生命令与 `commands/*.md` 模板命令，并带说明 | `/code-review` 等模板命令已进入聊天框 `/` 菜单 |
| `CC-N01-D05c` | `Done（2026-04-26）` | `doctor --json` / API summary 暴露 `command_center`，`doctor.sync` 覆盖 commands/skills/rules/hooks 缺失诊断 | JSON 字段稳定，能给出 actionable repair |
| `CC-N01-D05d` | `Done（2026-04-26）` | `repair --apply` 创建最小命令中心资产面：`commands/`、`skills/`、`rules/*`、`hooks/hooks.json` | 新 workspace 能恢复到可发现、可诊断、可补全的最小结构 |
| `CC-N01-D05e` | `Done（2026-04-26）` | 补自动化/烟测验证并记录 Windows sandbox 临时目录限制 | `test_command_registry.py` + `test_tui_slash_suggester.py` 通过；repair/doctor CLI smoke 通过 |
| `CC-N02-D02a` | `Done（2026-04-26）` | `feedback bug` 新增结构化复现步骤字段 | CLI 支持 `--step` 多次传入，JSON 输出 `repro_steps` |
| `CC-N02-D02b` | `Done（2026-04-26）` | `feedback bug` 新增期望/实际行为字段 | CLI 支持 `--expected` / `--actual`，JSON 输出同名结构字段 |
| `CC-N02-D02c` | `Done（2026-04-26）` | `feedback bug` 新增附件列表字段 | CLI 支持 `--attachment` 多次传入，落盘前脱敏 |
| `CC-N02-D02d` | `Done（2026-04-26）` | 补测试与文档验收回写 | `test_feedback_cli.py` 补 human/json 同结构断言；CLI smoke 通过 |

---

## 2. 开发：能力级 Done（原 `DEVELOPER_TODOS` §4～§6）

### 2.1 Claude Code 线（原 §4）

| ID | 状态 | 优先级 | 功能 | 备注 |
|---|---|---|---|---|
| `CC-N01` | `Done` | `P0` | 安装 / 升级 / 修复一体化入口 | `CC-N01-D01`～`D05` 已交付 |
| `CC-N02` | `Done` | `P0` | `/bug` 等价反馈与自助诊断链路 | `CC-N02-D01`～`D04` 已交付 |

### 2.2 Hermes 线（原 §5）

| ID | 状态 | 优先级 | 功能 | 备注 |
|---|---|---|---|---|
| `HM-N05` | `Done` | `P1` | Gateway 第一批平台扩展 | ROADMAP `HM-N05-D01`～`D05` |
| `HM-N07` | `Done` | `P1` | Gateway 联邦 / 频道监控 / proxy | ROADMAP `HM-N07-D01`～`D04` |
| `HM-N08` | `Done` | `P2` | Voice mode | ROADMAP `HM-N08-D01`～`D04` |
| `HM-N09` | `Done` | `P2` | External memory providers | ROADMAP `HM-N09-D01`～`D04` |
| `HM-N10` | `Done` | `P2` | Tool Gateway 等价能力 | ROADMAP `HM-N10-D01`～`D05` |

### 2.3 ECC 线（原 §6）

| ID | 状态 | 优先级 | 功能 | 备注 |
|---|---|---|---|---|
| `ECC-N01` | `Done` | `P1` | home sync / local catalog / install-repair 收口 | `ECC-N01-D02`～`D04`；catalog 基线见 `ECC-N03-D01` |

---

## 3. 开发：原子级 Done（原 `DEVELOPER_TODOS` §7）

### 3.1 Claude Code 线（原 §7.2 中 Done 行）

| 子任务 ID | 对应能力 | 交付物 | 主要入口 | 验收点 |
|---|---|---|---|---|
| `CC-N01-D01` | 安装 / 升级 / 修复 | **`Done（2026-04-26）`**：`repair --dry-run|--apply --json`（`repair_plan_v1` / `repair_result_v1`） | `__main__.py`、`doctor.py` | pytest `test_repair_cli.py` |
| `CC-N01-D02` | 安装 / 升级 / 修复 | **`Done（2026-04-26）`**：`doctor_install_v1` | `doctor.py`、`templates/` | pytest `test_doctor_cli.py` |
| `CC-N01-D03` | 安装 / 升级 / 修复 | **`Done（2026-04-26）`**：`doctor_sync_v1` | `doctor.py`、`plugin_registry.py` | pytest `test_doctor_cli.py` |
| `CC-N01-D04` | 安装 / 升级 / 修复 | **`Done（2026-04-26）`**：`doctor_upgrade_hints_v1`（统一 repair/ecc/export 与文档指针） | `doctor.py` | pytest `test_doctor_cli.py` |
| `CC-N01-D05` | 安装 / 升级 / 修复 | 命令中心发现链路：TUI slash 菜单、`commands/*.md`、doctor/repair 诊断同源 | `command_registry.py`、`tui.py`、`doctor.py`、`tests/` | **Done（2026-04-26）**：`/code-review` 等模板命令可补全；doctor/repair 能发现并修复命令资产面 |
| `CC-N02-D01` | 反馈与诊断 | feedback bundle schema，自动附带 doctor 摘要、版本、平台、配置摘要 | `feedback.py`、`doctor.py` | **Done（2026-04-26）**：`feedback bundle --dest ... --json` 输出 `feedback_bundle_v1` / `feedback_bundle_export_v1` |
| `CC-N02-D02` | 反馈与诊断 | `feedback bug` 模板补齐复现步骤、期望行为、实际行为、附件列表 | `feedback.py`、`__main__.py` | **Done（2026-04-26）**：CLI 交互和 JSON 输出都能表达同一结构 |
| `CC-N02-D03` | 反馈与诊断 | 反馈前 triage 提示，串起 `doctor -> repair -> feedback bug` | `doctor.py`、`feedback.py` | **Done（2026-04-26）**：`doctor_feedback_triage_v1` 指向 doctor / repair / feedback bug / feedback bundle 流程 |
| `CC-N02-D04` | 反馈与诊断 | 脱敏策略和导出目录策略收口 | `feedback.py`、`release_runbook.py` | **Done（2026-04-26）**：`sanitize_feedback_text` 扩展；`append_feedback`/JSONL export/bundle 递归脱敏；`feedback_bundle_export_v1` 不泄露绝对 workspace；`dest_placement` + `redaction.warnings`；见 ROADMAP `CC-N02-D04` |
| `CC-N03-D02` | Plugin / marketplace / home sync | **`Done（2026-04-26）`**：`cai-agent plugins sync-home` → **`plugins_sync_home_plan_v1`**（与 export/ecc 同源；codex 为 manifest_only） | `__main__.py`、`plugin_registry.py` | pytest `test_plugin_compat_matrix` + smoke |
| `CC-N03-D03` | Plugin / marketplace / home sync | **`Done（2026-04-26）`**：**`plugins_home_sync_drift_v1`**（与 **`ecc_home_sync_drift_v1`** 同源）；**`doctor --json` → `plugins.home_sync_drift`**；**`repair_plan_v1.plugins_sync_home_preview_commands`**；**`api_doctor_summary_v1.plugins_home_sync_drift_targets`**；文本 doctor 摘要 | `plugin_registry.py`、`doctor.py` | pytest `test_plugin_compat_matrix` + `test_doctor_cli` + `test_repair_cli` + `test_api_http_server` + smoke |

### 3.2 Hermes 线（原 §7.3 中 Done 行）

| 子任务 ID | 对应能力 | 交付物 | 主要入口 | 验收点 |
|---|---|---|---|---|
| `HM-N01-D02` | Profiles | **`Done（2026-04-26）`**：`models clone` / `clone-all`（dry-run、家目录复制、`--force-home`） | `__main__.py`、`profiles.py` | pytest `test_profile_clone_alias_cli.py` + smoke |
| `HM-N01-D03` | Profiles | **`Done（2026-04-26）`**：`load_agent_settings_for_workspace`；**`gateway discord`/`slack`** 增加 **`--config`** 并在执行链路使用与 **`api serve --config`** 一致的加载语义 | `config.py`、`api_http_server.py`、`gateway_discord.py`、`gateway_slack.py`、`__main__.py` | pytest 全量 + smoke |
| `HM-N01-D04` | Profiles | **`Done（2026-04-26）`**：`models alias`（`models_alias_v1`） | `__main__.py`、`profiles.py` | pytest `test_profile_clone_alias_cli.py` + smoke |
| `HM-N01-D05` | Profiles | **`Done（2026-04-26）`**：`profile_home_migration` 诊断（doctor JSON + 文本摘要） | `doctor.py`、`profiles.py` | pytest `test_profile_clone_alias_cli.py` |
| `HM-N05-D01` | Gateway 平台扩展 | 抽出平台 adapter contract，统一 send/receive/health/map | `gateway_platforms.py`、`gateway_production.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N05-D01` |
| `HM-N05-D02` | Gateway 平台扩展 | Signal adapter skeleton 与 CLI 配置 | `gateway_signal.py`、`__main__.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N05-D02` |
| `HM-N05-D03` | Gateway 平台扩展 | Email adapter，覆盖 SMTP/IMAP 或等价最小方案 | `gateway_email.py`、`gateway_platforms.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N05-D03` |
| `HM-N05-D04` | Gateway 平台扩展 | Matrix adapter，覆盖 room map、send、health | `gateway_matrix.py`、`gateway_maps.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N05-D04` |
| `HM-N05-D05` | Gateway 平台扩展 | 新平台纳入 lifecycle、prod-status、docs | `gateway_lifecycle.py`、`gateway_production.py`、`docs/` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N05-D05` |
| `HM-N07-D01` | Gateway 联邦 | workspace federation schema，描述多个 workspace/platform/channel 状态 | `gateway_maps.py`、`gateway_production.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N07-D01` |
| `HM-N07-D02` | Gateway 联邦 | channel monitoring 字段：last_seen、latency、error_count、owner | `gateway_production.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N07-D02` |
| `HM-N07-D03` | Gateway 联邦 | gateway proxy / routing 最小方案 | `api_http_server.py`、`gateway_lifecycle.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N07-D03` |
| `HM-N07-D04` | Gateway 联邦 | CLI/API 汇总命令和 JSON 输出 | `__main__.py`、`api_http_server.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N07-D04` |
| `HM-N08-D01` | Voice mode | voice provider contract，定义 STT/TTS/provider health | `voice.py`、`doctor.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N08-D01` |
| `HM-N08-D02` | Voice mode | CLI voice config/check 命令 | `__main__.py`、`voice.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N08-D02` |
| `HM-N08-D03` | Voice mode | 一个 gateway voice reply 最小闭环，优先 Telegram 或 Discord | `gateway_telegram.py`、`gateway_discord.py`、`voice.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N08-D03` |
| `HM-N08-D04` | Voice mode | voice OOS/可用边界文档和成本提示 | `docs/` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N08-D04` |
| `HM-N09-D01` | Memory providers | provider registry，支持 list/use/test | `memory.py`、`user_model_store.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N09-D01` |
| `HM-N09-D02` | Memory providers | builtin local provider 显式注册 | `memory.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N09-D02` |
| `HM-N09-D03` | Memory providers | mock HTTP external provider，用于 contract 验证 | `memory.py`、`doctor.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N09-D03` |
| `HM-N09-D04` | Memory providers | doctor/export/profile 感知 active provider | `doctor.py`、`profiles.py`、`user_model_store.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N09-D04` |
| `HM-N10-D01` | Tool Gateway | tool provider contract，统一 web/image/browser/tts 的配置和权限 | `tool_provider.py`、`plugin_registry.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N10-D01` |
| `HM-N10-D02` | Tool Gateway | 四类工具 registry：web、image、browser、tts | `tool_provider.py`、`mcp_presets.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N10-D02` |
| `HM-N10-D03` | Tool Gateway | MCP bridge，优先复用现有 MCP preset | `mcp_presets.py`、`mcp_serve.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N10-D03` |
| `HM-N10-D04` | Tool Gateway | 至少一类真实 provider 接入 | `tool_provider.py` 等 | **Done（2026-04-25～26）**：见 ROADMAP `HM-N10-D04` |
| `HM-N10-D05` | Tool Gateway | approval / policy / cost guard | `doctor.py`、`plugin_registry.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N10-D05` |
| `HM-N11-D01` | Cloud runtime 条件项 | 云后端需求门槛文档 | `docs/` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N11-D01` |
| `HM-N11-D02` | Cloud runtime 条件项 | runtime backend interface 与现有 docker/ssh 对齐 | `runtime/registry.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N11-D02` |

### 3.3 Everything Claude Code 线（原 §7.4 中 Done 行）

| 子任务 ID | 对应能力 | 交付物 | 主要入口 | 验收点 |
|---|---|---|---|---|
| `ECC-N01-D02` | home sync / catalog | **`Done（2026-04-26）`**：`ecc sync-home`（`ecc_home_sync_result_v1`）、`export --dry-run`（`ecc_home_sync_plan_v1`） | `exporter.py`、`__main__.py` | pytest `test_ecc_layout_cli.py` + smoke |
| `ECC-N01-D03` | home sync / catalog | **`Done（2026-04-26）`**：`ecc_home_sync_drift_v1`；`export_ecc_dir_diff_v1` 支持 codex/opencode | `exporter.py`、`doctor.py` | pytest `test_ecc_layout_cli.py` + `test_doctor_cli.py` |
| `ECC-N01-D04` | home sync / catalog | **`Done（2026-04-26）`**：`repair_plan_v1.ecc_sync_commands` | `doctor.py` | pytest `test_repair_cli.py` |
| `ECC-N02-D01` | Asset pack | **`Done（2026-04-26）`**：`ecc pack-manifest` → `ecc_asset_pack_manifest_v1` | `exporter.py`、`__main__.py` | pytest `test_ecc_layout_cli.py` + smoke |
| `ECC-N02-D02` | Asset pack | **`Done（2026-04-26）`**：与 D01 同源 checksum；`export --dry-run` / `ecc sync-home --dry-run` | `exporter.py` | pytest + smoke |
| `ECC-N04-D01` | 资产生态 ingest | registry schema 草案，包含来源、license、签名、版本 | `docs/schema/` | **Done（2026-04-25～26）**：`ecc_asset_registry_v1` snapshot，见 ROADMAP `ECC-N04-D01` |
| `ECC-N04-D02` | 资产生态 ingest | ingest sanitizer 方案，隔离不可信脚本和危险 hook | `plugin_registry.py`、`docs/` | **Done（2026-04-25～26）**：政策文档 + `ecc_ingest_sanitizer_policy_v1`，见 ROADMAP `ECC-N04-D02` |
| `ECC-N04-D03` | 资产生态 ingest | provenance / signature / trust level 设计与 sanitizer 合流门禁 | `docs/`、`docs/schema/` | **Done（2026-04-26）**：`ECC_04C_*` 中英文档 + `ecc_ingest_provenance_trust_v1.snapshot.json`；见 ROADMAP `ECC-N04-D03` |

---

## 4. 测试：`MODEL-P0`（原 `TEST_TODOS` §3）

| ID | 状态 | 测试重点 | 现有测试入口 | 需新增自动化 | 手工 / 真机 | 通过标准 |
|---|---|---|---|---|---|---|
| `MODEL-P0-01` | `Done` | Model Gateway contract 不破坏旧 adapter | `test_llm_factory_dispatch.py`、`test_model_gateway.py` | 已覆盖 gateway response / adapter contract 与 `model_response_v1` schema 文件 | 无 | 旧 `chat_completion` 行为不变，新 response envelope 稳定 |
| `MODEL-P0-02` | `Done` | capabilities 元数据与脱敏 | `test_model_gateway.py`、`test_model_profiles_cli.py` | 已覆盖 provider/model 能力推断 | 手工检查真实配置输出 | 不暴露 `api_key` / `base_url` |
| `MODEL-P0-03` | `Done` | `/models` ping + chat smoke + doctor 建议 | `test_model_profiles_cli.py`、`test_doctor_cli.py` | 已覆盖 chat smoke 与 doctor model gateway 摘要 | 至少 OpenAI-compatible 和 Anthropic 真 key 各跑一次 | 常见失败有稳定 status |
| `MODEL-P0-04` | `Done` | `model_response_v1` 统一响应 | `test_model_gateway.py`、`test_api_http_server.py` | 已覆盖 direct/API response 与 SSE wrapper | 无 | content/usage/latency/provider/model/profile 字段稳定 |
| `MODEL-P0-05` | `Done` | routing explain + capabilities + fallback candidates | `test_model_routing.py` | 已覆盖 fallback candidate / capability constraint 测试 | 手工跑复杂 routing 规则 | 用户能看懂选型原因 |
| `MODEL-P0-06` | `Done` | 模型接入 UX 闭环 | `test_model_profiles_cli.py`、smoke | 已补 add -> capabilities -> ping -> chat-smoke -> use -> routing-test onboarding flow | 手工接一个本地模型和一个远端模型 | 新模型接入流程可复现 |
| `MODEL-P0-07` | `Done` | API Server 复用 Model Gateway | `test_api_http_server.py` | 已补 `/v1/models`、非流式 `/v1/chat/completions`、`stream=true` SSE 与 profile-aware 请求 | OpenAI-compatible client 接入 | API server 不重复 provider 分支 |

### 4.1 模型接入原子测试（原 `TEST_TODOS` §7.1 全表）

| 开发子任务 | 自动化覆盖 | 手工 / 真机覆盖 | 通过标准 |
|---|---|---|---|
| `MODEL-P0-D01` | `test_model_gateway.py` 覆盖 contract 和 capabilities | 无 | 新模块不影响旧 adapter |
| `MODEL-P0-D02` | `test_llm_factory_dispatch.py` 补 response wrapper | 无 | role-aware response 字段稳定 |
| `MODEL-P0-D03` | `test_model_profiles_cli.py` 覆盖 `models capabilities --json`；`test_model_gateway.py` 覆盖 `model_capabilities_v1` / `model_capabilities_list_v1` schema | 真实配置手工检查 | 不泄漏密钥或 base_url |
| `MODEL-P0-D04` | `test_api_http_server.py` 覆盖 `/v1/models/capabilities` 和 bearer | 浏览器/curl 走查 | API 只读且鉴权一致 |
| `MODEL-P0-D05` | `test_model_profiles_cli.py` 覆盖 `ping --chat-smoke` | 真 key 显式 smoke | 默认不消耗 token，显式 smoke 可诊断 |
| `MODEL-P0-D06` | `test_model_profiles_cli.py` 补 429/404 status 映射 | 无 | 常见 HTTP 失败不全是 `NET_FAIL` |
| `MODEL-P0-D07` | `test_model_routing.py` 覆盖 capabilities 出现在 routing-test JSON | 手工读 explain | 选型解释包含能力信息 |
| `MODEL-P0-D08` | `test_provider_registry.py` 覆盖 `provider_registry_v1` / readiness 的 `capabilities_hint` 与 schema 文件；onboarding flow 测试 | 新 provider 文档评审 | preset 更新不破坏旧配置 |
| `MODEL-P0-D09` | `test_doctor_cli.py` 覆盖 `doctor_model_gateway_v1` | 坏 key / 缺 env 手工走查 | doctor 建议可执行 |
| `MODEL-P0-D10` | `test_tui_model_panel.py` 覆盖模型面板行内 capabilities / health / cost / local 提示 | TUI 手工查看 | CLI/TUI 状态一致 |
| `MODEL-P0-D11` | `test_model_routing.py` 覆盖 `model_fallback_candidates_v1` | 手工模拟失败模型 | 默认 explain，不静默切换 |
| `MODEL-P0-D12` | API server OpenAI-compatible contract 测试（已覆盖 `/v1/models`、非流式与 SSE `/v1/chat/completions`） | OpenAI-compatible client 实测 | API 复用 gateway |
| `MODEL-P0-D13` | metrics snapshot 测试（已覆盖 `api.chat_completions`） | 跑一次真实调用检查指标 | provider/model/profile/latency/usage 可追踪 |
| `MODEL-P0-D14` | `scripts/smoke_new_features.py` 覆盖 onboarding flow；`test_model_profiles_cli.py` 覆盖 `model_onboarding_flow_v1` schema；`test_model_onboarding_docs.py` 覆盖 runbook 可发现性与命令链；文档见 `MODEL_ONBOARDING_RUNBOOK.zh-CN.md` | 按 runbook 接 OpenAI/Anthropic/本地模型 | 新用户能复现 |

---

## 5. 测试：能力级 Done（原 `TEST_TODOS` §4～§6）

| ID | 状态 | 测试重点 |
|---|---|---|
| `CC-N01` | `Done` | init / doctor / repair / upgrade 路径 |
| `CC-N02` | `Done` | 反馈与自助 triage / bundle / 导出脱敏 |
| `HM-N02` | `Done` | OpenAI-compatible API、streaming、profile-aware request |
| `HM-N05` | `Done` | Signal / Email / Matrix 等平台适配 |
| `HM-N07` | `Done` | federation / monitoring / proxy 等 |
| `HM-N08` | `Done` | voice contract、CLI、`gateway voice reply` |
| `HM-N09` | `Done` | memory provider registry / mock / doctor 暴露 |
| `HM-N10` | `Done` | tool provider / registry / MCP bridge / guard |
| `ECC-N01` | `Done` | local catalog、sync-home、doctor drift、repair 建议 |

---

## 6. 测试：原子级含 Done 标记行（原 `TEST_TODOS` §7.2～§7.4）

### 6.1 Claude Code 线

| 开发子任务 | 自动化覆盖 | 手工 / 真机覆盖 | 通过标准 |
|---|---|---|---|
| `CC-N01-D01` | `test_repair_cli.py` 覆盖 `--dry-run`、`--apply`、`--json`、退出码 | 构造坏 home 后执行 repair | dry-run 不写文件，apply 后配置恢复 |
| `CC-N01-D02` | `test_doctor_cli.py` 增加 `doctor.install` JSON snapshot | 新机器或干净 venv 走查 | install 诊断字段稳定、建议可执行 |
| `CC-N01-D03` | `test_install_surface_cli.py` 覆盖 `doctor.sync` drift 场景 | 手工制造模板缺失/旧 schema | 能区分 error/warning/action |
| `CC-N01-D04` | docs link check 或 smoke 中校验 onboarding 命令存在 | 按 README 从零跑一遍 | 新旧用户路径没有冲突文案 |
| `CC-N01-D05` | **Done（2026-04-26）**：`test_command_registry.py` 覆盖 `command_discovery_v1`；`test_tui_slash_suggester.py` 覆盖模板命令菜单说明；`test_doctor_cli.py` / `test_repair_cli.py` 覆盖 command_center 与最小资产面 | 已执行：`test_command_registry.py` + `test_tui_slash_suggester.py` = 29 passed；`repair --apply --json` 与 `doctor --json` CLI smoke 通过。Windows sandbox 下 pytest `tmp_path` / `TemporaryDirectory` 会被临时目录权限拦截，repair/doctor 用等价 CLI smoke 验证 | 命令发现、补全、诊断、修复四处同源 |
| `CC-N02-D01` | `test_feedback_bundle_cli.py` 已覆盖 bundle schema、脱敏字段、doctor 摘要、repair plan | 打开导出的 bundle 检查内容 | bundle 可复现问题且不泄漏敏感字段 |
| `CC-N02-D02` | **Done（2026-04-26）**：`test_feedback_cli.py` 已补 bug 模板字段和 JSON 输出断言（`repro_steps` / `expected` / `actual` / `attachments`） | 已执行 JSON 与文本模式 CLI smoke；当前 Windows sandbox 下 pytest `tmp_path` 仍会被系统临时目录权限拦截，保留测试文件用于正常环境回归 | human/json 两种输出结构一致 |
| `CC-N02-D03` | `test_feedback_bundle_cli.py` 已覆盖 `doctor_feedback_triage_v1` | 手工走 `doctor -> repair -> feedback bug -> feedback bundle` | 常见错误先给修复建议再导出反馈 |
| `CC-N02-D04` | `test_feedback_export.py` 补 path/token/email 脱敏断言 | 检查真实导出目录 | 敏感信息不会出现在明文 bundle |
| `HM-N01-D02` | **`Done（2026-04-26）`**：`test_profile_clone_alias_cli.py` 覆盖 clone dry-run / 冲突 / 家目录复制 | clone 一个真实 profile | clone 后可启动 |
| `HM-N01-D03` | **`test_api_http_server`** 已覆盖 **`api serve` 等价 `--config` + workspace**；smoke 补 TUI/gateway 与 API 同配置对照 | 手工切 profile 后跑 TUI/API/gateway | 所有入口读同一 active profile |
| `HM-N01-D04` | **`Done（2026-04-26）`**：`test_profile_clone_alias_cli.py` 覆盖 `models alias --json` | 复制 alias 命令执行 | alias 可直接进入 profile |
| `HM-N01-D05` | **`Done（2026-04-26）`**：`test_profile_clone_alias_cli.py` + `doctor --json` 的 `profile_home_migration` | 用旧配置跑 doctor | 老配置有安全迁移路径 |
| `ECC-N01-D02` | **`test_ecc_layout_cli.py`** 覆盖 **`ecc sync-home --dry-run`** / **`export --dry-run`** | 对至少两个 harness 执行 dry-run | `ecc_home_sync_plan_v1` / `ecc_home_sync_result_v1` 稳定 |
| `ECC-N01-D03` | **`test_ecc_layout_cli.py`** + **`test_doctor_cli.py`** 覆盖 **`ecc_home_sync_drift_v1`** 与 **`export_ecc_dir_diff_v1`**（含 opencode） | 手工制造缺失/冲突资产 | doctor 能指出问题 |
| `ECC-N01-D04` | **`test_repair_cli.py`** 覆盖 **`repair_plan_v1.ecc_sync_commands`** | 按建议命令手工执行 | 诊断能转成行动 |
| `ECC-N02-D01` | **`test_ecc_layout_cli.py`** 覆盖 **`ecc pack-manifest`**（`ecc_asset_pack_manifest_v1`） | 检查 pack metadata | manifest 可校验 |
| `ECC-N02-D02` | 与 D01 同源：`test_ecc_layout_cli.py` + smoke | 打包后解压检查 | 打包可复现 |
| `ECC-N04-D01` | registry schema snapshot | 方案评审 | registry 能作为后续入口 |
| `ECC-N04-D02` | sanitizer policy 单测或文档审查 | 审查危险 hook 场景 | 不可信资产不直接执行 |
| `ECC-N04-D03` | provenance 字段校验 | 评审 trust level | 来源可信度可表达 |

### 6.2 Hermes：`HM-N02`～`HM-N11` 已交付原子测试映射（原 `TEST_TODOS` §7.3 迁出）

| 开发子任务 | 自动化覆盖 | 手工 / 真机覆盖 | 通过标准 |
|---|---|---|---|
| `HM-N02-D01` | `test_api_openai_chat_completions.py` 覆盖 `/v1/models` | `curl /v1/models` | 返回 OpenAI 风格模型列表 |
| `HM-N02-D02` | `test_api_openai_chat_completions.py` 覆盖非流式 chat | OpenAI-compatible client 发请求 | 响应字段兼容 |
| `HM-N02-D03` | `test_api_http_server.py` 覆盖 SSE chunk / done | 客户端读取 streaming | 流式能结束且不丢 chunk |
| `HM-N02-D04` | `test_api_auth_config.py` 覆盖 token、无 token、错误码 | 手工验证 localhost 默认安全策略 | 未授权请求被拒绝 |
| `HM-N02-D05` | `test_api_openai_chat_completions.py` 补 profile-aware 参数 | 两个 profile 分别请求 | profile 上下文不串 |
| `HM-N05-D01` | gateway adapter contract 单测 | 新平台配置走查 | adapter 复用有效 |
| `HM-N05-D02` | `test_gateway_signal_cli.py` 覆盖 config/health/map | Signal 真机链路可选 | skeleton 可诊断 |
| `HM-N05-D03` | `test_gateway_email_cli.py` 覆盖 SMTP/IMAP 或 mock | 邮箱沙箱收发 | Email 最小链路可用 |
| `HM-N05-D04` | `test_gateway_matrix_cli.py` 覆盖 room map/send/health | Matrix room 真机验证 | 进入 prod-status |
| `HM-N05-D05` | `test_gateway_maps_summarize.py` 补新平台 prod-status | 至少一个新平台真机消息 | 至少 2 个新平台 CLI + map + health 可用 |
| `HM-N07-D01` | `test_gateway_federation_summary.py` 覆盖 federation schema | 多 workspace fixture 走查 | 聚合输出稳定 |
| `HM-N07-D02` | `test_gateway_federation_summary.py` 覆盖 channel health 字段 | 手工制造错误/延迟 | 频道级健康可见 |
| `HM-N07-D03` | `test_gateway_proxy_routes.py` 覆盖 routing 决策 | 本地多 workspace 路由 | 消息能到目标 workspace/profile |
| `HM-N07-D04` | CLI/API JSON snapshot | 运营脚本读取 JSON | 输出可被脚本消费 |
| `HM-N08-D01` | `test_voice_provider_contract.py` 覆盖 STT/TTS/health | 无 provider/错 provider 手工检查 | 错误语义清楚 |
| `HM-N08-D02` | `test_voice_cli.py` 覆盖 voice config/check | 本地音频配置检查 | 无 provider 时不崩 |
| `HM-N08-D03` | `test_gateway_voice_settings.py` 覆盖 gateway voice 开关 | Telegram 或 Discord 真机 voice reply | 至少一个语音闭环可用 |
| `HM-N08-D04` | 文档检查 | 评审成本、OOS、可用能力说明 | 用户不误解能力范围 |
| `HM-N09-D01` | `test_memory_provider_registry.py` 覆盖 list/use/test | CLI 切 provider | provider 体系可操作 |
| `HM-N09-D02` | `test_memory_provider_registry.py` 覆盖 builtin local provider | 现有 memory 流程不回退 | 旧行为保持 |
| `HM-N09-D03` | `test_memory_provider_http_mock.py` 覆盖 mock HTTP provider | 本地 mock 服务 | 外部 provider contract 可验证 |
| `HM-N09-D04` | `test_doctor_cli.py` / export 测试覆盖 active provider | 切 provider 后导出 | doctor/export 能识别 provider |
| `HM-N10-D01` | `test_tool_gateway_contract.py` 覆盖 provider contract | 配置高风险工具 | 权限字段稳定 |
| `HM-N10-D02` | `test_tool_provider_registry.py` 覆盖四类 registry | CLI list/enable/disable | web/image/browser/tts 可列出 |
| `HM-N10-D03` | MCP bridge 测试复用 existing preset tests | 手工跑 MCP 工具 | 不重复实现已有 MCP |
| `HM-N10-D04` | 至少一个真实 provider 的端到端测试 | 实机调用一个 provider | 端到端可用 |
| `HM-N10-D05` | approval/policy/cost guard 单测 | 手工触发高风险工具 | 高风险动作需显式允许 |
| `HM-N11-D01` | 文档检查 | 授权/成本/部署评审 | 未授权不写云后端 |
| `HM-N11-D02` | `test_runtime_docker_mock.py` / `test_runtime_ssh_mock.py` 保持接口兼容 | 本地 runtime smoke | 本地路径不被云接口破坏 |
