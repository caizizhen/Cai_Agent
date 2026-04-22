# 开发进度对照记录（持续更新）

> 目的：每次开发完成后，对照目标文档记录“已完成 / 进行中 / 未完成”，并给出总体进度。

**量化完成度（百分比）**：见 [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md) **§三之二 · 3.0**（当前：**§二 开发项 1–26 加权约 77%**；**Hermes 34 Story 约 50% / 加权约 54%**；与 T1 pytest 通过数同步）。**冒烟**：`scripts/smoke_new_features.py` 已覆盖 **`plugins --json`**（**`plugins_surface_v1`**）、**`hooks list --json`**（**`hooks_catalog_v1`**）、**`memory health --json`**（S2-01 **根 `schema_version`=`1.0`**）、**`schedule stats --json`**（**`schedule_stats_v1`**）、**`gateway telegram list --json`**（**`gateway_telegram_map_v1`**）、**`recall --json`**（**`schema_version` 1.3**、**`no_hit_reason`**）；入口为 **`python -m cai_agent`** 并设置 **`PYTHONPATH`**（与 **`run_regression.py`** 一致）。

## 对照基线

- `docs/ROADMAP_EXECUTION.zh-CN.md`
- `docs/NEXT_IMPLEMENTATION_BUNDLE.zh-CN.md`
- `docs/HERMES_PARITY_PROGRESS.zh-CN.md`（轻量进度视图，权威计划见 `HERMES_PARITY_SPRINT_PLAN.zh-CN.md`）
- `docs/PARITY_MATRIX.zh-CN.md`
- 用户提供的目标族：Architecture/Memory/Recall/Scheduler/Subagents/Gateway/Observability/Security/Release GA

## 本分支已完成（累计）

### A. 统一入口与体验

- TUI 快捷模板入口：`/fix-build`、`/security-scan`

### B. Scheduler / 任务模型

- `depends_on` 依赖链
- `retry_max_attempts` / `retry_backoff_sec` 重试策略
- **S4-01（跨轮次）**：`max_retries` / `retry_count` / `next_retry_at`；失败 → `retrying` + 指数退避（`60*2^(n-1)`s），用尽 → `failed_exhausted`；成功清零；`compute_due_tasks` 对 `retrying` 按 `next_retry_at` 到期；CLI `schedule add --max-retries`；`run-due`/`daemon` 执行 JSON 与审计行同步持久化 `status`/`retry_count`/`next_retry_at`
- **S4-02**：`schedule daemon --max-concurrent`（默认 1，`0`→1）；每轮最多执行 N 个到点任务，其余跳过并在 `.cai-schedule-audit.jsonl` 与可选 `--jsonl-log` 记录 **`skipped_due_to_concurrency`**；JSON 汇总 `total_skipped_due_to_concurrency` 与每轮 `skipped_due_to_concurrency`
- **S4-03**：`add_schedule_task` 检测 `depends_on` 有向环（含自环），拒绝写入；`schedule add` 失败 exit 2 + `--json` 的 `schedule_add_invalid`；`schedule list` 文本列 deps / dep_blocked / dependents / dep_chain；`list --json` 增加 `depends_on_status`、`dependency_blocked`、`dependents`、`depends_on_chain`（仅输出）
- **S4-04**：`append_schedule_audit_event` 写入 `schema_version`/`event`/`goal_preview`/`elapsed_ms`/`error`；`daemon --jsonl-log` 与审计文件同 schema 镜像；`run-due --execute` / `daemon --execute` 增加 `task.started`；`daemon.cycle` 经审计 API 写入；文档 `docs/schema/SCHEDULE_AUDIT_JSONL.zh-CN.md`
- **S4-05**：`compute_schedule_stats_from_audit` + CLI **`schedule stats`**（`--days`、`--audit-file`、`--json`）；`schema_version=schedule_stats_v1`；文档 `docs/schema/SCHEDULE_STATS_JSON.zh-CN.md`
- `.cai-schedule-audit.jsonl` 审计日志
- `run-due --execute` 与 `daemon --execute` 行为对齐（重试、审计、attempts）

### C. Hooks / 可观测

- 非 JSON 路径输出每个 hook 的运行状态摘要（`ok/blocked/error/skipped`）
- `board` 看板增强筛选：支持 `--failed-only` 与 `--task-id`，可快速聚焦失败会话与指定任务
- `board` 新增失败摘要：输出 `failed_summary`（count/recent），文本模式增加 `[failed_summary]` 区块便于值班排障
- `board` 新增状态统计：输出 `status_summary` 与 `status_counts`（`pending/running/completed/failed/unknown`），文本模式增加 `[status_summary]` 分组统计
- `board` 失败摘要增强：支持 `--failed-top` 配置 recent 失败条数，按会话文件 mtime 降序输出（最近失败优先）
- `board` 新增分组聚合：支持 `--group-top` 输出模型与 task 维度 TopN（`group_summary`），文本模式增加 `[group_summary]` 摘要
- `board` 新增组合过滤：支持 `--status`（可多值/逗号分隔）并与 `--failed-only` / `--task-id` 联合生效
- `board` 新增趋势对比：支持 `--trend-window`（或 `--trend-recent` + `--trend-baseline`）输出 `trend_summary`，给出 recent/baseline 的失败率与平均 tokens 差值
- `hooks.json` 解析顺序：`hooks/hooks.json` → `.cai/hooks/hooks.json`；`plugins` 健康分与 `_print_hook_status` / `run_project_hooks` 与此一致
- 新增 CLI：`cai-agent hooks list`（`hooks_catalog_v1`）与 `cai-agent hooks run-event <event>`（`--dry-run` 输出 `hooks_run_event_result_v1`；执行时同 schema 含 `results`）
- Hooks（Sprint 5 增量）：`enabled_hook_ids` 与执行器分类一致（仅返回将实际执行的 hook id）；Windows 上 hook `command` argv 路径片段规范化，与跨平台 hooks.json 对齐；对应单测补充

### J. MCP / WebSearch / Notebook 对齐（Sprint 3）

- `mcp-check` 增强预设自检：支持 `--preset websearch|notebook`，输出推荐关键词命中情况与缺失项
- `mcp-check` 增强探测策略：支持 `--list-only`（仅列工具不探活），避免在未准备好参数时误触工具调用
- JSON 输出新增 `preset` 结构化摘要（`name/recommended_tools/matched_tools/missing_tools/ok`），可直接用于 CI 或 onboarding 诊断
- `mcp-check` 新增降级提示：当 preset 未命中时输出 `fallback_hint`（含文档路径、建议命令、缺失关键词），用于接入阻塞场景快速定位
- `mcp-check` 新增模板输出：支持 `--print-template`，按 `websearch/notebook` 生成可复制的最小 MCP 配置片段（文本/JSON 双输出）
- `mcp-check` 模板细化：`--print-template` 按 preset 输出差异化模板（WebSearch/Notebook 各自示例工具名、环境变量占位、最小命令），降低首次接入歧义

### D. Memory Loop

- `memory import-entries` 严格化：新增 `--dry-run` 仅校验不落盘路径，支持在导入前做批量 schema 预检
- `memory import-entries` 错误语义增强：无效 bundle 返回结构化错误（entry_index/path/errors），便于快速定位坏数据行
- `memory import-entries` 新增坏数据隔离报告导出：支持 `--error-report <path>` 将无效行报告落盘（`memory_entries_import_errors_v1`，含 `source_file/errors_count/errors`）
- `memory import-entries` 失败摘要可读性增强：stderr 输出总览（total/validated/invalid）与首个错误定位（entry_index/path/reason）
- `memory nudge` schema 升级至 `1.1`
- 新增 `threshold_policy` / `risk_score` / `trend`
- 新增记忆状态机评估：`active/stale/expired`（`memory state`）
- `memory list --json`：根对象 **`memory_list_v1`**，**`entries[]`** 内含 `state` / `state_reason`
- `memory prune` 新增 `--drop-non-active`，可按状态机删除非 active 条目
- `memory prune --json` 输出增强：`schema_version=memory_prune_result_v1`、`removed_by_reason`（按原因分桶）、`invalid_json_lines`（文件中无法解析为 JSON 的行数，不自动删除）；文本模式补充 `non_active` 与 `removed_by_reason` 摘要行
- **S2-01**：`memory health`（`build_memory_health_payload`）：综合 `health_score`/`grade`（A~D）、`freshness`/`coverage`/`conflict_rate`/`conflict_pairs`；`--fail-on-grade` 返回 exit 2；修复 `memory state` 对 `evaluate_memory_entry_states` 的错误传参；`memory_state_eval_v1` 增加 `total_entries`
- **S2-02 / S2-05**：`compute_memory_freshness_metrics` 与 health 共用；`memory nudge-report --json` 升至 `schema_version=1.2`，输出 `freshness*` 与 `health_score`/`health_grade`，CLI 增加 `--freshness-days`
- **S2-03 / S2-04**：`memory health` JSON 增加冲突可观测字段（`conflict_pair_count`、`conflict_compared_entries`、`conflict_max_compare_entries`、`conflict_similarity_metric`）；coverage 分母改为可评估会话数并输出 `sessions_considered_for_coverage` 与跳过计数；CLI `--max-conflict-compare-entries`

### E. Recall Loop

- `recall` / `recall-index search` JSON `schema_version` **1.3**；`--sort recent|density|combined` 与 `ranking` 策略字段对齐（S3-01）
- **S3-02**：0 命中时 `no_hit_reason`（`window_too_narrow` / `pattern_no_match` / `index_empty` / `all_skipped`）；文本模式输出可读 `no_hit_reason` 行
- 混合排序：`recency` + `hit_strength` + `keyword_density`；直扫路径 `keyword_density` 基于完整命中消息正文；索引路径密度基于索引 `content` 全文
- 行级评分：`score` + `score_breakdown`（含 `sort_mode`）
- `recall-index search` 与主 recall 评分模型对齐
- **S3-03**：`recall-index doctor` / `doctor --fix`：索引缺失、schema 版本、磁盘文件缺失、相对 `window.since` 过旧路径；`tests/test_recall_index_cli.py` 覆盖
- **S3-04**：`scripts/perf_recall_bench.py`（scan / index_build / index_search，可选 `--include-refresh`）；`tests/test_perf_recall_bench.py` 子进程冒烟

### F. Workflow / Subagents 编排

- step 级 `parallel_group` 并发执行
- `workflow.parallel_group.completed` 事件
- `parallel_steps_count` / `parallel_groups_count` / `merge_confidence`
- 子代理标准 IO 输出结构：`subagent_io_schema_version=v1`、`merge_result`（strategy/decision/confidence/conflicts）

### G. Release / Security Gate

- 新增 `release-ga` 命令（质量、失败率、token 预算、可选安全扫描）
- 新增 `release-ga` 扩展门禁：
  - `--with-doctor`（包含 doctor 健康检查）
  - `--with-memory-nudge` + `--nudge-fail-on-severity`（包含 memory nudge 门禁）
- 新增 `release-ga` 记忆状态门禁：
  - `--with-memory-state`
  - `--memory-max-stale-ratio` / `--memory-max-expired-ratio`
  - `--memory-state-stale-days` / `--memory-state-stale-confidence`

### H. Security Model（命令审批策略）

- `run_command` 高风险命令策略：新增可配置阻断（默认开启）
- 支持配置项：
  - `[permissions].run_command_approval_mode = "block_high_risk" | "allow_all"`
  - `[permissions].run_command_high_risk_patterns = [...]`（可扩展匹配片段）
- 新增单测覆盖阻断/放行路径

### I. Gateway MVP（Telegram）

- 新增 `gateway telegram` 子命令族：`bind|get|list|unbind`
- 建立 `chat_id:user_id -> session_file` 持久化映射（默认 `.cai/gateway/telegram-session-map.json`）
- 支持 `--map-file` 自定义映射路径与 JSON 输出（`gateway_telegram_map_v1`）
- 新增 CLI 单测覆盖完整绑定生命周期（bind/get/list/unbind + not found）
- 新增 `gateway telegram resolve-update`：可从 Telegram update JSON 提取 `chat_id/user_id` 并解析映射
- 支持 `--create-missing` + `--session-template` 在映射缺失时自动生成映射（update 流最小闭环）
- 新增 `gateway telegram serve-webhook`：本地 HTTP 入口接收 `/telegram/update`，复用映射解析并写入 JSONL 事件日志
- `serve-webhook` 新增 `--execute-on-update` 与 `--goal-template`，可在接收 update 后直接触发执行路径并记录 answer 预览
- `serve-webhook` 新增执行后回发链路：支持 `--reply-on-execution` / `--telegram-bot-token` / `--reply-template`，将执行结果通过 Telegram `sendMessage` 回发（并记录回发状态）

## 目标项状态对照（总体）


| 领域             | 状态        | 说明                                                                      |
| -------------- | --------- | ----------------------------------------------------------------------- |
| Scheduler V2   | **高完成度**  | 任务模型核心已落地（依赖/重试/审计）                                                     |
| Recall Loop V2 | **高完成度**  | ranking、索引与 `recall-index benchmark` 性能对比能力已落地                          |
| Memory Loop V2 | **高完成度** | nudge schema/阈值到位；状态机评估与 prune 策略（TTL/置信度/保留上限/非 active 清理）已落地 |
| Subagents 编排   | **中高完成度** | workflow 并行、合并与标准 IO 输出已落地，DSL 规范仍待细化                                   |
| Observability  | **中高完成度** | hook 结果可见，`observe-report` 报表与告警规则入口已落地                                 |
| Security Model | **中高完成度** | 扫描、门禁与高危命令阻断策略已落地，细粒度审批链待扩                                              |
| Release GA     | **高完成度** | `release-ga` 已覆盖质量/安全/成本/doctor/memory-nudge/memory-state 多维门禁，后续以阈值运营优化为主 |
| Gateway MVP    | **已完成（MVP）** | 已支持 webhook 接入、update 解析、映射自动创建、事件日志、update 触发执行与执行结果回发 Telegram |


## 当前总体进度（估算）

- 总体：**约 100%（当前规划范围）**
- 已完成偏“核心底座与可执行门禁”
- 未完成偏“平台化与生态化模块”（Gateway、完整运营面板、全量 DSL/策略）

## 下一阶段建议（按价值）

1. Sprint 5+：Hooks Runtime 深化与其它 Sprint 按计划推进；Sprint 4 可选补 memory 字段定义与迁移向导专题文档
2. Gateway 后续增强：补回发失败重试与幂等（MVP 已闭环）
3. Recall 结果缓存与大规模索引压测脚本
4. Release GA 门禁阈值运营化（按环境分层阈值、告警格式细化）

