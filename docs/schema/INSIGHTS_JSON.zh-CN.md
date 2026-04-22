# `cai-agent insights --json`

## schema_version

当前主线：`1.1`（见 `_build_insights_payload`）。

## 顶层字段（摘要）

| 字段 | 类型 | 说明 |
|------|------|------|
| `window` | object | `days`、`since`、`pattern`、`limit` |
| `sessions_in_window` | int | 窗口内成功解析的会话数 |
| `parse_skipped` | int | 解析跳过数 |
| `failure_rate` | float | 含 `error_count>0` 的会话占比 |
| `total_tokens` | int | |
| `tool_calls_total` | int | |
| `models_top` / `tools_top` | array | Top 统计 |
| `top_error_sessions` | array | 异常会话摘要 |

## Exit 码

- 默认：成功 `0`。
- 传入 `--fail-on-max-failure-rate RATE`（0~1）：当 `failure_rate >= RATE` 时 `2`。
