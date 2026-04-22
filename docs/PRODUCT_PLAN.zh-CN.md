# CAI Agent 产品计划（唯一执行清单）

本文件是 **开发与测试进度的唯一权威表**：按顺序写要做什么、是否完成，以及测什么、测到哪里。  
**细粒度 Story ID / AC** 仍以 [`HERMES_PARITY_BACKLOG.zh-CN.md`](HERMES_PARITY_BACKLOG.zh-CN.md) 为准；本表做 **顺序、状态、证据** 汇总，避免与进度表 [`HERMES_PARITY_PROGRESS.zh-CN.md`](HERMES_PARITY_PROGRESS.zh-CN.md) 重复维护长文。

**非本表职责**：愿景 [`PRODUCT_VISION_FUSION.zh-CN.md`](PRODUCT_VISION_FUSION.zh-CN.md)、缺口 [`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md)、子系统矩阵 [`PARITY_MATRIX.zh-CN.md`](PARITY_MATRIX.zh-CN.md)、架构 [`ARCHITECTURE.zh-CN.md`](ARCHITECTURE.zh-CN.md)。

---

## 一、与 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) 的能力差（摘要）

| 维度 | Hermes（上游 README / 文档站） | 本仓（CAI Agent） | 本表状态 |
|------|----------------------------------|-------------------|----------|
| 多平台网关 | Telegram / Discord / Slack / WhatsApp / Signal / Email 等统一 gateway | 已有 `gateway` Telegram 子集（会话映射、CLI）；**未覆盖**全渠道矩阵 | **部分完成**（见开发项 24） |
| 技能自进化闭环 | 任务后自动生成 / 改进 skills、Skills Hub | 有 `skills/` 与插件扫描；**无**自动提炼闭环 | **未开始** |
| 定时无人值守 | 内置 cron + 任意平台投递 | `schedule` / `daemon` / scaffold **已落地** | **完成** |
| 跨会话检索 | FTS5 + LLM 摘要等 | `recall` / `recall-index`、`insights` **已落地** | **完成** |
| 记忆治理 | 周期性 nudge、健康度、用户建模（Honcho 等） | `memory nudge` / `nudge-report`、**`memory health`（S2-01）已合并** | **部分完成**（见开发项 **9–10**；用户建模 / Honcho 级能力见 **§一** 与 **开发项 25**） |
| 子代理 / 并行 | 隔离子 agent、RPC 脚本 | `workflow`、路由与 hooks **部分**对齐 | **进行中**（Hermes backlog S5+） |
| 运行后端 | 本地 / Docker / SSH / Modal / Daytona 等 | 以本机 + 可选配置为主；**无** Modal/Daytona 一等公民 | **未开始**（P2） |
| 语音 / Bridge | 产品化能力 | **OOS** 或 MCP 路径（见 Parity 矩阵） | **定案** |

---

## 二、开发项（按执行顺序）

| 顺序 | 开发项 | 状态 | 说明 / 证据 |
|------|--------|------|-------------|
| 1 | 核心 CLI：`plan` / `run` / `continue` / `command` / `workflow` | **完成** | README；`workflow` schema / `task_id` 等与 Hermes 轨迹类能力部分对齐 |
| 2 | 工作区工具 + 沙箱 + Shell 白名单 | **完成** | `sandbox.py`、`tools.py` |
| 3 | `fix-build`、`security-scan`、`quality-gate` | **完成** | 回归与 pytest |
| 4 | 插件发现 `plugins --json` | **完成** | |
| 5 | 多模型 profile、`models` CLI、TUI `/models`、`session` 含 `profile` | **完成** | |
| 6 | `board --json` 与 `observe` 同源、`observe_schema_version` | **完成** | |
| 7 | `fetch_url` + MCP Web 配方 | **完成** | `MCP_WEB_RECIPE.zh-CN.md` |
| 8 | WebSearch/Notebook | **定案 MCP 优先** | `WEBSEARCH_NOTEBOOK_MCP.zh-CN.md` |
| 9 | 记忆 CLI：`extract` / `list` / `search` / `prune`、instincts、`nudge`、`nudge-report`、import/export、状态机、prune 策略 | **完成（持续演进）** | `memory.py`、`__main__.py`；pytest `test_memory_*` |
| 10 | **S2-01 `memory health` 综合评分**（`health_score`、`grade` A–D、`--fail-on-grade`） | **完成** | **已在 `main`**（`build_memory_health_payload`、`cai-agent memory health`、`tests/test_memory_health_cli.py`）；原 [PR #12](https://github.com/caizizhen/Cai_Agent/pull/12) 单提交已由主线 Sprint 合入取代，见 §四。 |
| 11 | 跨会话 `insights`、`recall`、`recall-index` | **完成** | |
| 12 | `schedule` / `daemon` / 依赖与审计 | **完成** | |
| 13 | Hooks：`hooks` CLI、路径解析、与 runner 对齐 | **完成** | `hook_runtime.py`、`test_hooks_cli.py` |
| 14 | LLM 传输重试、`max_http_retries`、Channel Error 重试 | **完成** | `test_llm_transport_error_retry.py` |
| 15 | `gateway telegram` 映射与解析 CLI | **完成** | `test_gateway_telegram_cli.py` |
| 16 | `export` 多 harness | **完成（基础）** | |
| 17 | Hermes backlog **S2-02～S2-05**（freshness / conflict_rate / coverage 指标、nudge-report 与 health 联动） | **完成** | 与 [`HERMES_PARITY_PROGRESS.zh-CN.md`](HERMES_PARITY_PROGRESS.zh-CN.md) 已完成表一致；**已在 `main`** |
| 18 | **S1-02** `docs/schema/` 各命令 JSON schema 文档 | **部分完成** | 契约汇总于 [`docs/schema/README.zh-CN.md`](schema/README.zh-CN.md)（含 observe … **`gateway telegram`（`gateway_telegram_map_v1`）**、**`plugins` → `plugins_surface_v1`**、**`mcp-check` / `sessions`（`sessions_list_v1`）/ `stats` / `run` 族 / `export`（`export_cli_v1`）**、**`quality-gate` / `security-scan`**、**`models ping` → `models_ping_v1`**、**`models fetch` → `models_fetch_v1`**、**`cost budget` → `cost_budget_v1`**、**`release-ga` → `release_ga_gate_v1`**、hooks / doctor / plan / **`init --json` → `init_cli_v1`** / memory / recall）；**`commands`/`agents` → `commands_list_v1`/`agents_list_v1`**；**`schedule`：`add`/`list`/`rm`/`add-memory-nudge`/`run-due`/`daemon` 等 JSON `schema_version`**；**`memory extract` → `memory_extract_v1`**，**`memory list`/`search`/`instincts --json` → `memory_list_v1`/`memory_search_v1`/`memory_instincts_list_v1`**，**`memory import`/`import-entries` stdout → `memory_instincts_import_v1`/`memory_entries_import_result_v1`/`memory_entries_import_dry_run_v1`**；**`memory export`/`export-entries --json` → `memory_instincts_export_v1`/`memory_entries_export_result_v1`**（见 schema README 与 memory 表）；调度审计与 stats 仍为 [`SCHEDULE_*`](schema/SCHEDULE_AUDIT_JSONL.zh-CN.md) 独立长文 |
| 19 | **S1-03** 全命令 exit 0/2 语义补齐（含 `schedule stats`、`observe-report` 等） | **部分完成** | **`main()` 兜底**：未分发子命令 **exit `2`** + stderr 诊断（此前 **`1`**）；**`init`**：**`config_exists`** / 模板或目录失败 **exit `2`**；**`models ping`** 非全 **`OK`** **默认 exit `2`**（**`--fail-on-any-error`** 同义）；**`hooks list --json`** 目录错误 **exit `2`**；另有 doctor / plugins / workflow 等；其余子命令仍按需对齐 0/2 叙事 |
| 20 | **S4-04** 调度审计 JSONL 事件类型统一（7 种标准事件名） | **完成** | 与 PROGRESS 一致；`docs/schema/SCHEDULE_AUDIT_JSONL.zh-CN.md`、`tests/test_schedule_audit_schema_s4_04.py` |
| 21 | 统一任务 ID / 全链路状态机 + Dashboard 消费 | **未开始** | |
| 22 | 敏感信息扫描、高危命令二次确认 | **未开始** | |
| 23 | 子 Agent 标准 IO、多 Agent 编排模板 | **未开始** | Hermes Sprint 5–6 backlog |
| 24 | 多平台 Gateway 与 Hermes 对齐（Discord/Slack/…） | **未开始** | 大项；依赖产品与密钥策略 |
| 25 | 技能自进化 / Skills Hub 式分发 | **未开始** | Hermes 核心差异 |
| 26 | 运营面板（队列、失败率、成本） | **未开始** | P2 |

---

## 三、测试项（测什么、测到哪里）

| 顺序 | 测试范围 | 类型 | 进度 | 证据 / 下一步 |
|------|----------|------|------|----------------|
| T1 | `pytest cai-agent/tests` | 自动化 | **完成** | 例：主线 **346 passed**（以本机 `pytest cai-agent/tests` 为准） |
| T2 | `python scripts/run_regression.py` | 自动化 | **完成** | 已修复：强制 `PYTHONPATH=cai-agent/src` + 使用 `python -m cai_agent`，避免 PATH 上旧版 `cai-agent` 脚本；**`smoke_new_features.py`** 含 **`init --json`**、**二次 init（`config_exists` / exit `2`）**、**`schedule add|list|rm`**、**`memory … --json`** 等契约校验；见 `docs/qa/runs/regression-*.md` |
| T3 | Hermes 总测试计划 | 文档 | **已写** | [`docs/qa/HERMES_PARITY_MASTER_TESTPLAN.zh-CN.md`](qa/HERMES_PARITY_MASTER_TESTPLAN.zh-CN.md) |
| T4 | Sprint2 memory health | 手工/自动化 | **S2-01 已覆盖** | [`docs/qa/sprint2-memory-health-testplan.md`](qa/sprint2-memory-health-testplan.md) + `test_memory_health_cli.py` |
| T5 | Sprint3–8 专项计划（recall v2、scheduler、subagents、gateway、observability、GA） | 手工 | **计划已写 / 随开发推进** | `docs/qa/sprint3-recall-v2-testplan.md` … `sprint8-ga-testplan.md` |
| T6 | S3 TUI 模型面板 40 用例 | 手工 | **计划已写** | `docs/qa/s3-tui-model-panel-testplan.md` |
| T7 | 发版前 `doctor` + Parity + CHANGELOG | 发布检查 | **部分完成** | 每版本人工过 |

---

## 三之二、开发进度统计 · 未开发项标记 · 测试移交（QA）

> **说明**：本节为 **进度统计** 与 **给测试人员的执行清单**。**开发项 21–26** 与 Hermes Sprint 5+  backlog 为 **大颗粒能力**，**未**在主线以「单提交全部实现」的方式交付；以下「未开发」表为 **全量列出并标记状态**，避免与「已完成」混淆。

### 3.0 同步完成度（百分比）

> **口径**：下表为 **文档化估算**，便于干系人对齐预期；**不以百分比替代 §二逐条状态**。每次合并主线后随 §三之二一并更新。

| 口径 | 计算方式 | **当前值** |
|------|----------|------------|
| **§二 开发项 1–26（加权）** | 「完成」权重 **1**；**定案**（项 8）**1**；**持续演进**（项 9）**1**；**部分完成**（项 18、19）各 **0.5**；「未开始」**0**。分子 ÷ **26** | **约 77%**（20÷26≈76.9%） |
| **Hermes Backlog 34 Story** | 仅 ✅ 条数 ÷ 34；括号内为 ⚠️ **3** 条各按 **0.5** 条计入 | **约 50%**（17÷34）；**约 54%**（18.5÷34≈54.4%） |
| **自动化测试 T1** | `pytest cai-agent/tests` 全绿即视为本条里程碑达成（用例数随版本增加） | **346 passed**（见上表 T1） |

### 3.1 §二 开发项（1–26）状态计数

| 状态 | 数量 | 含开发项编号 / 说明 |
|------|------|---------------------|
| **完成** | **17** | 1–7、9–17、20 |
| **定案（产品决策，无对等代码里程碑）** | **1** | 8（WebSearch/Notebook **MCP 优先**） |
| **完成（持续演进）** | **1** | 9（记忆 CLI 仍随需求迭代） |
| **部分完成** | **2** | 18（S1-02 JSON 契约与文档）、19（S1-03 exit 0/2 叙事） |
| **未开始** | **6** | **21、22、23、24、25、26**（见下表 **已全部标记**） |

### 3.2 未开发项全表（**标记：待分 Sprint / 立项后开发**）

以下各项 **当前主线未实现业务闭环**；开发需按 [`HERMES_PARITY_BACKLOG.zh-CN.md`](HERMES_PARITY_BACKLOG.zh-CN.md) / [`HERMES_PARITY_PROGRESS.zh-CN.md`](HERMES_PARITY_PROGRESS.zh-CN.md) **拆 Story、排期、再编码**。**不可**期望在未排期的情况下「一次开发全部落地」。

| 开发项 | 主题 | 依赖 / 风险摘要 |
|--------|------|-----------------|
| **21** | 统一任务 ID、全链路状态机、Dashboard 消费 | 跨 `run` / `schedule` / `workflow` 数据模型；需架构设计 |
| **22** | 敏感信息扫描、高危命令二次确认 | 安全策略、误报率、与 `sandbox` 联动 |
| **23** | 子 Agent 标准 IO、多 Agent 编排模板 | Hermes **S5**；见 `docs/qa/sprint5-subagents-testplan.md` |
| **24** | 多平台 Gateway（Discord/Slack/…） | 密钥与合规；**S6** 起 |
| **25** | 技能自进化 / Skills Hub 式分发 | 与 **§一**「技能自进化」维度同源；产品未定稿前保持 **未开始** |
| **26** | 运营面板（队列、失败率、成本） | P2；依赖可观测数据管道 |

### 3.3 测试移交清单（请测试人员按序执行并回填）

| 序号 | 测试对象 | 类型 | 建议执行人 | 操作说明 | 当前证据（开发侧） |
|------|----------|------|------------|----------|---------------------|
| **QA-1** | **T1** `pytest cai-agent/tests` | 自动化 | CI / 测试 | 每版合并后必跑；失败则阻塞发布 | 主线最近一次：**346 passed**（以执行机 `pytest cai-agent/tests` 为准） |
| **QA-2** | **T2** `python scripts/run_regression.py` | 自动化 | 测试 | 仓库根执行；关注 `docs/qa/runs/regression-*.md` | 脚本已固定 `PYTHONPATH` + `python -m cai_agent`；含 **`scripts/smoke_new_features.py`** |
| **QA-3** | **冒烟** `python scripts/smoke_new_features.py` | 自动化 | 测试 | 与 T2 可合并执行；校验 `init`（含二次 **`config_exists`**）、`schedule` / `memory` JSON 信封 | 退出码 **0** 且 stdout **`NEW_FEATURE_CHECKS_OK`** |
| **QA-4** | Hermes 总测 | 文档化手工 | 测试 | 按 [`HERMES_PARITY_MASTER_TESTPLAN.zh-CN.md`](qa/HERMES_PARITY_MASTER_TESTPLAN.zh-CN.md) 抽样 | 文档已维护 |
| **QA-5** | Sprint2 memory health | 手工 + 自动化 | 测试 | [`sprint2-memory-health-testplan.md`](qa/sprint2-memory-health-testplan.md) + `test_memory_health_cli.py` | S2-01 已在 `main` |
| **QA-6** | Sprint3–8 专项 | 手工 | 测试 | `docs/qa/sprint3-recall-v2-testplan.md` … `sprint8-ga-testplan.md`；**未开发项 21–26 对应段落待开发完成后再测** | 计划已写 |
| **QA-7** | S3 TUI 模型面板 | 手工 | 测试 | [`s3-tui-model-panel-testplan.md`](qa/s3-tui-model-panel-testplan.md) | 40 用例 |
| **QA-8** | 发版前 gate | 人工 | 测试 / 发布 | `doctor`、Parity、CHANGELOG、**§二 18–19 契约抽样** | T7 **部分完成** |

**回填方式**：测试负责人在本表右侧「当前证据」列追加日期与结论（或仅在 `docs/qa/runs/` 新增回归 Markdown 由流程约定处理）；**不必**在本文件重复粘贴大段日志。

---

## 四、[PR #12](https://github.com/caizizhen/Cai_Agent/pull/12)（`cursor/hermes-s2-01-memory-health-9ed2`）处理说明

| 项 | 说明 |
|----|------|
| **PR 状态** | Draft「单提交 `6df633f`」与当前 **`main` 历史不一致**：S2-01 `memory health` 等能力已由主线上的 **Hermes Sprint 2** 等提交合入（例如 `git log main --oneline --grep=Sprint` / `memory` 可见），**请勿再合并 PR #12**（会引入重复或冲突历史）。 |
| **远端分支** | **`origin/cursor/hermes-s2-01-memory-health-9ed2` 已删除**（2026-04-22），避免与主线双轨。 |
| **请在 GitHub 上** | 打开 [PR #12](https://github.com/caizizhen/Cai_Agent/pull/12) → **Close pull request**（建议选 *Close as not planned* 或说明 *Superseded by main*），保持仓库 PR 列表干净。 |

---

## 五、分支策略（团队约定）

- **默认集成分支**：`main`；功能与修复经 **PR 合入**，合入前保持 CI 绿。
- **不要随意新建长期 `cursor/*` 或平行功能分支**：优先在 **已有 PR 分支上追加 commit**，或 **一个功能一个短生命周期分支**，合入后立即删除远端分支。
- **Hermes 对标迭代**：以 [`HERMES_PARITY_PROGRESS.zh-CN.md`](HERMES_PARITY_PROGRESS.zh-CN.md) 认领 Story，避免同一 Story 开多条平行分支。

---

*文档版本：2026-04-23（§三之二 **3.0** 同步完成度：**§二 加权约 77%**、**Hermes Story 约 50%（加权约 54%）**；§二 S1-02 补充 **`gateway telegram`** 契约索引；T1/QA-1 **346 passed**；**开发项 21–26** 见 §三之二。）*
