# 产品愿景：三源融合的「完全体」（统一栈）

## 一句话

在 **单一运行时** 内融合三类参考面：以 **Python + LangGraph + OpenAI 兼容 API** 为唯一编排内核，向 **官方 Claude Code 的能力与体验**、**claude-code-analysis 所归纳的架构完备度**、**Everything Claude Code 的治理与跨 harness 资产** 收敛；**不**以复制官方 TS/Bun/Ink 技术栈为目标，**不**采用「官方 CLI + ECC + Cai_Agent」多产品套件编排作为默认交付形态。

## 三类参考面分别解决什么问题

| 参考 | 用途 |
|------|------|
| [anthropics/claude-code](https://github.com/anthropics/claude-code) | **用户可感知的「能干活」**：工具类别与深度、计划/执行、子 Agent、MCP、权限与交互习惯。 |
| [ComeOnOliver/claude-code-analysis](https://github.com/ComeOnOliver/claude-code-analysis/blob/main/DOCUMENTATION.zh-CN.md) | **工程验收骨架**：Query 循环、工具表、状态、任务、服务（compact/cost/MCP）、钩子与扩展边界——用于模块是否齐全，而非栈名一致。 |
| [affaan-m/everything-claude-code](https://github.com/affaan-m/everything-claude-code) | **治理与资产**：记忆/本能、安全与验证闭环、跨工具导出与安装叙事；海量技能库以 **兼容导出 + 生态包** 渐进吸收，避免拖死核心版本。 |

## 三层验收（L1 / L2 / L3）

### L1 — 官方能力环（体验基线）

目标：用户主观感受接近「官方终端 Agent 能覆盖的日常开发闭环」。

- 工具：文件、搜索、Shell（受限）、Git、MCP；对 Web/Notebook 等 **要么内置补齐，要么提供经文档认证的 MCP 等价路径**（见 [PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md)）。
- 编排：计划 → 执行 → 会话延续；多步 `workflow` 与子 Agent 能力持续加强。
- 缺口从「文档里接受没有」升级为 **版本里程碑上必须关闭或等价替代**（见 [PRODUCT_GAP_ANALYSIS.zh-CN.md](PRODUCT_GAP_ANALYSIS.zh-CN.md) 发布门禁）。

### L2 — 架构完备度（可演进）

目标：主循环与周边子系统可对照 analysis 文档做 **结构化复盘**，便于加工具、加策略、加观测而不推翻重写。

- 主循环：`cai_agent.graph` 与工具分发、权限、重试与上限。
- 状态与会话：统一任务 ID、状态流、结构化事件（与 `observe` / CI 消费对齐）。
- 上下文与成本：压缩提示、token 统计、预算策略（见 [CONTEXT_AND_COMPACT.zh-CN.md](CONTEXT_AND_COMPACT.zh-CN.md)、[MEMORY_AND_COST_GOVERNANCE.zh-CN.md](MEMORY_AND_COST_GOVERNANCE.zh-CN.md)）。

### L3 — ECC 式治理与运营（可审计、可迁移）

目标：团队与流水线能 **依赖同一套命令与 schema** 做质量、安全、成本与导出。

- 已有入口：`quality-gate`、`security-scan`、`cost`、`export`、`memory`、`observe` 等——向 **策略与 schema 完整** 演进（记忆 TTL/置信度、报告目录、跨 harness manifest 版本等）。
- 可视化运营面板（类 ECC Dashboard）列为 **P2+ 可选**，不阻塞 L1。

## 明确不在默认「完全体」内或需单独立项的能力

以下多依赖 **商业授权、封闭服务或独立产品形态**，默认不纳入「开源统一栈完全体」的必达项；若在 parity 矩阵中出现，须标注 **OutOfScope** 或 **需外部服务**。

- 官方企业特性示例：部分 Bridge / 语音 / Kairos 等门控能力（以官方仓库实际暴露为准）。
- 「捆绑多个 CLI 成一个安装包」的套件模式：非当前默认愿景（见本文首段）。

## 相关文档

- 维度级缺口与发布门禁：[PRODUCT_GAP_ANALYSIS.zh-CN.md](PRODUCT_GAP_ANALYSIS.zh-CN.md)
- 子系统级勾选矩阵（维护中）：[PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md)
- 执行阶段清单（唯一）：[PRODUCT_PLAN.zh-CN.md](PRODUCT_PLAN.zh-CN.md)
- 仓库入口说明：[README.zh-CN.md](../README.zh-CN.md)、[README.md](../README.md)
