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
- **`schema_version`**：`plugins_surface_v1`；另含 **`plugin_version`**（当前 **`0.1.0`**，与 `PLUGIN_VERSION` 常量一致）、`project_root`、`health_score`（0~100）、`compatibility`、`components`（`skills` / `commands` / `agents` / `hooks` / `rules` / `mcp-configs` 各含 `exists`、`path`、`files_count`）。

**Exit**：默认 `0`；配置缺失等 `2`。`--fail-on-min-health SCORE`：`health_score < SCORE` → `2`。

---

## `commands` / `agents` / `--json`

- **`commands --json`**：对象 **`schema_version`=`commands_list_v1`**，**`commands`**：字符串数组（模板 **stem**，与文本模式 `/{name}` 对应的无斜杠名；实现 `list_command_names`）。
- **`agents --json`**：对象 **`schema_version`=`agents_list_v1`**，**`agents`**：字符串数组（`list_agent_names`）。

**Exit**：配置可读 `0`；`Settings.from_env` 失败（如缺配置）→ `2`。

---

## `mcp-check` / `mcp-check --json`

- **实现**：`__main__.py` `mcp-check` 分支
- **`schema_version`**：`mcp_check_result_v1`（`--json` 单行对象）
- **主要字段（摘要）**：`ok`、`provider`、`model`、`mcp_enabled`、`mcp_base_url`、`force`、`tool`、`list_only`、`preset`（对象或 `null`）、`elapsed_ms`、`result`（文本摘要）、`tool_names`、`preset_matches`、`preset_missing_keywords`、`fallback_hint`（如 `kind: preset_missing_tools`）、`template`、`probe_result` 等

**Exit**：`ok == true` → `0`；否则 → `2`。

---

## `sessions` / `sessions --json`

- **根形态**：**JSON 数组**（无顶层 `schema_version`）。元素至少含 `name`、`path`、`mtime`、`size`；成功解析会话时通过 `_session_file_json_extra` 合并 `events_count`、`run_schema_version`、`task_id`、`total_tokens`、`error_count`。
- **`--details`**：解析失败项含 `error: parse_failed`；成功项可含 `messages_count`、`tool_calls_count`、`used_tools`、`last_tool`、`answer_preview` 等。
- **无 `--details`**：尽力解析；失败时元素可含 **`parse_error: true`**。

**Exit**：默认 `0`。

---

## `stats` / `stats --json`

- **实现**：`__main__.py` `stats` 分支
- **`stats_schema_version`**：`1.0`（与 `plan_schema_version` 类似，为顶层版本键）
- **主要字段**：`sessions_count`、`elapsed_ms_total` / `elapsed_ms_avg`、`tool_calls_total` / `tool_calls_avg`、`tool_errors_total` / `tool_errors_avg`、`models_distribution`、`run_events_total`、`sessions_with_events`、`parse_skipped`、`session_summaries[]`（`name`、`events_count`、`task_id`、`tool_calls_count` 等）

**Exit**：默认 `0`。

---

## `run` / `continue` / `command` / `agent` / `fix-build`（`--json`）

- **实现**：`__main__.py` 共享 `invoke` 路径
- **版本键**：**`run_schema_version`**：`1.0`（与 `--save-session` 落盘 JSON 对齐；**不设**第二个顶层 `schema_version`，避免与 `run_schema_version` 重复）
- **成功结束**：`answer`、`iteration`、`finished`、`config`、`workspace`、`provider`、`model`、`mcp_enabled`、`elapsed_ms`、`prompt_tokens` / `completion_tokens` / `total_tokens`、`tool_calls_count`、`used_tools`、`last_tool`、`error_count`、`task`、`events`（`run.started` / `run.finished`）、`post_gate`（仅 **`fix-build`** 且未 `--no-gate` 时有对象；内含 **`schema_version`：`quality_gate_result_v1`**）
- **Ctrl+C 中断**：仍打印一行 JSON；`finished: false`、`error: interrupted`、`message`；**exit `130`**（与 shell 约定一致）

**Exit**：会话读取/校验失败、模板缺失等 → `2`；正常完成 → `0`（未 `finished` 时 `task.status` 可为 `failed`，exit 仍为 `0`，由负载字段判断）。

---

## `export`（单行 JSON）

- **实现**：`cai_agent.exporter.export_target` → `print(json.dumps(result))`
- **`schema_version`**：`export_cli_v1`；另含 `target`、`output_dir`、`manifest`（`cursor` / `codex` 有路径；**`opencode`** 分支当前无 `manifest` 键）、`copied`、`mode`（`structured` / `manifest` / `copy`）。磁盘上的 `cai-export-manifest.json` 使用 **`manifest_version`** 与内嵌 **`schema`: `export-v2`**（与 CLI 负载的 `schema_version` 不同层）。

**Exit**：配置不可读 → `2`；不支持 `--target` → 异常前由 argparse 约束；成功 → `0`。

---

## `init`

- **输出**：文本（写入 `cai-agent.toml` 路径提示）；**无** `--json`。

**Exit**：目标已存在且无 `--force` → **`1`**；模板读取失败等 → **`1`**。

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

## `models` 子命令 JSON 摘要

| 子命令 | `--json` 形态 | `schema_version` / 说明 |
|--------|----------------|-------------------------|
| `models list` | 对象：`active`、`subagent`、`planner`、`profiles[]` | **`models_list_v1`**（`profile_to_public_dict` 行） |
| `models fetch` | 对象：`schema_version`=`models_fetch_v1`、`models[]`（排序去重后的模型 id 字符串） | **`models_fetch_v1`** |
| `models ping` | 对象：`schema_version`=`models_ping_v1`、`results[]`（`profile_id`、`status`、`http_status?`、`message?` 等） | **`models_ping_v1`** |

**Exit**：`list` / `fetch`：配置错误 → `2`。`ping`：任一 profile 不存在 → `2`；**默认** 存在非 `OK` 的 ping → **`1`**；成功全 `OK` → **`0`**。`ping --fail-on-any-error`：存在非 `OK` → **`2`**（便于与 CI 的 exit 2 约定对齐）。

---

## `hooks` 子命令 JSON 摘要

| 子命令 | `--json` | `schema_version` |
|--------|----------|------------------|
| `hooks list` | `describe_hooks_catalog` 输出 | **`hooks_catalog_v1`**；错误时仍输出 JSON 且含 `error`：`hooks_json_not_found` / `invalid_hooks_document` |
| `hooks run-event` | 见实现 | **`hooks_run_event_result_v1`** |

**Exit**：`list`：`hooks.json` 缺失或文档无效时，**文本模式与 `--json` 均为 `2`**。`run-event`：见各分支（缺文件等 `2`）。

---

## `quality-gate` / `security-scan`（`--json`）

- **`quality-gate --json`**：`cai_agent.quality_gate.run_quality_gate` 返回对象含 **`schema_version`：`quality_gate_result_v1`**，以及 `task`、`workspace`、`config`（各阶段开关）、`checks[]`（`name` / `exit_code` / `elapsed_ms` / `skipped` 等）、`ok`、`failed_count`。
- **`security-scan --json`**：`run_security_scan` 返回 **`schema_version`：`security_scan_result_v1`**，以及 `workspace`、`ok`、`scanned_files`、`findings_count`、`findings[]`、`rule_flags` 等。

**Exit**：`quality-gate`：`ok == false` → `2`；`security-scan`：`ok == false`（存在 **high** 级命中）→ `2`；配置不可读 → `2`。

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

- **`commands --json` / `agents --json`**：自 **`commands_list_v1` / `agents_list_v1`** 起，根对象为 `{ "schema_version", "commands"|"agents" }`；**不再**直接输出裸字符串数组（旧脚本请改为读 **`commands`** / **`agents`** 字段）。
- **`models fetch --json`**：自 **`models_fetch_v1`** 起，根对象固定为 `{ "schema_version", "models" }`；**不再**直接输出裸字符串数组（旧脚本请改为读 `models` 字段）。

升级对应 **`schema_version`**（或索引 `recall_index_schema_version`）时，请同步更新 **本节**、[`SCHEDULE_AUDIT_JSONL.zh-CN.md`](SCHEDULE_AUDIT_JSONL.zh-CN.md)、[`SCHEDULE_STATS_JSON.zh-CN.md`](SCHEDULE_STATS_JSON.zh-CN.md) 及 `CHANGELOG`。
