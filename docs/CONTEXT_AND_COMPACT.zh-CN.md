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

## 上下文使用进度条（已落地）

0.5.0 起 TUI 输入框上方会显示一行进度条：

```
ctx ███░░░░░░░░░░░░░░░░░ 12,340 / 32,768 (37.6%)
```

### 数据链路

1. **LLM 客户端**：`cai_agent.llm.chat_completion`（OpenAI-compat）与 `cai_agent.llm_anthropic.chat_completion` 在每次成功响应后调用 `_record_last_usage(prompt_tokens, completion_tokens, total_tokens)`，覆盖一份 **最近一次快照**（与累计计数器分离）。
2. **图层**：`cai_agent.graph.llm_node` 调用 `chat_completion_by_role` 后通过 `get_last_usage()` 读取快照，并 `progress_cb(phase="usage", prompt_tokens=..., completion_tokens=..., total_tokens=..., context_window=...)`。
3. **TUI**：`CaiAgentApp.on_progress_update` 订阅 `phase="usage"`，更新 `_ctx_tokens` / `_ctx_is_estimate` 并调 `_refresh_context_bar()`；颜色阈值 70% 黄 / 90% 红。
4. **估算兜底**：首次响应前 / `/clear` / `/load` / `/use-model` 后、以及 **用户按 Enter 提交新消息那一瞬间**，TUI 都会用 `estimate_tokens_from_messages(messages)` 重算一次（包含 system prompt、project_context、git_context 的展开结果）；估算器 **CJK-aware**，中日韩字符按 ~1.5 chars/token 折算、ASCII/拉丁字符按 ~4 chars/token 折算（老版本的 `chars/4` 在纯中文场景会低估 2–3 倍）。估算态会显示 `~` 前缀与"估算"字样；收到服务端真实 `prompt_tokens` 后立即切回精确值。

### 配置优先级

分母 `context_window` 的解析顺序（`cai_agent.config.Settings.from_sources`）：

1. **当前激活 profile** 的 `context_window`（`[[models.profile]]` 单独配置，优先级最高）
2. `[llm].context_window`
3. 环境变量 `CAI_CONTEXT_WINDOW`
4. 默认 `8192`

解析结果会被裁剪到 `[256, 10_000_000]`。该字段 **仅用于显示**，不会以任何形式发送给服务端。

`Settings.context_window_source` 会记录命中哪一层（`profile|llm|env|default`），TUI 欢迎页与 `/status` 都会打印出来——如果你在 TOML 里设了 `32768` 但 `/status` 显示 `source=default`，说明 TUI 根本没读到你这份 TOML（最常见原因：TUI 从别的 `-w` 工作区启动，找不到 `cai-agent.toml`，用了内置默认 `8192`）。

### 对 `[context] compact_after_iterations` 的启发式补位

旧的 `compact_after_iterations` 仍然保留（按轮次触发压缩提示），进度条只是把"压力"可视化；当它进入红色区间（≥ 90%）而对话还未收束时，建议把 `max_iterations` 或 `compact_after_iterations` 往下调，让模型更早给出 `finish`。

## 后续可增强（未承诺路线图）

- 在接近红线时自动注入一次"**please finish now**"提示（已有 `compact_after_iterations` 轮次触发；缺 token 阈值触发）。
- 自动截断或外部摘要服务（复杂度与合规成本较高，建议优先用 MCP）。
