# Hermes 对齐开发进度状态表

> 生成时间：2026-04-21  
> 基准版本：main 分支（含已合并 memory/recall/schedule 基础能力）  
> 分析依据：`docs/HERMES_PARITY_BACKLOG.zh-CN.md` 的 34 条 Story  
>
> 说明：**开发和 QA 以本文件为当前起点**，开发按"待开发"列表依序认领，QA 按"待测试"列表在开发完成后介入。

---

## 总体进度


| 状态           | 数量     | 占比       |
| ------------ | ------ | -------- |
| ✅ 已完成        | 10     | 29%      |
| ⚠️ 部分完成（需补齐） | 4      | 12%      |
| ❌ 未开发        | 20     | 59%      |
| **合计**       | **34** | **100%** |


---

## ✅ 已完成（开发不需要再动，QA 已有测试覆盖）


| Story ID    | 标题               | 说明                                                              |
| ----------- | ---------------- | --------------------------------------------------------------- |
| S1-01       | 命令参数命名一致性        | `--json`/`--days`/`--limit`/`--index-path`/`--history-file` 已统一 |
| S1-04       | Parity Matrix 基础 | `docs/PARITY_MATRIX.zh-CN.md` 已有，需按新格式补充 Gap 列                  |
| S1-03（基础部分） | 错误码 exit 0/2     | `--fail-on-severity`、`--fail-on-grade` 接口已规范，部分命令已实现            |
| **S2-01**   | `memory health` 统一评分 | `cai-agent memory health --json`（`schema_version`=`1.0`）、`--fail-on-grade` exit 0/2；实现见 `memory.build_memory_health_payload` + `tests/test_memory_health_cli.py` |
| **S2-02**   | freshness 指标 | `compute_memory_freshness_metrics` 与 `memory health` 共用；`memory nudge-report --json` 输出 `freshness` / `freshness_days` / `since_freshness` / `fresh_entries`；CLI `--freshness-days` |
| **S2-05**   | nudge-report health_score | `nudge-report --json` 升级为 `schema_version`=`1.2`，含 `health_score` 与 `health_grade`（与当前工作区 `memory health` 一致） |
| **S2-03**   | conflict_rate 指标 | `memory health --json`：`conflict_pair_count`、`conflict_compared_entries`、`conflict_max_compare_entries`、`conflict_similarity_metric`；`--max-conflict-compare-entries` 可调采样规模 |
| **S2-04**   | coverage 指标 | `coverage` 分母为 `--days` 窗口内 **可评估会话**（goal≥8 且解析成功）；`counts.sessions_considered_for_coverage` 与跳过计数可观测 |
| **S3-01**   | recall `--sort` 策略 | `recall` / `recall-index search|benchmark`：`--sort recent|density|combined`；`ranking` 随策略变化；JSON `schema_version` 演进见 S3-02 |
| **S3-02**   | recall 无命中解释 | 0 命中时 JSON `no_hit_reason`：`window_too_narrow` / `pattern_no_match` / `index_empty` / `all_skipped`；`schema_version=1.3`；文本模式打印可读提示 |


---

## ⚠️ 部分完成（开发需补齐，QA 需扩充测试）

### S1-03 错误码规范（补齐剩余命令）

- **现状**：`memory nudge`、`recall`、`memory health`（`--fail-on-grade`）等已实现 exit 0/2；`schedule stats`、`observe report` 等新命令的错误码仍待补齐
- **需要**：所有新 Sprint 命令必须同步实现 exit 0/2 语义
- **QA**：随每个新命令提测时同步验证

### S1-02 错误码规范文档（需补文档）

- **现状**：无 `docs/schema/` 目录
- **需要**：建立目录，每个命令一份 schema 描述（字段/类型/版本）
- **QA**：文档验证 + 契约测试

### S4-04 调度审计日志 schema（需标准化事件类型）

- **现状**：`--jsonl-log` 已实现，JSONL 可追加写入，但事件类型字段名不统一（有 `schedule.daemon.cycle`、`daemon.started` 等混用）
- **需要**：统一 7 种事件类型：`task.started` / `task.completed` / `task.failed` / `task.retrying` / `task.skipped` / `daemon.cycle` / `daemon.started`
- **测试用例**：`SCH-AUDIT-001~004`
- **QA**：等待开发完成事件类型统一后开测

### S8-01 全量回归套件（需扩充覆盖新功能）

- **现状**：`scripts/run_regression.py` 已有，覆盖基础 27 个回归点
- **需要**：随每个 Sprint 新增用例时同步扩充
- **QA**：每个 Sprint 结束必须更新回归脚本

---

## ❌ 未开发（按 Sprint 排序，开发认领后逐步交付）

### Sprint 2：Memory Loop 2.0

**本 Sprint（S2-01 ~ S2-05）在当前主线能力上已收口**；后续若 backlog 增补新 Story，再从此表续写。

---

### Sprint 3：Recall Loop 2.0


| Story ID  | 标题                                       | 优先级 | 估算  | 测试计划                                                                               |
| --------- | ---------------------------------------- | --- | --- | ---------------------------------------------------------------------------------- |
| **S3-03** | `recall-index doctor` 命令                 | P1  | M   | RCL-DOC-001~006                                                                    |
| **S3-04** | recall 性能基准脚本                            | P2  | M   | PERF-RCL-001~005                                                                   |


**开发关键文件**：

- `__main__.py`：`recall` / `recall-index search|benchmark` 已支持 `--sort`；`recall-index doctor` 仍待办
- `scripts/perf_recall_bench.py`：新建性能基准脚本  
**QA 等待信号**：S3-03 提测后，整体运行 `python3 -m pytest -q tests/test_recall*.py` + RCL-DOC 手工系列（S3-01/S3-02 已合主线时可做回归）

---

### Sprint 4：Scheduler 2.0


| Story ID      | 标题                        | 优先级 | 估算  | 测试计划                                                                                      |
| ------------- | ------------------------- | --- | --- | ----------------------------------------------------------------------------------------- |
| **S4-01**     | 失败重试与指数退避                 | P1  | L   | [sprint4-scheduler-v2-testplan.md](qa/sprint4-scheduler-v2-testplan.md) SCH-RETRY-001~004 |
| **S4-02**     | 并发控制（`--max-concurrent`）  | P1  | L   | SCH-CONC-001~003                                                                          |
| **S4-03**     | 任务依赖（`--depends-on`）      | P2  | L   | SCH-DEP-001~003                                                                           |
| **S4-04**（补齐） | 审计日志事件类型统一                | P1  | M   | SCH-AUDIT-001~004                                                                         |
| **S4-05**     | `schedule stats` SLA 指标命令 | P2  | M   | SCH-SLA-001~002                                                                           |


**开发关键文件**：

- `cai-agent/src/cai_agent/schedule.py`：schema 扩展（retry/backoff/deps 字段）
- `__main__.py`：daemon 状态机升级；新增 `schedule stats` 子命令  
**QA 等待信号**：S4-01 + S4-02 提测后开始 SCH-RETRY 和 SCH-CONC 用例

---

### Sprint 5：Subagents 并行编排


| Story ID  | 标题                               | 优先级 | 估算  | 测试计划                                                                              |
| --------- | -------------------------------- | --- | --- | --------------------------------------------------------------------------------- |
| **S5-01** | workflow schema 增加 `parallel` 字段 | P1  | L   | [sprint5-subagents-testplan.md](qa/sprint5-subagents-testplan.md) SAG-PAR-001~006 |
| **S5-02** | fan-out/fan-in 结果聚合              | P1  | L   | SAG-AGG-001~004                                                                   |
| **S5-03** | fail-fast / continue-on-error 策略 | P2  | M   | SAG-ERR-001~003                                                                   |
| **S5-04** | 预算与质量门禁联动                        | P2  | M   | SAG-BUDGET-001~003                                                                |


**开发关键文件**：

- `__main__.py`：workflow 执行逻辑重构（并行调度器）
- workflow schema 扩展文档  
**QA 等待信号**：S5-01 + S5-02 提测后开始并行编排测试（此模块需要集成测试，建议开发提供 mock 示例）

---

### Sprint 6：Messaging Gateway（Telegram MVP）


| Story ID  | 标题                          | 优先级 | 估算  | 测试计划                                                                                            |
| --------- | --------------------------- | --- | --- | ----------------------------------------------------------------------------------------------- |
| **S6-03** | 用户身份绑定与 allowlist（**安全前置**） | P0  | M   | [sprint6-gateway-telegram-testplan.md](qa/sprint6-gateway-telegram-testplan.md) GTW-SEC-001~007 |
| **S6-01** | gateway 命令组基础结构             | P1  | XL  | GTW-BASE-001~003                                                                                |
| **S6-02** | Telegram 消息收发               | P1  | XL  | GTW-TG-001~006                                                                                  |
| **S6-04** | 跨端会话连续性                     | P2  | L   | GTW-CONT-001                                                                                    |


**注意**：S6-03（安全）**必须先完成**才允许进行 S6-02 的手工测试，避免 Bot 未授权可用的安全风险。  
**开发关键文件**：

- `cai-agent/src/cai_agent/gateway/`（新建模块）
- `__main__.py`：新增 `gateway` 顶级命令组  
**QA 等待信号**：S6-01 + S6-03 提测后开始自动化测试；S6-02 需要测试人员准备测试 Bot Token

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
- S6（gateway）独立，可单独认领（需 S6-03 安全先行）

---

## 给 QA 的等待状态

**当前可以开始测试的**：

- ✅ 所有已完成项的回归测试（`python3 -m pytest -q cai-agent/tests/`）
- ⚠️ 准备好 Sprint 2~8 各阶段手工测试环境与测试数据模板

**等待开发信号后开测**：


| Sprint | 开发完成信号                     | QA 开始动作                                           |
| ------ | -------------------------- | ------------------------------------------------- |
| S2     | Sprint 2 Memory（health / nudge-report 1.2）待合并 PR | 运行 `python3 -m pytest -q cai-agent/tests/test_memory_*.py` + 手工 [sprint2-memory-health-testplan.md](qa/sprint2-memory-health-testplan.md) |
| S3     | S3-03 待合并（S3-01/S3-02 已合主线） | 运行 `test_recall*.py` + 手工 RCL-DOC 系列 |
| S4     | S4-01/S4-02 合并             | 运行 `test_schedule*.py` + 故障注入测试 SCH-FI-001~003    |
| S5     | S5-01/S5-02 合并             | 运行 `test_workflow*.py` + 并行编排端到端                  |
| S6     | S6-01/S6-03 合并             | 自动化 GTW-SEC-001~004；准备 Bot Token 待手工测             |
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
| [qa/sprint5-subagents-testplan.md](qa/sprint5-subagents-testplan.md) | S5 专项测试 |
| [qa/sprint6-gateway-telegram-testplan.md](qa/sprint6-gateway-telegram-testplan.md) | S6 专项测试（含安全） |
| [qa/sprint7-observability-pro-testplan.md](qa/sprint7-observability-pro-testplan.md) | S7 专项测试 |
| [qa/sprint8-ga-testplan.md](qa/sprint8-ga-testplan.md) | S8 发布门禁 |

---

## 工程注记（合并记录）

- **2026-04-22 · Sprint 5 Hooks**：`enabled_hook_ids` 与 `run_project_hooks` 分类一致；Windows 上 hook `command` argv 路径片段 `Path` 规范化。详见 `HERMES_PARITY_SPRINT_PLAN.zh-CN.md` Sprint 5 完成记录与 [PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md) L2。
