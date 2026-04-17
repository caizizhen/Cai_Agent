# 上下文压缩与成本治理（设计说明）

本文档描述 **对话轮次增长时的压缩提示策略** 及其与 **token 统计 / 预算检查** 的关系，对标 Claude Code 分析文档中的 QueryEngine「自动压缩」思路；实现为轻量、可配置、可关闭。

## 目标

- 在长工具循环中提醒模型做 **摘要与收尾**，减少无效往返与 token 浪费。
- 与 `cai-agent cost budget --check` 及会话级 `observe` 聚合配合，便于团队制定「轮次 + 成本」门槛。

## 配置（`cai-agent.toml`）

在 `[context]` 中配置（均为可选，默认关闭）：

| 键 | 含义 |
|----|------|
| `compact_after_iterations` | 从第几轮 **LLM 调用** 起注入一次压缩提示；`0` 表示关闭 |
| `compact_min_messages` | 仅当非 system 消息数 ≥ 该值时才注入，避免极短对话误触发 |

注入内容为一条 **user** 角色提示，要求模型在适当时机用 `finish` 给出阶段性摘要或结论；仅注入 **一次**（每轮会话）。

## 与 observe / cost 的联动建议

1. **会话侧**：`observe --json` 汇总 `.cai-session*.json` 的 token 与失败率；`schema_version` 见实现。
2. **预算侧**：`cost budget --check` 使用 `[cost] budget_max_tokens` 与历史会话 token 总和对比。
3. **运营侧**：当 `failure_rate` 或单会话 `total_tokens` 持续偏高时，下调 `max_iterations` 或调低 `compact_after_iterations`，使模型更早收束。

## 后续可增强（未承诺路线图）

- 基于真实 prompt token 阈值触发（需与 LLM 客户端暴露的 usage 对齐到图状态）。
- 自动截断或外部摘要服务（复杂度与合规成本较高，建议优先用 MCP）。
