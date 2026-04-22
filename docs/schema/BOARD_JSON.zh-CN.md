# `cai-agent board --json`

## schema_version

`board_v1`（见 `cai_agent.board_state.build_board_payload`）。

## 顶层字段（摘要）

| 字段 | 类型 | 说明 |
|------|------|------|
| `observe_schema_version` | string | 内嵌 `observe` 的代际，与 `observe --json` 一致 |
| `observe` | object | 与 `build_observe_payload` 根对象同源；筛选后 `sessions` 与 `sessions_count` 会更新，`aggregates` 可能仍为全量扫描值（见实现注释） |
| `last_workflow` | object \| null | `.cai/last-workflow.json` |
| `failed_summary` / `status_summary` / `group_summary` / `trend_summary` | object | 看板附加块（随 CLI 选项填充） |

## Exit 码

- 默认：`0`。
- `--fail-on-failed-sessions`：当前输出中的 **`observe.sessions` 列表**里存在 `error_count>0` 的会话时 `2`（与 `--failed-only` 等筛选后的列表一致）。
