# Hermes 对齐开发进度状态表

> 生成时间：2026-04-23（**发行包 `cai-agent` `0.6.5`**；**S6-04** **`gateway telegram continue-hint`**（**`gateway_telegram_continue_hint_v1`**）+ **`docs/qa/sprint6-gateway-telegram-testplan.md`** **GTW-CONT**；此前 **S6-01/S6-02/S6-03** 仍有效；**§二 24–26** CLI **MVP**（**`0.6.1`**）；Hermes **34 Story ✅ 27/34**；进度统计与 **QA** 见 [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md) **§三之二**；T1 **`pytest`** 例 **373 passed**（**3 subtests**）+ **`smoke_new_features`**；T2 回归日志 [`docs/qa/runs/regression-20260423-091003.md`](qa/runs/regression-20260423-091003.md) **PASS**；**`QA_SKIP_LOG=1`** **`run_regression.py`** **本日复跑 PASS**（**不写** `docs/qa/runs/` 新文件））  
> 基准版本：main 分支（含已合并 memory/recall/schedule 基础能力）  
> 分析依据：`docs/HERMES_PARITY_BACKLOG.zh-CN.md` 的 34 条 Story  
>
> 说明：**开发和 QA 以本文件为当前起点**，开发按"待开发"列表依序认领，QA 按"待测试"列表在开发完成后介入。产品级 **完成 / 未开始 / 测试交接** 的一页汇总以 **`PRODUCT_PLAN.zh-CN.md` §三之二** 为准（与 [`DEVELOPMENT_PROGRESS_TRACKER.zh-CN.md`](DEVELOPMENT_PROGRESS_TRACKER.zh-CN.md) 互链 **QA-2 / `QA_SKIP_LOG`**，自测可不写新 **`runs/`** 回归文件）。

---

## 总体进度


| 状态           | 数量     | 占比       |
| ------------ | ------ | -------- |
| ✅ 已完成        | 27     | 79%      |
| ⚠️ 部分完成（需补齐） | 0      | 0%       |
| ❌ 未开发        | 7      | 21%      |
| **合计**       | **34** | **100%** |

**完成度快照（与 [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md) §三之二 · 3.0 对齐）**：仅计 ✅ 为 **27/34 ≈ 79.4%**（**>20%** 同步基线之上；与 §三之二 **3.0** Hermes 行一致）。

---

## ✅ 已完成（开发不需要再动，QA 已有测试覆盖）


| Story ID    | 标题               | 说明                                                              |
| ----------- | ---------------- | --------------------------------------------------------------- |
| S1-01       | 命令参数命名一致性        | `--json`/`--days`/`--limit`/`--index-path`/`--history-file` 已统一 |
| **S1-02**   | JSON schema 契约索引 | `docs/schema/README.zh-CN.md` **§ S1-02/S1-03** 收口；`smoke_new_features` 跨命令抽样；`SCHEDULE_*` 独立长文 |
| **S1-03**   | 错误码 exit 0/2 / 130 | 见 schema README；主流失败路径 **exit `2`**；`run` 族 Ctrl+C **exit `130`** |
| S1-04       | Parity Matrix 基础 | `docs/PARITY_MATRIX.zh-CN.md` 已有，需按新格式补充 Gap 列                  |
| **S8-01**   | 回归与冒烟套件 | `scripts/run_regression.py` + `scripts/smoke_new_features.py`（`PYTHONPATH` + `python -m cai_agent`）；随 Sprint 扩充 |
| **S2-01**   | `memory health` 统一评分 | `cai-agent memory health --json`（`schema_version`=`1.0`）、`--fail-on-grade` exit 0/2；实现见 `memory.build_memory_health_payload` + `tests/test_memory_health_cli.py` |
| **S2-02**   | freshness 指标 | `compute_memory_freshness_metrics` 与 `memory health` 共用；`memory nudge-report --json` 输出 `freshness` / `freshness_days` / `since_freshness` / `fresh_entries`；CLI `--freshness-days` |
| **S2-05**   | nudge-report health_score | `nudge-report --json` 升级为 `schema_version`=`1.2`，含 `health_score` 与 `health_grade`（与当前工作区 `memory health` 一致） |
| **S2-03**   | conflict_rate 指标 | `memory health --json`：`conflict_pair_count`、`conflict_compared_entries`、`conflict_max_compare_entries`、`conflict_similarity_metric`；`--max-conflict-compare-entries` 可调采样规模 |
| **S2-04**   | coverage 指标 | `coverage` 分母为 `--days` 窗口内 **可评估会话**（goal≥8 且解析成功）；`counts.sessions_considered_for_coverage` 与跳过计数可观测 |
| **S3-01**   | recall `--sort` 策略 | `recall` / `recall-index search|benchmark`：`--sort recent|density|combined`；`ranking` 随策略变化；JSON `schema_version` 演进见 S3-02 |
| **S3-02**   | recall 无命中解释 | 0 命中时 JSON `no_hit_reason`：`window_too_narrow` / `pattern_no_match` / `index_empty` / `all_skipped`；`schema_version=1.3`；文本模式打印可读提示 |
| **S3-03**   | `recall-index doctor` | `recall-index doctor [--fix] [--json]`：`schema_version=recall_index_doctor_v1`，`is_healthy` / `issues` / `stale_paths` / `missing_files` / `schema_version_ok`；`--fix` 剔除缺失与相对索引窗口过旧条目；健康 exit 0、有问题 exit 2 |
| **S3-04**   | recall 性能基准 | `scripts/perf_recall_bench.py`：生成会话并测 scan / index_build / index_search（可选 `--include-refresh`）；Markdown 默认落 `docs/qa/runs/`；`tests/test_perf_recall_bench.py` 冒烟 |
| **S4-01**   | 调度失败跨轮次重试与指数退避 | `.cai-schedule.json`：`max_retries`（默认 3）/`retry_count`/`next_retry_at`；失败写入 `last_status=retrying`，超限 `failed_exhausted`；退避 `schedule_retry_backoff_seconds` = `60*2^(retry_count-1)` 秒；`compute_due_tasks` 对 `retrying` 仅当 `now>=next_retry_at`（或缺失时间戳）时到期；成功清零 `retry_count`；CLI `schedule add --max-retries`；`run-due --execute` / `daemon --execute` 的 JSON 与审计行携带持久化 `status`/`retry_count`/`next_retry_at`；`tests/test_schedule_retry_backoff.py`、`test_schedule_run_due_retry_json.py` |
| **S4-02**   | `schedule daemon` 并发上限 | `schedule daemon --max-concurrent <N>`（默认 1，`0` 视为 1）；每轮仅执行前 N 个 `due` 任务，其余本跳过、下轮再判；`.cai-schedule-audit.jsonl` 与可选 `--jsonl-log` 写入 **`skipped_due_to_concurrency`**；JSON 汇总含 `max_concurrent`、`total_skipped_due_to_concurrency`、每轮 `skipped_due_to_concurrency`；`tests/test_schedule_daemon_cli.py` |
| **S4-03**   | 任务依赖链与环检测 | `add_schedule_task` 写入前检测 `depends_on` 有向环（含自环），拒绝并 `ValueError`；`schedule add` 失败 **exit 2**，`--json` 输出 `schedule_add_invalid`；`schedule list` 文本列 **`deps` / `dep_blocked` / `dependents` / `dep_chain`**；`--json` 每行增加 **`depends_on_status`**、**`dependency_blocked`**、**`dependents`**、**`depends_on_chain`**（不落盘）；`tests/test_schedule_depends_s4_03.py` |
| **S4-04**   | 调度审计 JSONL 统一 schema | `.cai-schedule-audit.jsonl` 与 `daemon --jsonl-log` **同行结构**：`schema_version=1.0`、`event` ∈ `task.started` / `task.completed` / `task.failed` / `task.retrying` / `task.skipped` / `daemon.cycle` / `daemon.started`，以及 `task_id`、`goal_preview`、`elapsed_ms`、`error`、`status`、`action`、`details`；`run-due --execute` 增加 **task.started**；文档 **`docs/schema/SCHEDULE_AUDIT_JSONL.zh-CN.md`**；`tests/test_schedule_audit_schema_s4_04.py` |
| **S4-05**   | `schedule stats` SLA 聚合 | **`cai-agent schedule stats [--days N] [--audit-file PATH] [--json]`**；`schema_version=schedule_stats_v1`；每任务 **`run_count`** / **`success_count`** / **`fail_count`** / **`success_rate`** / **`avg_elapsed_ms`** / **`p95_elapsed_ms`**；兼容无 `event` 的旧审计行；文档 **`docs/schema/SCHEDULE_STATS_JSON.zh-CN.md`**；`tests/test_schedule_stats_cli.py` |
| **S5-01**   | workflow `parallel_group` 字段 | 同名字符串步骤同批调度；`summary.parallel_groups_count` / `parallel_steps_count`；`tests/test_cli_workflow.py::test_workflow_parallel_group_emits_group_summary` |
| **S5-02**   | fan-out/fan-in 结果聚合 | `subagent_io.merge`（`decision` / `confidence` / `conflicts` 等）、`merge_confidence`；与并行组摘要同源；`test_cli_workflow.py` |
| **S5-03**   | fail-fast / continue-on-error | 根级 **`on_error`**（`fail_fast` 默认 / `continue-on-error` 别名 → `continue_on_error`）；`summary.on_error`、`steps_skipped`、`merge_steps_considered`；事件 **`workflow.step.skipped`**；`tests/test_cli_workflow.py` |
| **S5-04**   | 预算与 token 门禁 | 根级 **`budget_max_tokens`**；批间 **`total_tokens`** 累计 ≥ 预算则 **`skipped`/`budget_exceeded`**；`summary` 与 **`workflow.finished`** 含 **`budget_used`** / **`budget_limit`** / **`budget_exceeded`**；`task.error` **`workflow_budget_exceeded`**；`tests/test_cli_workflow.py` |
| **S6-01**   | **`gateway setup|start|status|stop` 生命周期** | **`cai_agent.gateway_lifecycle`**；**`telegram-config.json`**（**`gateway_telegram_config_v1`**）+ **PID**；**`start`** 拉起 **`serve-webhook`**；**`-w/--workspace`**；`tests/test_gateway_lifecycle_cli.py`；**`smoke_new_features`** **`gateway status --json`** |
| **S6-02**   | Telegram **`serve-webhook` 执行与回发** | **`_execute_gateway_telegram_goal`**：绑定 **`session_file`** 与 **`run`/`continue`** 同源加载/写回；**`_telegram_send_text_chunked`**；slash **`/ping`** / **`/status`** / **`/help`** / **`/start`** / **`/new`** / **`/stop`**（默认 **`gateway stop`** 提示，可选 env 远程 **`stop_webhook`**）；**`test_gateway_telegram_execute_goal.py`**。**真机**媒体/附件等仍为 **GTW-TG** 扩展 |
| **S6-03**   | Telegram **`allowed_chat_ids` 白名单** | 映射 JSON 根级 **`allowed_chat_ids`**；**`gateway telegram allow add|list|rm`**；**`resolve-update`** / **`serve-webhook`** 路径 **`not_allowed`**；**`list --json`** 含 **`allowed_chat_ids`** / **`allowlist_enabled`**；可选 **`serve-webhook --reply-on-deny`**；`tests/test_gateway_telegram_cli.py` |
| **S6-04**   | **跨端会话连续性（CLI ↔ Telegram）** | **`gateway telegram continue-hint`**（**`gateway_telegram_continue_hint_v1`**）；slash **`/help`**/**`/new`** 引导；**`docs/qa/sprint6-gateway-telegram-testplan.md`** **GTW-CONT-001~003**；**`test_gateway_telegram_cli.py`** |


---

## ⚠️ 部分完成（开发需补齐，QA 需扩充测试）

*（当前 **0** 条 Story 置于此区。真机 **GTW-TG** 媒体/长链路仍以专项计划与手工为主。）*

---

## ❌ 未开发（按 Sprint 排序，开发认领后逐步交付）

### Sprint 2：Memory Loop 2.0

**本 Sprint（S2-01 ~ S2-05）在当前主线能力上已收口**；后续若 backlog 增补新 Story，再从此表续写。

---

### Sprint 3：Recall Loop 2.0

**本 Sprint（S3-01 ~ S3-04）在当前主线能力上已收口**；后续若 backlog 增补新 Story，再从此表续写。

---

### Sprint 4：Scheduler 2.0

**本 Sprint（S4-01 ~ S4-05）在当前主线能力上已收口**；后续若 backlog 增补新 Story，再从此表续写。


**开发关键文件**：

- `cai-agent/src/cai_agent/schedule.py`：`schema_version` 1.1；跨轮次重试；`depends_on` 环检测；`enrich_schedule_tasks_for_display`；**`compute_schedule_stats_from_audit`**
- `__main__.py`：`schedule daemon --max-concurrent`；**`schedule stats`**  
**QA 等待信号**：S4-01~S4-05：**SCH-RETRY**、**SCH-CONC**、**SCH-DEP**、**SCH-AUDIT**、**SCH-SLA**

---

### Sprint 5：Subagents 并行编排

**本 Sprint（S5-01 ~ S5-04）在当前主线能力上已收口**；后续若 backlog 增补新 Story，再从此表续写。

**开发关键文件**：

- `cai_agent/workflow.py`：`parallel_group`、**`on_error`**（S5-03）、**`budget_max_tokens`**（S5-04）与 **`subagent_io`** 汇总  
**QA 等待信号**：编排与预算自动化见 `docs/qa/sprint5-subagents-testplan.md`；**质量门禁与 `quality-gate` 深度联动**仍为后续增量。

---

### Sprint 6：Messaging Gateway（Telegram MVP）

**Sprint 6 所列 Hermes Story（S6-01～S6-04）已在主线以 CLI MVP 收口**；真机 **GTW-TG** 仍以 Bot Token 手工为主。

**注意**：**S6-01 / S6-02 / S6-03 / S6-04** 已合 **`0.6.1`–`0.6.5`**；手工测仍建议配置 **`allowed_chat_ids`** 与测试 Bot。  
**开发关键文件**：

- `cai-agent/src/cai_agent/gateway_lifecycle.py`（**S6-01**）
- `__main__.py`：`gateway` 顶级命令组、**`serve-webhook`** 与 Telegram HTTP 辅助  
**QA 等待信号**：**GTW-BASE** 随 **S6-01** 自动化；**GTW-TG** 真机与媒体用例仍待测试 Bot Token

---

### Sprint 7：Observability Pro


| Story ID  | 标题                                | 优先级 | 估算  | 测试计划                                                                                                  |
| --------- | --------------------------------- | --- | --- | ----------------------------------------------------------------------------------------------------- |
| **S7-01** | 统一指标模型（metrics schema）            | P1  | M   | [sprint7-observability-pro-testplan.md](qa/sprint7-observability-pro-testplan.md) OBS-METRICS-001~003 |
| **S7-02** | `observe report` 导出命令             | P1  | L   | OBS-RPT-001~006                                                                                       |
| **S7-03** | 跨域关联洞察（`insights --cross-domain`） | P2  | L   | OBS-CROSS-001~002                                                                                     |
| **S7-04** | 运营看板导出（CSV/JSON/Markdown）         | P2  | M   | OBS-EXP-001~004                                                                                       |


**开发关键文件**：

- `__main__.py`：`observe` 增加 `report`/`export` 子命令；`insights` 增加 `--cross-domain`
- 新建 `cai-agent/src/cai_agent/metrics.py`（统一指标模型）  
**QA 等待信号**：S7-01 + S7-02 提测后开始 OBS-RPT 系列测试

---

### Sprint 8：GA 收敛


| Story ID      | 标题        | 优先级 | 估算  | 测试计划                                                               |
| ------------- | --------- | --- | --- | ------------------------------------------------------------------ |
| **S8-01**（补齐） | 全量回归套件扩充  | P0  | L   | [sprint8-ga-testplan.md](qa/sprint8-ga-testplan.md) GA-REG-001~003 |
| **S8-02**     | 关键路径压测脚本  | P0  | L   | PERF-GA-001~005                                                    |
| **S8-03**（补齐） | 安全审计完整覆盖  | P0  | M   | SEC-GA-001~005                                                     |
| **S8-04**     | 发布说明与迁移指南 | P1  | M   | 文档验证                                                               |


> Sprint 8 依赖 S2~S7 全部 P0/P1 完成后才能启动。

---

## 给开发的认领顺序建议

**推荐执行顺序（最小依赖链）**：

```
Sprint 2 全部 → Sprint 3 全部 → Sprint 4（P1 先）
     ↓                              ↓
Sprint 5 P1       →         Sprint 7 P1
     ↓
Sprint 6（安全优先）
     ↓
Sprint 8（GA）
```

**可并行开发的组合**（互不依赖）：

- S2（memory）可与 S3（recall）并行
- S4（scheduler）可与 S7（observability）并行
- S5（subagents）独立，可单独认领
- S6（gateway）独立，可单独认领（**S6-03** 安全先行；**S6-01** 生命周期已合 **`0.6.3`**）

---

## 给 QA 的等待状态

**当前可以开始测试的**：

- ✅ 所有已完成项的回归测试（`python3 -m pytest -q cai-agent/tests/`）
- ⚠️ 准备好 Sprint 2~8 各阶段手工测试环境与测试数据模板

**等待开发信号后开测**：


| Sprint | 开发完成信号                     | QA 开始动作                                           |
| ------ | -------------------------- | ------------------------------------------------- |
| S2     | Sprint 2 Memory（health / nudge-report 1.2）待合并 PR | 运行 `python3 -m pytest -q cai-agent/tests/test_memory_*.py` + 手工 [sprint2-memory-health-testplan.md](qa/sprint2-memory-health-testplan.md) |
| S3     | Sprint 3 Recall 已收口 | `python3 -m pytest -q tests/test_recall*.py tests/test_perf_recall_bench.py` + [sprint3-recall-v2-testplan.md](qa/sprint3-recall-v2-testplan.md) PERF-RCL 手工 |
| S4     | S4-01~S4-05 已合并主线（PR #18~#22） | `test_schedule*.py` + SCH-RETRY + SCH-CONC + SCH-DEP + SCH-AUDIT + SCH-SLA；故障注入 SCH-FI-001~003 |
| S5     | S5-01/S5-02 合并             | 运行 `test_workflow*.py` + 并行编排端到端                  |
| S6     | S6-01～S6-04 合并 | 自动化 **GTW-BASE** + **GTW-SEC** + **`test_gateway_telegram_execute_goal`** + **`test_gateway_telegram_cli`（continue-hint）**；**GTW-TG** 真机待 Bot Token |
| S7     | S7-01/S7-02 合并             | 运行 `test_observe*.py` + OBS-RPT-001~006           |
| S8     | S2~S7 全部 P0/P1 完成          | 全量回归 + 压测 + 安全审计 + 发布冒烟                           |


---

## 文档索引

| 文件 | 用途 |
|------|------|
| [HERMES_PARITY_BACKLOG.zh-CN.md](HERMES_PARITY_BACKLOG.zh-CN.md) | 完整 34 条 Story（AC/优先级/依赖/估算），供开发认领 |
| [HERMES_PARITY_SPRINT_PLAN.zh-CN.md](HERMES_PARITY_SPRINT_PLAN.zh-CN.md) | 8 Sprint 路线图与 DoD |
| [qa/HERMES_PARITY_MASTER_TESTPLAN.zh-CN.md](qa/HERMES_PARITY_MASTER_TESTPLAN.zh-CN.md) | QA 总策略与回归套件 |
| [qa/sprint2-memory-health-testplan.md](qa/sprint2-memory-health-testplan.md) | S2 专项测试 |
| [qa/sprint3-recall-v2-testplan.md](qa/sprint3-recall-v2-testplan.md) | S3 专项测试 |
| [qa/sprint4-scheduler-v2-testplan.md](qa/sprint4-scheduler-v2-testplan.md) | S4 专项测试 |
| [schema/SCHEDULE_AUDIT_JSONL.zh-CN.md](schema/SCHEDULE_AUDIT_JSONL.zh-CN.md) | S4-04 调度审计 JSONL 字段与 `event` 枚举 |
| [schema/SCHEDULE_STATS_JSON.zh-CN.md](schema/SCHEDULE_STATS_JSON.zh-CN.md) | S4-05 `schedule stats --json` 输出说明 |
| [qa/sprint5-subagents-testplan.md](qa/sprint5-subagents-testplan.md) | S5 专项测试 |
| [qa/sprint6-gateway-telegram-testplan.md](qa/sprint6-gateway-telegram-testplan.md) | S6 专项测试（含安全） |
| [qa/sprint7-observability-pro-testplan.md](qa/sprint7-observability-pro-testplan.md) | S7 专项测试 |
| [qa/sprint8-ga-testplan.md](qa/sprint8-ga-testplan.md) | S8 发布门禁 |

---

## 工程注记（合并记录）

- **2026-04-22 · Sprint 4 Scheduler（S4-01，已合并 PR #18）**：跨轮次失败重试与指数退避（`retrying` / `failed_exhausted`、`schedule add --max-retries`）。
- **2026-04-22 · Sprint 4 Scheduler（S4-02，已合并 PR #19）**：`schedule daemon --max-concurrent`、审计与 JSONL **`skipped_due_to_concurrency`**、汇总计数。
- **2026-04-22 · Sprint 4 Scheduler（S4-03，已合并 PR #20）**：`depends_on` 环检测；`schedule list` 依赖链/阻塞/反向依赖展示；`schedule add` 环时 exit 2 + JSON `schedule_add_invalid`。
- **2026-04-22 · Sprint 4 Scheduler（S4-04，已合并 PR #21）**：审计与 `--jsonl-log` 统一 `schema_version`/`event`/`goal_preview`/`elapsed_ms`；`task.started`；文档 `docs/schema/SCHEDULE_AUDIT_JSONL.zh-CN.md`。
- **2026-04-22 · Sprint 4 Scheduler（S4-05，已合并 PR #22）**：`schedule stats --json` + `compute_schedule_stats_from_audit`；文档 `docs/schema/SCHEDULE_STATS_JSON.zh-CN.md`。
- **2026-04-22 · Sprint 5 Hooks**：`enabled_hook_ids` 与 `run_project_hooks` 分类一致；Windows 上 hook `command` argv 路径片段 `Path` 规范化。详见 `HERMES_PARITY_SPRINT_PLAN.zh-CN.md` Sprint 5 完成记录与 [PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md) L2。
- **2026-04-23 · Sprint 6 Gateway（`0.6.3`）**：**`gateway setup|start|status|stop`**（**`gateway_lifecycle.py`**）；**`serve-webhook`** 长文本分块与 slash 快捷回复（**S6-02** 部分）。
- **2026-04-23 · Sprint 6 Gateway（`0.6.4`）**：**`_execute_gateway_telegram_goal`** 会话写回；**`/stop`** 与 env 门控；**`test_gateway_telegram_execute_goal.py`**。
- **2026-04-23 · Sprint 6 Gateway（`0.6.5`）**：**`gateway telegram continue-hint`**（**S6-04**）；**`sprint6-gateway-telegram-testplan.md`** **GTW-CONT**。
