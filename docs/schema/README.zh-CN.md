# JSON 输出契约索引（S1-02）

本文件汇总 **`cai-agent` 各命令 `--json` 或专用 JSON 输出** 的 `schema_version`、主要字段与 **exit 码约定**（与 [S1-03](../HERMES_PARITY_BACKLOG.zh-CN.md) 一致：成功 `0`，逻辑/阈值失败 `2`，用法错误 `2`）。

**仅下列长文仍拆成独立文件**（历史路径，CI/外链可能引用）：[SCHEDULE_AUDIT_JSONL.zh-CN.md](SCHEDULE_AUDIT_JSONL.zh-CN.md)、[SCHEDULE_STATS_JSON.zh-CN.md](SCHEDULE_STATS_JSON.zh-CN.md)。其余命令契约 **以本节为准**，更新时只改本文件与上述两文件，勿再新增平行 schema 文档。

---

## `observe` / `observe --json`

- **实现**：`cai_agent.session.build_observe_payload`
- **`schema_version`**：`1.1`

| 顶层字段（摘要） | 类型 | 说明 |
|------------------|------|------|
| `schema_version` | string | 契约版本 |
| `generated_at` | string (ISO8601) | |
| `workspace` / `pattern` / `limit` | string / int | |
| `sessions_count` / `sessions` | int / array | 会话行含 `path`、`mtime`、`error_count`、`task_id`、`task_status`、`events_count` 等 |
| `aggregates` | object | `total_tokens`、`failed_count`、`failure_rate`、`run_events_total` 等 |
| `task` / `events` | object / array | 内部 observe 任务与 `observe.summarized` 事件 |

**Exit**：默认 `0`。`--fail-on-max-failure-rate RATE`（0~1）：当 `aggregates.failure_rate >= RATE` 时 `2`（与 `insights --fail-on-max-failure-rate` 语义一致）。

---

## `observe-report` / `observe-report --json`

- **实现**：`_build_observe_report_payload`
- **`schema_version`**：`observe_report_v1`

| 顶层字段（摘要） | 类型 | 说明 |
|------------------|------|------|
| `state` | string | `pass` / `warn` / `fail` |
| `alerts` | array | `metric`、`value`、`warn_threshold`、`fail_threshold`、`level`（`ok`/`warn`/`fail`） |
| `observe` | object | 嵌套 observe 摘要 |

阈值：`--warn-failure-rate` / `--fail-failure-rate`、`--warn-token-budget` / `--fail-token-budget`、`--warn-tool-errors` / `--fail-tool-errors`。

**Exit**：`state == fail` → `2`；`state == warn` 且 `--fail-on-warn` → `2`；否则 `0`。

---

## `insights` / `insights --json`

- **实现**：`_build_insights_payload`
- **`schema_version`**：`1.1`

| 顶层字段（摘要） | 类型 | 说明 |
|------------------|------|------|
| `window` | object | `days`、`since`、`pattern`、`limit` |
| `sessions_in_window` / `parse_skipped` | int | |
| `failure_rate` | float | 窗口内含错误的会话占比 |
| `models_top` / `tools_top` / `top_error_sessions` | array | |

**Exit**：默认 `0`。`--fail-on-max-failure-rate RATE`：`failure_rate >= RATE` → `2`。

---

## `board` / `board --json`

- **实现**：`cai_agent.board_state.build_board_payload` 等
- **`schema_version`**：`board_v1`；`observe_schema_version` 与内嵌 `observe` 同源 `build_observe_payload`

内嵌 `observe` 与 `observe --json` 根对象同源；筛选后 `sessions` / `sessions_count` 会更新，`aggregates` 可能仍为全量扫描值（实现细节以代码为准）。

**Exit**：默认 `0`。`--fail-on-failed-sessions`：当前 **`observe.sessions` 列表**中存在 `error_count > 0` → `2`。

---

## `plugins` / `plugins --json`

- **实现**：`cai_agent.plugin_registry.list_plugin_surface`
- **无**顶层 `schema_version` 字段；含 **`plugin_version`**（当前 **`0.1.0`**，与 `PLUGIN_VERSION` 常量一致）、`project_root`、`health_score`（0~100）、`compatibility`、`components`（`skills` / `commands` / `agents` / `hooks` / `rules` / `mcp-configs` 各含 `exists`、`path`、`files_count`）。

**Exit**：默认 `0`；配置缺失等 `2`。`--fail-on-min-health SCORE`：`health_score < SCORE` → `2`。

---

## `commands` / `agents` / `--json`

- **`commands --json`**：`list_command_names` → **字符串数组**（斜杠命令名，无 `schema_version`）。
- **`agents --json`**：`list_agent_names` → **字符串数组**。

**Exit**：配置可读 `0`；`Settings.from_env` 失败（如缺配置）→ `2`。

---

## `workflow` / `workflow <file> --json`

- **实现**：`cai_agent.workflow.run_workflow`
- **`schema_version`**：`workflow_run_v1`；另有 **`subagent_io_schema_version`**：`1.0` 与 `subagent_io`（`inputs` / `merge` / `outputs`）、`steps`、`summary`、`events`、`task`。

**Exit**：文件缺失/解析失败 → `2`；默认成功 `0`。`--fail-on-step-errors`：`task.status == failed` 或 `summary.tool_errors_total > 0` 或任一步 `error_count > 0` → `2`。

---

## `doctor` / `doctor --json`

- **实现**：`cai_agent.doctor.run_doctor` / `build_doctor_payload`
- **`schema_version`**：`doctor_v1`（仅 `--json` 时打印的负载；文本模式无 JSON）

顶层字段含：`cai_agent_version`、`workspace`、`provider`、`model`、`api_key_present`、`api_key_masked_line`、`mock`、`instruction_files`、`git_inside_work_tree`、`profile_ping_skipped`、`profile_pings`（`CAI_DOCTOR_PING=1` 时填充）等。

**Exit**：配置缺失 → `2`；默认 `0`。`--fail-on-missing-api-key`：非 `mock` 且 API Key 解析后为空 → `2`（可与 `--json` 同用于 CI）。

---

## `plan` / `plan --json`

- **实现**：`__main__.py` 内 `plan` 分支 + `chat_completion_by_role`
- **`plan_schema_version`**：`1.0`

成功时：`ok: true`，`plan` 为规划正文，`task`、`usage`、`elapsed_ms` 等。失败时：`ok: false`，`error` 如 `config_not_found` / `goal_empty` / `llm_error` / `interrupted`；**Ctrl+C 中断** exit **`130`**（与常见 shell 约定一致）。

**Exit**：配置/goal/LLM 错误 → `2`；成功 → `0`。

---

## `memory` 子命令 JSON 摘要

| 子命令 | `--json` 形态 | `schema_version` / 说明 |
|--------|----------------|-------------------------|
| `memory extract` | 单行对象 `written` / `entries_appended` | 无统一 `schema_version` |
| `memory list` | **条目数组**（非包一层对象） | 行内字段见 `memory.py`；无顶层 `schema_version` |
| `memory search` | 命中数组 | 同上 |
| `memory instincts` | 路径字符串数组 | |
| `memory prune` | `memory_prune_result_v1` | 含 `removed_total`、`removed_by_reason` 等 |
| `memory state` | `memory_state_eval_v1` | |
| `memory export` / `import` / `export-entries` / `import-entries` | 见实现 | `memory_entries_bundle_v1` / `memory_entries_import_errors_v1` 等 |
| `memory health` | 健康负载 | **`1.0`**（S2-01）；`--fail-on-grade` → exit `2` |
| `memory nudge` | nudge 负载 | `--fail-on-severity` → exit `2` |
| `memory nudge-report` | 报表 | **`schema_version`=`1.2`**；含 `health_score` 等 |

---

## `recall` / `recall-index` JSON 摘要

| 命令场景 | `schema_version` 或备注 |
|----------|---------------------------|
| `recall --json`（扫描） | **`1.3`**；含 `no_hit_reason`、`sort`、`ranking` 等 |
| `recall-index search` / `benchmark` | 负载内含 `recall_index_schema_version`（索引文件 **`1.1`**） |
| `recall-index doctor --json` | **`recall_index_doctor_v1`**；不健康 exit `2` |
| `recall-index` 性能脚本输出 | `recall_benchmark_v1`（见 `scripts/perf_recall_bench.py`） |

---

## 破坏性变更

升级对应 **`schema_version`**（或索引 `recall_index_schema_version`）时，请同步更新 **本节**、[`SCHEDULE_AUDIT_JSONL.zh-CN.md`](SCHEDULE_AUDIT_JSONL.zh-CN.md)、[`SCHEDULE_STATS_JSON.zh-CN.md`](SCHEDULE_STATS_JSON.zh-CN.md) 及 `CHANGELOG`。
