# Cai_Agent 当前阶段开发计划（三仓集成版）

本文档回答的是：在当前产品目标调整为集成

- [`anthropics/claude-code`](https://github.com/anthropics/claude-code)
- [`NousResearch/hermes-agent`](https://github.com/NousResearch/hermes-agent)
- [`affaan-m/everything-claude-code`](https://github.com/affaan-m/everything-claude-code)

之后，`Cai_Agent` 接下来一段时间应该优先开发什么、哪些能力先不做、哪些文档应该继续保留。

权威边界：

- 已做了什么：[`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md)
- 为什么还不够：[`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md)
- 产品定位：[`PRODUCT_VISION_FUSION.zh-CN.md`](PRODUCT_VISION_FUSION.zh-CN.md)
- 发版勾选：[`PARITY_MATRIX.zh-CN.md`](PARITY_MATRIX.zh-CN.md)

---

## 1. 当前阶段目标

本阶段不是继续做“单一上游 parity 冲刺”，而是把三条能力线整合成一个更清晰的产品面：

- **Claude Code 线**：补强 CLI / TUI 交互、安装与更新体验、任务视图、MCP 接入体验。
- **Hermes 线**：补强 profiles、API/server、多平台 gateway、voice、dashboard、memory providers、runtime backends。
- **ECC 线**：补强 rules / skills / hooks 资产化、模型路由、插件与跨 harness 生态治理。

一句话目标：

**把当前已经完成的本地 Agent 主链路，推进成一个可运行、可扩展、可治理、可发布的统一 Agent 平台。**

---

## 2. 当前基线判断

截至 `2026-04-24`，当前仓库已经具备以下基础：

- 主链路 CLI、`run` / `workflow` / `subagent` / 安全门禁 / 基础 TUI 已可用。
- 记忆、召回、调度、可观测、导出、skills hub、Telegram gateway 已有完整主路径。
- Discord / Slack、运营面板、用户模型、成本与路由等能力已经有雏形，但仍偏 `MVP` 或“开发者可用”。
- 与 Hermes 最新产品面、Claude Code 体验细节、ECC 生态化治理相比，仍有明显缺口。

因此本阶段的原则是：

1. 不再以“新增命令数量”作为核心目标，而以“用户能否稳定使用”和“团队能否稳定维护”作为目标。
2. 所有未做能力必须归入三类之一：`实现中`、`MCP/文档定案`、`OOS`。
3. 所有规划统一收敛到少数主文档，不再在历史 parity 文档中重复维护。

---

## 3. 当前 To-dos（按优先级）

| ID | 优先级 | 来源 | 目标 | 本阶段交付 |
|---|---|---|---|---|
| `DOC-01` | `P0` | 共享 | 文档收敛 | 统一文档入口；删除重复 backlog / roadmap；中英文入口同步 |
| `REL-01` | `P0` | 共享 | 发布与反馈闭环 | `release-ga`、`doctor`、`feedback`、CHANGELOG、Parity 回写形成固定流程 |
| `CC-01` | `P1` | Claude Code | WebSearch / Notebook 产品化入口 | 保持 `MCP 优先`，补齐预设、自检、模板、文档与任务入口 |
| `CC-02` | `P1` | Claude Code | 安装 / 更新 / 问题反馈体验 | 梳理 installer-style 路径、版本提示、`/bug` 类反馈入口或等价命令 |
| `CC-03` | `P1` | Claude Code | CLI / TUI 交互收口 | `/tasks`、任务板、会话继续、模型切换、状态提示的统一体验 |
| `HM-01` | `P1` | Hermes | Profiles | 明确 profile 数据模型、切换命令、持久化结构与 QA 场景 |
| `HM-02` | `P1` | Hermes | API / server | 形成最小 OpenAI-compatible 或仓内标准 API 面，支持外部驱动 |
| `HM-03` | `P1` | Hermes | 多平台 gateway | 在 Telegram 之外明确 Discord / Slack 生产路径，并评估下一批平台 |
| `HM-04` | `P1` | Hermes | Dashboard 产品化 | 从静态看板推进到动态运营视图，但先坚持只读和同源 schema |
| `HM-05` | `P1` | Hermes | Memory providers / 用户模型 | 从 `behavior_extract/export` 推进到 query / learn / provider 抽象 |
| `HM-06` | `P2` | Hermes | Runtime backends | 把 Docker / SSH / 本地后端产品化，云后端继续条件立项 |
| `HM-07` | `P2` | Hermes | Voice | 仅做能力评估与边界定义，不进入默认交付 |
| `ECC-01` | `P1` | ECC | rules / skills / hooks 资产化 | 统一目录、模板、导出、安装、推荐与兼容说明 |
| `ECC-02` | `P1` | ECC | model-route / 成本治理 | 把 routing、budget、compact、profile 选择做成稳定产品路径 |
| `ECC-03` | `P2` | ECC | 插件 / 分发治理 | 插件矩阵、版本语义、跨 harness 导出与安装叙事统一 |

---

## 4. 里程碑拆解

| 里程碑 | 时间窗口 | 目标 | 对应 To-dos |
|---|---|---|---|
| `M1` | `2026-04-27` ~ `2026-05-08` | 文档收敛与产品定位统一 | `DOC-01` |
| `M2` | `2026-05-11` ~ `2026-05-29` | Claude Code 体验线第一阶段收口 | `CC-01` `CC-02` `CC-03` |
| `M3` | `2026-06-01` ~ `2026-06-26` | Hermes 产品化第一阶段 | `HM-01` `HM-02` `HM-03` `HM-04` `HM-05` |
| `M4` | `2026-06-29` ~ `2026-07-10` | ECC 治理与生态化第一阶段 | `ECC-01` `ECC-02` |
| `M5` | `2026-07-13` ~ `2026-07-17` | 发布闭环与下周期立项 | `REL-01` `HM-06` `ECC-03` `HM-07` 评审 |

---

## 5. 每项 To-do 的完成标准

### 5.1 `DOC-01` 文档收敛

- `README.md` / `README.zh-CN.md` / `docs/README.md` / `docs/README.zh-CN.md` 对产品目标表述一致。
- `PRODUCT_PLAN` 只维护“已完成能力与状态”。
- `ROADMAP_EXECUTION` 只维护“当前阶段要做什么”。
- `PRODUCT_GAP_ANALYSIS` 只维护“还差什么、哪些 OOS、哪些用 MCP/文档定案”。
- 删除至少一批重复历史文档，并清理掉所有悬空引用。

### 5.2 `REL-01` 发布与反馈闭环

- 每次发版前能固定输出：`doctor`、回归、smoke、CHANGELOG、Parity 勾选、反馈摘要。
- 新增能力后不再允许只改代码不回写产品文档。
- 反馈入口、导出结构、归档位置有统一说明。

### 5.3 `CC-*` Claude Code 体验线

- 用户能够更低成本完成：安装、初始化、自检、开始、继续、反馈。
- WebSearch / Notebook 保持 `MCP 优先`，但接入体验不再依赖分散文档。
- TUI / CLI 的任务、模型、会话状态展示更一致。

### 5.4 `HM-*` Hermes 产品化线

- profile、gateway、dashboard、memory provider、API/server 都必须有清晰的数据结构与测试入口。
- Discord / Slack 不再仅是“能跑通”，而要有值班、映射、故障排查说明。
- Dashboard 优先保证“同源数据 + 运维可读”，避免过早引入重交互和多套状态源。

### 5.5 `ECC-*` 治理与生态线

- rules / skills / hooks 不再只是散落能力，而是有明确资产目录、模板和安装说明。
- 成本、模型路由、compact、profile 不再是分散开关，而是产品层可解释能力。
- 跨 harness 导出、插件兼容矩阵与分发叙事保持一致。

---

## 6. 明确不做或暂不做

本阶段继续维持以下边界：

- **内置 WebSearch / Notebook 重实现**：不做，继续走 `MCP 优先`。
- **默认云运行后端**：不做，Modal / Daytona / 同类方案只保留条件立项。
- **依赖封闭企业能力的官方专属功能**：不做，除非能以开放接口实现等价路径。
- **多 CLI 套娃式产品形态**：不做，目标是一个统一运行时，而不是包装多个独立 agent。
- **Voice 默认交付**：不做，只保留能力评估与边界梳理。

---

## 7. 文档维护规则

当前建议保留为“主文档”的只有：

- [`PRODUCT_VISION_FUSION.zh-CN.md`](PRODUCT_VISION_FUSION.zh-CN.md)
- [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md)
- [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md)
- [`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md)
- [`PARITY_MATRIX.zh-CN.md`](PARITY_MATRIX.zh-CN.md)
- `CHANGELOG.md` / `CHANGELOG.zh-CN.md`

其他文档应遵守：

- 专题文档只解释一个主题，不重复维护大而全的状态表。
- 历史 parity / sprint 文档只保留为追溯入口，不再承载当前排期。
- 中英文文档优先同步入口文档和滚动摘要，不强求所有专题逐页双写。

---

## 8. 发版门禁

本阶段所有新增能力都应满足以下条件：

- 有实现，或有明确 `MCP/OOS` 定案，不能悬空。
- 有至少一个可执行验证入口：`pytest`、回归、smoke、人工 testplan 三者之一。
- 有文档回写，至少覆盖 `PRODUCT_PLAN`、`PRODUCT_GAP_ANALYSIS`、`PARITY_MATRIX`、`CHANGELOG` 中的相关项。
- 不引入新的重复文档源。

---

## 9. 成功标准

到本阶段结束时，视为达标的标准是：

1. 产品定位已经从“对齐单一上游”转成“集成三条能力线”，且中英文入口一致。
2. 文档数量下降，重复状态表明显减少，团队知道“该改哪份文档”。
3. Claude Code 体验线、Hermes 产品化线、ECC 治理线各至少收口一批 `P1` 能力。
4. 发布、反馈、文档同步不再依赖手工补洞。

---

## 10. 执行 backlog（可直接开 issue）

为避免再出现“路线图一份、画布一份、专题文档一份”三套口径，下面这张表就是当前建议的**开 issue 顺序**。规则是：

完整 issue 草案见 [`ISSUE_BACKLOG.zh-CN.md`](ISSUE_BACKLOG.zh-CN.md)。已完成任务的归档摘要见 [`COMPLETED_TASKS_ARCHIVE.zh-CN.md`](COMPLETED_TASKS_ARCHIVE.zh-CN.md)；[`DEVELOPER_TODOS.zh-CN.md`](DEVELOPER_TODOS.zh-CN.md) 只保留未完成项、未来方向与 OOS/条件立项。

- `Done`：本轮已经收口，不再单独开开发单，只保留回归和维护。
- `Ready`：边界清晰，可以直接开开发 issue。
- `Design`：先定契约或数据结构，再开实现 issue。
- `Explore`：保留调研或预研，不进入当前默认交付。
- **说明（2026-04-25）**：**`HM-03c` / `ECC-03a` / `HM-06a` / `HM-07a`** 以 **`docs/rfc/*.zh-CN.md`** 结论文档交付并标 **Done**；后续 **实现类**工作需另开 issue（如 Teams gateway）。

| Issue | 状态 | 对应 To-do | 建议标题 | 主要输出 | 依赖 | 验证 |
|---|---|---|---|---|---|---|
| `DOC-01a` | `Done` | `DOC-01` | 统一根 README 与 docs 入口 | 中英文入口统一、主文档收敛 | — | 手工检查 + 链接检查 |
| `DOC-01b` | `Done` | `DOC-01` | 删除重复 roadmap / backlog 文档 | 删除历史重复页并清理引用 | `DOC-01a` | `rg` 无残链 |
| `REL-01a` | `Done` | `REL-01` | 收口 release-ga / doctor / changelog 回写流程 | 一条固定发版 runbook，明确输入输出 | — | `doctor` + smoke + checklist |
| `REL-01b` | `Done` | `REL-01` | 统一 feedback、doctor 与发布摘要出口 | `feedback stats` CLI；`doctor --json` 的 **`feedback`** 与 **`release_runbook.feedback`** 同源（单次 runbook 构建） | `REL-01a` | pytest `test_doctor_cli` / `test_feedback_cli` + smoke |
| `CC-01a` | `Done` | `CC-01` | 收口 MCP 预设与 WebSearch/Notebook 接入入口 | `mcp-check` preset、模板、文档、onboarding 入口统一 | — | 预设探测 + 文档示例 |
| `CC-01b` | `Done` | `CC-01` | 在 CLI/TUI 暴露 WebSearch/Notebook 推荐入口 | **`/mcp-presets`**；**`/help`**/**`/status`**/**任务看板** 同源 quickstart；**`mcp-check --help`** epilog | `CC-01a` | pytest |
| `CC-02a` | `Done` | `CC-02` | 梳理安装、更新与版本提示体验 | 安装/升级路径、版本差异提示、常见错误指引 | — | onboarding walkthrough |
| `CC-02b` | `Done` | `CC-02` | 设计 /bug 等价反馈入口 | **`feedback bug`**（**`feedback_bug_report_v1`** + **`sanitize_feedback_text`**）；runbook 步骤说明 | `REL-01b` | pytest `test_feedback_cli` |
| `CC-03a` | `Done` | `CC-03` | 统一任务板、状态栏与会话继续体验 | **`tui_session_strip`**；**`/help`**/欢迎/**`/sessions`**/**`/load`**/**`/retry`**/placeholder/看板/`#context-label` | — | pytest |
| `CC-03b` | `Done` | `CC-03` | 收口模型切换与状态提示 | RFC：`docs/rfc/CC_03B_MODEL_STATUS_UX.zh-CN.md` | `HM-01a` | RFC 评审 + 后续 UI 对齐 |
| `HM-01a` | `Done` | `HM-01` | 定义 profile 数据模型与持久化结构 | profile schema、切换规则、默认项、迁移策略 | — | schema review |
| `HM-01b` | `Done` | `HM-01` | 落地 profile 管理命令与测试夹具 | `models add/edit/rm/use/route/list` + `profile_contract_v1` + fixture / smoke 回归 | `HM-01a` | pytest + smoke |
| `HM-02a` | `Done` | `HM-02` | 设计最小 API / server 契约 | RFC：`docs/rfc/HM_02_MINIMAL_SERVER_CONTRACT.zh-CN.md` | — | RFC 合入 |
| `HM-02b` | `Done` | `HM-02` | 实现最小只读或任务触发型 API 面 | **`cai-agent api serve`**；**`GET /healthz`**、**`/v1/status`**、**`/v1/doctor/summary`**、**`POST /v1/tasks/run-due`**（仅 **dry_run**） | `HM-02a` | pytest + smoke --help |
| `HM-03a` | `Done` | `HM-03` | 把 Discord 从 MVP 推到生产路径 | slash / mapping / health / 故障排查收口 | — | gateway smoke + doctor |
| `HM-03b` | `Done` | `HM-03` | 把 Slack 从 MVP 推到生产路径 | `gateway slack health`、Slash/Interactivity form 分发、mapping 元数据与 `--execute-on-slash` 收口 | — | gateway smoke + doctor |
| `HM-03c` | `Done` | `HM-03` | 评估下一批 gateway 平台 | 结论文档：**`docs/rfc/HM_03C_NEXT_GATEWAY_PLATFORMS.zh-CN.md`** | `HM-03a` `HM-03b` | 文档评审 |
| `HM-04a` | `Done` | `HM-04` | 统一 ops/gateway/status 聚合载荷 | `board` / `observe` / `ops` 同源字段收口 | — | JSON snapshot |
| `HM-04b` | `Done` | `HM-04` | 增加只读动态 dashboard 能力 | `ops serve` 已暴露 `dashboard/events`，HTML 支持 `live_mode=sse|poll`，继续保持只读 | `HM-04a` | 浏览器手测 |
| `HM-05a` | `Done` | `HM-05` | 补齐 user-model store/query/learn 主链路 | 从 `behavior_extract/export` 推到闭环 | — | pytest + smoke |
| `HM-05b` | `Done` | `HM-05` | 建 recall 评估与负样本机制 | `recall --evaluate`、负样本审计、`recall_evaluation_v1` | `HM-05a` | pytest + smoke |
| `HM-05c` | `Done` | `HM-05` | 把 memory policy 接进 doctor / release gate | 文本 doctor、`--with-memory-policy` | `HM-05a` | doctor + release-ga pytest |
| `ECC-01a` | `Done` | `ECC-01` | 统一 rules/skills/hooks 资产目录与模板 | 目录约定、模板、安装说明 | — | 文档 + sample asset |
| `ECC-01b` | `Done` | `ECC-01` | 收口导出/安装/共享流转 | `CROSS_HARNESS_COMPATIBILITY*.md` 编号化流转 | `ECC-01a` | 文档走查 |
| `ECC-02a` | `Done` | `ECC-02` | 把 routing/profile/budget 变成稳定产品路径 | `models routing-test`、wizard、默认策略收口 | — | CLI smoke |
| `ECC-02b` | `Done` | `ECC-02` | 补齐成本视图与 compact 策略解释 | `cost report` 嵌 `compact_policy_explain_v1`、文本摘要 | `ECC-02a` | pytest + smoke |
| `ECC-03a` | `Done` | `ECC-03` | 插件矩阵与版本治理方案 | 结论文档：**`docs/rfc/ECC_03A_PLUGIN_VERSION_GOVERNANCE.zh-CN.md`** | — | 文档评审 |
| `HM-06a` | `Done` | `HM-06` | Runtime backend 产品化评估 | 结论文档：**`docs/rfc/HM_06A_RUNTIME_BACKEND_ASSESSMENT.zh-CN.md`** | — | 文档评审 |
| `HM-07a` | `Done` | `HM-07` | Voice 能力边界评估 | 结论文档：**`docs/rfc/HM_07A_VOICE_BOUNDARY.zh-CN.md`**（默认 **OOS**，**MCP** 替代） | — | 文档评审 |
| `HM-02c` | `Done` | `HM-02` | API 只读扩展（profile / plugins / release） | **`GET /v1/models/summary`**（`api_models_summary_v1`）、**`GET /v1/plugins/surface`**（`api_plugins_surface_v1`，**可选 `?compat=1`**）、**`GET /v1/release/runbook`**（`api_release_runbook_v1`） | `HM-02b` | pytest |
| `CC-03c` | `Done` | `CC-03` | 模型切换与状态文案最小对齐 | TUI **`#context-label`** 追加 **`· route=sub/pl`** 与迁移警示；**`/models`** 切换与 CLI **`models use`** 同时打印 **`profile_switched: <id>`** | `CC-03b` | pytest |
| `ECC-03b` | `Done` | `ECC-03` | 插件治理最小可验证入口 | **`plugin_compat_matrix_v1.maintenance_checklist`** + **`plugins_compat_check_v1`**（**`plugins --compat-check`**） | `ECC-03a` | pytest |
| `HM-03d-teams` | `Done` | `HM-03` | Teams Gateway 生产路径（下一批第一顺位） | **`gateway teams`**（`bind/get/list/unbind`、`allow`、`health`、`manifest`、`serve-webhook`）；**`gateway_teams_map_v1`** / **`gateway_teams_health_v1`** / **`gateway_teams_manifest_v1`**；`gateway platforms` 与 `gateway maps` 纳入 Teams | `HM-03b` `HM-03c` | pytest `test_gateway_discord_slack_cli` + `test_gateway_maps_summarize` |
| `HM-06b-docker` | `Done` | `HM-06` | Runtime **docker** 后端产品化 | **`runtime.docker`** 支持 `container` / `image` 双模式、`workdir`、`volume_mounts`、`cpus`、`memory`；**`doctor_runtime_v1.describe`** 暴露 mode/image/workdir/volumes/limits | `HM-06a` | pytest `test_runtime_docker_mock` + smoke |
| `HM-06c-ssh` | `Done` | `HM-06` | Runtime **SSH** 后端产品化 | **`runtime.ssh`** 诊断补齐 `ssh_binary_present`、key/known_hosts 存在性、连接超时；新增可选 **`runtime_ssh_audit_v1`** JSONL 审计（默认不记录命令明文） | `HM-06a` | pytest `test_runtime_ssh_mock` + smoke |
| `HM-04c` | `Done` | `HM-04` | Dashboard 高级交互预览契约 | **`ops_dashboard_interactions_v1`**；`GET /v1/ops/dashboard/interactions` 支持 `schedule_reorder_preview` / `gateway_bind_edit_preview`，固定 dry-run、无写入 | `HM-04b` | pytest `test_ops_http_server` |
| `HM-03e-prod` | `Done` | `HM-03` | Gateway 生产化状态摘要 | **`gateway prod-status --json`** 输出 **`gateway_production_summary_v1`**，汇总 Telegram/Discord/Slack/Teams map/health/env/run-state，本地只读无外部 API | `HM-03b` | pytest `test_gateway_lifecycle_cli` + smoke |
| `ECC-03c` | `Done` | `ECC-03` | 插件兼容矩阵 CI snapshot | **`scripts/gen_plugin_compat_snapshot.py`** 生成/校验 **`docs/schema/plugin_compat_matrix_v1.snapshot.json`**；snapshot 内嵌 `plugin_compat_matrix_v1` 与 `plugin_compat_matrix_check_v1` | `ECC-03b` | pytest `test_plugin_compat_matrix` + smoke `--check` |
| `HM-05d` | `Done` | `HM-05` | Memory providers 扩展 / 用户模型深化 | **`memory provider --json`** 输出 **`memory_provider_contract_v1`**，描述 local entries / user-model SQLite provider 与 future external adapter 边界 | `HM-05a/b/c` | pytest `test_memory_provider_contract_cli` + smoke |
| `DOC-01c` | `Done` | `DOC-01` | 英文对照 & 入口双语持续收敛 | 根 README 与 docs README 补 Teams/runtime/plugin snapshot 入口；中英入口互指实现摘要、测试清单与 snapshot | — | 手工 + `rg` |

### 10.1 建议开单顺序

如果只按“最能尽快形成产品面”的顺序开单，建议是：

1. `REL-01a`
2. `CC-01a`
3. `CC-02a`
4. `HM-01a`
5. `HM-03a`
6. `HM-04a`
7. `HM-05a`
8. `ECC-01a`
9. `ECC-02a`

### 10.2 每个 issue 的统一模板

每个开发 issue 建议都带这 5 个字段，避免后续再次散掉：

- **目标**：补哪条上游能力线，想把什么体验收口。
- **边界**：这次不做什么，哪些能力继续走 MCP 或 OOS。
- **输出**：代码、文档、schema、命令、runbook 各会改什么。
- **验证**：`pytest`、smoke、手工 testplan、截图或 JSON snapshot。
- **回写**：至少回写 `PRODUCT_PLAN` / `PRODUCT_GAP_ANALYSIS` / `PARITY_MATRIX` / `CHANGELOG` 中相关项。

### 10.3 画布与 roadmap 对齐约定

`docs/canvas/GAP_TRACKER.md` 不再维护另一套独立主题，而是只做两件事：

- 记录旧 canvas 行与当前 `CC/HM/ECC/REL` ID 的映射。
- 标记当前每个 backlog 项是 `Done`、`Ready`、`Design` 还是 `Explore`。

这样后面如果你要继续拆 GitHub issues，直接按本节往下开就可以了。

---

*文档版本：2026-04-24。若三上游产品面发生明显变化，先更新 [`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md) 与本页，再决定是否进入新周期。*
