# CAI Agent 产品计划（唯一执行清单）

本文件是 **开发与测试进度的唯一权威表**。  
**Story 级 AC** 见 [`HERMES_PARITY_BACKLOG.zh-CN.md`](HERMES_PARITY_BACKLOG.zh-CN.md)；**Story 勾选状态** 见 [`HERMES_PARITY_PROGRESS.zh-CN.md`](HERMES_PARITY_PROGRESS.zh-CN.md)。

**非本表职责**：愿景 [`PRODUCT_VISION_FUSION.zh-CN.md`](PRODUCT_VISION_FUSION.zh-CN.md)、缺口 [`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md)、矩阵 [`PARITY_MATRIX.zh-CN.md`](PARITY_MATRIX.zh-CN.md)、架构 [`ARCHITECTURE.zh-CN.md`](ARCHITECTURE.zh-CN.md)。

---

## 〇、已完成功能 vs 未完成功能（总览）

> 下表按 **产品能力** 归纳，便于对外说明；**与 §二 编号一一对应** 的索引见 §二。

### 〇.1 已交付（主线已合入）

| 领域 | 已具备能力（摘要） |
|------|---------------------|
| **核心 CLI** | `plan` / `run` / `continue` / `command` / `workflow`；`workflow` JSON（含 `task_id`、`parallel_group`、`subagent_io`、`on_error`、预算字段等）；`init`、`doctor`、`release-ga` |
| **工作区与安全** | 读写/搜索/Git、沙箱路径、`run_command` 白名单、`fetch_url`（白名单 + 权限） |
| **质量与 CI** | `fix-build`、`security-scan --json`、`quality-gate` |
| **扩展发现** | `plugins --json`、`commands` / `agents` 列表 JSON |
| **模型与 UI** | `[[models.profile]]`、`cai-agent models`、TUI `/models`；会话落盘含 `profile` |
| **可观测与看板** | `stats`、`sessions`、`observe`、`observe-report`、`observe export`、`board --json`、`insights`（含 `--cross-domain`）、**`ops dashboard --json`**（聚合 board + 调度 SLA + 成本 rollup） |
| **记忆与本能** | `memory extract/list/search/prune`、`instincts`、`nudge`、`nudge-report`、**`memory health`**（评分 / grade / `--fail-on-grade`）、import/export、状态机、prune 策略、**`memory user-model`**（占位）；S2  freshness / conflict / coverage / nudge-report 与 health 联动等 |
| **跨会话** | `insights`、`recall`（含 sort、`no_hit_reason`、schema 演进）、`recall-index`（build/refresh/doctor/info/benchmark 等） |
| **调度** | `schedule` CRUD、`daemon`、`run-due`、依赖与环检测、审计 JSONL（S4-04 七种事件）、跨轮次重试退避、并发上限、`schedule stats`（SLA） |
| **Hooks** | `hooks` CLI、`hooks list`、`hooks run-event`（dry-run JSON）、与 runner 对齐 |
| **LLM 健壮性** | HTTP 重试、`max_http_retries`、Transport / 畸形 JSON 等重试路径 |
| **Gateway** | **`gateway telegram`** 生产路径（映射 / bind / webhook / continue-hint 等）；**`gateway platforms list --json`**（多平台目录：Telegram 等 **full**，Discord/Slack 等 **stub/planned**）；**`gateway status --json`** |
| **导出** | `export` → Cursor / Codex / OpenCode（基础 manifest） |
| **契约与退出码** | [`docs/schema/README.zh-CN.md`](schema/README.zh-CN.md) **§ S1-02 / S1-03**；`docs/schema/SCHEDULE_*.zh-CN.md`、[`SCHEDULE_AUDIT_JSONL.zh-CN.md`](schema/SCHEDULE_AUDIT_JSONL.zh-CN.md)；`scripts/smoke_new_features.py` 对主要命令 JSON **抽样** |
| **产品定案** | WebSearch / Notebook **MCP 优先**（[`WEBSEARCH_NOTEBOOK_MCP.zh-CN.md`](WEBSEARCH_NOTEBOOK_MCP.zh-CN.md)） |
| **技能 Hub（MVP）** | **`skills hub manifest --json`**；**`skills hub suggest`**（可选落盘演进建议稿） |

### 〇.2 未完成或仅部分交付（与 Hermes 全量 / 理想形态仍有差距）

| 领域 | 缺口说明 | 对应 §二 |
|------|----------|----------|
| **安全交互** | `security-scan` 已可用；**高危命令可配置的二次确认**、面向 prompt/文件的**敏感信息专项扫描**仍属增量 | **22** |
| **子代理 / RPC** | 已有 `parallel_group`、`subagent_io`、`on_error`、**workflow 内预算**；**RPC 级标准 IO**、更完整的「探索-实现-评审」模板仍待加强 | **23** |
| **多平台 Gateway** | **`gateway platforms`** 为目录 + 运行时信号 + **stub**；Discord/Slack 等 **真机 Bot 运行时**未等同 Hermes | **24** |
| **技能自进化** | 已有 **manifest / suggest**；**任务后自动提炼并写回 skills**、Skills Hub **运行时分发**未闭环 | **25** |
| **运营形态** | **`ops dashboard` 为 JSON**；**Web 可视化运营 UI**、队列拖拽类体验未做 | **26** |
| **运行后端（P2）** | Modal / Daytona 等「休眠即省钱」后端未纳入默认交付 | **§一** |
| **语音 / 官方 Bridge** | 明确 **OOS** 或走 MCP | **§一** |

---

## 一、与 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) 的能力差（摘要）

| 维度 | Hermes（上游） | 本仓 | 本表状态 |
|------|----------------|------|----------|
| 多平台网关 | 全渠道统一 gateway | Telegram **full** + `gateway platforms` **目录 + stub** | **部分完成** → **§二 24** |
| 技能自进化 | 自动生成 / 改进 skills、Hub | manifest + suggest；**无**自动闭环 | **部分完成** → **§二 25** |
| 定时与投递 | cron + 多平台投递 | `schedule` 系 **已对齐 MVP** | **完成** |
| 跨会话检索 | FTS5 + LLM 摘要等 | `recall` / `recall-index` / `insights` | **完成** |
| 记忆治理 | nudge、健康度、用户建模 | health / nudge / **`memory user-model`** 占位 | **部分完成** → **§二 9–10** |
| 子代理 / 并行 | 隔离子 agent、RPC | `workflow` 并行组 + **`subagent_io` + 错误策略 + 预算** | **部分完成** → **§二 23** |
| 运行后端 | Modal / Daytona 等 | 本机 + 配置为主 | **未开始（P2）** |
| 语音 / Bridge | 产品化 | **OOS / MCP** | **定案** |

---

## 二、开发项索引（1–26）

| 顺序 | 开发项 | 状态 | 说明 / 证据 |
|------|--------|------|-------------|
| 1 | 核心 CLI：`plan` / `run` / `continue` / `command` / `workflow` | **完成** | README；`workflow_run_v1`、根级 `task_id` |
| 2 | 工作区工具 + 沙箱 + Shell 白名单 | **完成** | `sandbox.py`、`tools.py` |
| 3 | `fix-build`、`security-scan`、`quality-gate` | **完成** | 回归与 pytest |
| 4 | 插件发现 `plugins --json` | **完成** | |
| 5 | 多模型 profile、`models` CLI、TUI `/models`、`session` 含 `profile` | **完成** | |
| 6 | `board --json` 与 `observe` 同源、`observe_schema_version` | **完成** | |
| 7 | `fetch_url` + MCP Web 配方 | **完成** | [`MCP_WEB_RECIPE.zh-CN.md`](MCP_WEB_RECIPE.zh-CN.md) |
| 8 | WebSearch/Notebook | **定案 MCP 优先** | [`WEBSEARCH_NOTEBOOK_MCP.zh-CN.md`](WEBSEARCH_NOTEBOOK_MCP.zh-CN.md) |
| 9 | 记忆 CLI 全家桶 + **`memory user-model`**（占位） | **完成（持续演进）** | `memory.py`、`__main__.py`、`test_memory_*` |
| 10 | **S2-01** `memory health` | **完成** | `build_memory_health_payload`、`test_memory_health_cli.py`；PR #12 见 **§四** |
| 11 | `insights`、`recall`、`recall-index` | **完成** | |
| 12 | `schedule` / `daemon` / 依赖与审计 / stats / 重试 / 并发 | **完成** | S4-01～S4-05；见 PROGRESS |
| 13 | Hooks CLI + runtime | **完成** | `hook_runtime.py`、`test_hooks_cli.py` |
| 14 | LLM 传输重试、`max_http_retries` | **完成** | `test_llm_transport_error_retry.py` |
| 15 | `gateway telegram` + **`gateway platforms`** + **`gateway status`** + continue-hint 等 | **完成** | `test_gateway_telegram_cli.py` 等；平台矩阵见 **§〇.2** |
| 16 | `export` 多 harness | **完成（基础）** | |
| 17 | Hermes **S2-02～S2-05** | **完成** | 与 PROGRESS ✅ 表一致 |
| 18 | **S1-02** JSON schema 契约 | **完成** | 索引：[`docs/schema/README.zh-CN.md`](schema/README.zh-CN.md) **§ S1-02**；调度/审计长文见 `docs/schema/SCHEDULE_*.zh-CN.md`；冒烟见 `scripts/smoke_new_features.py` |
| 19 | **S1-03** exit 0/2/130 | **完成** | 同上 **§ S1-03** |
| 20 | **S4-04** 审计 JSONL 七种事件 | **完成** | [`SCHEDULE_AUDIT_JSONL.zh-CN.md`](schema/SCHEDULE_AUDIT_JSONL.zh-CN.md) |
| 21 | **`task_id` 贯通** + **`ops dashboard` JSON** | **完成** | `run`/`continue`/`workflow`/`sessions`/`observe`；**Web Dashboard** 仍为后续 |
| 22 | 敏感扫描、高危命令二次确认 | **部分完成** | **`security-scan --json`** 已合冒烟；**二次确认策略**见 [`NEXT_IMPLEMENTATION_BUNDLE.zh-CN.md`](NEXT_IMPLEMENTATION_BUNDLE.zh-CN.md) |
| 23 | 子 Agent IO、编排模板 | **部分完成** | **`parallel_group` + `subagent_io` + `on_error` + 预算**（S5-01～S5-04）；**RPC 标准 IO** 仍增量 |
| 24 | 多平台 Gateway 对齐 Hermes | **部分完成（MVP）** | **`gateway_platforms_v1`**；真机 Discord/Slack 等仍待 Sprint |
| 25 | 技能自进化 / Hub | **部分完成（MVP）** | **`skills_hub_manifest_v1` + `skills_evolution_suggest_v1`**；**自动写 skills** 仍待 Sprint |
| 26 | 运营面板 | **部分完成（MVP）** | **`ops_dashboard_v1`**（JSON）；**Web 运营 UI** 为 P2 |

---

## 三、测试项（测什么、测到哪里）

| 顺序 | 测试范围 | 类型 | 进度 | 证据 / 下一步 |
|------|----------|------|------|----------------|
| T1 | `pytest cai-agent/tests` | 自动化 | **完成** | 以本机/CI 最近一次全绿为准（例：**442 passed**、**3 subtests**；版本号以 `cai-agent --version` 为准） |
| T2 | `python scripts/run_regression.py` | 自动化 | **完成** | `PYTHONPATH=cai-agent/src` + `python -m cai_agent`；`docs/qa/runs/regression-*.md` |
| T3 | Hermes 总测计划 | 文档 | **已写** | [`HERMES_PARITY_MASTER_TESTPLAN.zh-CN.md`](qa/HERMES_PARITY_MASTER_TESTPLAN.zh-CN.md) |
| T4 | Sprint2 memory health | 混合 | **已覆盖** | [`sprint2-memory-health-testplan.md`](qa/sprint2-memory-health-testplan.md) |
| T5 | Sprint3–8 专项 | 手工 | **计划已写** | `docs/qa/sprint3-recall-v2-testplan.md` … `sprint8-ga-testplan.md` |
| T6 | S3 TUI 模型面板 40 条 | 手工 | **计划已写** | [`s3-tui-model-panel-testplan.md`](qa/s3-tui-model-panel-testplan.md) |
| T7 | 发版 gate | 人工 | **部分完成** | `doctor`、Parity、CHANGELOG、schema 抽样 |

**冒烟子集**：`python scripts/smoke_new_features.py`（与 T2 同源入口）；详列命令与 schema 以 **schema README** 与脚本内校验为准。

---

## 三之二、进度统计与 QA 移交

> **横向索引**：[`DEVELOPMENT_PROGRESS_TRACKER.zh-CN.md`](DEVELOPMENT_PROGRESS_TRACKER.zh-CN.md)（与本节 QA 说明互链）。

### 3.0 完成度（估算）

| 口径 | 计算方式 | 当前值（与 §二一致时更新） |
|------|----------|---------------------------|
| **§二 1–26 加权** | 「完成」「定案」「持续演进」各权 **1**；「部分完成」各 **0.5**；÷26 | **约 94%**（20+1+1+5×0.5 = **24.5** → **24.5/26≈94.2%**） |
| **Hermes 34 Story** | ✅ 数 ÷ 34 | 以 [`HERMES_PARITY_PROGRESS.zh-CN.md`](HERMES_PARITY_PROGRESS.zh-CN.md) 首页表为准（若与 §二口径冲突，**以 PROGRESS 的 Story 定义为准**） |
| **T1** | pytest 全绿 | 同 §三 T1 |

### 3.1 §二 状态计数

| 状态 | 数量 | 编号 |
|------|------|------|
| **完成** | **20** | 1–7、10–21 |
| **定案** | **1** | 8 |
| **持续演进** | **1** | 9 |
| **部分完成** | **5** | 22–26 |
| **未开始** | **0** | — |

### 3.2 后续大颗粒（与 §〇.2 对应）

| 项 | 说明 |
|----|------|
| **24** | Discord/Slack 等 **真机** gateway 与 Hermes 对齐 |
| **25** | 任务后 **自动** 生成/改进 skills、Hub **运行时** |
| **26** | **Web** 运营 UI、队列可视化 |
| **§一 P2** | Modal/Daytona 类后端（若立项） |

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
- **Hermes 迭代**：以 [`HERMES_PARITY_PROGRESS.zh-CN.md`](HERMES_PARITY_PROGRESS.zh-CN.md) 认领 Story。

---

*文档版本：2026-04-23 — 重组 **§〇**「已完成 / 未完成」总览；精简 §二～§三之二与页脚。*
