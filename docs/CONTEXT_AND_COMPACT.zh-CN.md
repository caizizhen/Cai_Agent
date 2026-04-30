# 上下文压缩与成本治理（设计说明）

本文档描述 **对话轮次增长时的压缩提示策略** 及其与 **token 统计 / 预算检查** 的关系，对标 Claude Code 分析文档中的 QueryEngine「自动压缩」思路；实现为轻量、可配置、可关闭。

后续开发计划与 QA 矩阵见 [`CONTEXT_COMPACTION_FUTURE_PLAN.zh-CN.md`](CONTEXT_COMPACTION_FUTURE_PLAN.zh-CN.md)。

## 目标

- 在长工具循环中提醒模型做 **摘要与收尾**，减少无效往返与 token 浪费。
- 与 `cai-agent cost budget --check` 及会话级 `observe` 聚合配合，便于团队制定「轮次 + 成本」门槛。

## 配置（`cai-agent.toml`）

在 `[context]` 中配置：

| 键 | 含义 |
|----|------|
| `compact_after_iterations` | 从第几轮 **LLM 调用** 起注入一次压缩提示；`0` 表示关闭（可选，默认 `0`） |
| `compact_min_messages` | 仅当非 system 消息数 ≥ 该值时才注入，避免极短对话误触发（可选，默认 `8`） |
| `compact_on_tool_error` | 工具返回 `工具执行失败` 前缀的结果后，下一轮 LLM 前注入一条收束提示；`false` 关闭（可选，默认 `true`） |
| `compact_after_tool_calls` | 每累计 **N** 次**成功**工具执行（`dispatch` 未返回失败前缀）后，在下一轮 LLM 前注入一条里程碑提示；`0` 关闭（可选，默认 `0`） |
| `compact_mode` | 真实压缩模式：`off` 关闭、`heuristic` 本地启发式摘要、`llm` 先请求模型生成语义摘要并在失败/不变小时降级启发式（可选，默认 `heuristic`） |
| `compact_trigger_ratio` | 真实压缩触发比例：当估算 prompt tokens ≥ `context_window * compact_trigger_ratio` 时，把旧消息折叠为 `context_summary_v1`；`0` 关闭（可选，默认 `0.85`） |
| `compact_keep_tail_messages` | 真实压缩时保留最近 N 条原始消息，避免丢失当前工具/错误上下文（可选，默认 `8`） |
| `compact_summary_max_chars` | `context_summary_v1` 的最大字符预算（可选，默认 `6000`） |

环境变量覆盖（与 TOML 二选一优先级以 `Settings.from_sources` 为准）：`CAI_CONTEXT_COMPACT_ON_TOOL_ERROR`、`CAI_CONTEXT_COMPACT_AFTER_TOOL_CALLS`。

`compact_after_iterations` 类提示仍为 **每会话至多一次**（由图状态 `compact_hint_sent` 记录）。`compact_on_tool_error` 在每次工具失败后由 `tools_node` 置位、`llm_node` 消费并清除（每轮失败至多一条收束提示）。`compact_after_tool_calls` 在 `tool_call_count` 达到 `N, 2N, …` 且尚未对该里程碑注入过时各触发一次（由 `compact_milestone_last_tc` 记录）。

### 真实上下文压缩（`context_summary_v1`）

`CTX-COMPACT-N01` 起，图执行层不再只注入“请收束”提示；当估算上下文达到阈值时，`graph.llm_node` 会调用 `context_compaction.compact_messages()`，保留 system prompt、初始用户目标与最近尾部消息，并把中间历史替换成一条结构化 `context_summary_v1` user message。摘要包含消息数量、角色分布、工具调用/错误计数、工具结果预览、重要路径和压缩前的对话要点。

`CTX-COMPACT-N02` 起，`compact_mode = "llm"` 会先构造有界 summarizer prompt，让模型输出目标、决策、事实、文件、工具证据、待办、风险和最近用户意图等语义摘要；如果 LLM 摘要失败、返回非 JSON，或压缩后不比原上下文更小，会自动降级到 `heuristic`，并发出 `phase="compact_fallback"` 事件。`compact_mode = "off"` 会关闭真实压缩，但旧的收束提示配置仍按原策略工作。

`CTX-COMPACT-N04` 起，LLM 摘要还必须通过 retention gate：压缩候选上下文要保留初始用户目标、最近 tail messages、重要路径、工具名，以及调用方指定的 marker。若 LLM summary 缺失这些关键证据，graph 自动压缩和 TUI `/compress` 都会降级到 `heuristic`，并在 `compact_fallback` 的 `error` 中记录 `llm_compaction_quality_failed: ...`。这避免了“语义摘要看起来正常，但丢掉路径/工具证据”的长会话回归。

`CTX-COMPACT-N06` 起，启发式压缩会识别已有 `[context_summary_v1]` 消息并合并其结构化证据，而不是把上一代 summary 当普通文本再次摘要。新 summary 会保留旧 summary 的重要路径、工具调用、对话要点和 LLM 语义字段，并用 `merged_summary_count` / `merged_source_message_count` 记录合并情况，降低连续压缩的信息衰减。

`CTX-COMPACT-N07` 起，`tool_calls[]` 会根据工具结果类型提取结构化证据。pytest/测试输出会保留 `failure_summary`，traceback 会提取错误线索，git diff 会记录 `diff_stats`，search/read/command 输出会保留路径和关键 evidence。旧字段 `tool`、`error`、`result_preview` 保持兼容。

`CTX-COMPACT-N08` 起，TUI 会记录最近一次上下文压缩状态，并在 `/status` 中显示 `mode`、`source`、message 数变化、估算 token 压缩前后、压缩率、fallback reason 与 quality score。手动 `/compress` 成功后也会在通知里显示 `source` 和 `quality`，便于判断压缩是否可靠。

TUI `/compress` 使用同一套启发式压缩器手动压缩当前会话，并刷新上下文进度条。压缩事件会通过 progress 回调发出 `phase="compact"`，字段包括压缩前后 message 数和估算 token 数。

### 长会话质量评估

`CTX-COMPACT-N03` 起，`cai-agent sessions --compact-eval --json` 会扫描近期会话文件，对每个会话离线执行启发式压缩并输出 `context_compaction_eval_v1`。评估项包括是否真实压缩、估算 token 压缩率、初始目标保留、最近尾部消息保留、路径保留、工具名保留，以及 `--compact-required-marker` 指定的关键字符串保留。任一会话未通过时 CLI exit `2`，可作为长会话回归或 CI gate。`CTX-COMPACT-N04` 后，运行时 LLM 压缩使用同类 retention 判断作为降级门槛。

常用参数：

```powershell
cai-agent sessions --compact-eval --json --limit 20 --compact-keep-tail 8 --compact-required-marker "关键路径"
```

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
