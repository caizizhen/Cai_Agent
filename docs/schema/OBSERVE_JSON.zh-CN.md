# `cai-agent observe --json`

## schema_version

当前主线：`1.1`（见 `cai_agent.session.build_observe_payload`）。

## 顶层字段（摘要）

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | string | 契约版本 |
| `generated_at` | string (ISO8601) | 生成时间 |
| `workspace` | string | 绝对路径工作区 |
| `pattern` | string | 会话文件 glob |
| `limit` | int | 扫描上限 |
| `sessions_count` | int | 本会话列表长度 |
| `sessions` | array | 每项含 `path`、`mtime`、`total_tokens`、`error_count`、`task_id`、`task_status` 等 |
| `aggregates` | object | `total_tokens`、`failed_count`、`failure_rate`、`run_events_total` 等 |
| `task` | object | 内部 observe 任务元数据 |
| `events` | array | 含 `observe.summarized` 等 |

## Exit 码

- 成功：`0`（当前实现不因失败会话而变码；阈值门禁请用 `observe-report`）。
