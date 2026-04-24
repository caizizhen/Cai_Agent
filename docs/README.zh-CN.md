# 文档总览（精简版）

这份索引用来回答两个问题：

1. **现在应该看哪几份文档？**
2. **哪些文档只是历史背景或兼容旧链接？**

## 1. 先看这些

| 目的 | 文档 |
|---|---|
| 新用户上手 | [`ONBOARDING.zh-CN.md`](ONBOARDING.zh-CN.md) |
| 当前能力、测试、执行顺序 | [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md) |
| 下一阶段开发计划 | [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md) |
| 可直接开单的 issue 草案 | [`ISSUE_BACKLOG.zh-CN.md`](ISSUE_BACKLOG.zh-CN.md) / [`ISSUE_BACKLOG.md`](ISSUE_BACKLOG.md) |
| 开发起步清单 | [`DEVELOPER_TODOS.zh-CN.md`](DEVELOPER_TODOS.zh-CN.md) |
| 测试起步清单 | [`TEST_TODOS.zh-CN.md`](TEST_TODOS.zh-CN.md) / [`TEST_TODOS.md`](TEST_TODOS.md) |
| 缺口、边界、发版门禁 | [`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md) |
| 发版评审勾选 | [`PARITY_MATRIX.zh-CN.md`](PARITY_MATRIX.zh-CN.md) |
| 版本变更 | 根目录 `CHANGELOG.md` / `CHANGELOG.zh-CN.md` |

当前产品目标：在一个统一运行时里集成 `Claude Code + Hermes Agent + Everything Claude Code`。详见 [`PRODUCT_VISION_FUSION.zh-CN.md`](PRODUCT_VISION_FUSION.zh-CN.md)。

## 2. 常用专题

| 主题 | 文档 |
|---|---|
| 架构概览 | [`ARCHITECTURE.zh-CN.md`](ARCHITECTURE.zh-CN.md) |
| JSON 契约 / exit 码 | [`schema/README.zh-CN.md`](schema/README.zh-CN.md) |
| Memory TTL / 置信度 | [`MEMORY_TTL_CONFIDENCE_POLICY.zh-CN.md`](MEMORY_TTL_CONFIDENCE_POLICY.zh-CN.md) |
| 动态运营 Web / HTTP 契约 | [`OPS_DYNAMIC_WEB_API.zh-CN.md`](OPS_DYNAMIC_WEB_API.zh-CN.md) |
| 模型路由 | [`MODEL_ROUTING_RULES.zh-CN.md`](MODEL_ROUTING_RULES.zh-CN.md) |
| MCP Web 配方 | [`MCP_WEB_RECIPE.zh-CN.md`](MCP_WEB_RECIPE.zh-CN.md) |
| Runtime 后端 | [`RUNTIME_BACKENDS.zh-CN.md`](RUNTIME_BACKENDS.zh-CN.md) |
| 跨 harness 导出 | [`CROSS_HARNESS_COMPATIBILITY.zh-CN.md`](CROSS_HARNESS_COMPATIBILITY.zh-CN.md) |
| 插件兼容矩阵 | [`PLUGIN_COMPAT_MATRIX.zh-CN.md`](PLUGIN_COMPAT_MATRIX.zh-CN.md) |

## 3. 一页摘要

如果只想快速了解“现在做到哪了”，看：

- [`IMPLEMENTATION_STATUS.zh-CN.md`](IMPLEMENTATION_STATUS.zh-CN.md)：一页滚动摘要

## 4. 历史 / 兼容入口

以下文档保留路径，主要用于历史背景、旧链接兼容或追溯，不再作为当前执行基线：

- [`DEVELOPMENT_PROGRESS_TRACKER.zh-CN.md`](DEVELOPMENT_PROGRESS_TRACKER.zh-CN.md)
- [`HERMES_PARITY_PROGRESS.zh-CN.md`](HERMES_PARITY_PROGRESS.zh-CN.md)
- [`HERMES_PARITY_SPRINT_PLAN.zh-CN.md`](HERMES_PARITY_SPRINT_PLAN.zh-CN.md)

## 5. 维护规则

- **执行、排期、测试进度**：只在 [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md) 维护。
- **下一阶段计划**：只在 [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md) 维护。
- **缺口与 OOS**：只在 [`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md) 维护。
- **版本变更**：只在 `CHANGELOG` 维护。
- 其他文档尽量只保留专题说明，不再重复维护状态表。
