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
| 记忆治理 | 周期性 nudge、健康度、用户建模（Honcho 等） | `memory nudge` / `nudge-report`、**`memory health`（S2-01）已合并** | **部分完成**（见开发项 15–16、31） |
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
| 18 | **S1-02** `docs/schema/` 各命令 JSON schema 文档 | **部分完成** | 契约汇总于 [`docs/schema/README.zh-CN.md`](schema/README.zh-CN.md)（含 observe … **`quality-gate` / `security-scan`** / models / hooks / doctor / plan / memory / recall）；调度审计与 stats 仍为 [`SCHEDULE_*`](schema/SCHEDULE_AUDIT_JSONL.zh-CN.md) 独立长文 |
| 19 | **S1-03** 全命令 exit 0/2 语义补齐（含 `schedule stats`、`observe-report` 等） | **部分完成** | 含 **`models ping --fail-on-any-error`**、**`hooks list --json` 错误时 exit `2`** 及既有 doctor / plugins / workflow 等；`models ping` 默认非全 OK 仍为 exit **`1`** |
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
| T1 | `pytest cai-agent/tests` | 自动化 | **完成** | 例：主线 **329 passed**（以本机 `pytest cai-agent/tests` 为准） |
| T2 | `python scripts/run_regression.py` | 自动化 | **完成** | 已修复：强制 `PYTHONPATH=cai-agent/src` + 使用 `python -m cai_agent`，避免 PATH 上旧版 `cai-agent` 脚本；见 `docs/qa/runs/regression-20260422-*.md` |
| T3 | Hermes 总测试计划 | 文档 | **已写** | [`docs/qa/HERMES_PARITY_MASTER_TESTPLAN.zh-CN.md`](qa/HERMES_PARITY_MASTER_TESTPLAN.zh-CN.md) |
| T4 | Sprint2 memory health | 手工/自动化 | **S2-01 已覆盖** | [`docs/qa/sprint2-memory-health-testplan.md`](qa/sprint2-memory-health-testplan.md) + `test_memory_health_cli.py` |
| T5 | Sprint3–8 专项计划（recall v2、scheduler、subagents、gateway、observability、GA） | 手工 | **计划已写 / 随开发推进** | `docs/qa/sprint3-recall-v2-testplan.md` … `sprint8-ga-testplan.md` |
| T6 | S3 TUI 模型面板 40 用例 | 手工 | **计划已写** | `docs/qa/s3-tui-model-panel-testplan.md` |
| T7 | 发版前 `doctor` + Parity + CHANGELOG | 发布检查 | **部分完成** | 每版本人工过 |

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

*文档版本：2026-04-22（§二 S1-02 增补 `quality-gate`/`security-scan` JSON `schema_version`；T1 **329 passed**。）*
