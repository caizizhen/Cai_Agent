# 实现状态（滚动摘要）

> **中文**说明；英文对照见 [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md)。  
> **唯一执行清单**仍以 [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md) 为准；逐条变更以根目录 **`CHANGELOG.md`** / **`CHANGELOG.zh-CN.md`** 为准。

当前产品目标：在一个统一运行时里集成 **Claude Code + Hermes Agent + Everything Claude Code**。规划细节见 [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md) 与 [`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md)。

## 近期已交付（面向开发/集成）

以下能力已在 **`main`** 落地（**0.7.0** 窗口及紧随补丁；完整列表见 **CHANGELOG §0.7.0**；**Unreleased** 见 CHANGELOG 顶部）：

| 领域 | 交付内容 | 代码/文档入口 |
|------|-----------|---------------|
| **未开发功能批次（HM-02c / CC-03c / ECC-03b）** | API 只读扩展（**`/v1/models/summary`**、**`/v1/plugins/surface`**、**`/v1/release/runbook`**）；TUI **`#context-label`** 路由/迁移提示 + **`profile_switched: <id>`** 单源；**`plugins --compat-check`**（**`plugin_compat_matrix_check_v1`**）与矩阵 **`maintenance_checklist`** | **`api_http_server.py`**、**`tui_session_strip.py`**、**`plugin_registry.py`**、**`DEVELOPER_TODOS`** §0.4 |
| **Explore 评估四连（HM-03c / ECC-03a / HM-06a / HM-07a）** | 下一批 gateway、插件版本治理、runtime 后端、Voice 边界等 **RFC 结论文档**（**`docs/rfc/HM_03C_*`**、**`ECC_03A_*`**、**`HM_06A_*`**、**`HM_07A_*`**）；路线图 issue 标 **Done**（文档交付） | **`DEVELOPER_TODOS`** §0.3.1 |
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
- **`pytest cai-agent/tests`**（自 **`cai-agent`** 目录 **`python -m pytest -q tests`**）：**688 passed**，**3 subtests passed**；**`PYTHONPATH=cai-agent\src`**。  
- **`python scripts/smoke_new_features.py`**：**NEW_FEATURE_CHECKS_OK**。  
- **`python scripts/run_regression.py`**：退出码 **0**（`HM-02c` / `CC-03c` / `ECC-03b` 批次后，**Git HEAD** 见当次提交）。最近一次落盘机器记录仍为 **[`docs/qa/runs/regression-20260424-191511.md`](qa/runs/regression-20260424-191511.md)**；需要新日志时勿设 **`QA_SKIP_LOG=1`** 后重跑（见 **QA_REGRESSION_LOGGING**）。

## QA 提示

- 自动化：**`pytest cai-agent/tests`**（用例数以 **PRODUCT_PLAN** §三 T1 为准）。  
- 冒烟：**仓库根**执行 **`python scripts/smoke_new_features.py`**。  
- 发版：**[`docs/qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md`](qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md)**。
