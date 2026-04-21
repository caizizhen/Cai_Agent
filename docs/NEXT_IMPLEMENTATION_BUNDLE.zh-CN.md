# 补齐方案总册（执行清单与长期 backlog）

本文档在「三源融合完全体」愿景下，给出 **尽可能长的可执行补齐面**：已在本轮落地的条目会标明 **[本轮已落地]**，其余按优先级供后续迭代勾选。

## 0. 文档与产品基线

- [本轮已落地] 愿景与分层验收：[PRODUCT_VISION_FUSION.zh-CN.md](PRODUCT_VISION_FUSION.zh-CN.md)
- [本轮已落地] Parity 矩阵与发版约定：[PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md)
- [ ] 每个版本更新 CHANGELOG（中英）与矩阵同步
- [ ] ONBOARDING 增加「读愿景 → 配 fetch_url / MCP → doctor → run」路径图

## L1 — 官方能力环（体验）

### 网络与只读 HTTP

- [x] 内置 **`fetch_url`**：HTTPS GET、主机白名单、响应体大小上限、超时；默认关闭 + 权限默认 `deny`；配置见 `cai-agent.toml` `[fetch_url]`、`[permissions].fetch_url`
- [ ] 可选：跟随重定向次数可配置、响应仅 `text/*` 硬拒绝二进制（当前为截断文本提示）
- [ ] 可选：DNS 解析后 SSRF 深度防护（当前：字面 IP 私网段拒绝 + 依赖白名单）
- [x] MCP 替代路径说明：[MCP_WEB_RECIPE.zh-CN.md](MCP_WEB_RECIPE.zh-CN.md)

### 工具与 Notebook

- [ ] Notebook 单元读写工具或 MCP 认证路径
- [ ] 与官方工具分类对齐的 **工具注册表文档**（自动生成自 `tools.py`）

### 任务与 UI

- [x] `run` / `continue` 等 JSON 输出增加 **`run_schema_version`** 与 **`events`** 信封（与 `workflow` 的 `events` 风格对齐）
- [x] `observe` 聚合 `run.*` 事件计数并与落盘会话对齐；`sessions --json` 默认附带 `events_count` / `task_id` 等摘要（无需 `--details`）
- [ ] 任务看板或 TUI 只读面板（P1）

### 计划与子 Agent

- [x] `plan --json` 稳定 schema（含成功 `ok: true` 与失败 `goal_empty` / `llm_error`）
- [x] `stats --json` 与 `observe` 对齐的 `run_events_total` 及 `session_summaries`
- [ ] 子 Agent 标准 IO schema（与 `agents/` 模板字段对齐）

## L2 — 架构完备度

### 状态与观测

- [ ] 会话文件 `version` 字段与 `run_schema_version` 对齐策略
- [ ] 结构化进度流：`graph` 中 `progress` 回调写入 ring buffer 供 `observe` 聚合

### 上下文与成本

- [ ] compact 触发与 `cost budget` 联动自动化（规则表）
- [ ] 模型路由建议（配置或启发式）

### 钩子

- [x] `hooks.json` 的 `event` 与 CLI 对齐：`session_*`、`workflow_*`、`quality_gate_*`、`security_scan_*`、`memory_*`、`export_*`、`observe_*`、`cost_budget_*`（见 [hooks/README.md](../hooks/README.md)）；自动执行 hook 脚本仍待办
- [本轮已落地] hook 执行结果可观测增强：CLI 非 JSON 输出会显示每个 hook 的 `ok/blocked/error/skipped` 摘要（不再仅打印 hook id）

## L3 — 治理与跨 harness

### 记忆

- [x] `memory/entries.jsonl` 行级 **schema v1** 校验（`cai_agent/schemas/memory_entry_v1.schema.json` + 写入前 Python 校验）
- [ ] 记忆 TTL/置信度策略与 `memory prune` 规则文档化
- [本轮已落地] `memory nudge` schema 升级到 `1.1`：增加 `threshold_policy`、`risk_score`、`trend`，并保持 `severity/actions` 兼容字段
- [ ] `memory extract` 可选 LLM 结构化抽取

### 质量与安全

- [ ] `quality-gate` 多语言栈模板（前端 monorepo）
- [ ] `security-scan` 规则与 CI 徽章示例
- [本轮已落地] `release-ga --json` 门禁聚合：统一汇总 quality-gate / security-scan / token 预算 / 会话失败率，并给出 `state=pass|warn|fail` 与门禁明细
- [本轮已落地] `release-ga` 扩展门禁：支持 `--with-doctor` 与 `--with-memory-nudge --memory-max-severity`，可把 doctor 健康检查与记忆严重度纳入 GA 判定
- [本轮已落地] `run_command` 高危命令审批策略：`[permissions].run_command_approval_mode=block_high_risk|allow_all` 与 `run_command_high_risk_patterns`

## 本轮已完成增量（补记）

- [本轮已落地] TUI 常用命令模板快捷入口：`/fix-build`、`/security-scan`
- [本轮已落地] Scheduler 任务模型增强：`depends_on` 依赖链、`retry_max_attempts/retry_backoff_sec` 重试策略、`.cai-schedule-audit.jsonl` 审计日志
- [本轮已落地] `schedule daemon --execute` 与 `run-due --execute` 行为对齐（重试+审计+attempts 输出）
- [本轮已落地] Recall Loop 增强：`recall` schema `1.1`、混合排序（recency/hit_strength/keyword_density）、行级 `score/score_breakdown`
- [本轮已落地] Recall 指标基准入口：`recall-index benchmark`（索引检索 vs 直扫检索耗时、加速比）
- [本轮已落地] Memory Loop 治理策略增强：`memory prune` 支持 `--min-confidence` / `--max-entries`，输出按原因统计（`expired`/`low_confidence`/`overflow`）
- [本轮已落地] Workflow 子代理编排增强：step 级 `parallel_group` 并发、`workflow.parallel_group.completed` 事件、`merge_confidence` 汇总
- [本轮已落地] Subagents 标准 IO 输出增强：`workflow` 结果新增 `subagent_io_schema_version=1.0`、`merge` 结构体（strategy/decision/confidence/conflicts/parallel_groups_count），并在每步 `protocol` 中补充 `schema_version=1.0`
- [本轮已落地] 发布门禁增强：`release-ga` 支持 `doctor` 健康检查与 `memory nudge` 严重度阈值（`--with-doctor`、`--with-memory-nudge`、`--max-memory-severity`）
- [本轮已落地] Observability 报表增强：新增 `observe-report`，基于 `observe` 聚合输出标准报表并按阈值生成 alerts（`state=pass|warn|fail`）
- [本轮已落地] Gateway MVP（Telegram）会话映射：新增 `gateway telegram bind|get|list|unbind`，支持 `chat_id+user_id -> session_file` 的持久化映射（默认 `.cai/gateway/telegram-session-map.json`）
- [本轮已落地] Gateway MVP（Telegram）update 解析入口：新增 `gateway telegram resolve-update`，可从 update JSON 提取 `chat_id/user_id` 并自动创建/复用映射（`--create-missing` + `--session-template`）
- [本轮已落地] Gateway MVP（Telegram）Webhook 入口：新增 `gateway telegram serve-webhook`，提供本地 HTTP `/telegram/update` 接收、映射解析/自动创建与 JSONL 事件日志落盘

### 导出与生态

- [ ] `export` 维度与 ECC 目录结构 diff 报告
- [ ] 选择性安装或「技能包」manifest（参考 ECC install-plan 思路）

## 验收习惯（与发布门禁一致）

每版本至少：

1. 更新 [PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md) 一行状态或备注；
2. 本表对应小节勾选或注明延期原因；
3. 运行 `pytest`（`cai-agent` 包）与 `cai-agent doctor`。

---

**说明**：本总册刻意保留大量未勾选项作为 backlog；工程节奏仍以 [ROADMAP_EXECUTION.zh-CN.md](ROADMAP_EXECUTION.zh-CN.md) 的 P0–P2 为 sprint 单位，避免无边界并行。
