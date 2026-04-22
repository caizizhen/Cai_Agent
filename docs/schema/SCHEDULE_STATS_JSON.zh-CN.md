# `cai-agent schedule stats --json`（S4-05）

## 用途

从 **`.cai-schedule-audit.jsonl`**（可用 `--audit-file` 覆盖）读取 S4-04 格式行，在 **`--days`** 时间窗内（按每行 `ts`）聚合每个 **`task_id`** 的执行结果与耗时分布。

## 顶层字段

| 字段 | 说明 |
|------|------|
| `schema_version` | 固定 **`schedule_stats_v1`** |
| `generated_at` | UTC ISO8601 |
| `days` | 统计窗口天数（1~366） |
| `audit_file` | 实际读取的审计文件绝对路径 |
| `audit_lines_in_window` | 时间窗内解析到的行数（含无 `task_id` 的行） |
| `tasks` | 数组，见下表 |

## `tasks[]` 每项

| 字段 | 说明 |
|------|------|
| `task_id` | 与 `.cai-schedule.json` 中任务 id 一致 |
| `goal_preview` | 来自当前 schedule 列表或审计行 `goal_preview` |
| `run_count` | `success_count` + `fail_count`（仅统计 `task.completed` / `task.failed` / `task.retrying`） |
| `success_count` | `task.completed` 次数 |
| `fail_count` | `task.failed` + `task.retrying` 次数 |
| `success_rate` | `success_count / run_count`；`run_count==0` 时为 `null` |
| `avg_elapsed_ms` | 上述事件里 `elapsed_ms>0` 的算术平均；无样本时为 `0` |
| `p95_elapsed_ms` | 同上样本的 **P95**（`ceil(0.95*n)` 位置）；无样本时为 `0` |

## 兼容

若审计行缺少 `event` 字段（S4-04 前旧格式），统计时会用 `action`/`status`/`details` 推导等价事件后再归类。

## Exit 码

- 默认：成功 `0`。
- `--fail-on-min-success-rate RATE`（0~1）：任一任务 `run_count >= 1` 且 `success_rate < RATE` 时 `2`。
