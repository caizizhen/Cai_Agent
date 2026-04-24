# Model routing rules (`[models.routing]`)

> Chinese: [MODEL_ROUTING_RULES.zh-CN.md](MODEL_ROUTING_RULES.zh-CN.md)

## Current behavior

- **`resolve_role_profile`**: maps `active` / `subagent` / `planner` to a profile id (with fallbacks documented in the Chinese file).
- **`chat_completion_by_role`**: after role resolution, applies **`[models.routing]`** rules in file order. The routing “goal” text is taken from the **first `user` message** in the `messages` list (same shape as the main graph loop).

## TOML

See **§3** in [MODEL_ROUTING_RULES.zh-CN.md](MODEL_ROUTING_RULES.zh-CN.md) for a full example. Rules support:

- **`roles`**: optional list; default is all three roles if omitted.
- **`goal_regex`**: Python `re.search` against the goal string (invalid regex rows are skipped at load time).
- **`goal_substring`**: literal substring match (used when no regex is set, or if only substring is configured).
- **`cost_budget_remaining_tokens_below`**: when set, the rule also requires  
  `max(0, cost_budget_max_tokens - total_tokens_used) < N`, using **`[cost].budget_max_tokens`** and **`get_usage_counters()["total_tokens"]`** (same source as the graph’s cost hint path).
- **`profile`**: target profile id; unknown ids are ignored (falls back to the role baseline profile).

At least one of **`goal_regex` / `goal_substring` / `cost_budget_remaining_tokens_below`** must be present per rule row.

**`[models.routing] enabled = false`**: disables overlay matching; rules may still be present for diagnostics.

## CLI

- **`cai-agent models routing-test [--goal …] [--role active|subagent|planner] [--total-tokens-used N] [--json]`**: without **`--json`**, prints **`effective_profile_id=`** plus a **Chinese summary** line. With **`--json`**, prints **`models_routing_test_v1`** including **`explain`** (**`routing_explain_v1`**: `decision`, `summary_zh`, `summary_en`), `base_profile_id`, `effective_profile_id`, `cost_budget_max_tokens`, `total_tokens_used`, `cost_budget_remaining`, and optional `matched_rule`. **`--total-tokens-used`** simulates usage for dry-runs. No LLM call.
- **`cai-agent cost budget`**: stdout **`cost_budget_v1`** now includes **`explain`** (**`cost_budget_explain_v1`**) and **`active_profile_id`** for the same “why pass/warn/fail” story.

## Doctor

**`doctor --json`** includes **`model_routing_enabled`** and **`model_routing_rules_count`**.

## JSON Schema

Machine-readable shape: **`cai-agent/src/cai_agent/schemas/models_routing_test_v1.schema.json`**.
