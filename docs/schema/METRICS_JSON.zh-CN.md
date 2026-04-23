# 指标事件 JSONL（S7-01 · `metrics_schema_v1`）

> 非 CLI 标准输出；当环境变量 **`CAI_METRICS_JSONL`** 指向可写路径时，部分命令会**追加一行 JSON**（JSONL），便于外接采集。

## 版本

- **`schema_version`**：固定为 **`metrics_schema_v1`**（与 `cai_agent.metrics.METRICS_SCHEMA_VERSION` 一致）。

## 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `schema_version` | string | 是 | `metrics_schema_v1` |
| `ts` | string (ISO8601 UTC) | 是 | 事件时间 |
| `module` | string | 是 | 逻辑模块，如 **`observe`** |
| `event` | string | 是 | 事件名，如 **`observe.summary`**、**`observe.report`** |
| `latency_ms` | number | 是 | 本次操作耗时（毫秒）；无则 `0` |
| `tokens` | int | 是 | 关联 token 计数（observe 路径下为聚合 **`total_tokens`** / **`token_total`**）；无则 `0` |
| `cost_usd` | number | 否 | 可选成本 |
| `success` | bool | 是 | 是否视为成功落盘 |

## 触发路径（当前实现）

- **`cai-agent observe`**（默认摘要或 **`--json`**）：成功生成 payload 后写入 **`observe.summary`**。
- **`cai-agent observe report`**：成功生成报告后写入 **`observe.report`**。
- **`cai-agent observe export`**：成功生成导出后写入 **`observe.export`**。
- **`cai-agent memory health`**（文本或 **`--json`**）：成功生成健康负载后写入 **`memory.health`**（**`tokens`** ≈ **`counts.memory_entries`**）。
- **`cai-agent recall`**（扫描或 **`--use-index`**，成功路径）：写入 **`recall.query`**（**`tokens`** ≈ **`sessions_scanned`**）。
- **`cai-agent schedule stats`**：写入 **`schedule.stats`**（**`tokens`** = 任务行数 **`len(tasks)`**）。
- **`cai-agent gateway status`**：写入 **`gateway.status`**（**`tokens`**=`0`）。
- **`cai-agent recall-index build` / `refresh` / `search`**（成功路径）：**`recall_index.build`** / **`recall_index.refresh`** / **`recall_index.search`**（**`tokens`** ≈ **`sessions_indexed`** / **`sessions_touched`** / **`sessions_scanned`**，视子命令而定）。
- **`cai-agent schedule list`**：**`schedule.list`**（**`tokens`** = **`len(jobs)`**）。
- **`cai-agent schedule add`**：**`schedule.add`**（**`tokens`** = **`len(depends_on)`**）。
- **`cai-agent gateway telegram list`**：**`gateway.telegram.list`**（**`tokens`** = **`bindings_count`**）。
- **`cai-agent run` / `continue`**（**`app.invoke`** 成功落盘路径）：**`run.invoke`** / **`continue.invoke`**（**`latency_ms`** = 会话 **`elapsed_ms`**；**`tokens`** = **`total_tokens`**；**`success`** = 任务是否 **`completed`**）。
- **`cai-agent command` / `agent` / `fix-build`**（**`app.invoke`** 成功落盘路径）：**`command.invoke`** / **`agent.invoke`** / **`fix-build.invoke`**（字段含义同 **`run.invoke`**）。
- **`cai-agent memory state`**：**`memory.state`**（**`tokens`** ≈ **`total_entries`**）。
- **`cai-agent memory nudge`**：**`memory.nudge`**（**`tokens`** ≈ **`memory_entries`**）。
- **`cai-agent memory nudge-report`**：**`memory.nudge_report`**（**`tokens`** ≈ **`entries_considered`**）。
- **`cai-agent recall-index benchmark` / `info` / `clear` / `doctor`**：**`recall_index.benchmark`** / **`recall_index.info`** / **`recall_index.clear`** / **`recall_index.doctor`**（**`doctor`** 的 **`success`** = **`is_healthy`**；**`tokens`** 视子命令为扫描会话数、**`entries_count`**、**`removed`** 或问题条目规模）。
- **`cai-agent schedule rm`**：**`schedule.rm`**（**`success`** = 是否删除成功；**`tokens`** 粗记 **`0`/`1`**）。
- **`cai-agent schedule run-due`**（dry-run 与 execute 成功路径）：**`schedule.run_due`**（**`tokens`** = **`len(due_jobs)`** 或 **`len(executed)`**）。
- **`cai-agent schedule daemon`**（单实例锁获取成功、正常结束摘要）：**`schedule.daemon`**（**`tokens`** = **`total_executed`**；**`success`** = 未 **`KeyboardInterrupt`**）。
- **`cai-agent gateway telegram bind` / `get` / `unbind` / `continue-hint`**：**`gateway.telegram.bind`** / **`gateway.telegram.get`** / **`gateway.telegram.unbind`** / **`gateway.telegram.continue_hint`**（CLI 子命令 **`continue-hint`**；**`get`** 的 **`success`** = 是否找到绑定）。
- **`cai-agent gateway telegram allow add|list|rm`**：**`gateway.telegram.allow_add`** / **`allow_list`** / **`allow_rm`**。

> 其它 **memory** 子命令（**`extract`/`list`/…**）、**`schedule`/`gateway telegram`** 的 **`resolve-update`** 等、**`quality-gate`/`security-scan`** 等仍为 **后续增量**（与 **S7-01 AC2** 一致）。

## 示例行

```json
{"schema_version":"metrics_schema_v1","ts":"2026-04-23T12:00:00+00:00","module":"observe","event":"observe.summary","latency_ms":12.3,"tokens":0,"success":true}
```
