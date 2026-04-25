# 文档总览（精简版）

这份索引只回答两个问题：

1. **现在产品做到哪了？**
2. **下一轮还要开发和测试什么？**

## 1. 先看这些

| 目的 | 文档 |
|---|---|
| 新用户上手 | [`ONBOARDING.zh-CN.md`](ONBOARDING.zh-CN.md) / [`ONBOARDING.md`](ONBOARDING.md) |
| 当前能力、测试、完成面 | [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md) / [`PRODUCT_PLAN.md`](PRODUCT_PLAN.md) |
| 当前产品缺口与下一轮优先级 | [`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md) / [`PRODUCT_GAP_ANALYSIS.md`](PRODUCT_GAP_ANALYSIS.md) |
| 下一轮开发对齐 backlog | [`DEVELOPER_TODOS.zh-CN.md`](DEVELOPER_TODOS.zh-CN.md) |
| 下一轮测试对齐 backlog | [`TEST_TODOS.zh-CN.md`](TEST_TODOS.zh-CN.md) |
| 路线图 / milestone / 状态映射 | [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md) / [`ROADMAP_EXECUTION.md`](ROADMAP_EXECUTION.md) |
| 可直接开单的 issue 草案 | [`ISSUE_BACKLOG.zh-CN.md`](ISSUE_BACKLOG.zh-CN.md) / [`ISSUE_BACKLOG.md`](ISSUE_BACKLOG.md) |
| 已完成任务归档 | [`COMPLETED_TASKS_ARCHIVE.zh-CN.md`](COMPLETED_TASKS_ARCHIVE.zh-CN.md) / [`COMPLETED_TASKS_ARCHIVE.md`](COMPLETED_TASKS_ARCHIVE.md) |
| 发版评审勾选 | [`PARITY_MATRIX.zh-CN.md`](PARITY_MATRIX.zh-CN.md) / [`PARITY_MATRIX.md`](PARITY_MATRIX.md) |
| 一页实现摘要 | [`IMPLEMENTATION_STATUS.zh-CN.md`](IMPLEMENTATION_STATUS.zh-CN.md) / [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md) |
| 版本变更 | 根目录 `CHANGELOG.md` / `CHANGELOG.zh-CN.md` |

当前产品目标：在一个统一运行时里集成 `Claude Code + Hermes Agent + Everything Claude Code`。详见 [`PRODUCT_VISION_FUSION.zh-CN.md`](PRODUCT_VISION_FUSION.zh-CN.md)。

如果只看 4 份，建议按这个顺序：

1. [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md)
2. [`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md)
3. [`DEVELOPER_TODOS.zh-CN.md`](DEVELOPER_TODOS.zh-CN.md)
4. [`TEST_TODOS.zh-CN.md`](TEST_TODOS.zh-CN.md)

## 2. 常用专题

| 主题 | 文档 |
|---|---|
| 架构概览 | [`ARCHITECTURE.zh-CN.md`](ARCHITECTURE.zh-CN.md) / [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| JSON 契约 / exit 码 | [`schema/README.zh-CN.md`](schema/README.zh-CN.md) / [`schema/README.md`](schema/README.md) |
| Memory TTL / 置信度 | [`MEMORY_TTL_CONFIDENCE_POLICY.zh-CN.md`](MEMORY_TTL_CONFIDENCE_POLICY.zh-CN.md) / [`MEMORY_TTL_CONFIDENCE_POLICY.md`](MEMORY_TTL_CONFIDENCE_POLICY.md) |
| 动态运营 Web / HTTP 契约 | [`OPS_DYNAMIC_WEB_API.zh-CN.md`](OPS_DYNAMIC_WEB_API.zh-CN.md) |
| 模型接入 Runbook | [`MODEL_ONBOARDING_RUNBOOK.zh-CN.md`](MODEL_ONBOARDING_RUNBOOK.zh-CN.md) |
| 模型路由 | [`MODEL_ROUTING_RULES.zh-CN.md`](MODEL_ROUTING_RULES.zh-CN.md) |
| MCP Web 配方 | [`MCP_WEB_RECIPE.zh-CN.md`](MCP_WEB_RECIPE.zh-CN.md) / [`MCP_WEB_RECIPE.md`](MCP_WEB_RECIPE.md) |
| Runtime 后端 | [`RUNTIME_BACKENDS.zh-CN.md`](RUNTIME_BACKENDS.zh-CN.md) |
| 跨 harness 导出 | [`CROSS_HARNESS_COMPATIBILITY.zh-CN.md`](CROSS_HARNESS_COMPATIBILITY.zh-CN.md) |
| 插件兼容矩阵 | [`PLUGIN_COMPAT_MATRIX.zh-CN.md`](PLUGIN_COMPAT_MATRIX.zh-CN.md)；CI snapshot：[`schema/plugin_compat_matrix_v1.snapshot.json`](schema/plugin_compat_matrix_v1.snapshot.json) |

## 3. 一页摘要

如果只想快速了解“现在做到哪了”，看：

- [`IMPLEMENTATION_STATUS.zh-CN.md`](IMPLEMENTATION_STATUS.zh-CN.md)：一页滚动摘要

## 4. 历史 / 兼容入口

历史文档已移入 [`archive/`](archive/)，主要用于旧链接兼容或追溯，不再作为当前执行基线：

- [`DEVELOPMENT_PROGRESS_TRACKER.zh-CN.md`](archive/legacy/DEVELOPMENT_PROGRESS_TRACKER.zh-CN.md)
- [`HERMES_PARITY_PROGRESS.zh-CN.md`](archive/legacy/HERMES_PARITY_PROGRESS.zh-CN.md)
- [`HERMES_PARITY_SPRINT_PLAN.zh-CN.md`](archive/legacy/HERMES_PARITY_SPRINT_PLAN.zh-CN.md)

## 5. 维护规则

- **当前完成度与测试基线**：只在 [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md) 维护。
- **产品缺口、优先级、OOS 边界**：只在 [`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md) 维护。
- **下一轮开发 backlog**：只在 [`DEVELOPER_TODOS.zh-CN.md`](DEVELOPER_TODOS.zh-CN.md) 维护。
- **下一轮测试 backlog**：只在 [`TEST_TODOS.zh-CN.md`](TEST_TODOS.zh-CN.md) 维护。
- **路线图 / milestone 状态**：只在 [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md) 维护。
- **已完成项证据**：统一移入 [`COMPLETED_TASKS_ARCHIVE.zh-CN.md`](COMPLETED_TASKS_ARCHIVE.zh-CN.md)。
- **版本变更**：只在 `CHANGELOG` 维护。
- 当前文档需要中英文同步；大型中文主文档允许英文轻量摘要，但不要再新增另一套独立状态表。
- 归档文档冻结内容，只做链接修复。
