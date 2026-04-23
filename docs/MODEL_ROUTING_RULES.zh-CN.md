# 模型路由规则表（TOML 草案 + 现状）

> **状态**：**§ 1～2** 描述 **当前已实现** 行为（代码：`cai_agent.llm_factory.resolve_role_profile` / `chat_completion_by_role`）。**§ 3** 为 **未来** `[models.routing]` 规则表 **TOML 草案**（**未解析、未生效**）；实现与可选 **`models route-test`** 等子命令仍属 backlog。

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

## 3. `[models.routing]` TOML 草案（未实现）

以下片段 **不会被当前 `Settings.from_env` 读取**；仅供设计与评审。

```toml
[models]
active = "fast"

# 未来扩展：按优先级从上到下匹配，命中则使用该 profile 覆盖本轮（或仅 planner/subagent 域）
[models.routing]
version = 1

[[models.routing.rules]]
# 仅当 role=planner 时尝试匹配（示例）
roles = ["planner"]
goal_regex = "(?i)(安全|security|audit)"
profile = "review"

[[models.routing.rules]]
roles = ["active", "subagent", "planner"]
goal_substring = "翻译"
profile = "translate"

# 可选：成本敏感任务强制小模型（需与 cost_budget 读数打通，实现时定稿）
# [[models.routing.rules]]
# cost_budget_remaining_tokens_below = 8000
# profile = "tiny"
```

**实现 backlog（摘要）**

1. 在 **`config.py`** 解析 `routing` 段为不可变结构挂到 **`Settings`**。
2. 在 **`llm_factory.chat_completion_by_role`**（或单独 **`resolve_routed_profile`**）在 **role 解析之后** 应用规则（需定义与 **`--model` / step override** 的优先级）。
3. **`doctor --json`** 输出 `routing_rules_count` 等诊断字段。
4. 可选 CLI：**`models routing explain --goal "..."`** 打印命中规则链。

## 4. 相关文档

- 模型切换总览：[MODEL_SWITCHER_BACKLOG.zh-CN.md](MODEL_SWITCHER_BACKLOG.zh-CN.md)
- Parity 成本/路由一行：[PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md) L2 **成本 / token 策略**
