# 模型路由规则表（TOML + 现状）

> **状态**：**§ 1～2** 描述 **当前已实现** 行为（代码：`cai_agent.llm_factory.resolve_role_profile` / `chat_completion_by_role`）。**§ 3** 的 **`[models.routing]`** 已由 **`cai_agent.model_routing`** 解析并挂到 **`Settings.model_routing_rules`**；**`chat_completion_by_role`** 会读取 **首条 `user` 消息** 作为 goal 文本做规则命中（与 **`graph`** 主循环一致）。**`cai-agent models routing-test`** 提供干跑 JSON（**`models_routing_test_v1`**）。**`doctor --json`** 含 **`model_routing_enabled`** / **`model_routing_rules_count`**，`doctor --json` 与 `models list --json` 还会暴露共享的 **`profile_contract_v1`**，用于描述显式/隐式 profile 来源、激活优先级与迁移状态。

## 1. 当前路由（已实现）

| 逻辑入口 | 行为 |
|----------|------|
| **`chat_completion_by_role(settings, messages, role=...)`** | `role ∈ {active, subagent, planner}` → 选 profile id → **`_project_settings_for_profile`** → 调适配器。 |
| **`active`** | 使用 **`[models].active`** 对应 profile（或从 `[llm]` 合成的 `default`）。 |
| **`subagent`** | 使用 **`subagent_profile_id`**；未配置时 **回退 `active`**。 |
| **`planner`** | 使用 **`planner_profile_id`**；未配置时 **回退 `active`**。 |
| **graph / workflow** | `build_app(..., role=...)` 传入的 `role` 映射到上述；非 `default` 的 Agent 角色倾向走 **`subagent`**（见 `agents.py` 注释）。 |

配置入口见 **`cai-agent.toml`**：`[[models.profile]]`、`[models].active`、`subagent`、`planner`（键名以仓库示例 `cai-agent.example.toml` 为准）。

## 2. 与「启发式路由」的关系

- **`models suggest`**（`models_suggest_v1`）：按 **任务描述关键词** 推荐 profile，**不自动切换**运行时路由；用户或脚本需显式改 `active` / TUI `/use-model`。
- **本文件 § 3**：意图将「规则表」**声明式**落入 TOML，便于审计与 CI 校验；与 `models suggest` 可并存（规则优先或 suggest 仅作默认）。

## 3. `[models.routing]` 配置与语义

以下片段 **会被 `Settings.from_env` 读取**；未配置 **`[models.routing]`** 时行为与旧版一致。

```toml
[models]
active = "fast"

[models.routing]
version = 1
# enabled = false   # 关闭声明式路由（仍解析 rules，供诊断）

[[models.routing.rules]]
# 仅当 role=planner 时尝试匹配（示例）
roles = ["planner"]
goal_regex = "(?i)(安全|security|audit)"
profile = "review"

[[models.routing.rules]]
roles = ["active", "subagent", "planner"]
goal_substring = "翻译"
profile = "translate"

# 成本敏感：当 ``max(0, [cost].budget_max_tokens - 进程累计 total_tokens) < N`` 时命中（读 ``get_usage_counters()``）
# [[models.routing.rules]]
# roles = ["active", "subagent", "planner"]
# cost_budget_remaining_tokens_below = 8000
# profile = "tiny"
```

**已实现（摘要）**

1. **`config.py`**：`parse_model_routing_section` → **`Settings.model_routing_rules`**；**`model_routing_enabled`**（默认 true，可由 **`[models.routing] enabled = false`** 关闭）。
2. **`llm_factory.resolve_effective_profile_for_llm`**：在 **role 解析之后** 用 **goal 条件**（首条 **`user`**）与 **成本条件**（**`[cost].budget_max_tokens` − `get_usage_counters().total_tokens`**）做 **AND** 命中；**`chat_completion_by_role`** 已接入。与 **`--model` / profile 投影** 的优先级：**先 role 基线 profile，再路由覆盖，再走 `_project_settings_for_profile`**（运行期 model override 规则不变）。
3. **`doctor --json`**：**`model_routing_enabled`**、**`model_routing_rules_count`**。
4. CLI：**`cai-agent models routing-test [--goal …] [--role …] [--total-tokens-used N] --json`** → **`models_routing_test_v1`**（含 **`cost_budget_max_tokens` / `total_tokens_used` / `cost_budget_remaining`**；**`--total-tokens-used`** 与 **`resolve_effective_profile_for_llm(..., routing_total_tokens_used_override=…)`** 对齐干跑）；JSON Schema：**`cai-agent/src/cai_agent/schemas/models_routing_test_v1.schema.json`**。
5. **成本条件**：**`cost_budget_remaining_tokens_below`** 与 **`[cost].budget_max_tokens`**（即 **`Settings.cost_budget_max_tokens`**）及 **`cai_agent.llm.get_usage_counters()`** 的 **`total_tokens`** 联动；可与 **`goal_regex` / `goal_substring` AND** 组合。

## 4. 相关文档

- 模型切换总览：[MODEL_SWITCHER_BACKLOG.zh-CN.md](MODEL_SWITCHER_BACKLOG.zh-CN.md)
- Parity 成本/路由一行：[PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md) L2 **成本 / token 策略**
- 英文摘要：[MODEL_ROUTING_RULES.md](MODEL_ROUTING_RULES.md)
