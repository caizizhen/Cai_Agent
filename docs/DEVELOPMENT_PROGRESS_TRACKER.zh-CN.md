# 开发进度对照记录（持续更新）

> 目的：每次开发完成后，对照目标文档记录“已完成 / 进行中 / 未完成”，并给出总体进度。

## 对照基线

- `docs/ROADMAP_EXECUTION.zh-CN.md`
- `docs/NEXT_IMPLEMENTATION_BUNDLE.zh-CN.md`
- `docs/PARITY_MATRIX.zh-CN.md`
- 用户提供的目标族：Architecture/Memory/Recall/Scheduler/Subagents/Gateway/Observability/Security/Release GA

## 本分支已完成（累计）

### A. 统一入口与体验

- TUI 快捷模板入口：`/fix-build`、`/security-scan`

### B. Scheduler / 任务模型

- `depends_on` 依赖链
- `retry_max_attempts` / `retry_backoff_sec` 重试策略
- `.cai-schedule-audit.jsonl` 审计日志
- `run-due --execute` 与 `daemon --execute` 行为对齐（重试、审计、attempts）

### C. Hooks / 可观测

- 非 JSON 路径输出每个 hook 的运行状态摘要（`ok/blocked/error/skipped`）
- `board` 看板增强筛选：支持 `--failed-only` 与 `--task-id`，可快速聚焦失败会话与指定任务
- `board` 新增失败摘要：输出 `failed_summary`（count/recent），文本模式增加 `[failed_summary]` 区块便于值班排障
- `board` 新增状态统计：输出 `status_summary` 与 `status_counts`（`pending/running/completed/failed/unknown`），文本模式增加 `[status_summary]` 分组统计
- `board` 失败摘要增强：支持 `--failed-top` 配置 recent 失败条数，按会话文件 mtime 降序输出（最近失败优先）

### D. Memory Loop

- `memory nudge` schema 升级至 `1.1`
- 新增 `threshold_policy` / `risk_score` / `trend`
- 新增记忆状态机评估：`active/stale/expired`（`memory state`）
- `memory list --json` 输出补充 `state` / `state_reason`
- `memory prune` 新增 `--drop-non-active`，可按状态机删除非 active 条目

### E. Recall Loop

- `recall` schema 升级至 `1.1`
- 混合排序：`recency` + `hit_strength` + `keyword_density`
- 行级评分：`score` + `score_breakdown`
- `recall-index search` 与主 recall 评分模型对齐

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

1. 看板继续增强：补按模型/任务维度聚合（TopN）与过滤组合（状态+失败）视图
2. Gateway 后续增强：补回发失败重试与幂等（MVP 已闭环）
3. Recall 结果缓存与大规模索引压测脚本
4. Release GA 门禁阈值运营化（按环境分层阈值、告警格式细化）

