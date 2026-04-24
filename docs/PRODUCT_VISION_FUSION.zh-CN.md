# 产品愿景：集成 Claude Code / Hermes Agent / Everything Claude Code

## 一句话

`cai-agent` 的产品目标是：以 **Python + LangGraph + OpenAI 兼容 API** 为统一运行时，把以下三个上游仓库的优势整合成 **一个** 可交付的 Agent 产品：

- [`anthropics/claude-code`](https://github.com/anthropics/claude-code)
- [`NousResearch/hermes-agent`](https://github.com/NousResearch/hermes-agent)
- [`affaan-m/everything-claude-code`](https://github.com/affaan-m/everything-claude-code)

目标是“**整合**”，不是复制某个上游的技术栈，也不是把多个 CLI 拼成套件。

## 三个上游分别提供什么

| 上游 | 在本产品中的定位 |
|---|---|
| `anthropics/claude-code` | **体验基线**：终端交互、计划→执行→继续、MCP、权限、slash 命令习惯、安装体验 |
| `NousResearch/hermes-agent` | **产品化能力**：profiles、API/server、dashboard、gateway、voice、runtime backends、memory providers |
| `affaan-m/everything-claude-code` | **治理与生态**：rules、skills、hooks、model-route、跨 harness 导出、资产打包与安装叙事 |

补充说明：`claude-code-analysis` 仍可作为架构分析参考，但**不再是顶层产品定位的一部分**。

## 三层集成目标

### L1：Claude Code 体验层

目标：用户在终端内获得接近官方 coding agent 的主观体验。

- 计划 → 执行 → 会话延续
- 文件 / 搜索 / Shell / Git / MCP
- 清晰的权限与审批体验
- TUI / slash 命令 / 使用习惯统一

### L2：Hermes 产品化层

目标：产品不只“能跑”，还具备多入口、多通道、多后端和可运营能力。

- 多 profile / 多实例配置
- API / server 对外接口
- 本地或 Web dashboard
- 多平台 gateway 与 voice
- runtime backends 与 memory providers

### L3：ECC 治理生态层

目标：团队和生态可以复用、扩展、迁移和治理这套 Agent。

- rules / skills / hooks
- model-route 与成本策略
- cross-harness export / compatibility
- 插件与资产打包、安装、状态管理

## 非目标

以下能力默认不作为“必须跟齐”的目标，除非单独立项：

- 复制官方 TS / Bun / Ink 技术栈
- 把多个上游 CLI 原样封装成一套 launcher
- 依赖封闭企业能力的官方专属功能

## 对当前仓库的直接要求

这一定义意味着：

1. 所有产品文档都应围绕这三个上游重写，而不是只围绕 Hermes 或只围绕 Claude Code。
2. `PRODUCT_PLAN` 维护“当前已集成到什么程度”。
3. `ROADMAP_EXECUTION` 维护“下一批按哪个上游能力桶推进”。
4. `PRODUCT_GAP_ANALYSIS` 维护“还差什么、哪些 OOS、哪些用 MCP 替代”。

## 相关文档

- 缺口与发版门禁：[PRODUCT_GAP_ANALYSIS.zh-CN.md](PRODUCT_GAP_ANALYSIS.zh-CN.md)
- 当前执行清单：[PRODUCT_PLAN.zh-CN.md](PRODUCT_PLAN.zh-CN.md)
- 当前阶段路线图：[ROADMAP_EXECUTION.zh-CN.md](ROADMAP_EXECUTION.zh-CN.md)
- 发版勾选矩阵：[PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md)
- 文档总入口：[README.zh-CN.md](README.zh-CN.md) / [README.md](../README.md)
