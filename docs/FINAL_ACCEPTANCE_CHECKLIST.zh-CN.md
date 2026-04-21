# 最终验收清单（当前规划范围）

> 目标：对“本轮规划范围内的剩余开发”给出可追踪、可复核的最终验收视图。

## 1) Gateway MVP（Telegram）

- [x] 映射管理：`gateway telegram bind|get|list|unbind`
- [x] update 解析：`gateway telegram resolve-update`
- [x] Webhook 接入：`gateway telegram serve-webhook`（`/telegram/update`）
- [x] 执行联动：`--execute-on-update` + `--goal-template`
- [x] 回发闭环：`--reply-on-execution` + `--telegram-bot-token` + `--reply-template`
- [x] 事件可追踪：JSONL 日志落盘（含解析、执行、回发结果）

## 2) Memory Loop 治理

- [x] `memory nudge` schema v1.1（`threshold_policy`/`risk_score`/`trend`）
- [x] `memory state` 状态机评估（`active/stale/expired`）
- [x] `memory list --with-state`（输出 `state`/`state_reason`）
- [x] `memory prune --drop-non-active`（基于状态机清理）
- [x] `memory prune` 保留策略修正（`--max-entries 0` = 不限制）

## 3) Release GA 门禁矩阵

- [x] 质量/安全/失败率/token 预算门禁
- [x] `--with-doctor` 健康检查门禁
- [x] `--with-memory-nudge` 严重度门禁
- [x] `--with-memory-state` 比例门禁（`stale/expired`）
- [x] 比例阈值参数：`--memory-max-stale-ratio` / `--memory-max-expired-ratio`

## 4) 回归测试（当前轮关键集合）

- [x] `test_gateway_telegram_cli`
- [x] `test_memory_state_machine_cli`
- [x] `test_release_ga_cli`
- [x] `test_memory_prune_policy_cli`
- [x] `test_memory_nudge_cli`
- [x] `test_schedule_cli`
- [x] `test_cli_workflow`
- [x] `test_observe_report_cli`

## 5) 结论

- 当前规划范围内“主链路”功能已闭环并通过回归。
- 后续工作建议转入“增强项”而非“缺失项”：
  - Gateway 回发失败重试与幂等策略；
  - Recall 大规模索引压测与缓存策略；
  - Release GA 更细粒度门禁矩阵模板（多语言栈）。
