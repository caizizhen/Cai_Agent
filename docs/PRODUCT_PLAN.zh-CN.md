# CAI Agent 产品计划（唯一执行清单）

本文件是 **开发与测试进度的唯一权威表**。
**Hermes 冻结阶段 Story 级 AC** 见 [`HERMES_PARITY_BACKLOG.zh-CN.md`](archive/legacy/HERMES_PARITY_BACKLOG.zh-CN.md)；**冻结阶段 Story 勾选状态** 见 [`HERMES_PARITY_PROGRESS.zh-CN.md`](archive/legacy/HERMES_PARITY_PROGRESS.zh-CN.md)。

**非本表职责**：愿景 [`PRODUCT_VISION_FUSION.zh-CN.md`](PRODUCT_VISION_FUSION.zh-CN.md)、缺口 [`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md)、矩阵 [`PARITY_MATRIX.zh-CN.md`](PARITY_MATRIX.zh-CN.md)、架构 [`ARCHITECTURE.zh-CN.md`](ARCHITECTURE.zh-CN.md)。**近期实现 vs 未完成的一页摘要**（中英）：[`IMPLEMENTATION_STATUS.zh-CN.md`](IMPLEMENTATION_STATUS.zh-CN.md) / [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md)。

---

## 〇、已完成功能 vs 未完成功能（总览）

> 下表按 **产品能力** 归纳，便于对外说明；**与 §二 编号一一对应** 的索引见 §二。

### 〇.1 已交付（主线已合入）

| 领域 | 已具备能力（摘要） |
|------|---------------------|
| **核心 CLI** | `plan` / `run` / `continue` / `command` / `workflow`；**`run`/`continue`/… `--json`**：`run_schema_version`=`1.1`，**`events`** 为 **`run_events_envelope_v1`**（`schema_version` + **`items[]`**）；`workflow` JSON（含 `task_id`、`parallel_group`、**`subagent_io_schema_version`=`1.1`**、`on_error`、预算字段、root **`quality_gate`** + 可选 **`post_gate`** 等）；`init`、**`doctor`**（含 **`.cai/`** 网关映射与 **`hooks.json`** 健康摘要）、`release-ga` |
| **工作区与安全** | 读写/搜索/Git、沙箱路径、`run_command` 白名单+高危模式二次确认、`fetch_url`（白名单 + 权限）；**`pii-scan`**（信用卡/身份证/手机号/JWT 等 PII 专项扫描，`pii_scan_result_v1`） |
| **质量与 CI** | `fix-build`、**`security-scan --json`** + **`security-scan --badge`**（**`security_badge_v1`**，shields.io 兼容）、`quality-gate`（**`CAI_QG_FRONTEND_MONOREPO=1`** 时自动追加 **`npm run -ws --if-present lint`**） |
| **扩展发现** | `plugins --json`、`commands` / `agents` 列表 JSON |
| **模型与 UI** | `[[models.profile]]`、`cai-agent models`、**`models onboarding`**（**`model_onboarding_flow_v1`** 接入命令链）、**`models suggest`**（**`models_suggest_v1`**）、**`models routing-test`**（**`routing_explain_v1`** + **`model_fallback_candidates_v1`**，explain-only fallback）、统一 **`ModelResponse`** / **`model_response_v1`**；TUI **`/models`**、**`/tasks`**（**`Ctrl+B`** 只读任务看板，见 **`tui_task_board.py`**）；会话落盘含 `profile` |
| **可观测与看板** | `stats`、`sessions`、`observe`、`observe-report`、`observe export`、`board --json`、`insights`（含 `--cross-domain`）、**`ops dashboard --format json/text/html`**（聚合 board + 调度 SLA + 成本 rollup；`--format html` 生成单文件 HTML 仪表盘） |
| **记忆与本能** | `memory extract/list/search/prune`、`instincts`、`nudge`、`nudge-report`、**`memory health`**（评分 / grade / `--fail-on-grade`）、import/export、状态机、prune 策略、**`memory user-model`**（**`honcho_parity: behavior_extract`**：工具频次、错误率、近期 goal 摘要；可叠加 **`.cai/user-model.json`**）、**`memory validate-entries`**（**`memory_entries_file_validate_v1`**）、**`memory extract --structured`**；S2 freshness / conflict / coverage / nudge-report 与 health 联动等 |
| **跨会话** | `insights`、`recall`（含 sort、`no_hit_reason`、schema 演进）、`recall-index`（build/refresh/doctor/info/benchmark 等） |
| **调度** | `schedule` CRUD、`daemon`、`run-due`、依赖与环检测、审计 JSONL（S4-04 七种事件）、跨轮次重试退避、并发上限、`schedule stats`（SLA） |
| **Hooks** | `hooks` CLI、`hooks list`、`hooks run-event`（**`--dry-run`** / 实跑 JSON **`hooks_run_event_result_v1`**）；**`hooks.json`** 支持 **`script`**（`.py`/`.sh`/`.ps1`/…）与 **`command[]`**，路径逃逸防护；与 runner 对齐 |
| **LLM 健壮性** | HTTP 重试、`max_http_retries`、Transport / 畸形 JSON 等重试路径；**`compact_hint`** 与 **`cost_budget_max_tokens`** 联动（约 **85%** 预算时追加成本提示） |
| **Gateway** | **`gateway telegram`** 生产路径（映射 / bind / webhook / continue-hint 等）；**`gateway discord`** Bot Polling MVP（`serve-polling` + bind/allow）；**`gateway slack`** Events API Webhook MVP（`serve-webhook` + bind/allow）；**`gateway teams`** Bot Framework Activity Webhook MVP（映射 / allow / health / manifest / serve-webhook）；**`gateway platforms list --json`**（Discord/Slack/Teams 状态为 `mvp`）；**`gateway status --json`**；**`gateway prod-status --json`**（`gateway_production_summary_v1`） |
| **导出** | `export` → Cursor / Codex / OpenCode（基础 manifest）；**`export --ecc-diff`**（**`export_ecc_dir_diff_v1`**，源目录 vs **`.cursor/cai-agent-export`** 差异报告，不写盘） |
| **契约与退出码** | [`docs/schema/README.zh-CN.md`](schema/README.zh-CN.md) **§ S1-02 / S1-03**；`api serve` 已含 OpenAI-compatible **`/v1/models`** 与非流式 / SSE **`/v1/chat/completions`**；[`TOOLS_REGISTRY.zh-CN.md`](TOOLS_REGISTRY.zh-CN.md)（13 工具与权限键）；`docs/schema/SCHEDULE_*.zh-CN.md`、[`SCHEDULE_AUDIT_JSONL.zh-CN.md`](schema/SCHEDULE_AUDIT_JSONL.zh-CN.md)；Browser provider `browser_provider_check_v1` / `browser_task_v1`；[`ONBOARDING.zh-CN.md`](ONBOARDING.zh-CN.md)；`scripts/smoke_new_features.py` 对主要命令 JSON **抽样** |
| **产品定案** | WebSearch / Notebook **MCP 优先**（[`WEBSEARCH_NOTEBOOK_MCP.zh-CN.md`](WEBSEARCH_NOTEBOOK_MCP.zh-CN.md)）；Browser automation **MCP first**（[`BROWSER_MCP.zh-CN.md`](BROWSER_MCP.zh-CN.md)、[`BROWSER_PROVIDER_RFC.zh-CN.md`](BROWSER_PROVIDER_RFC.zh-CN.md)） |
| **技能 Hub** | **`skills hub manifest --json`**；**`skills hub suggest`**；**`skills hub install`**（manifest 选择性安装，`--only`/`--dry-run`）；**`skills hub serve`**；**`auto_extract_skill_after_task`**；**`CAI_SKILLS_AUTO_SUGGEST=1`** 时在 **`session_end`** 后 dry-run 落盘演进草稿 |
| **子代理 / RPC** | `parallel_group`、**`subagent_io`**（**`subagent_io_schema_version`=`1.1`**，每步 **`agent_template_id`** 与可选 **`rpc_step_input`/`rpc_step_output`**）、`on_error`、预算控制；**RPC 标准 IO TypedDict**；**`agent_templates`** 与 **`workflow --templates`**（三套内置模板） |

### 〇.2 仍有差距或待演进（P2 方向）

| 领域 | 说明 | 对应 §二 |
|------|------|----------|
| **运营 Web UI** | `ops dashboard --format html` 已生成静态单文件 HTML；动态 HTTP 已支持只读 JSON/HTML/SSE；高级交互先收口为 `ops_dashboard_interactions_v1` dry-run 预览契约，真实写操作仍需后续鉴权/应用边界 | **26（后续）** |
| **Gateway 全量** | Discord/Slack/Teams 已有 MVP；`gateway_production_summary_v1` 已提供本地生产状态摘要；Slash Commands 深化、频道监控、多工作区联邦仍为后续 Sprint | **24（后续）** |
| **运行后端（P2）** | Docker 已产品化（`image` / `volume_mounts` / limits / doctor）；SSH 已产品化（key / known_hosts / timeout / audit）；Modal / Daytona 等「休眠即省钱」后端未纳入默认交付 | **§一** |
| **语音 / 官方 Bridge** | 明确 **OOS** 或走 MCP | **§一** |

---

## 一、与三上游仓库的能力差（摘要）

| 来源 | 目标能力 | 本仓当前状态 | 结论 |
|------|----------|--------------|------|
| `anthropics/claude-code` | 官方终端 Agent 的主体验：计划→执行→继续、工具、权限、MCP、TUI | 主链路已具备，WebSearch / Notebook / 安装体验仍有差距 | **部分完成** |
| `NousResearch/hermes-agent` | Profiles、API/server、gateway、voice、dashboard、memory providers、runtime backends | Hermes 34 Story 冻结版已收口；MODEL-P0 模型接入地基已完成（capabilities / health / onboarding / routing fallback / OpenAI-compatible API），OpenAPI / 管理化仍待继续 | **部分完成** |
| `affaan-m/everything-claude-code` | rules / skills / hooks / model-route / cross-harness / 生态资产治理 | 规则、技能、导出与兼容矩阵已有基础，资产化与安装叙事仍不足 | **部分完成** |

**说明**：

- `HERMES_PARITY_PROGRESS` 中的 **34/34** 代表“冻结版 Hermes 第一阶段完成”，不代表“当前最新 Hermes 产品面已全部同步”。
- 当前产品目标不再是单独对齐 Hermes，而是把这三条上游能力线整合成一个统一产品。

---

## 二、开发项索引（1–26）

| 顺序 | 开发项 | 状态 | 说明 / 证据 |
|------|--------|------|-------------|
| 1 | 核心 CLI：`plan` / `run` / `continue` / `command` / `workflow` | **完成** | README；`workflow_run_v1`、根级 `task_id` |
| 2 | 工作区工具 + 沙箱 + Shell 白名单 | **完成** | `sandbox.py`、`tools.py` |
| 3 | `fix-build`、`security-scan`（**`--json`** / **`--badge`**）、`quality-gate` | **完成** | 回归与 pytest；**`security_badge_v1`** |
| 4 | 插件发现 `plugins --json` | **完成** | |
| 5 | 多模型 profile、`models` CLI、**`models suggest`**、TUI `/models`/`/tasks`、`session` 含 `profile` | **完成** | **`models_suggest_v1`**；**`tui_task_board`** |
| 6 | `board --json` 与 `observe` 同源、`observe_schema_version` | **完成** | |
| 7 | `fetch_url` + MCP Web 配方 | **完成** | [`MCP_WEB_RECIPE.zh-CN.md`](MCP_WEB_RECIPE.zh-CN.md) |
| 8 | WebSearch/Notebook | **定案 MCP 优先** | [`WEBSEARCH_NOTEBOOK_MCP.zh-CN.md`](WEBSEARCH_NOTEBOOK_MCP.zh-CN.md) |
| 8b | Browser automation | **定案 MCP first / 契约已落地** | [`BROWSER_MCP.zh-CN.md`](BROWSER_MCP.zh-CN.md)、[`BROWSER_PROVIDER_RFC.zh-CN.md`](BROWSER_PROVIDER_RFC.zh-CN.md)；`tools browser-check --json`、`browser check/task --json` |
| 9 | 记忆 CLI 全家桶 + **`memory user-model`**（**`behavior_extract`**）+ **`validate-entries`** / **`extract --structured`** | **完成（持续演进）** | `memory.py`、`user_model.py`、`test_memory_*`、`test_memory_validate_entries_cli.py` |
| 10 | **S2-01** `memory health` | **完成** | `build_memory_health_payload`、`test_memory_health_cli.py`；PR #12 见 **§四** |
| 11 | `insights`、`recall`、`recall-index` | **完成** | |
| 12 | `schedule` / `daemon` / 依赖与审计 / stats / 重试 / 并发 | **完成** | S4-01～S4-05；见 PROGRESS |
| 13 | Hooks CLI + runtime（**`script`** + **`command`**、实跑 **`run-event`**） | **完成** | `hook_runtime.py`、`test_hooks_cli.py`、`test_hook_runtime.py` |
| 14 | LLM 传输重试、`max_http_retries` | **完成** | `test_llm_transport_error_retry.py` |
| 15 | `gateway telegram` + **`gateway platforms`** + **`gateway status`** + continue-hint 等 | **完成** | `test_gateway_telegram_cli.py` 等；平台矩阵见 **§〇.1** |
| 16 | `export` 多 harness + **`export --ecc-diff`** | **完成（基础）** | **`export_ecc_dir_diff_v1`** |
| 17 | Hermes **S2-02～S2-05** | **完成** | 与 PROGRESS ✅ 表一致 |
| 18 | **S1-02** JSON schema 契约 | **完成** | 索引：[`docs/schema/README.zh-CN.md`](schema/README.zh-CN.md) **§ S1-02**；调度/审计长文见 `docs/schema/SCHEDULE_*.zh-CN.md`；冒烟见 `scripts/smoke_new_features.py` |
| 19 | **S1-03** exit 0/2/130 | **完成** | 同上 **§ S1-03** |
| 20 | **S4-04** 审计 JSONL 七种事件 | **完成** | [`SCHEDULE_AUDIT_JSONL.zh-CN.md`](schema/SCHEDULE_AUDIT_JSONL.zh-CN.md) |
| 21 | **`task_id` 贯通** + **`ops dashboard` JSON** | **完成** | `run`/`continue`/`workflow`/`sessions`/`observe` |
| 22 | 敏感扫描、高危命令二次确认 | **完成** | `security-scan --json`（密钥扫描）+ **`pii-scan`**（`pii_scan_result_v1`，覆盖信用卡/身份证/手机号/JWT/SSN）+ `run_command_approval_mode` 高危二次确认；`test_pii_scan.py`（11 cases） |
| 23 | 子 Agent IO、编排模板 | **完成** | `parallel_group` + **`subagent_io_schema_version`=`1.1`**（**`agent_template_id`** + 可选 **`rpc_step_*`**）+ `on_error` + 预算 + root **`quality_gate`** / **`post_gate`**（S5-01～S5-04）；**`workflow --templates`**；`test_workflow_templates_rpc.py`（14 cases） |
| 24 | 多平台 Gateway 对齐 Hermes | **完成（MVP）** | `gateway_platforms_v1`（Discord/Slack/Teams 为 `mvp`）；**`gateway discord serve-polling`**（Bot Polling）；**`gateway slack serve-webhook`**（Events API Webhook）；**`gateway teams serve-webhook`**（Bot Framework Activity Webhook + manifest）；bind/unbind/get/list/allow 完整映射管理；**`gateway prod-status --json`** 输出 `gateway_production_summary_v1`；`test_gateway_discord_slack_cli.py` / `test_gateway_lifecycle_cli.py` |
| 25 | 技能自进化 / Hub | **完成** | `skills_hub_manifest_v1` + `skills_evolution_suggest_v1` + **`skills hub install`**；**`auto_extract_skill_after_task`**；**`skills hub serve`**；**`CAI_SKILLS_AUTO_SUGGEST`**；`test_skills_auto_extract_hub_serve.py`（8 cases） |
| 26 | 运营面板 | **完成（MVP）** | `ops_dashboard_v1`（JSON）；**`ops dashboard --format html`** 单文件 HTML 仪表盘；**`ops serve`** 只读 JSON/HTML/SSE；**`ops_dashboard_interactions_v1`** 支持 schedule reorder / gateway bind-edit dry-run 预览；`test_ops_dashboard_html.py` / `test_ops_http_server.py` |

---

## 三、测试项（测什么、测到哪里）

| 顺序 | 测试范围 | 类型 | 进度 | 证据 / 下一步 |
|------|----------|------|------|----------------|
| T1 | `pytest cai-agent/tests` | 自动化 | **完成** | **2026-04-26** 全量回归：**826 passed**，**3 subtests passed**（Windows / Python 3.12）；含 **`api serve`** OpenAI-compatible chat 契约测试、Gateway（含 Teams / prod-status）、Runtime docker/SSH、插件兼容 snapshot、`models routing-test` fallback candidates、`models onboarding` preset 校验与 capabilities hint、`model_onboarding_flow_v1` / `provider_registry_v1` / `model_capabilities_v1` / `model_capabilities_list_v1` / `model_response_v1` / `model_fallback_candidates_v1` / `routing_explain_v1` / `doctor_model_gateway_v1` / `api_models_capabilities_v1` / `api_openai_models_v1` / `api_openai_chat_completion_v1` / `api_openai_chat_completion_chunk_v1` schema、模型接入 runbook 可发现性、TUI model panel capabilities/health/cost 行、memory provider、ops dashboard interactions、repair/feedback bundle、**`test_profile_clone_alias_cli`**、**`test_ecc_ingest_schema_snapshots`**、**feedback export/bundle 脱敏** 等） |
| T2 | `python scripts/run_regression.py` | 自动化 | **完成** | `PYTHONPATH=cai-agent/src` + `python -m cai_agent`；`docs/qa/runs/regression-*.md` |
| T3 | Hermes 总测计划 | 文档 | **已写** | [`HERMES_PARITY_MASTER_TESTPLAN.zh-CN.md`](qa/HERMES_PARITY_MASTER_TESTPLAN.zh-CN.md) |
| T4 | Sprint2 memory health | 混合 | **已覆盖** | [`sprint2-memory-health-testplan.md`](qa/sprint2-memory-health-testplan.md) |
| T5 | Sprint3–8 专项 | 手工 | **计划已写** | `docs/qa/sprint3-recall-v2-testplan.md` … `sprint8-ga-testplan.md` |
| T6 | S3 TUI 模型面板 40 条 | 手工 | **计划已写** | [`s3-tui-model-panel-testplan.md`](qa/s3-tui-model-panel-testplan.md) |
| T7 | 发版 gate | 人工 | **部分完成** | `doctor`、Parity、CHANGELOG、schema 抽样 |

**冒烟子集**：`python scripts/smoke_new_features.py`（与 T2 同源入口）；详列命令与 schema 以 **schema README** 与脚本内校验为准。

---

## 三之二、进度统计与 QA 移交

> **横向索引**：[`DEVELOPMENT_PROGRESS_TRACKER.zh-CN.md`](archive/legacy/DEVELOPMENT_PROGRESS_TRACKER.zh-CN.md)（与本节 QA 说明互链）。

### 3.0 完成度（估算）

| 口径 | 计算方式 | 当前值（与 §二一致时更新） |
|------|----------|---------------------------|
| **§二 1–26 加权** | 「完成」「定案」「持续演进」各权 **1**；「部分完成」各 **0.5**；÷26 | **约 100%**（22完成 + 1定案 + 1持续演进 + 2MVP完成 = **26** → **26/26=100%**） |
| **Hermes 34 Story** | ✅ 数 ÷ 34 | 以 [`HERMES_PARITY_PROGRESS.zh-CN.md`](archive/legacy/HERMES_PARITY_PROGRESS.zh-CN.md) 首页表为准 |
| **T1** | pytest 全绿 | 同 §三 T1（**742** cases + **3** subtests，见上表证据列） |

### 3.1 §二 状态计数

| 状态 | 数量 | 编号 |
|------|------|------|
| **完成** | **24** | 1–7、10–26（其中 24/26 为 MVP 完成） |
| **定案** | **1** | 8 |
| **持续演进** | **1** | 9 |
| **部分完成** | **0** | — |
| **未开始** | **0** | — |

### 3.2 后续演进方向（当前 To-dos）

| 项 | 说明 |
|----|------|
| **Claude Code 线** | WebSearch / Notebook 的产品化路径、安装 / 更新体验、CLI/TUI 交互统一；**CC-03b** 见 RFC **`docs/rfc/CC_03B_MODEL_STATUS_UX.zh-CN.md`** |
| **Hermes 线** | Profiles、**`HM-02b` 最小 HTTP API**（**`cai-agent api serve`**，契约 **`docs/rfc/HM_02_MINIMAL_SERVER_CONTRACT.zh-CN.md`**）、多平台 gateway、voice、dashboard 高级交互、memory providers、runtime backends（docker/SSH 已产品化，云后端仍 OOS/条件立项） |
| **ECC 线** | rules / skills / hooks 的资产化、`model-route`、**`cost report` + compact 策略说明**、插件与跨 harness 深化 |
| **共享项** | 中英文文档同步、反馈闭环、发布闭环、OOS / MCP 备案机制 |
| **明确 OOS** | 依赖封闭企业能力的官方专属特性、默认多 CLI 套件模式 |

### 3.3 QA 移交顺序

| 序号 | 内容 | 说明 |
|------|------|------|
| QA-1 | T1 pytest | 每版必跑 |
| QA-2 | T2 回归 | 可设 `QA_SKIP_LOG=1` 不写 `runs/` |
| QA-3 | `smoke_new_features.py` | 与 T2 同源 CLI；退出码 0 且含 `NEW_FEATURE_CHECKS_OK` |
| QA-4～QA-8 | Hermes 总测、Sprint2～8、TUI、发版 gate | 见 §三与各 `docs/qa/*testplan.md` |

**回填**：在 `docs/qa/runs/` 追加回归 Markdown，或于 PROGRESS / TRACKER 记结论即可。

---

## 四、[PR #12](https://github.com/caizizhen/Cai_Agent/pull/12) 说明

| 项 | 说明 |
|----|------|
| **结论** | S2-01 能力已在 **`main`**；**勿合并** PR #12（历史 SHA 不一致）。 |
| **远端分支** | `cursor/hermes-s2-01-memory-health-9ed2` **已删**；请在 GitHub **Close** PR #12（*not planned* / *superseded*）。 |

---

## 五、分支策略

- **默认分支**：`main`，经 **PR** 合入。
- **少建长期 `cursor/*`**：单功能短分支，合并后删远端。
- **Hermes 迭代**：以 [`HERMES_PARITY_PROGRESS.zh-CN.md`](archive/legacy/HERMES_PARITY_PROGRESS.zh-CN.md) 认领 Story。

---

*文档版本：2026-04-24 — 在 A 部分（§22–§26）已合入基础上，同步 **0.7.0** 能力：`run_schema_version`/`run_events_envelope_v1`、TUI `/tasks`、`hooks` **`script`**、**`memory validate-entries`/`extract --structured`**、**`user_model` `behavior_extract`**、**`export --ecc-diff`**、**`skills hub install`**、**`models suggest`**、**`security-scan --badge`**、**`subagent_io_schema_version`=`1.1`**、**`progress_ring`**、**`doctor` `.cai/` 健康** 等；**`CHANGELOG.md` §0.7.0** 为英文权威条目，本表与 **`PARITY_MATRIX`** / **`ROADMAP_EXECUTION`** 对齐；**发行 tarball 版本号** 以 **`cai-agent/pyproject.toml`** / **`cai_agent.__version__`** 为准（若尚未 bump 至 0.7.0，以仓库实际为准）。*
