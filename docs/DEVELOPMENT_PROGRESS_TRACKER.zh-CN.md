# 开发进度对照记录（持续更新）

> 目的：每次开发完成后，对照目标文档记录“已完成 / 进行中 / 未完成”，并给出总体进度。

## 对照基线

- `docs/ROADMAP_EXECUTION.zh-CN.md`
- `docs/NEXT_IMPLEMENTATION_BUNDLE.zh-CN.md`
- `docs/PARITY_MATRIX.zh-CN.md`
- 用户提供的目标族：Architecture/Memory/Recall/Scheduler/Subagents/Gateway/Observability/Security/Release GA

## 本分支已完成（累计）

### A. 统一入口与体验
- [x] TUI 快捷模板入口：`/fix-build`、`/security-scan`

### B. Scheduler / 任务模型
- [x] `depends_on` 依赖链
- [x] `retry_max_attempts` / `retry_backoff_sec` 重试策略
- [x] `.cai-schedule-audit.jsonl` 审计日志
- [x] `run-due --execute` 与 `daemon --execute` 行为对齐（重试、审计、attempts）

### C. Hooks / 可观测
- [x] 非 JSON 路径输出每个 hook 的运行状态摘要（`ok/blocked/error/skipped`）

### D. Memory Loop
- [x] `memory nudge` schema 升级至 `1.1`
- [x] 新增 `threshold_policy` / `risk_score` / `trend`

### E. Recall Loop
- [x] `recall` schema 升级至 `1.1`
- [x] 混合排序：`recency` + `hit_strength` + `keyword_density`
- [x] 行级评分：`score` + `score_breakdown`
- [x] `recall-index search` 与主 recall 评分模型对齐

### F. Workflow / Subagents 编排
- [x] step 级 `parallel_group` 并发执行
- [x] `workflow.parallel_group.completed` 事件
- [x] `parallel_steps_count` / `parallel_groups_count` / `merge_confidence`
- [x] 子代理标准 IO 输出结构：`subagent_io_schema_version=v1`、`merge_result`（strategy/decision/confidence/conflicts）

### G. Release / Security Gate
- [x] 新增 `release-ga` 命令（质量、失败率、token 预算、可选安全扫描）
- [x] 新增 `release-ga` 扩展门禁：
  - `--with-doctor`（包含 doctor 健康检查）
  - `--with-memory-nudge` + `--nudge-fail-on-severity`（包含 memory nudge 门禁）

### H. Security Model（命令审批策略）
- [x] `run_command` 高风险命令策略：新增可配置阻断（默认开启）
- [x] 支持配置项：
  - `[permissions].run_command_approval_mode = "block_high_risk" | "allow_all"`
  - `[permissions].run_command_high_risk_patterns = [...]`（可扩展匹配片段）
- [x] 新增单测覆盖阻断/放行路径

## 目标项状态对照（总体）

| 领域 | 状态 | 说明 |
|---|---|---|
| Scheduler V2 | **高完成度** | 任务模型核心已落地（依赖/重试/审计） |
| Recall Loop V2 | **高完成度** | ranking、索引与 `recall-index benchmark` 性能对比能力已落地 |
| Memory Loop V2 | **中高完成度** | nudge schema/阈值到位；`memory prune` 已支持 TTL+最小置信度+保留上限策略 |
| Subagents 编排 | **中高完成度** | workflow 并行、合并与标准 IO 输出已落地，DSL 规范仍待细化 |
| Observability | **中高完成度** | hook 结果可见，`observe-report` 报表与告警规则入口已落地 |
| Security Model | **中高完成度** | 扫描、门禁与高危命令阻断策略已落地，细粒度审批链待扩 |
| Release GA | **中高完成度** | `release-ga` 聚合门禁已可用，门禁矩阵仍可继续丰富 |
| Gateway MVP | **低完成度** | Telegram 接入协议与会话映射尚未实现 |

## 当前总体进度（估算）

- 总体：**约 82%**
- 已完成偏“核心底座与可执行门禁”
- 未完成偏“平台化与生态化模块”（Gateway、完整运营面板、全量 DSL/策略）

## 下一阶段建议（按价值）

1. Gateway MVP（Telegram）最小闭环
2. Memory Loop 状态机 + TTL 策略固化
3. Recall 结果缓存与大规模索引压测脚本
4. Release GA 门禁矩阵扩展（回归覆盖、性能阈值、告警格式）

