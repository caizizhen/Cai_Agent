# 开发 TODO（只保留未完成与未来方向）

> English companion: [`DEVELOPER_TODOS.md`](DEVELOPER_TODOS.md). Completed-task archive: [`COMPLETED_TASKS_ARCHIVE.zh-CN.md`](COMPLETED_TASKS_ARCHIVE.zh-CN.md).

这份文档只回答一个问题：**接下来还能做什么？**

已完成的开发 / 设计 / 文档任务不再留在本页，统一归档到 [`COMPLETED_TASKS_ARCHIVE.zh-CN.md`](COMPLETED_TASKS_ARCHIVE.zh-CN.md)。产品边界与状态源仍以 [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md)、[`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md)、[`ISSUE_BACKLOG.zh-CN.md`](ISSUE_BACKLOG.zh-CN.md) 为准；本页只做开发执行翻译。测试配套清单见 [`TEST_TODOS.zh-CN.md`](TEST_TODOS.zh-CN.md)。

---

## 1. 当前结论

截至 2026-04-25，上一轮已创建的开发 TODO 已全部完成并推送到 `main`。当前默认开发面没有 `Ready` / `Design` 实现项。

后续只从下面两类中继续：

1. **未来方向**：需要先重新开 issue 或补充契约。
2. **OOS / 条件立项**：默认不开发，除非产品边界变化或用户明确授权。

---

## 2. 未来方向候选

这些不是当前待办，只有在明确立项后才进入开发。

| 方向 | 状态 | 下一步 | 主要参考 |
|---|---|---|---|
| Dashboard 真实写操作 | Future | 在 `ops_dashboard_interactions_v1` 基础上补 `apply` 契约、鉴权、审计和回滚边界 | `ops_dashboard.py`、`ops_http_server.py`、[`OPS_DYNAMIC_WEB_API.zh-CN.md`](OPS_DYNAMIC_WEB_API.zh-CN.md) |
| Gateway 多工作区联邦 / 频道监控 | Future | 先定义生产监控字段、采样策略和跨 workspace 聚合规则 | `gateway_production.py`、`gateway_maps.py`、[`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md) |
| Memory 外部 provider adapter | Future | 先定义 provider adapter 接口、凭据边界、离线测试夹具 | `memory.py`、`user_model_store.py`、[`docs/rfc/HONCHO_USER_MODEL_EPIC.zh-CN.md`](rfc/HONCHO_USER_MODEL_EPIC.zh-CN.md) |
| Runtime 真实 CI 镜像矩阵 | Future | 在 docker/ssh 已产品化基础上补真实环境矩阵与非本机 smoke | [`RUNTIME_BACKENDS.md`](RUNTIME_BACKENDS.md)、`runtime/docker.py`、`runtime/ssh.py` |
| TUI 进一步模型/状态体验 | Future | 以用户反馈重新开小 issue，不从旧完成项继续堆叠 | `tui.py`、`tui_model_panel.py`、`tui_session_strip.py` |

---

## 3. OOS / 条件立项

默认不进入开发队列，只保留替代方案。

| 主题 | 边界 | 替代方案 / 条件 |
|---|---|---|
| Voice（`HM-07`） | 默认 OOS | [`docs/rfc/HM_07A_VOICE_BOUNDARY.zh-CN.md`](rfc/HM_07A_VOICE_BOUNDARY.zh-CN.md)：优先 MCP 接入 STT/TTS |
| 默认云运行后端（Modal / Daytona 等） | 默认 OOS，条件立项 | [`CLOUD_RUNTIME_OOS.zh-CN.md`](CLOUD_RUNTIME_OOS.zh-CN.md)；当前默认 local / docker / ssh |
| 内置 WebSearch / Notebook 重实现 | OOS | [`WEBSEARCH_NOTEBOOK_MCP.zh-CN.md`](WEBSEARCH_NOTEBOOK_MCP.zh-CN.md)；默认 MCP 优先 |
| 第三方插件市场 / 签名公证 / 付费分成 | 默认 OOS | [`docs/rfc/ECC_03A_PLUGIN_VERSION_GOVERNANCE.zh-CN.md`](rfc/ECC_03A_PLUGIN_VERSION_GOVERNANCE.zh-CN.md) §4 |
| IRC / 自建 XMPP | OOS | 见 [`docs/rfc/HM_03C_NEXT_GATEWAY_PLATFORMS.zh-CN.md`](rfc/HM_03C_NEXT_GATEWAY_PLATFORMS.zh-CN.md)，优先 MCP / 外部桥 |
| LINE / 企业微信 | Explore / 区域驱动 | 有明确商业/区域需求后再开评估 issue |
| 多 CLI 套娃 / 封闭企业专属 | 不做 | 统一运行时优先，不包装多个独立 agent |

---

## 4. 开发统一约定

开始新开发前：

1. 先在 [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md) §10 新增或更新 issue 状态。
2. 再把本页新增为“未来方向”或明确的待办。
3. 不把 `Done` 行继续留在本页；完成后移入 [`COMPLETED_TASKS_ARCHIVE.zh-CN.md`](COMPLETED_TASKS_ARCHIVE.zh-CN.md)。

每个新 issue 至少包含：

| 字段 | 要求 |
|---|---|
| 目标 | 补哪条能力线，收口什么体验 |
| 边界 | 本次不做什么，哪些能力走 MCP / OOS |
| 输出 | 代码、文档、schema、命令、runbook |
| 验证 | pytest、smoke、regression、手工 testplan 或 JSON snapshot |
| 回写 | ROADMAP、TODO、CHANGELOG、schema README、相关专题文档 |

---

## 5. 当前 QA 基线

2026-04-25 在仓库根 `D:\gitrepo\Cai_Agent` 实测结果：

| 检查项 | 命令 | 结果 |
|---|---|---|
| 全量单测 | `python -m pytest -q cai-agent/tests` | **714 passed**, **3 subtests passed** |
| 冒烟 | `python scripts/smoke_new_features.py` | **PASS**，输出 `NEW_FEATURE_CHECKS_OK` |
| 回归 | `QA_SKIP_LOG=1 python scripts/run_regression.py` | **PASS**，compileall / unittest / smoke / CLI 子集全绿 |

后续若只改局部模块，允许先跑子集；合入前建议至少补一遍 smoke。涉及共享 CLI / API / runtime 的变更，继续跑 `QA_SKIP_LOG=1 python scripts/run_regression.py`。
