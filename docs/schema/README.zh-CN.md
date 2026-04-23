# JSON 输出契约索引（S1-02）

本文件汇总 **`cai-agent` 各命令 `--json` 或专用 JSON 输出** 的 `schema_version`、主要字段与 **exit 码约定**（与 [S1-03](../HERMES_PARITY_BACKLOG.zh-CN.md) 一致：成功 `0`，逻辑/阈值失败 `2`，用法错误 `2`）。

**主入口兜底**：`main()` 若未能分发到已知子命令（仅应出现于内部实现不同步），**exit `2`** 并向 stderr 打印一行诊断（此前兜底为 **`1`** 且无提示）。

**仅下列长文仍拆成独立文件**（历史路径，CI/外链可能引用）：[SCHEDULE_AUDIT_JSONL.zh-CN.md](SCHEDULE_AUDIT_JSONL.zh-CN.md)、[SCHEDULE_STATS_JSON.zh-CN.md](SCHEDULE_STATS_JSON.zh-CN.md)、[METRICS_JSON.zh-CN.md](METRICS_JSON.zh-CN.md)（**S7-01** 指标 JSONL）。其余命令契约 **以本节为准**；新增契约优先写入本节，确需独立长文时再增文件。

**从 0.5.x 升级 0.6.x**：破坏性 `--json` 形态与 exit 码摘要见 **[`docs/MIGRATION_GUIDE.md`](../MIGRATION_GUIDE.md)**（Hermes **S8-04**）。

### S1-02 / S1-03 收口口径（本仓）

- **S1-02**：以 **本节** 为各命令 JSON 契约的 **唯一索引**（外加 `SCHEDULE_*` 两长文）；破坏性变更须升 `schema_version` 并同步 `CHANGELOG`；**`scripts/smoke_new_features.py`** 提供跨命令 JSON 抽样回归（**含** **`security-scan --json` → `security_scan_result_v1`**、**`workflow --json` → `workflow_run_v1`** 与根级 **`task_id`**）。
- **S1-03**：**`0`** 成功；**`2`** 配置/参数/阈值/逻辑失败及未知子命令、**`argparse` 用法错误**；**`run`/`continue`/… 族** 用户 **Ctrl+C** 中断 → **exit `130`**（与 shell 约定一致）；**不将 `1` 作为稳定 CLI 契约**。

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
| `aggregates` | object | `total_tokens`、`failed_count`、`failure_rate`、`run_events_total`、`tool_errors_total`、`tool_errors_top` 等 |
| `task` / `events` | object / array | 内部 observe 任务与 `observe.summarized` 事件 |

**Exit**：默认 `0`。`--fail-on-max-failure-rate RATE`（0~1）：当 `aggregates.failure_rate >= RATE` 时 `2`（与 `insights --fail-on-max-failure-rate` 语义一致）。

**指标（S7-01）**：若设置 **`CAI_METRICS_JSONL`**，成功执行后追加 **`observe.summary`** 等事件；**`memory.*`**（含 **`health`/`state`/`nudge`/`user_model`/`extract`/`list`/…**）、**`recall`/`recall_index.*`/`schedule.*`/`gateway.*`**（含 **`gateway telegram serve-webhook`** 正常结束一轮）、**`hooks`/`sessions`/`stats`/`insights`/`plugins`/`skills`·`hub`（**`manifest`/`evolution_suggest`**）/`commands`/`agents`/`doctor`/`plan`/`cost budget`/`export`/`observe-report`/`ops dashboard`/`board`**、**`init`/`models`/`workflow`/`release-ga`/`ui`**、**`mcp-check`**、**`quality_gate.run`/`security_scan.run`** 与 **`run`/`continue`/`command`/`agent`/`fix-build` 的 `*.invoke`** 等同见 [METRICS_JSON.zh-CN.md](METRICS_JSON.zh-CN.md) **触发路径**。

---

## `observe report`（`--format json` / `--format markdown`）

- **实现**：`cai_agent.observe_ops_report.build_observe_ops_report_v1`（内部调用 `build_observe_payload`，按 **`mtime`** 与 **`--days`** 时间窗过滤）
- **顶层 `schema_version`**：`1.0`（运营报告信封，与内嵌 **`observe.schema_version`** `1.1` 区分）

| 顶层字段（摘要） | 类型 | 说明 |
|------------------|------|------|
| `report_kind` | string | `observe_ops_report_v1` |
| `window_days` / `generated_at` | int / string | |
| `session_count` / `success_rate` / `failure_rate` | int / float | |
| `token_total` / `token_avg` | int / float | |
| `tool_error_rate` | float | **`tool_errors_total` / `session_count`**（无会话时为 `0`） |
| `top_failing_tools` | array | `{ "tool", "errors" }` |
| `observe` | object | 完整 **`build_observe_payload`** 结果 |

**参数**：继承父级 **`--pattern` / `--limit`**；子命令专有 **`--days`**、**`--format`**、**`-o`/`--output`**。

**Exit**：默认 `0`。**指标**：成功执行后追加 **`observe.report`**（同上 **`CAI_METRICS_JSONL`**）。

**冒烟**：`scripts/smoke_new_features.py` 在空临时工作区执行 **`observe report --format json --days 1`**，断言 **`schema_version`=`1.0`** 与 **`report_kind`=`observe_ops_report_v1`**。

---

## `observe export`（S7-04）

- **实现**：`cai_agent.observe_export.build_observe_export_v1`
- **`schema_version`**：`observe_export_v1`；**`report_kind`**：`observe_export_daily_v1`
- **子命令**：**`cai-agent observe export`**（继承父级 **`--pattern` / `--limit`**）

| 参数 | 说明 |
|------|------|
| **`--days`** | 回溯天数（默认 **30**；dest **`observe_export_days`**，与 **`observe report --days`** 独立） |
| **`--format`** | **`csv`** / **`json`** / **`markdown`**（dest **`observe_export_format`**） |
| **`-o`/`--output`** | 输出文件（dest **`observe_export_output`**）；省略则 **stdout** |

**`rows[]` 字段（摘要）**：**`date`**、**`session_count`**、**`success_rate`** / **`failure_rate`**、**`token_total`** / **`token_avg`**、**`schedule_tasks_ok`** / **`schedule_tasks_failed`** / **`schedule_success_rate`**、**`memory_health_score`** / **`memory_grade`**（按日与 **`aggregate_schedule_audit_by_calendar_day_utc`**、**`build_memory_health_payload`** 对齐）。

**Exit**：默认 **`0`**。**指标**：成功执行后 **`observe.export`**（**`CAI_METRICS_JSONL`**）。

**冒烟**：`scripts/smoke_new_features.py` 在空临时工作区 **`observe export --format json --days 2 -o …`**，断言 **`observe_export_v1`** 且 **`rows`** 长度为 **`days`**。

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

**冒烟**：`scripts/smoke_new_features.py` 在**空临时工作区**（与 **`sessions --json`** 同目录）执行 **`observe-report --json`**，断言 **`observe_report_v1`** 且 **`state`=`pass`**（无会话时指标为 0）。

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

**冒烟**：`scripts/smoke_new_features.py` 在**空临时工作区**执行 **`insights --json`**，断言 **`schema_version`=`1.1`** 且 **`sessions_in_window`=`0`**（无窗口内会话时的快速路径与完整路径输出一致）。

---

## `insights --json --cross-domain`（S7-03）

- **实现**：`cai_agent.insights_cross_domain.build_insights_cross_domain_v1`（嵌套 **`insights`** 为 `_build_insights_payload` 的 **`1.1`** 对象）
- **`schema_version`**：`insights_cross_domain_v1`
- **必选**：与 **`--json`** 同用；否则 **exit `2`**（stderr 一行提示）。

| 顶层字段（摘要） | 类型 | 说明 |
|------------------|------|------|
| `window` | object | `days`、`since`、`until_exclusive`（UTC）、`pattern`、`limit`、`memory_session_pattern` |
| `insights` | object | 与 **`insights --json`** 根对象同源 **`1.1`** |
| `recall_hit_rate_trend` | array | 按 **UTC 日历日** 升序；无 **`.cai-recall-index.json`** 时 **`hit_rate`=`null`**，`no_index_reason`=`index_missing`；有索引时为子串探测 **`the`** 的 **`probe_hits`/`indexed_rows`** 比值 |
| `memory_health_trend` | array | 每日 **`build_memory_health_payload`**（会话 **mtime** 落入该日）的 **`health_score`** / **`grade`** / **`recent_sessions`** |
| `schedule_success_trend` | array | 来自 **`aggregate_schedule_audit_by_calendar_day_utc`**（`task.completed` vs `task.failed`/`task.retrying`） |

**Exit**：与 **`insights --json`** 相同（含 **`--fail-on-max-failure-rate`**，对嵌套 **`insights.failure_rate`** 判定）。

**冒烟**：`scripts/smoke_new_features.py` 在空临时工作区执行 **`insights --json --cross-domain --days 3`**，断言 **`insights_cross_domain_v1`** 与三条 trend 数组长度等于 **`days`**。

---

## `board` / `board --json`

- **实现**：`cai_agent.board_state.build_board_payload` 等
- **`schema_version`**：`board_v1`；`observe_schema_version` 与内嵌 `observe` 同源 `build_observe_payload`

内嵌 `observe` 与 `observe --json` 根对象同源；筛选后 `sessions` / `sessions_count` 会更新，`aggregates` 可能仍为全量扫描值（实现细节以代码为准）。

**Exit**：默认 `0`。`--fail-on-failed-sessions`：当前 **`observe.sessions` 列表**中存在 `error_count > 0` → `2`。

**冒烟**：`scripts/smoke_new_features.py` 在空临时工作区执行 **`board --json`**，断言 **`board_v1`**、**`observe_schema_version`=`1.1`** 与内嵌 **`observe.schema_version`=`1.1`**。

---

## `plugins` / `plugins --json`

- **实现**：`cai_agent.plugin_registry.list_plugin_surface`
- **`schema_version`**：`plugins_surface_v1`；另含 **`plugin_version`**（当前 **`0.1.0`**，与 `PLUGIN_VERSION` 常量一致）、`project_root`、`health_score`（0~100）、`compatibility`、`components`（`skills` / `commands` / `agents` / `hooks` / `rules` / `mcp-configs` 各含 `exists`、`path`、`files_count`）。

**Exit**：默认 `0`；配置缺失等 `2`。`--fail-on-min-health SCORE`：`health_score < SCORE` → `2`。

**冒烟**：`scripts/smoke_new_features.py` 在仓库根以 **`--config <repo>/cai-agent.toml`** 执行 **`plugins --json`**，断言 **`plugins_surface_v1`** 与 **`components`**。

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

**冒烟**：`scripts/smoke_new_features.py` 在仓库根以 **`--config <repo>/cai-agent.toml`** 执行 **`mcp-check --json --list-only`**，接受 exit **`0`** 或 **`2`**，并断言 **`mcp_check_result_v1`** 与 **`mcp_enabled`** 字段存在。

---

## `sessions` / `sessions --json`

- **根形态**：对象 **`schema_version`=`sessions_list_v1`**，含 **`pattern`**、**`limit`**、**`details`**（bool）、**`sessions`**（数组）。**`sessions`** 元素至少含 `name`、`path`、`mtime`、`size`；成功解析时通过 `_session_file_json_extra` 合并 `events_count`、`run_schema_version`、`task_id`、`total_tokens`、`error_count`。
- **`--details`**：`sessions` 内解析失败项含 `error: parse_failed`；成功项可含 `messages_count`、`tool_calls_count`、`used_tools`、`last_tool`、`answer_preview` 等。
- **无 `--details`**：尽力解析；失败时元素可含 **`parse_error: true`**。

**Exit**：默认 `0`。

**冒烟**：`scripts/smoke_new_features.py` 在**空临时工作区**执行 **`sessions --json`**，断言 **`sessions_list_v1`** 与 **`sessions`** 数组类型。

---

## `stats` / `stats --json`

- **实现**：`__main__.py` `stats` 分支
- **`stats_schema_version`**：`1.0`（与 `plan_schema_version` 类似，为顶层版本键）
- **主要字段**：`sessions_count`、`elapsed_ms_total` / `elapsed_ms_avg`、`tool_calls_total` / `tool_calls_avg`、`tool_errors_total` / `tool_errors_avg`、`models_distribution`、`run_events_total`、`sessions_with_events`、`parse_skipped`、`session_summaries[]`（`name`、`events_count`、`task_id`、`tool_calls_count` 等）

**Exit**：默认 `0`。

---

## `cost` / `cost budget`（单行 JSON，无 `--json` 开关）

- **实现**：`__main__.py` `cost budget` 分支；聚合 `aggregate_sessions`（默认 `limit=200`）的 **`total_tokens`** 与配置 **`max_tokens`**（CLI **`--max-tokens`** 或 **`[cost] budget_max_tokens`**）。
- **`schema_version`**：`cost_budget_v1`
- **字段**：`state`（`pass` / `warn` / `fail`：`total_tokens > max_tokens` 为 `fail`；`> 0.8 * max_tokens` 为 `warn`）、`total_tokens`、`max_tokens`

**Exit**：`state == fail` → **`2`**；`pass` / `warn` → **`0`**。

---

## `release-ga` / `release-ga --json`

- **实现**：`_run_release_ga_gate`
- **`schema_version`**：`release_ga_gate_v1`；含 `generated_at`、`workspace`、`ok`、`state`（`pass`/`fail`）、`checks_passed` / `checks_failed`、`failed_checks`、`failure_rate`、`total_tokens`、`checks[]`、`aggregates` 等。

**Exit**：`ok == false`（任一子检查失败）→ **`2`**；否则 **`0`**。

---

## `run` / `continue` / `command` / `agent` / `fix-build`（`--json`）

- **实现**：`__main__.py` 共享 `invoke` 路径
- **版本键**：**`run_schema_version`**：`1.0`（与 `--save-session` 落盘 JSON 对齐；**不设**第二个顶层 `schema_version`，避免与 `run_schema_version` 重复）
- **根级 `task_id`（开发项 21 MVP）**：与 **`task.task_id`** 同源字符串，便于与 `sessions`/`observe` 行内 `task_id` 及调度审计 **`task_id`** 对齐消费。
- **成功结束**：`answer`、`iteration`、`finished`、`config`、`workspace`、`provider`、`model`、`mcp_enabled`、`elapsed_ms`、`prompt_tokens` / `completion_tokens` / `total_tokens`、`tool_calls_count`、`used_tools`、`last_tool`、`error_count`、`task`、`events`（`run.started` / `run.finished`）、`post_gate`（仅 **`fix-build`** 且未 `--no-gate` 时有对象；内含 **`schema_version`：`quality_gate_result_v1`**）
- **Ctrl+C 中断**：仍打印一行 JSON；含 **`task_id`**；`finished: false`、`error: interrupted`、`message`；**exit `130`**（与 shell 约定一致）

**Exit**：会话读取/校验失败、模板缺失等 → `2`；正常完成 → `0`（未 `finished` 时 `task.status` 可为 `failed`，exit 仍为 `0`，由负载字段判断）。

---

## `export`（单行 JSON）

- **实现**：`cai_agent.exporter.export_target` → `print(json.dumps(result))`
- **`schema_version`**：`export_cli_v1`；另含 `target`、`output_dir`、`manifest`（`cursor` / `codex` 有路径；**`opencode`** 分支当前无 `manifest` 键）、`copied`、`mode`（`structured` / `manifest` / `copy`）。磁盘上的 `cai-export-manifest.json` 使用 **`manifest_version`** 与内嵌 **`schema`: `export-v2`**（与 CLI 负载的 `schema_version` 不同层）。

**Exit**：配置不可读 → `2`；不支持 `--target` → 异常前由 argparse 约束；成功 → `0`。

---

## `gateway telegram`（`--json`）

- **实现**：`__main__.py` `gateway` → `telegram` 子命令；会话映射默认文件 **`.cai/gateway/telegram-session-map.json`**（可用 **`--map-file`** 覆盖，相对路径以工作区根解析）。磁盘 JSON 除 **`bindings`** 外可含根级 **`allowed_chat_ids`**（字符串数组）；**非空**时仅允许这些 **`chat_id`** 走 **`resolve-update`** / **`serve-webhook`** 成功路径（否则 **`error`=`not_allowed`**，**S6-03**）。
- **白名单 CLI**：**`gateway telegram allow add --chat-id …`** / **`allow list`** / **`allow rm --chat-id …`**（`action` 分别为 **`allow_add`** / **`allow_list`** / **`allow_rm`**）。
- **`schema_version`**：stdout JSON 多为 **`gateway_telegram_map_v1`**；顶层含 **`action`**（`bind` / `get` / `list` / `unbind` / **`allow_*`** / `resolve-update` / `serve-webhook`）及 **`map_file`** 等。
- **`gateway telegram continue-hint`**（**S6-04**，`--json`）：独立 **`gateway_telegram_continue_hint_v1`**（**`action`=`continue_hint`**）；**`ok`**、**`hints[]`**（**`chat_id`** / **`user_id`** / **`session_path_resolved`** / **`session_file_exists`** / **`continue_cli`**）、**`workspace_root`**、**`note`**。未找到绑定时 **`ok:false`**、**`error`=`binding_not_found`**（exit **`2`**）。**`--chat-id`** 与 **`--user-id`** 须成对出现，或两者皆省略以列出全部绑定。
- **字段摘要（随子命令变化）**：
  - **bind**：`ok`、`binding`（`chat_id` / `user_id` / `session_file`）、`bindings_count`
  - **get**：`ok`（是否命中）、`binding`（未命中时为 `null`）
  - **list**：`ok`、`bindings`（数组）、`bindings_count`、**`allowed_chat_ids`**（数组）、**`allowlist_enabled`**（bool）
  - **unbind**：`ok`、`removed`、`binding`、`bindings_count`
  - **resolve-update**：失败时 `ok:false` 与 **`error`**（`invalid_args` / `read_update_failed` / `invalid_update` / **`not_allowed`**）及 `message`；成功时 `created`、`chat_id`、`user_id`、`binding`
  - **serve-webhook**：服务结束后的单行摘要含 `ok`、`host`、`port`、`path`、`events_handled`、`log_file`、`create_missing` 等（与运行态一致）。**`--execute-on-update`**（**S6-02**）：非 slash 文本走 **`_execute_gateway_telegram_goal`**，对绑定 **`session_file`** 与 CLI **`run`/`continue`** 同源（读会话、追加用户消息、**`invoke`**、写回 **`run_schema_version`=`1.0`** 负载）；**`reply-on-execution`** 下 **`{answer}`** 为完整文本（发送仍分块）。JSONL **`execution`** 可含 **`persisted_session`**。slash **`/stop`**：默认仅文案引导 **`gateway stop`**；若 **`CAI_TELEGRAM_STOP_WEBHOOK=1`** 且发令 **`user_id`** ∈ **`CAI_TELEGRAM_ADMIN_USER_IDS`**（逗号分隔），则调用 **`gateway_lifecycle.stop_webhook_subprocess`**。

**Exit**：缺参、读 update 失败、`resolve-update` 无映射且未创建等 → **`2`**；**`get`/`unbind`/`resolve-update`** 在「未找到绑定 / 无移除 / 无映射且未 `--create-missing`」等业务失败时 → **`2`**；**`serve-webhook`** 正常结束 → **`0`**；未知 `telegram` 子命令 → **`2`**。
- **工作区根**：**`gateway telegram -w DIR …`**（或各子命令等价的 **`--workspace`**）将 **DIR** 作为 Gateway 上下文根（默认映射路径等）；与 **`gateway setup|start|status|stop`** 上的 **`-w`** 语义一致。

---

## `gateway setup` / `start` / `status` / `stop`（Hermes **S6-01**）

- **实现**：`cai_agent.gateway_lifecycle`；CLI 在 **`__main__.py`** 的 **`gateway`** 分支分发。
- **`gateway setup`**：写入 **`.cai/gateway/telegram-config.json`**（**`schema_version`=`gateway_telegram_config_v1`**），可选 **`serve_webhook`** 字段（与 **`gateway telegram serve-webhook`** 对齐的开关/模板）；**`--allow-chat-id`** 可重复，合并进 **`telegram-session-map.json`** 的 **`allowed_chat_ids`**。stdout **`--json`** 含 **`ok`**、**`config_path`**、**`workspace`** 等。
- **`gateway start`**：按配置文件组装 **`python -m cai_agent gateway telegram serve-webhook …`** 后台进程，写 **`.cai/gateway/telegram-webhook.pid`**（**`gateway_telegram_pid_v1`**）。stdout **`gateway_lifecycle_start_v1`**（**`ok`** / **`pid`** / **`pid_file`** / 日志路径等）。
- **`gateway status`**：stdout **`gateway_lifecycle_status_v1`**（**`config_exists`**、**`webhook_pid`**、**`webhook_running`**、**`allowed_chat_ids`**、**`allowlist_enabled`** 等）。
- **`gateway stop`**：读 PID 文件并结束进程；stdout **`gateway_lifecycle_stop_v1`**。**无 PID 文件**时 **`ok:false`**、**`error`=`no_pid_file`**（CLI **exit `0`**，幂等）；**`stop_failed`** 等 → **exit `2`**。**`start`** 在配置缺失时 **exit `2`**。

---

## `gateway platforms list`（`--json`）

- **实现**：`cai_agent.gateway_platforms.build_gateway_platforms_payload`；`cai-agent gateway platforms list --json`。
- **`schema_version`**：**`gateway_platforms_v1`**；含 **`workspace`**、**`telegram_map_exists`**、**`telegram_session_map_path`**、**`telegram_webhook_pid_path`** / **`telegram_webhook_pid_exists`**（生命周期 PID 文件是否落盘）、**`telegram_bot_token_env_present`**（是否检测到 **`CAI_TELEGRAM_BOT_TOKEN`** 或 **`TELEGRAM_BOT_TOKEN`** 已配置，**不输出**具体值）、**`platforms[]`**（各 **`id`** / **`implementation`**（`full`|`stub`|`planned`）/ **`cli_prefix`** / **`env`** / **`notes`**；stub 平台另含 **`env_present`**：各文档化环境变量是否**已非空配置**）。

**Exit**：成功 → **`0`**。

---

## `ops dashboard`（`--json`）

- **实现**：`cai_agent.ops_dashboard.build_ops_dashboard_payload`；聚合 **`board_v1`**（含 **`observe`** 嵌套）、**`schedule_stats_v1`**（`compute_schedule_stats_from_audit`）、**`aggregate_sessions`**（成本 rollup）。
- **`schema_version`**：**`ops_dashboard_v1`**；顶层 **`summary`**（`sessions_count` / `failure_rate` / `schedule_tasks_in_stats` / `cost_total_tokens` 等）与 **`board`** / **`schedule_stats`** / **`cost_aggregate`**。

**Exit**：成功 → **`0`**。

---

## `skills hub manifest`（`--json`）

- **实现**：`cai_agent.skills.build_skills_hub_manifest`；扫描工作区 **`skills/`** 下 **`.md` / `.markdown` / `.txt`**（与 `load_skills` 一致）。
- **`schema_version`**：**`skills_hub_manifest_v1`**；含 **`count`**、**`entries[]`**（`name` / `path` / `size_bytes` / `mtime_iso`）、**`skills_dir_exists`**。

**Exit**：成功 → **`0`**。

---

## `skills hub suggest`（`GOAL...` / `--json` / `--write`）

- **实现**：`cai_agent.skills.build_skill_evolution_suggest`；`cai-agent skills hub suggest <任务描述…> [--write] [--json]`（**`GOAL` 建议写在 `--json` 之前**）。
- **`schema_version`**：**`skills_evolution_suggest_v1`**；含 **`suggested_path`**（默认位于 **`skills/_evolution_<slug>.md`**）、**`preview`**、**`write_requested`** / **`written`** / **`file_existed_before`**（**`--write`** 仅在目标文件尚不存在时落盘，避免覆盖已有草稿）。

**Exit**：成功 → **`0`**；**`goal` 为空** → **`2`**。

---

## `init`

- **输出**：默认文本（写入 `cai-agent.toml` 路径提示等）。**`init --json`**：stdout **仅一行** **`init_cli_v1`**：`ok`（bool）、成功时 **`config_path`** / **`preset`**（`default`|`starter`）/ **`global`**；失败时 **`error`**（`config_exists` / `template_read_failed` / `mkdir_failed`）及 **`message`** 等。

**Exit**：自 **S1-03** 起，失败路径（目标已存在且无 `--force`、模板读取失败、创建目录失败）均为 **`2`**（此前为 **`1`**）；成功 → **`0`**。

---

## `workflow` / `workflow <file> --json`

- **实现**：`cai_agent.workflow.run_workflow`
- **`schema_version`**：`workflow_run_v1`；根级 **`task_id`** 与 **`task.task_id`** 同源（与 `run --json` 对齐）；另有 **`subagent_io_schema_version`**：`1.0` 与 `subagent_io`（`inputs` / `merge` / `outputs`）、`steps`、`summary`、`events`、`task`。
- **并行**：步骤可设 **`parallel_group`**（同名字符串同批并发）；`summary` 含 **`parallel_groups_count`** / **`parallel_steps_count`** 等；**S5-01 / S5-02** 能力见 `tests/test_cli_workflow.py`。
- **S5-03**：workflow JSON 根级可选 **`on_error`**：`fail_fast`（默认）或 `continue_on_error`（亦接受 `continue-on-error`）。`fail_fast` 下后续未跑步骤以 **`skipped: true`** 占位并产生 **`workflow.step.skipped`** 事件；`continue_on_error` 跑满全步骤，**merge / conflict** 仅统计 **`finished` 且无 `error_count`** 的步骤。`summary` 增补 **`on_error`**、**`steps_skipped`**、**`merge_steps_considered`**；`workflow.finished` 事件含 **`on_error`** / **`steps_skipped`**。
- **S5-04**：根级可选 **`budget_max_tokens`**（非负整数）。已执行步骤的 **`total_tokens`** 累计在下一批开始前 **≥** 限额时，本批及之后未启动步骤 **`skipped`**（**`budget_exceeded`**）；已提交的并行批仍跑完。`summary` 与 **`workflow.finished`** 含 **`budget_limit`** / **`budget_used`** / **`budget_exceeded`**。

**Exit**：文件缺失/解析失败 → `2`；默认成功 `0`。`--fail-on-step-errors`：`task.status == failed` 或 `summary.tool_errors_total > 0` 或任一步 `error_count > 0` → `2`。

**冒烟**：`scripts/smoke_new_features.py` 在 **`CAI_MOCK=1`** 下对最小 **`workflow.json`** 执行 **`workflow … --json`**，断言 **`workflow_run_v1`**、根级 **`task_id`**，以及 **`summary.on_error`** / **`budget_limit`** / **`budget_used`** / **`budget_exceeded`**（无预算帽时为 **`null`** / 数值 / **`false`**）。

---

## `doctor` / `doctor --json`

- **实现**：`cai_agent.doctor.run_doctor` / `build_doctor_payload`
- **`schema_version`**：`doctor_v1`（仅 `--json` 时打印的负载；文本模式无 JSON）

顶层字段含：`cai_agent_version`、`workspace`、`provider`、`model`、`api_key_present`、`api_key_masked_line`、`mock`、`instruction_files`、`git_inside_work_tree`、`profile_ping_skipped`、`profile_pings`（`CAI_DOCTOR_PING=1` 时填充）等。

**Exit**：配置缺失 → `2`；默认 `0`。`--fail-on-missing-api-key`：非 `mock` 且 API Key 解析后为空 → `2`（可与 `--json` 同用于 CI）。

**冒烟**：`scripts/smoke_new_features.py` 在仓库根以 **`--config <repo>/cai-agent.toml`** 执行 **`doctor --json`**，断言 **`doctor_v1`** 与非空 **`workspace`**。

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

**Exit**：`list` / `fetch`：配置错误 → `2`。`ping`：任一 profile 不存在 → `2`；存在任一 status 非 `OK` → **`2`**；成功全 `OK` → **`0`**。**`--fail-on-any-error`** 为与默认相同的显式别名（兼容旧脚本）。

---

## `hooks` 子命令 JSON 摘要

| 子命令 | `--json` | `schema_version` |
|--------|----------|------------------|
| `hooks list` | `describe_hooks_catalog` 输出 | **`hooks_catalog_v1`**；错误时仍输出 JSON 且含 `error`：`hooks_json_not_found` / `invalid_hooks_document` |
| `hooks run-event` | 见实现 | **`hooks_run_event_result_v1`** |

**Exit**：`list`：`hooks.json` 缺失或文档无效时，**文本模式与 `--json` 均为 `2`**。`run-event`：见各分支（缺文件等 `2`）。

**冒烟**：`scripts/smoke_new_features.py` 在隔离临时目录写入最小 **`cai-agent.toml`** + **`hooks/hooks.json`**，执行 **`hooks list --json`**（**`hooks_catalog_v1`**、非空 **`hooks[]`**），并执行 **`hooks run-event observe_start --dry-run --json`**（**`hooks_run_event_result_v1`**、**`dry_run`: true**、**`results`** 为数组）。

---

## `quality-gate` / `security-scan`（`--json`）

- **`quality-gate --json`**：`cai_agent.quality_gate.run_quality_gate` 返回对象含 **`schema_version`：`quality_gate_result_v1`**，以及 `task`、`workspace`、`config`（各阶段开关）、`checks[]`（`name` / `exit_code` / `elapsed_ms` / `skipped` 等）、`ok`、`failed_count`。
- **`security-scan --json`**：`run_security_scan` 返回 **`schema_version`：`security_scan_result_v1`**，以及 `workspace`、`ok`、`scanned_files`、`findings_count`、`findings[]`、`rule_flags` 等。

**冒烟**：`scripts/smoke_new_features.py` 在仓库根以 **`--config <repo>/cai-agent.toml`、`-w` 指向空临时目录** 执行 **`security-scan --json`**，断言 **`security_scan_result_v1`** 与 **`scanned_files`** 为 int（**exit `0`/`2`** 均接受）。

**Exit**：`quality-gate`：`ok == false` → `2`；`security-scan`：`ok == false`（存在 **high** 级命中）→ `2`；配置不可读 → `2`。

---

## `memory` 子命令 JSON 摘要

| 子命令 | `--json` 形态 | `schema_version` / 说明 |
|--------|----------------|-------------------------|
| `memory extract` | 单行对象 **`memory_extract_v1`**：`written`、`entries_appended` | 始终 JSON stdout（无 `--json` 开关） |
| `memory list` | 对象 **`memory_list_v1`**：`entries`（条目数组）、`limit`、`sort` | 行内字段见 `memory.py` |
| `memory search` | 对象 **`memory_search_v1`**：`hits`、`query`、`limit`、`sort` | |
| `memory instincts` | 对象 **`memory_instincts_list_v1`**：`paths`（字符串数组）、`limit` | |
| `memory prune` | `memory_prune_result_v1` | 含 `removed_total`、`removed_by_reason` 等 |
| `memory state` | `memory_state_eval_v1` | |
| `memory export` / `import` | **`export --json`** stdout：**`memory_instincts_export_v1`**（**`output_file`**、**`snapshots_exported`**）；默认仅打印目标路径字符串。**`import`** stdout：**`memory_instincts_import_v1`**（**`imported`**） | 导入文件为 **JSON 数组**（元素含 `content`） |
| `memory export-entries` / `import-entries` | **`export-entries --json`** stdout：**`memory_entries_export_result_v1`**（**`output_file`**、**`entries_count`**、**`export_warnings`**）；磁盘文件仍为 **`memory_entries_bundle_v1`**。**`import-entries --dry-run`** stdout：**`memory_entries_import_dry_run_v1`**；成功导入 stdout：**`memory_entries_import_result_v1`**；失败时可选 **`memory_entries_import_errors_v1`** 报告文件 | 与 `memory.py` 校验一致 |
| `memory health` | 健康负载 | **`1.0`**（S2-01）；`--fail-on-grade` → exit `2` |
| `memory nudge` | nudge 负载 | `--fail-on-severity` → exit `2` |
| `memory nudge-report` | 报表 | **`schema_version`=`1.2`**；含 `health_score` 等 |
| `memory user-model` | 占位摘要 **`memory_user_model_v1`**：`sessions_total` / `sessions_recent_in_window` / 可选 **`.cai/user-model.json`** 合并为 **`user_declared`**；**`honcho_parity`**=`stub` | `--days` 控制会话 mtime 窗口（默认 14） |

**冒烟**：`scripts/smoke_new_features.py` 在空临时工作区执行 **`memory health --json`**（**`schema_version`=`1.0`**、**`grade`**、**`health_score`**）、**`memory state --json`**（**`memory_state_eval_v1`**、**`counts`** 对象）与 **`memory user-model --json`**（**`memory_user_model_v1`**）。

---

## `recall` / `recall-index` JSON 摘要

| 命令场景 | `schema_version` 或备注 |
|----------|---------------------------|
| `recall --json`（扫描） | **`1.3`**；含 `no_hit_reason`、`sort`、`ranking` 等 |
| `recall-index search` / `benchmark` | 负载内含 `recall_index_schema_version`（索引文件 **`1.1`**） |
| `recall-index doctor --json` | **`recall_index_doctor_v1`**；不健康 exit `2` |
| `recall-index info --json` | 轻量对象：**`ok`**（bool）、**`index_file`**；无索引时 **`ok`=`false`**、**`error`=`index_not_found`**，**exit `0`**（与 doctor 的「不健康即 2」区分） |
| `recall-index` 性能脚本输出 | `recall_benchmark_v1`（见 `scripts/perf_recall_bench.py`） |

**冒烟**：`scripts/smoke_new_features.py` 在空临时工作区执行 **`recall --json`**（**`1.3`**、`hits_total`=`0`、`no_hit_reason`）；空目录 **`recall-index doctor --json`**：**exit `2`**、**`recall_index_doctor_v1`**、**`issues`** 含 **`index_file_missing`**；同场景 **`recall-index info --json`**：**exit `0`**、**`ok`=`false`**、**`error`=`index_not_found`**。

---

## `schedule add` / `schedule list` / `schedule rm` / `schedule add-memory-nudge`（`--json`）

- **`schedule add --json`（成功）**：在任务负载上增加 **`schema_version`=`schedule_add_v1`**（与 `id`、`goal`、`every_minutes`、`depends_on` 等同一层；实现为 `{**job, "schema_version": …}`）。
- **`schedule add --json`（失败，如依赖成环）**：**`schema_version`=`schedule_add_invalid_v1`**，以及 `ok`=`false`、`error`=`schedule_add_invalid`、`message`。
- **`schedule list --json`**：对象 **`schema_version`=`schedule_list_v1`**，**`jobs`** 为任务行数组（含 `depends_on_status`、`dependency_blocked` 等展示字段）。
- **`schedule rm --json`**：**`schema_version`=`schedule_rm_v1`**，`removed`（bool）。
- **`schedule add-memory-nudge --json`**：**`schema_version`=`schedule_add_memory_nudge_v1`**，以及 `template`、`goal`、`job`。

---

## `schedule run-due` / `schedule run-due --json`

- **实现**：`__main__.py` `schedule run-due` 分支
- **`schema_version`**：`schedule_run_due_v1`
- **`mode`=`dry-run`**（无 `--execute`）：`due_jobs`、`executed`（空数组）
- **`mode`=`execute`**（`--execute`）：`due_jobs`、**`executed`**（每任务 `ok` / `status` / `answer_preview` / `attempts` / `retry_count` / `next_retry_at` 等，见实现）

**Exit**：见代码路径（dry-run 恒 `0`；execute 见任务结果与审计）。

---

## `schedule daemon` / `schedule daemon --json`

- **实现**：`__main__.py` `schedule daemon` 分支
- **`schema_version`**：`schedule_daemon_summary_v1`
- **锁冲突**（未能获取锁）：`ok`=`false`，`error`=`lock_conflict`，`message`；**exit `2`**
- **正常结束**：`mode`=`daemon`，`execute`、`interval_sec`、`max_cycles`、`max_concurrent`、`cycles`、`total_due`、`total_executed`、`total_skipped_due_to_concurrency`、`interrupted`、`results[]`（每轮 `cycle` / `due_count` / `executed` / `skipped_due_to_concurrency` 等）、`lock_file`、`jsonl_log`

**审计 JSONL**（`--jsonl-log` / `.cai-schedule-audit.jsonl`）仍为每行 **`schema_version`=`1.0`**，见 [SCHEDULE_AUDIT_JSONL.zh-CN.md](SCHEDULE_AUDIT_JSONL.zh-CN.md)。

---

## `schedule stats` / `schedule stats --json`

- **实现**：`cai_agent.schedule.compute_schedule_stats_from_audit`；CLI **`cai-agent schedule stats`**（`__main__.py`）。
- **`schema_version`**：**`schedule_stats_v1`**；支持 **`--days`**（1–366）、**`--audit-file`**、**`--fail-on-min-success-rate`**。
- **主要字段（摘要）**：`generated_at`、`days`、`audit_file`、`audit_lines_in_window`、**`tasks[]`**（每任务 **`task_id`**、**`goal_preview`**、**`run_count`** / **`success_count`** / **`fail_count`**、**`success_rate`**、**`avg_elapsed_ms`**、**`p95_elapsed_ms`** 等）。完整列说明见 [SCHEDULE_STATS_JSON.zh-CN.md](SCHEDULE_STATS_JSON.zh-CN.md)。

**Exit**：默认 **`0`**；**`--fail-on-min-success-rate RATE`**（0~1）：任一任务 **`run_count` ≥ 1** 且 **`success_rate` < `RATE`** → **`2`**（与独立文档「Exit 码」节一致）。

---

## 破坏性变更

- **`memory list --json` / `memory search --json` / `memory instincts --json`**：根对象分别为 **`memory_list_v1`**（读 **`entries`**）、**`memory_search_v1`**（读 **`hits`**）、**`memory_instincts_list_v1`**（读 **`paths`**）；**不再**直接输出裸数组。
- **`memory extract`**：stdout JSON 增加顶层 **`schema_version`：`memory_extract_v1`**（字段 **`written`** / **`entries_appended`** 不变）。
- **`memory import`**（instincts 数组文件）与 **`memory import-entries`** 成功路径：stdout 增加 **`schema_version`**（分别为 **`memory_instincts_import_v1`**、**`memory_entries_import_result_v1`**）；**`import-entries --dry-run`** stdout 增加 **`memory_entries_import_dry_run_v1`**（原有 `validated` / `errors` 等字段不变）。
- **`schedule list --json`**：自 **`schedule_list_v1`** 起，根对象为 **`{ "schema_version", "jobs" }`**；**不再**直接输出任务数组（旧脚本请读 **`jobs`**）。
- **`schedule run-due --json` / `schedule daemon --json`**：stdout 根对象新增 **`schema_version`**（分别为 **`schedule_run_due_v1`**、**`schedule_daemon_summary_v1`**）；其余字段保持，**若脚本以固定键集合校验需放行新键**。
- **`sessions --json`**：自 **`sessions_list_v1`** 起，根对象为 `{ "schema_version", "pattern", "limit", "details", "sessions" }`；**不再**直接输出裸数组（旧脚本请改为读 **`sessions`** 字段）。
- **`commands --json` / `agents --json`**：自 **`commands_list_v1` / `agents_list_v1`** 起，根对象为 `{ "schema_version", "commands"|"agents" }`；**不再**直接输出裸字符串数组（旧脚本请改为读 **`commands`** / **`agents`** 字段）。
- **`models fetch --json`**：自 **`models_fetch_v1`** 起，根对象固定为 `{ "schema_version", "models" }`；**不再**直接输出裸字符串数组（旧脚本请改为读 `models` 字段）。
- **`models ping`**：自 **S1-03 收口** 起，任一结果非 `OK` 时 **默认 exit `2`**（此前为 **`1`**）；依赖 exit `1` 表示「部分失败」的 CI 脚本需改为识别 **`2`** 或仅以 JSON `results[].status` 判定。
- **`init`**（含 **`init --json`**）：**`config_exists`** / **`template_read_failed`** / **`mkdir_failed`** 等失败路径 **exit `2`**（此前为 **`1`**）；JSON 负载仍为 **`init_cli_v1`**（`ok: false` + `error`）。
- **`main()` 子命令分发兜底**：未知 / 未接线子命令 **exit `2`** + stderr 一行（此前为 **`1`** 且无输出）。

升级对应 **`schema_version`**（或索引 `recall_index_schema_version`）时，请同步更新 **本节**、[`SCHEDULE_AUDIT_JSONL.zh-CN.md`](SCHEDULE_AUDIT_JSONL.zh-CN.md)、[`SCHEDULE_STATS_JSON.zh-CN.md`](SCHEDULE_STATS_JSON.zh-CN.md) 及 `CHANGELOG`。
