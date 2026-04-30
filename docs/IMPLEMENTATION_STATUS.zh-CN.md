# 实现状态（滚动摘要）

> **中文**说明；英文对照见 [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md)。  
> **唯一执行清单**仍以 [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md) 为准；逐条变更以根目录 **`CHANGELOG.md`** / **`CHANGELOG.zh-CN.md`** 为准。

当前产品目标：在一个统一运行时里集成 **Claude Code + Hermes Agent + Everything Claude Code**。规划细节见 [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md) 与 [`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md)。

## 近期已交付（面向开发/集成）

以下能力已在 **`main`** 落地（**0.7.0** 窗口及紧随补丁；完整列表见 **CHANGELOG §0.7.0**；**Unreleased** 见 CHANGELOG 顶部）：

| 领域 | 交付内容 | 代码/文档入口 |
|------|-----------|---------------|
| **Design backlog 契约（HM-04c / HM-03e / HM-05d）** | 新增 **`ops_dashboard_interactions_v1`**（Dashboard dry-run 预览）、**`gateway prod-status --json`** 输出 **`gateway_production_summary_v1`**、**`memory provider --json`** 输出 **`memory_provider_contract_v1`**；均为本地只读/预览契约，不依赖外部服务 | **`ops_dashboard.py`**、**`ops_http_server.py`**、**`gateway_production.py`**、**`memory.py`**、**`test_ops_http_server.py`**、**`test_gateway_lifecycle_cli.py`**、**`test_memory_provider_contract_cli.py`** |
| **Cloud runtime 条件项（HM-N11-D01 / D02）** | 新增云后端条件立项门槛文档（`CLOUD_RUNTIME_OOS` 中英同步），并在 `runtime_registry_v1.interface` 暴露 **`runtime_backend_interface_v1`**，统一 `local/docker/ssh` 的接口与配置键口径，为后续条件立项保留稳定接入面 | **`docs/CLOUD_RUNTIME_OOS.zh-CN.md`**、**`docs/CLOUD_RUNTIME_OOS.md`**、**`runtime/registry.py`**、**`test_runtime_local.py`** |
| **CC-N02-D04 feedback 导出脱敏** | **`sanitize_feedback_text`** 扩展；**`feedback bundle`** / **`feedback export`** / **`feedback_stats`** 统一不泄露绝对 workspace；**`feedback_bundle_export_v1.dest_placement`** 与 **`redaction.warnings`**；**`release_runbook`** 增补 bundle 步骤 | **`feedback.py`**、**`release_runbook.py`**、**`test_feedback_*`** |
| **ECC ingest 草案（ECC-N04-D01～D03）** | 新增/扩展资产生态 ingest 草案：**`ecc_asset_registry_v1`**、**`ecc_ingest_sanitizer_policy_v1`**、**`ecc_ingest_provenance_trust_v1`** 三份机读快照；补齐 **`ECC_04B`**（sanitizer）与 **`ECC_04C`**（provenance/signature/trust 与 sanitizer 合流门禁）中英文策略文档；registry 快照 `boundaries` 标注 provenance 策略已覆盖 | **`docs/schema/ecc_*`**、**`docs/ECC_04B_*`**、**`docs/ECC_04C_*`**、**`cai-agent/tests/test_ecc_ingest_schema_snapshots.py`** |
| **插件兼容矩阵 CI snapshot（ECC-03c）** | 新增 **`scripts/gen_plugin_compat_snapshot.py`**，可生成/校验 **`docs/schema/plugin_compat_matrix_v1.snapshot.json`**；snapshot 内嵌 **`plugin_compat_matrix_v1`** 与 **`plugin_compat_matrix_check_v1`**，smoke 执行 `--check` | **`scripts/gen_plugin_compat_snapshot.py`**、**`plugin_compat_matrix_v1.snapshot.json`**、**`test_plugin_compat_matrix.py`** |
| **SSH Runtime（HM-06c）** | **`runtime.ssh`** 诊断补齐 `ssh_binary_present`、key/known_hosts 存在性、严格 host key 与连接超时；新增可选 **`runtime_ssh_audit_v1`** JSONL 审计（默认不记录命令明文，可用 `audit_include_command=true` 显式打开） | **`runtime/ssh.py`**、**`runtime/registry.py`**、**`config.py`**、**`test_runtime_ssh_mock.py`** |
| **Docker Runtime（HM-06b）** | **`runtime.docker`** 支持既有 `container` / `docker exec` 模式与新增 `image` / `docker run --rm` 模式；新增 **`workdir`**、**`volume_mounts`**、**`cpus`**、**`memory`** 配置，**`doctor_runtime_v1.describe`** 暴露 mode/image/workdir/volumes/limits | **`runtime/docker.py`**、**`runtime/registry.py`**、**`config.py`**、**`test_runtime_docker_mock.py`** |
| **Teams Gateway（HM-03d）** | **`gateway teams`** 新增会话映射（`bind/get/list/unbind`）、allowlist、`health`、Teams app `manifest` 模板与 Bot Framework Activity **`serve-webhook`**；`gateway platforms` / `gateway maps` 已纳入 Teams；机读载荷含 **`gateway_teams_map_v1`**、**`gateway_teams_health_v1`**、**`gateway_teams_manifest_v1`** | **`gateway_teams.py`**、**`gateway_platforms.py`**、**`gateway_maps.py`**、**`test_gateway_discord_slack_cli.py`** |
| **解限关键写 noop（SAFETY-N07-D01 / D02）** | **`[safety].dangerous_critical_write_skip_if_unchanged`**：`write_file` 命中关键 basename 时，磁盘已有 UTF-8（≤512KiB）且 **规范化正文一致** 或 **`.toml`/`.json` 解析后结构化等价** 则跳过 basename 级危险二次确认；仍受 `dangerous_confirmation_required` 总控；清单见 **`docs/SAFETY_UNRESTRICTED_BACKLOG.zh-CN.md`** | **`tools.py`**、**`config.py`**、**`test_unrestricted_danger_dispatch_extended.py`** |
| **未开发功能批次（HM-02c / CC-03c / ECC-03b）** | API 只读扩展（**`/v1/models/summary`**、**`/v1/plugins/surface`**、**`/v1/release/runbook`**）；TUI **`#context-label`** 路由/迁移提示 + **`profile_switched: <id>`** 单源；**`plugins --compat-check`**（**`plugin_compat_matrix_check_v1`**）与矩阵 **`maintenance_checklist`** | **`api_http_server.py`**、**`tui_session_strip.py`**、**`plugin_registry.py`**、**`COMPLETED_TASKS_ARCHIVE.zh-CN.md`** |
| **Explore 评估四连（HM-03c / ECC-03a / HM-06a / HM-07a）** | 下一批 gateway、插件版本治理、runtime 后端、Voice 边界等 **RFC 结论文档**（**`docs/rfc/HM_03C_*`**、**`ECC_03A_*`**、**`HM_06A_*`**、**`HM_07A_*`**）；路线图 issue 标 **Done**（文档交付），完成历史归档到 **`COMPLETED_TASKS_ARCHIVE.zh-CN.md`** | **`COMPLETED_TASKS_ARCHIVE.zh-CN.md`** |
| **最小 HTTP API（HM-02b）** | **`cai-agent api serve`**（默认 **`CAI_API_PORT`**=**8788**；**`CAI_API_TOKEN`** 可选 Bearer）；**`GET /healthz`**、**`/v1/status`**（**`api_status_v1`**）、**`/v1/doctor/summary`**（**`api_doctor_summary_v1`**）、**`POST /v1/tasks/run-due`**（仅 **dry_run**） | **`api_http_server.py`**、**`doctor.build_api_doctor_summary_v1`**、**`test_api_http_server.py`** |
| **Recall / 记忆策略** | **`recall --evaluate`** 无需 **`--query`**；**`recall_evaluation_v1`**；**`doctor`** 文本 **`[memory.policy]`**；**`release-ga --with-memory-policy`** | **`recall_audit.py`**、**`doctor.py`**、**`__main__.py`**、**`smoke_new_features`** |
| **成本 / compact** | **`cost report --json`** 嵌 **`compact_policy_explain_v1`**；**`cost report`** 文本摘要 | **`cost_aggregate.py`** |
| **路线图设计** | **HM-02a** / **CC-03b** RFC | **`docs/rfc/HM_02_MINIMAL_SERVER_CONTRACT.zh-CN.md`**、**`docs/rfc/CC_03B_MODEL_STATUS_UX.zh-CN.md`** |
| **ECC 流转文档** | 安装 → **`ecc layout`** → **`export`** → 共享 | **`CROSS_HARNESS_COMPATIBILITY*.md`** |
| **运营 / 可观测** | **`cai-agent ops dashboard`**（json/text/html）；**`--html-refresh-seconds`**（HTML **`meta refresh`**）；**`cai-agent ops serve`** 只读 HTTP（**`/v1/ops/dashboard`**、**`/v1/ops/dashboard.html`**）；可选 **`CAI_OPS_API_TOKEN`** | [`OPS_DYNAMIC_WEB_API.zh-CN.md`](OPS_DYNAMIC_WEB_API.zh-CN.md)、**`cai_agent/ops_dashboard.py`**、**`cai_agent/ops_http_server.py`** |
| **记忆 / 用户模型** | **`memory user-model export`**（可选 **`--with-store`**）；**`store init`/`list`**、**`learn`**、**`query`** 与 SQLite **`.cai/user_model_store.sqlite3`** 最小闭环（**HM-05a**） | **`user_model.py`**、**`user_model_store.py`**、RFC [`docs/rfc/HONCHO_USER_MODEL_EPIC.zh-CN.md`](rfc/HONCHO_USER_MODEL_EPIC.zh-CN.md) |
| **ECC / 路由与预算** | **`models routing-test`** 文本/JSON 双语 **`explain`**；**`cost budget`** 嵌 **`cost_budget_explain_v1`**（**ECC-02a**） | **`model_routing.py`**、**`cost_aggregate.py`**、[`MODEL_ROUTING_RULES.zh-CN.md`](MODEL_ROUTING_RULES.zh-CN.md) |
| **测试 / 冒烟** | **`test_ops_http_server.py`**、**`test_ops_dashboard_html.py`**（含刷新）、**`test_memory_user_model_export.py`**；**`scripts/smoke_new_features.py`** 已扩 **`memory user-model export`** | **`cai-agent/tests/`**、**`scripts/smoke_new_features.py`** |

## 仍未完成（产品文档口径）

以下为 **PRODUCT_PLAN / PRODUCT_GAP / RFC** 中仍标为后续或 OOS 的项（非本页详尽清单）：

| 主题 | 说明 |
|------|------|
| **Claude Code 体验线** | 安装/更新/反馈流程、MCP 优先的 WebSearch/Notebook 入口、任务与状态交互还在收口 |
| **Hermes 产品化线** | profiles、API/server、多平台 gateway、动态 dashboard、memory providers、runtime backends 仍待补齐 |
| **ECC 治理线** | rules / skills / hooks 资产化、模型路由与成本治理、插件/分发叙事仍待产品化 |
| **共享发布闭环** | feedback、语义 changelog、Parity 回写、发版门禁已进入显式 roadmap，不再依赖手工补洞 |
| **OOS / 条件立项** | 内置重实现 WebSearch/Notebook、默认云后端、封闭企业专属特性继续保持 OOS 或条件立项 |

## 最近回归执行记录（QA）

- **日期**：2026-04-25（仓库根 `D:\gitrepo\Cai_Agent`，本地时区）。  
- **`pytest cai-agent/tests`**（仓库根执行 **`python -m pytest -q cai-agent/tests`**）：**826 passed**，**3 subtests passed**；**`PYTHONPATH=cai-agent\src`**。
- **`python scripts/smoke_new_features.py`**：**NEW_FEATURE_CHECKS_OK**。  
- **`QA_SKIP_LOG=1 python scripts/run_regression.py`**：退出码 **0**（HM-04c / HM-03e / HM-05d 后）。最近一次落盘机器记录仍为 **[`docs/qa/runs/regression-20260424-191511.md`](qa/runs/regression-20260424-191511.md)**；需要新日志时勿设 **`QA_SKIP_LOG=1`** 后重跑（见 **QA_REGRESSION_LOGGING**）。

## QA 提示

- 自动化：**`pytest cai-agent/tests`**（用例数以 **PRODUCT_PLAN** §三 T1 为准）。  
- 冒烟：**仓库根**执行 **`python scripts/smoke_new_features.py`**。  
- 发版：**[`docs/qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md`](qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md)**。
