# RFC：模型切换与状态提示一致（CC-03b）

> 状态：**设计草案**。依赖 **`profile_contract_v1`**（**HM-01a** 已落地）。

## 1. 问题

TUI **`/models`**、**`/status`** 与 CLI **`models list`** / **`doctor`** 应对 **同一 active profile**、**subagent/planner** 与 **迁移状态** 给出一致文案，避免一处显示 `default` 另一处显示合成 id 的困惑。

## 2. 原则

- **单一数据源**：机读一律以 **`profile_contract_v1`**（及 **`Settings.active_profile_id`**）为准。
- **人读短标签**：TUI 状态条 **`#context-label`** 仅展示 **`<active_id>`**；若存在 **subagent/planner** 覆盖，在同一行用 **`· route=sub/pl`** 缩写（长度上限 80 字符截断）。
- **切换反馈**：在 **`/models`** 内切换成功后，底部 strip 打印一行 **`profile_switched: <id>`**（与 CLI **`models use`** 成功文案同义）。

## 3. 与 `/status` 对齐字段

| 概念 | `/status` 展示 | `doctor` 文本 | `doctor --json` |
|------|-----------------|---------------|-----------------|
| 当前模型 profile | **`active_profile_id`** | 同行 **`Profile:`** | **`active_profile_id`** + **`profile_contract`** |
| 路由覆盖 | **`subagent` / `planner` 行** | **`路由:`** 行 | **`subagent_profile_id`** / **`planner_profile_id`** |
| 迁移提示 | 若有 **`migration_state != clean`** | 在 **Profile Contract** 后追加一行警告 | **`profile_contract.migration_state`** |

## 4. 验收

- 手工：在含 **`[[models.profile]]`** 与 **`[models] active`** 的 TOML 下切换 profile，**`/status`** 与 **`doctor`** 的 active id 一致。
- 自动化：扩展 **`test_tui_*`** 或 **`test_doctor_cli`** 对 **`profile_contract.active_profile_id`** 与 TUI 解析结果做快照比对（后续 **`HM-02b`** 不阻塞本项）。
