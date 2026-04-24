# Sprint 4 QA 测试计划：Scheduler 2.0（生产可用）

> 对应开发文档：`docs/archive/legacy/HERMES_PARITY_SPRINT_PLAN.zh-CN.md` §Sprint 4
> 对应 backlog：`docs/archive/legacy/HERMES_PARITY_BACKLOG.zh-CN.md` §Epic S4
> 执行命令入口：`python3 -m pytest -q cai-agent/tests/test_schedule*.py`

---

## 1. 测试范围

| 功能 | 命令 | 测试重点 |
|------|------|---------|
| 重试与退避 | `schedule run-due --execute` | 失败后自动重试、退避间隔 |
| 并发控制 | `schedule daemon --max-concurrent N` | 同时执行任务上限 |
| 任务依赖 | `schedule add --depends-on` | 依赖未完成则跳过 |
| 审计日志 | `--jsonl-log` | 事件类型、字段完整性 |
| 任务 SLA | `schedule stats --json` | 统计指标正确性 |

---

## 2. 测试用例

### SCH-RETRY-001：单任务失败后触发重试
- **前置条件**：创建一个任务，mock 首次执行失败
- **执行**：`cai-agent schedule run-due --execute --json`（连续执行多次）
- **期望**：
  - 失败后 `retry_count` 递增
  - `next_retry_at` 设置为 `now + 60 * 2^(retry_count-1)` 秒（第 1 次失败 60s，第 2 次 120s，第 3 次 240s）
  - 状态为 `retrying` 而非 `failed`

### SCH-RETRY-002：达到最大重试次数后放弃
- **前置条件**：`max_retries=3`，连续 3 次 mock 失败
- **执行**：多轮执行直到 `retry_count=3`
- **期望**：第 4 次状态变为 `failed_exhausted`，不再重试

### SCH-RETRY-003：重试成功后重置计数
- **前置条件**：前 2 次失败，第 3 次成功
- **执行**：模拟 3 轮
- **期望**：第 3 轮后 `retry_count=0`，`last_status=completed`

### SCH-RETRY-004：退避间隔递增正确
- **执行**：追踪 `next_retry_at` 字段
- **期望**：第 1 次失败等 60s，第 2 次等 120s，第 3 次等 240s（可允许 ±5s 误差）

### SCH-CONC-001：`--max-concurrent 1` 时只执行一个任务
- **前置条件**：同时有 3 个到期任务
- **执行**：`cai-agent schedule daemon --max-concurrent 1 --max-cycles 1 --execute --json`
- **期望**：`total_executed=1`，其余任务延迟到下轮

### SCH-CONC-002：`--max-concurrent 3` 时允许 3 个并发
- **前置条件**：同时有 5 个到期任务
- **执行**：`cai-agent schedule daemon --max-concurrent 3 --max-cycles 1 --execute --json`
- **期望**：`total_executed=3`、`total_skipped_due_to_concurrency=2`；`.cai-schedule-audit.jsonl` 或 `--jsonl-log` 路径下存在 **`skipped_due_to_concurrency`** 事件（审计行 `details.reason` 同值）

### SCH-CONC-003：并发为 0 时使用默认值（不崩溃）
- **执行**：`cai-agent schedule daemon --max-concurrent 0`
- **期望**：使用默认并发值（1），不崩溃

### SCH-DEP-001：依赖任务未完成时跳过当前任务
- **前置条件**：B 任务 `depends_on=A_id`，A 任务未运行
- **执行**：`cai-agent schedule run-due --json`
- **期望**：B 不出现在 `due_jobs`；`schedule list --json` 中 B 行 **`dependency_blocked`** 为 true，**`depends_on_chain`** 含上游 `last_status`

### SCH-DEP-002：依赖任务完成后当前任务可执行
- **前置条件**：A 已完成（`last_status=completed`），B 依赖 A
- **执行**：`cai-agent schedule run-due --json`
- **期望**：B 在 `due_jobs` 中且可执行

### SCH-DEP-003：循环依赖检测
- **前置条件**：A depends_on B，B depends_on A
- **执行**：添加会形成环的 `schedule add --depends-on …`（或等价 API）
- **期望**：命令 **exit 2**，`--json` 为 **`{"ok":false,"error":"schedule_add_invalid",…}`**，`.cai-schedule.json` 不增加新任务

### SCH-AUDIT-001：JSONL 日志事件字段完整
- **前置条件**：启用 `--jsonl-log`，运行一个任务
- **执行**：解析 JSONL 文件
- **期望**：每行包含 `schema_version`、`ts`、`event`、`task_id`、`goal_preview`、`elapsed_ms`、`error`、`details`（与 `.cai-schedule-audit.jsonl` 顶层一致）

### SCH-AUDIT-002：所有事件类型均有覆盖
- **前置条件**：运行多轮（含成功/失败/重试/跳过）
- **执行**：检查 JSONL 日志
- **期望**：包含以下事件类型：
  - `task.started`
  - `task.completed`
  - `task.failed`
  - `task.retrying`
  - `task.skipped`
  - `daemon.cycle`
  - `daemon.started`

### SCH-AUDIT-003：JSONL 每行均为合法 JSON
- **执行**：`cat .cai-schedule-daemon.jsonl | python3 -c "import sys,json;[json.loads(l) for l in sys.stdin]"`
- **期望**：无解析错误

### SCH-AUDIT-004：日志文件不超过合理大小（长跑）
- **执行**：daemon 跑 50 轮次
- **期望**：日志文件增长符合预期（无内存泄漏、无意外重复写入）

### SCH-SLA-001：`schedule stats` 基础输出
- **前置条件**：至少一个任务有运行历史
- **执行**：`cai-agent schedule stats --json`
- **期望**：包含 **`schema_version`**（`schedule_stats_v1`）、**`tasks`** 数组；每项含 **`success_rate`**、**`avg_elapsed_ms`**、**`p95_elapsed_ms`**、**`run_count`**、**`fail_count`**

### SCH-SLA-002：`--days` 时间窗口过滤
- **前置条件**：任务在 31 天前有运行记录，30 天内没有
- **执行**：`cai-agent schedule stats --json --days 30`
- **期望**：该任务 **`run_count=0`**（窗口内无审计事件）；或该 `task_id` 不出现在 `tasks` 中（若 schedule 中已无该任务定义且窗口内无事件）

---

## 3. 故障注入测试

### SCH-FI-001：lock 文件残留后 daemon 启动
- **前置条件**：手动创建 lock 文件（模拟上次崩溃遗留）
- **执行**：`cai-agent schedule daemon --stale-lock-sec 60`（设置回收阈值）
- **期望**：超过阈值的 lock 被自动回收，daemon 正常启动

### SCH-FI-002：schedule 文件损坏
- **前置条件**：`.cai-schedule.json` 中写入无效 JSON
- **执行**：`cai-agent schedule list --json`
- **期望**：exit 2，清晰错误信息，不产生部分写入

### SCH-FI-003：daemon kill 后重启状态可恢复
- **执行**：启动 daemon → kill -9 → 重启
- **期望**：任务状态（retry_count/last_status/next_retry_at）从文件恢复，不重置

---

## 4. 回归关联

```bash
python3 -m pytest -q cai-agent/tests/test_schedule_cli.py
python3 -m pytest -q cai-agent/tests/test_schedule_daemon_cli.py
python3 -m pytest -q cai-agent/tests/test_schedule_daemon_guardrails.py
python3 -m pytest -q cai-agent/tests/test_schedule_run_due_execute.py
```

---

## 5. 验收信号

- SCH-RETRY-001~004、SCH-CONC-001~003、SCH-AUDIT-001~004 全部通过
- 故障注入用例 SCH-FI-001~003 通过
- schedule stats 命令在 README 有示例
