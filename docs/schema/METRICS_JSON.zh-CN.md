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
- **`cai-agent gateway telegram resolve-update`**：**`gateway.telegram.resolve_update`**（**`success`** = 无 **`error`** 且解析到 **`binding`**）。
- **`cai-agent memory extract` / `list` / `instincts` / `search` / `prune` / `export` / `import` / `export-entries` / `import-entries`**：**`memory.extract`** / **`memory.list`** / **`memory.instincts`** / **`memory.search`** / **`memory.prune`** / **`memory.export`** / **`memory.import`** / **`memory.export_entries`** / **`memory.import_entries`**（**`tokens`** 视子命令为会话数、条目数、命中数、**`removed_total`**、导入计数等）。
- **`cai-agent schedule add-memory-nudge`**：**`schedule.add_memory_nudge`**。
- **`cai-agent quality-gate`**：**`quality_gate.run`**（**`tokens`** = **`len(checks)`**；**`success`** = **`ok`**）。
- **`cai-agent security-scan`**：**`security_scan.run`**（**`tokens`** ≈ **`findings_count`** 或 **`scanned_files`**）。
- **`cai-agent mcp-check`**：**`mcp.check`**（**`latency_ms`** = CLI **`elapsed_ms`**；**`tokens`** = **`len(tool_names)`**；**`success`** = **`ok`**）。
- **`cai-agent hooks run-event`**：**`hooks.run_event`**（**`tokens`** = dry-run 预览条数或执行 **`results`** 条数；**`success`** 与 exit 语义一致；未找到 **`hooks.json`** 时 **`success=false`**）。
- **`cai-agent gateway telegram serve-webhook`**：**`gateway.telegram.serve_webhook`**（**`tokens`** ≈ **`handled_requests`**；**`success`** = 返回负载 **`ok`**；在 HTTP 服务正常结束一轮后打点）。
- **`cai-agent sessions`**：**`sessions.list`**（**`tokens`** = 列出的会话文件数 **`len(files)`**）。
- **`cai-agent stats`**：**`stats.summary`**（**`tokens`** = **`sessions_count`** 汇总值）。
- **`cai-agent insights`**：**`insights.summary`**；**`--cross-domain --json`** 时为 **`insights.cross_domain`**（**`tokens`** ≈ **`sessions_in_window`/`total_tokens`**；**`--fail-on-max-failure-rate`** 触发 exit **`2`** 时 **`success=false`**）。
- **`cai-agent plugins`**：**`plugins.surface`**（**`tokens`** = 各组件 **`files_count`** 之和；**`--fail-on-min-health`** 未达标时 **`success=false`**）。
- **`cai-agent skills hub manifest`**：**`skills.hub_manifest`**（**`tokens`** ≈ **`count`**）。
- **`cai-agent commands` / `agents`**：**`commands.list`** / **`agents.list`**（**`tokens`** = 名称条数）。
- **`cai-agent doctor`**：**`doctor.run`**（**`tokens`**=`0`**；**`success`** = exit **`0`**）。
- **`cai-agent plan`**：**`plan.generate`**（**`tokens`** ≈ LLM **`usage.total_tokens`**；配置/goal 错误、中断、LLM 失败时 **`success=false`**）。
- **`cai-agent cost budget`**：**`cost.budget`**（**`tokens`** = **`total_tokens`** 聚合；**`state=fail`** 时 **`success=false`**）。
- **`cai-agent export`**：**`export.target`**（**`tokens`** = **`len(copied)`**）。
- **`cai-agent observe-report`**：**`observe.report`**（与 **`observe report`** 同事件名；**`tokens`** ≈ **`observe.aggregates.total_tokens`**；**`state=fail`** 或 **`--fail-on-warn`** 触发 **`2`** 时 **`success=false`**）。
- **`cai-agent ops dashboard`**：**`ops.dashboard`**（**`tokens`** ≈ **`summary.sessions_count`** 或 **`schedule_tasks_in_stats`**）。
- **`cai-agent board`**：**`board.summary`**（**`tokens`** ≈ 内嵌 **`observe.sessions_count`**）。
- **`cai-agent hooks list`**：**`hooks.list`**（**`tokens`** = 目录 **`hooks`** 条数；**`hooks.json` 缺失/无效** 时 **`success=false`**）。
- **`cai-agent init`**：**`init.apply`**（**`tokens`** = 成功 **`1`** / 失败 **`0`**；**`success`** 与 exit 一致）。
- **`cai-agent models`**：**`models.list`** / **`models.fetch`** / **`models.ping`** / **`models.route`** / **`models.add`** / **`models.use`** / **`models.rm`** / **`models.edit`**（未映射子命令为 **`models.cli`**；**`tokens`** 为 profile 数、**`fetch`+`--json`** 成功记 **`1`**、变更类成功记 **`1`** 等粗粒度提示）。
- **`cai-agent workflow`**：**`workflow.run`**（**`tokens`** = 汇总 **`budget_used`**；**`success`** = 任务 **`completed`** 且未因 **`--fail-on-step-errors`** 置 **`2`**；**`run_workflow` 抛错** 时 **`success=false`**、**`tokens=0`**）。
- **`cai-agent release-ga`**：**`release_ga.gate`**（**`tokens`** = **`len(checks)`**；**`success`** = **`state`** 为 **`pass`**）。
- **`cai-agent ui`**：**`ui.tui`**（**`tokens`**=`0`**；**`success`** = TUI 正常退出；配置缺失等 **`success=false`**）。

> 其它长尾子命令若需指标，仍按 **S7-01 AC2** 增量扩展。

## 示例行

```json
{"schema_version":"metrics_schema_v1","ts":"2026-04-23T12:00:00+00:00","module":"observe","event":"observe.summary","latency_ms":12.3,"tokens":0,"success":true}
```
