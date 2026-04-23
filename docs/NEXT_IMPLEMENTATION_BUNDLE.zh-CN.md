# 补齐方案总册（执行清单与长期 backlog）

本文档在「三源融合完全体」愿景下，给出 **尽可能长的可执行补齐面**：已在本轮落地的条目会标明 **[本轮已落地]**，其余按优先级供后续迭代勾选。

## 0. 文档与产品基线

- [本轮已落地] 愿景与分层验收：[PRODUCT_VISION_FUSION.zh-CN.md](PRODUCT_VISION_FUSION.zh-CN.md)
- [本轮已落地] Parity 矩阵与发版约定：[PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md)
- [本轮已落地] 每个版本更新 CHANGELOG（中英）与矩阵同步（**`CHANGELOG.md` / `CHANGELOG.zh-CN.md` §0.7.0** 已记本轮条目）
- [本轮已落地] ONBOARDING：**[`ONBOARDING.zh-CN.md`](ONBOARDING.zh-CN.md)**「读愿景 → 配 fetch_url / MCP → doctor → run」路径

## L1 — 官方能力环（体验）

### 网络与只读 HTTP

- 内置 `**fetch_url`**：HTTPS GET、主机白名单、响应体大小上限、超时；默认关闭 + 权限默认 `deny`；配置见 `cai-agent.toml` `[fetch_url]`、`[permissions].fetch_url`
- [本轮已落地] **`fetch_url` 跟随重定向次数**：**`[fetch_url].max_redirects`**（**1–50**，默认 **20**）或 **`CAI_FETCH_URL_MAX_REDIRECTS`**；`httpx.Client(max_redirects=…)`；**`doctor`** JSON/文本展示 **`fetch_url_max_redirects`**
- 可选：响应仅 `text/*` 硬拒绝二进制（当前为截断文本提示）
- [本轮已落地] **`fetch_url` 解析后 SSRF / 反 DNS rebinding**：`getaddrinfo` 后对解析 IP 做私网/本机/链路本地等拒绝；内网解析显式 **`[fetch_url].allow_private_resolved_ips`** / **`CAI_FETCH_URL_ALLOW_PRIVATE_RESOLVED_IPS`**；**`doctor`** 展示对应开关
- MCP 替代路径说明：[MCP_WEB_RECIPE.zh-CN.md](MCP_WEB_RECIPE.zh-CN.md)

### 工具与 Notebook

- Notebook 单元读写工具或 MCP 认证路径
- [本轮已落地] 与官方工具分类对齐的 **工具注册表文档**：**[`docs/TOOLS_REGISTRY.zh-CN.md`](TOOLS_REGISTRY.zh-CN.md)**（13 工具）由 **`scripts/gen_tools_registry_zh.py`** 根据 **`cai_agent/tools_registry_doc.py`** 的 **`BUILTIN_TOOLS_DOC_ROWS`** 生成；**`tools.DISPATCH_TOOL_NAMES`** 与元数据由 **`test_tools_registry_doc_sync.py`** 校验；CI **`gen_tools_registry_zh.py --check`**

### 任务与 UI

- [本轮已落地] `run` / `continue` 等 JSON：**`run_schema_version`=`1.1`**，**`events`** 为 **`run_events_envelope_v1`**（与 `workflow` 事件风格对齐）；**`cai_agent.session_events`**
- [本轮已落地] `observe` 聚合 `run.*` 事件计数并与落盘会话对齐；`sessions --json` 为 **`sessions_list_v1`**，**`sessions[]`** 默认附带 **`events_count`** / **`task_id`** 等（**`normalize_session_run_events`**）
- [本轮已落地] TUI 只读任务看板：**`/tasks`**、**`Ctrl+B`**（**`tui_task_board.py`**）

### 计划与子 Agent

- [本轮已落地] `plan --json` 稳定 schema（失败 **`goal_empty`** 含 **`task:null`**；各分支含 **`plan_schema_version`**）
- [本轮已落地] `stats --json` 与 `observe` 对齐的 **`run_events_total`** 及 **`session_summaries`**
- [本轮已落地] 子 Agent 标准 IO：**`subagent_io_schema_version`=`1.1`**，**`agent_template_id`** + 可选 **`rpc_step_*`**（与 **`agents/`** 对齐）

## L2 — 架构完备度

### 状态与观测

- [本轮已落地] **`insights --json --cross-domain`**：**`insights_cross_domain_v1`** 增加 **`recall_hit_rate_metric_kind`/`recall_hit_rate_metric_note`** 与 **`recall_hit_rate_trend[]`** 行级 **`metric_kind`**，避免将索引子串探测与 **`recall`** 查询命中率混淆（S7-03 诚实标注）
- [本轮已落地] 会话落盘与 **`run_schema_version`**（当前 **`1.1`**）对齐；**`session_events.wrap_run_events`**
- [本轮已落地] 结构化进度流：**`progress_ring.py`** + **`graph._emit`** 写入 ring；**`run --json`** 含 **`progress_ring`** 摘要

### 上下文与成本

- [本轮已落地] compact 与 **`cost_budget_max_tokens`** 联动（约 **85%** 阈值追加成本提示）
- [本轮已落地] 模型路由建议：**`models suggest`** → **`models_suggest_v1`**

### 钩子

- [本轮已落地] `hooks.json` 的 **`event`** 与 CLI 对齐（见 [hooks/README.md](../hooks/README.md)）；**`script`** + **`command`** 实跑 **`hooks run-event`**（非 **`--dry-run`**）
- [本轮已落地] hook 执行结果可观测增强：CLI 非 JSON 输出会显示每个 hook 的 `ok/blocked/error/skipped` 摘要（不再仅打印 hook id）

## L3 — 治理与跨 harness

### 记忆

- [本轮已落地] `memory/entries.jsonl` 行级校验 CLI：**`memory validate-entries`** → **`memory_entries_file_validate_v1`**
- [本轮已落地] **`append_memory_entry` / `import_memory_entries_bundle` 写入前** 对已有 `entries.jsonl` 做与 validate-entries **同源**的整文件洁净性门禁（脏文件拒绝追加；救急：`CAI_MEMORY_ALLOW_DIRTY_ENTRIES_JSONL=1`）；**`memory extract`** 在写条目前同样预检并 JSON 报错退出
- [本轮已落地] 记忆 TTL/置信度策略与 **`memory prune`/`state`/`health` 对齐说明**：[MEMORY_TTL_CONFIDENCE_POLICY.zh-CN.md](MEMORY_TTL_CONFIDENCE_POLICY.zh-CN.md)
- [本轮已落地] `memory nudge` schema 升级到 `1.1`：增加 `threshold_policy`、`risk_score`、`trend`，并保持 `severity/actions` 兼容字段
- [本轮已落地] `memory extract --structured` 可选 LLM 结构化抽取（mock 回退启发式）

### 质量与安全

- [本轮已落地] `quality-gate` 前端 monorepo：**`CAI_QG_FRONTEND_MONOREPO=1`** → **`npm run -ws --if-present lint`**
- [本轮已落地] `security-scan --badge`：**`security_badge_v1`**（shields.io 兼容）
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
- [本轮已落地] Subagents 标准 IO 输出增强：`workflow` 结果 **`subagent_io_schema_version`=`1.1`**（每步 **`agent_template_id`** + 可选 **`rpc_step_*`**）、`merge` 结构体（strategy/decision/confidence/conflicts/parallel_groups_count）；历史 **`1.0`** 负载仍可能被旧会话引用
- [本轮已落地] 发布门禁增强：`release-ga` 支持 `doctor` 健康检查与 `memory nudge` 严重度阈值（`--with-doctor`、`--with-memory-nudge`、`--max-memory-severity`）
- [本轮已落地] Observability 报表增强：新增 `observe-report`，基于 `observe` 聚合输出标准报表并按阈值生成 alerts（`state=pass|warn|fail`）
- [本轮已落地] Gateway MVP（Telegram）会话映射：新增 `gateway telegram bind|get|list|unbind`，支持 `chat_id+user_id -> session_file` 的持久化映射（默认 `.cai/gateway/telegram-session-map.json`）
- [本轮已落地] Gateway MVP（Telegram）update 解析入口：新增 `gateway telegram resolve-update`，可从 update JSON 提取 `chat_id/user_id` 并自动创建/复用映射（`--create-missing` + `--session-template`）
- [本轮已落地] Gateway MVP（Telegram）Webhook 入口：新增 `gateway telegram serve-webhook`，提供本地 HTTP `/telegram/update` 接收、映射解析/自动创建与 JSONL 事件日志落盘
- [本轮已落地] Gateway MVP（Telegram）Webhook 执行联动：`serve-webhook` 支持 `--execute-on-update` 与 `--goal-template`，可在 update 解析成功后触发执行链并写入执行摘要（`answer_preview`）
- [本轮已落地] Gateway MVP（Telegram）Webhook 回发闭环：`serve-webhook` 支持 `--reply-on-execution` + `--telegram-bot-token` + `--reply-template`，执行完成后可自动调用 Telegram `sendMessage` 回传结果并记录回发状态
- [本轮已落地] Memory Loop 状态机固化：新增 `memory state`（`active/stale/expired` 分布评估）、`memory list --with-state` 状态视图、`memory prune --drop-non-active` 基于状态机的清理路径
- [本轮已落地] Release GA 门禁矩阵增强：`release-ga` 新增 `--with-memory-state`，支持基于 memory 状态机的 `stale/expired` 占比门禁（`--memory-max-stale-ratio` / `--memory-max-expired-ratio`），并可配置状态判定阈值（`--memory-state-stale-days` / `--memory-state-stale-confidence`）

## A 部分补齐（2026-04-23，§22–§26）

- [本轮已落地] **§22 PII 专项扫描**：`pii-scan [--dir PATH] [--json]` 检测信用卡/CN 身份证/手机号/邮箱/JWT/SSN 等 PII 信息；`pii_scan_result_v1` schema；`test_pii_scan.py`（11 cases）
- [本轮已落地] **§23 RPC 标准 IO + 内置工作流模板**：`RpcStepInput` / `RpcStepOutput` TypedDict（`rpc_step_input_v1` / `rpc_step_output_v1`）；`workflow --templates` 列出内置模板；`workflow --template <name> --goal <text>` 执行内置模板；三套内置模板：`explore-implement-review`、`security-audit`、`parallel-research`；`test_workflow_templates_rpc.py`（14 cases）
- [本轮已落地] **§24 Discord Bot Polling MVP**：`gateway discord serve-polling [--token TOKEN] [--channel CHANNEL_ID] [--poll-interval N]`；bind/unbind/get/list/allow/deny 映射管理；`gateway_discord.py`；`test_gateway_discord_slack_cli.py`（19 cases）
- [本轮已落地] **§24 Slack Events API Webhook MVP**：`gateway slack serve-webhook [--signing-secret S] [--bot-token T] [--host H] [--port P]`；HMAC 签名验证；bind/allow 映射管理；`gateway_slack.py`；`gateway platforms list --json` 中 Discord/Slack 状态升级为 `mvp`
- [本轮已落地] **§25 技能自进化闭环**：`auto_extract_skill_after_task(..., settings=...)` 在具备 **API key** 且非 **mock** 时经 **`chat_completion_by_role`** 生成 Markdown 草稿（**`draft_method`=`llm`**；失败回退 **`template`**）；否则仍为占位模板；`skills hub serve [--host H] [--port P]` HTTP 运行时分发（`GET /manifest`、`GET /skill/<name>`）；`test_skills_auto_extract_hub_serve.py` 已扩 case
- [本轮已落地] **§26 运营面板 HTML 导出**：`ops dashboard --format html [-o FILE]` 生成自包含单文件 HTML 仪表盘（KPI 卡片、调度 SLA 表、Top 工具表）；`build_ops_dashboard_html(payload)` 函数；`test_ops_dashboard_html.py`（10 cases）

### 导出与生态

- [本轮已落地] `export --ecc-diff`：**`export_ecc_dir_diff_v1`**（源 vs **`.cursor/cai-agent-export`**）
- [本轮已落地] 选择性安装：**`skills hub install`**（manifest + **`--only`** / **`--dry-run`**）

## B 部分补齐（0.7.0，2026-04-23）

与 **`CHANGELOG.md` / `CHANGELOG.zh-CN.md` §0.7.0** 及 **`PRODUCT_PLAN.zh-CN.md` §〇** 对齐的增量：**`session_events`**（**`run_events_envelope_v1`**）、TUI **`/tasks`**、**`hooks` `script`**、**`memory validate-entries` / `extract --structured`**、**`user_model` `behavior_extract`**、**`export --ecc-diff`**、**`skills hub install`**、**`models suggest`**、**`security-scan --badge`**、**`subagent_io_schema_version`=`1.1`**、**`progress_ring`**、**`doctor` `.cai/` 健康**、**`CAI_SKILLS_AUTO_SUGGEST`**、**`CAI_QG_FRONTEND_MONOREPO`** 等；单测 **`pytest cai-agent/tests`** 当前 **505 passed** 量级。

## 验收习惯（与发布门禁一致）

每版本至少：

1. 更新 [PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md) 一行状态或备注；
2. 本表对应小节勾选或注明延期原因；
3. 运行 `pytest`（`cai-agent` 包）与 `cai-agent doctor`。

---

**说明**：本总册刻意保留大量未勾选项作为 backlog；工程节奏仍以 [ROADMAP_EXECUTION.zh-CN.md](ROADMAP_EXECUTION.zh-CN.md) 的 P0–P2 为 sprint 单位，避免无边界并行。