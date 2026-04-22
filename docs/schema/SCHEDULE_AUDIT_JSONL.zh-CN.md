# Schedule 审计 JSONL（S4-04）

> 文件：工作区根目录 **`.cai-schedule-audit.jsonl`**；`cai-agent schedule daemon --jsonl-log <path>` 时，**同一行格式**会镜像追加到指定路径（与审计文件并行写入）。

其它 CLI JSON 契约与 exit 约定见同目录 [`README.zh-CN.md`](README.zh-CN.md)。

## 版本

- 每行 JSON 含 **`schema_version`**：当前为 **`1.0`**。

## 每行必填顶层字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `schema_version` | string | 固定 `1.0` |
| `ts` | string | UTC ISO8601 |
| `event` | string | 见下表 |
| `task_id` | string | 任务 id；`daemon.started` / `daemon.cycle` 可为空字符串 |
| `goal_preview` | string | 目标文本截断预览（最长约 120 字符） |
| `elapsed_ms` | int | 毫秒；无计时语义时为 `0` |
| `error` | string \| null | 失败/跳过时的人类可读摘要；成功为 `null` |
| `status` | string | 与调度持久化语义相关的状态（如 `completed` / `retrying` / `skipped`） |
| `action` | string | 来源子命令，如 `schedule.add`、`schedule.run_due`、`schedule.daemon` |
| `details` | object | 扩展字段（`attempts`、`cycle`、`retry_count` 等） |

## `event` 取值（Hermes S4-04）

| `event` | 含义 |
|---------|------|
| `task.started` | 单次执行开始前（`run-due --execute` / `daemon --execute`） |
| `task.completed` | 单次执行成功；`schedule add` 成功创建任务也记为此类（任务已就绪） |
| `task.failed` | 单次执行失败或不可恢复错误（如 `empty_goal`、`failed_exhausted`） |
| `task.retrying` | 失败后进入跨轮次重试窗口（`last_status=retrying`） |
| `task.skipped` | 本周期未执行（如并发上限 `skipped_due_to_concurrency`） |
| `daemon.started` | `schedule daemon` 取得锁并开始主循环 |
| `daemon.cycle` | 每轮轮询结束摘要（`details` 内含 `cycle`、`due_count`、`executed` 等） |

## jq 示例

```bash
jq -c 'select(.event=="task.completed")' .cai-schedule-audit.jsonl
jq -c 'select(.event=="daemon.cycle")' .cai-schedule-daemon.jsonl
```
