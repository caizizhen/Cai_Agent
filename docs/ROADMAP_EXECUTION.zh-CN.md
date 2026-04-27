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

截至 `2026-04-25`，当前仓库已经具备以下基础：

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
| `MODEL-P0` | `P0` | 共享 | 模型接入地基 | Model Gateway、capabilities、health/chat-smoke、response envelope、routing explain，作为后续 Profiles / API Server / TUI / cost 的共同依赖 |
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
| `M1` | `2026-04-27` ~ `2026-05-08` | 模型接入地基与文档收敛 | `MODEL-P0` `DOC-01` |
| `M2` | `2026-05-11` ~ `2026-05-29` | Claude Code 体验线第一阶段收口 | `CC-01` `CC-02` `CC-03` |
| `M3` | `2026-06-01` ~ `2026-06-26` | Hermes 产品化第一阶段 | `HM-01` `HM-02` `HM-03` `HM-04` `HM-05` |
| `M4` | `2026-06-29` ~ `2026-07-10` | ECC 治理与生态化第一阶段 | `ECC-01` `ECC-02` |
| `M5` | `2026-07-13` ~ `2026-07-17` | 发布闭环与下周期立项 | `REL-01` `HM-06` `ECC-03` `HM-07` 评审 |

---

## 5. 每项 To-do 的完成标准

### 5.1 `MODEL-P0` 模型接入地基

- 所有 provider/profile 先落到统一 `Model Gateway` 契约，再被 API Server、TUI、routing、cost 复用。
- `models capabilities` 与 `/v1/models/capabilities` 只暴露非敏感能力元数据，不泄漏 `api_key`、`base_url`。
- `models ping` 能区分 env/auth/rate/model/base_url/network 等常见问题；真实 chat smoke 必须显式开启。
- routing explain 能输出 base/effective profile 的能力信息，后续 fallback 只先 explain，不静默切换模型。

### 5.2 `DOC-01` 文档收敛

- `README.md` / `README.zh-CN.md` / `docs/README.md` / `docs/README.zh-CN.md` 对产品目标表述一致。
- `PRODUCT_PLAN` 只维护“已完成能力与状态”。
- `ROADMAP_EXECUTION` 只维护“当前阶段要做什么”。
- `PRODUCT_GAP_ANALYSIS` 只维护“还差什么、哪些 OOS、哪些用 MCP/文档定案”。
- 删除至少一批重复历史文档，并清理掉所有悬空引用。

### 5.3 `REL-01` 发布与反馈闭环

- 每次发版前能固定输出：`doctor`、回归、smoke、CHANGELOG、Parity 勾选、反馈摘要。
- 新增能力后不再允许只改代码不回写产品文档。
- 反馈入口、导出结构、归档位置有统一说明。

### 5.4 `CC-*` Claude Code 体验线

- 用户能够更低成本完成：安装、初始化、自检、开始、继续、反馈。
- WebSearch / Notebook 保持 `MCP 优先`，但接入体验不再依赖分散文档。
- TUI / CLI 的任务、模型、会话状态展示更一致。

### 5.5 `HM-*` Hermes 产品化线

- profile、gateway、dashboard、memory provider、API/server 都必须有清晰的数据结构与测试入口。
- Discord / Slack 不再仅是“能跑通”，而要有值班、映射、故障排查说明。
- Dashboard 优先保证“同源数据 + 运维可读”，避免过早引入重交互和多套状态源。

### 5.6 `ECC-*` 治理与生态线

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

完整 issue 草案见 [`ISSUE_BACKLOG.zh-CN.md`](ISSUE_BACKLOG.zh-CN.md)。已完成任务的归档摘要见 [`COMPLETED_TASKS_ARCHIVE.zh-CN.md`](COMPLETED_TASKS_ARCHIVE.zh-CN.md)；从双 TODO 拆出的 Done 表格行见 [`TODOS_DONE_ARCHIVE.zh-CN.md`](TODOS_DONE_ARCHIVE.zh-CN.md)。[`DEVELOPER_TODOS.zh-CN.md`](DEVELOPER_TODOS.zh-CN.md) 与 [`TEST_TODOS.zh-CN.md`](TEST_TODOS.zh-CN.md) 作为当前开发/测试执行基准。

- `Done`：本轮已经收口，不再单独开开发单，只保留回归和维护。
- `Ready`：边界清晰，可以直接开开发 issue。
- `Design`：先定契约或数据结构，再开实现 issue。
- `Explore`：保留调研或预研，不进入当前默认交付。
- **说明（2026-04-25）**：**`HM-03c` / `ECC-03a` / `HM-06a` / `HM-07a`** 以 **`docs/rfc/*.zh-CN.md`** 结论文档交付并标 **Done**；后续 **实现类**工作需另开 issue（如 Teams gateway）。

| Issue | 状态 | 对应 To-do | 建议标题 | 主要输出 | 依赖 | 验证 |
|---|---|---|---|---|---|---|
| `MODEL-P0a` | `Done` | `MODEL-P0` | 统一模型接入契约与能力元数据 | `model_gateway.py`、`ModelAdapter` / `ModelCapabilities` / `ModelResponse`、`model_response_v1`、`model_capabilities_list_v1`、CLI/API capabilities；API server 已复用 `model_response_v1` 支撑 `/v1/models` 与非流式/SSE `/v1/chat/completions` | — | pytest `test_model_gateway` / `test_model_profiles_cli` / `test_api_http_server` |
| `MODEL-P0b` | `Done` | `MODEL-P0` | 模型健康检查与 chat smoke 收口 | `models ping --chat-smoke`、细分健康状态、`doctor_model_gateway_v1` 建议、`MODEL_ONBOARDING_RUNBOOK` | `MODEL-P0a` | pytest `test_model_profiles_cli` / `test_doctor_cli` + smoke |
| `MODEL-P0c` | `Done` | `MODEL-P0` | routing explain / fallback / cost 对齐 | `routing_explain_v1`、base/effective capabilities、`model_fallback_candidates_v1` explain-only fallback、`api.chat_completions` metrics | `MODEL-P0a` | pytest `test_model_routing` / `test_metrics_jsonl` + smoke |
| `DOC-01a` | `Done` | `DOC-01` | 统一根 README 与 docs 入口 | 中英文入口统一、主文档收敛 | — | 手工检查 + 链接检查 |
| `DOC-01b` | `Done` | `DOC-01` | 删除重复 roadmap / backlog 文档 | 删除历史重复页并清理引用 | `DOC-01a` | `rg` 无残链 |
| `REL-01a` | `Done` | `REL-01` | 收口 release-ga / doctor / changelog 回写流程 | 一条固定发版 runbook，明确输入输出 | — | `doctor` + smoke + checklist |
| `REL-01b` | `Done` | `REL-01` | 统一 feedback、doctor 与发布摘要出口 | `feedback stats` CLI；`doctor --json` 的 **`feedback`** 与 **`release_runbook.feedback`** 同源（单次 runbook 构建） | `REL-01a` | pytest `test_doctor_cli` / `test_feedback_cli` + smoke |
| `CC-01a` | `Done` | `CC-01` | 收口 MCP 预设与 WebSearch/Notebook 接入入口 | `mcp-check` preset、模板、文档、onboarding 入口统一 | — | 预设探测 + 文档示例 |
| `CC-01b` | `Done` | `CC-01` | 在 CLI/TUI 暴露 WebSearch/Notebook 推荐入口 | **`/mcp-presets`**；**`/help`**/**`/status`**/**任务看板** 同源 quickstart；**`mcp-check --help`** epilog | `CC-01a` | pytest |
| `CC-02a` | `Done` | `CC-02` | 梳理安装、更新与版本提示体验 | 安装/升级路径、版本差异提示、常见错误指引 | — | onboarding walkthrough |
| `CC-02b` | `Done` | `CC-02` | 设计 /bug 等价反馈入口 | **`feedback bug`**（**`feedback_bug_report_v1`** + **`sanitize_feedback_text`**）；runbook 步骤说明 | `REL-01b` | pytest `test_feedback_cli` |
| `CC-N01-D05` | `Done` | `CC-N01` | TUI slash command center 与 repair/doctor 发现面收口 | TUI `/` 菜单统一读取原生命令与 `commands/*.md` 模板（含 `/code-review`）；新增 **`command_discovery_v1`**，并接入 `doctor_v1.command_center` / `api_doctor_summary_v1.command_center`；`doctor_sync_v1` 检查 `commands`、`skills`、`rules/*`、`hooks/hooks.json`；`repair_plan_v1` 可创建最小命令/技能/规则/hook 资产面 | `CC-02a` / `ECC-01a` | pytest `test_command_registry` + `test_tui_slash_suggester` + `test_doctor_cli` + `test_repair_cli`；repair/doctor CLI smoke |
| `CC-N02-D02` | `Done` | `CC-N02` | `feedback bug` 结构化字段收口 | **`feedback_bug_report_v1`** 新增 `repro_steps[]`、`expected`、`actual`、`attachments[]`；CLI 新增 `--step`、`--expected`、`--actual`、`--attachment`；继续复用 `sanitize_feedback_text` 脱敏，文本/JSON 输出同步展示结构化采集状态 | `CC-02b` / `REL-01b` | pytest `test_feedback_cli`；feedback bug JSON/text CLI smoke |
| `CC-N02-D04` | `Done` | `CC-N02` | feedback bundle / export 脱敏与导出路径策略收口 | 扩展 **`sanitize_feedback_text`**（workspace/home 路径、`/home/<user>`、Slack `xox*`）；**`append_feedback`** 持久化前脱敏；**`export_feedback_jsonl`** 行级再脱敏且 **`feedback_export_v1.workspace`** 与 **`feedback_stats_v1.workspace`** 统一为 **`<workspace>`**；**`feedback_bundle_export_v1`** 不再回传绝对 workspace，新增 **`dest_placement`** 与 **`redaction.warnings`**（工作区外 `--dest` 警告）；**`release_runbook`** 增补 **`feedback bundle`** 步骤 | `CC-N02-D02` | pytest `test_feedback_*` + `test_doctor_cli` + smoke |
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
| `HM-02d-openai` | `Done` | `HM-02` | OpenAI-compatible API Server 最小闭环 | **`GET /v1/models`**（`api_openai_models_v1`）；**`POST /v1/chat/completions`** 非流式与 **`stream=true` SSE**（`api_openai_chat_completion_v1` / `api_openai_chat_completion_chunk_v1`），复用 **`model_response_v1`**；`CAI_API_TOKEN` Bearer 与既有 API 同源；`CAI_METRICS_JSONL` 记录 **`api.chat_completions`** | `MODEL-P0a` `HM-02c` | pytest `test_api_http_server` + smoke |
| `CC-03c` | `Done` | `CC-03` | 模型切换与状态文案最小对齐 | TUI **`#context-label`** 追加 **`· route=sub/pl`** 与迁移警示；**`/models`** 切换与 CLI **`models use`** 同时打印 **`profile_switched: <id>`** | `CC-03b` | pytest |
| `ECC-03b` | `Done` | `ECC-03` | 插件治理最小可验证入口 | **`plugin_compat_matrix_v1.maintenance_checklist`** + **`plugins_compat_check_v1`**（**`plugins --compat-check`**） | `ECC-03a` | pytest |
| `HM-03d-teams` | `Done` | `HM-03` | Teams Gateway 生产路径（下一批第一顺位） | **`gateway teams`**（`bind/get/list/unbind`、`allow`、`health`、`manifest`、`serve-webhook`）；**`gateway_teams_map_v1`** / **`gateway_teams_health_v1`** / **`gateway_teams_manifest_v1`**；`gateway platforms` 与 `gateway maps` 纳入 Teams | `HM-03b` `HM-03c` | pytest `test_gateway_discord_slack_cli` + `test_gateway_maps_summarize` |
| `HM-06b-docker` | `Done` | `HM-06` | Runtime **docker** 后端产品化 | **`runtime.docker`** 支持 `container` / `image` 双模式、`workdir`、`volume_mounts`、`cpus`、`memory`；**`doctor_runtime_v1.describe`** 暴露 mode/image/workdir/volumes/limits | `HM-06a` | pytest `test_runtime_docker_mock` + smoke |
| `HM-06c-ssh` | `Done` | `HM-06` | Runtime **SSH** 后端产品化 | **`runtime.ssh`** 诊断补齐 `ssh_binary_present`、key/known_hosts 存在性、连接超时；新增可选 **`runtime_ssh_audit_v1`** JSONL 审计（默认不记录命令明文） | `HM-06a` | pytest `test_runtime_ssh_mock` + smoke |
| `HM-04c` | `Done` | `HM-04` | Dashboard 高级交互预览契约 | **`ops_dashboard_interactions_v1`**；`GET /v1/ops/dashboard/interactions` 支持 `schedule_reorder_preview` / `gateway_bind_edit_preview`，固定 dry-run、无写入 | `HM-04b` | pytest `test_ops_http_server` |
| `HM-03e-prod` | `Done` | `HM-03` | Gateway 生产化状态摘要 | **`gateway prod-status --json`** 输出 **`gateway_production_summary_v1`**，汇总 Telegram/Discord/Slack/Teams map/health/env/run-state，本地只读无外部 API | `HM-03b` | pytest `test_gateway_lifecycle_cli` + smoke |
| `ECC-03c` | `Done` | `ECC-03` | 插件兼容矩阵 CI snapshot | **`scripts/gen_plugin_compat_snapshot.py`** 生成/校验 **`docs/schema/plugin_compat_matrix_v1.snapshot.json`**；snapshot 内嵌 `plugin_compat_matrix_v1` 与 `plugin_compat_matrix_check_v1` | `ECC-03b` | pytest `test_plugin_compat_matrix` + smoke `--check` |
| `HM-05d` | `Done` | `HM-05` | Memory providers 扩展 / 用户模型深化 | **`memory provider --json`** 输出 **`memory_provider_contract_v1`**，描述 local entries / user-model SQLite provider 与 future external adapter 边界 | `HM-05a/b/c` | pytest `test_memory_provider_contract_cli` + smoke |
| `HM-N05-D01` | `Done` | `HM-N05` | Gateway 平台 adapter 契约统一 | 在 **`gateway_platforms_v1`** 为每个平台补齐 **`gateway_platform_adapter_contract_v1`**（`send/receive/health/map/lifecycle`），并让 **`gateway_production_summary_v1`** 透传该契约，减少新平台接入时的能力面漂移与重复逻辑 | `HM-03e-prod` | pytest `test_ops_gateway_skills_cli` + `test_gateway_user_model_skills_evolution` + `test_gateway_lifecycle_cli` |
| `HM-N05-D02` | `Done` | `HM-N05` | Signal adapter skeleton + CLI 配置面 | 新增 **`gateway signal`**（`bind/get/list/unbind`、`allow`、`health`）与 **`gateway_signal_map_v1`** / **`gateway_signal_health_v1`**；`gateway_platforms_v1` 将 Signal 升级为 `mvp` 并补齐环境变量提示与 adapter contract | `HM-N05-D01` | pytest `test_gateway_discord_slack_cli` + gateway suites + smoke |
| `HM-N05-D03` | `Done` | `HM-N05` | Email adapter 最小链路（SMTP/IMAP 配置面） | 新增 **`gateway email`**（`bind/get/list/unbind`、`allow`、`send`、`receive`、`health`），落地 **`gateway_email_map_v1`** / **`gateway_email_health_v1`** / **`gateway_email_messages_v1`**，以本地 spool 实现最小发送-读取链路；`gateway_platforms_v1` 将 Email 升级为 `mvp` 并补齐 adapter contract | `HM-N05-D02` | pytest `test_gateway_discord_slack_cli` + gateway suites + smoke |
| `HM-N05-D04` | `Done` | `HM-N05` | Matrix adapter（room map/send/health） | 新增 **`gateway matrix`**（`bind/get/list/unbind`、`allow`、`send`、`receive`、`health`），落地 **`gateway_matrix_map_v1`** / **`gateway_matrix_health_v1`** / **`gateway_matrix_messages_v1`**，并在 `gateway_platforms_v1` 将 Matrix 升级为 `mvp` + adapter contract | `HM-N05-D03` | pytest `test_gateway_discord_slack_cli` + gateway suites + smoke |
| `HM-N05-D05` | `Done` | `HM-N05` | 新平台纳入 prod-status/lifecycle/docs | `gateway_production_summary_v1` 已纳入 Signal/Email/Matrix health+env+map 汇总，`gateway prod-status --json` 平台计数随之扩展；配套测试与 changelog 同步，形成“至少 2 个新平台可见且可验证”的闭环 | `HM-N05-D04` | pytest `test_gateway_lifecycle_cli` + gateway suites + smoke |
| `ECC-N03-D01` | `Done` | `ECC-N03` | local catalog schema（rules/skills/hooks/plugins） | 新增 **`local_catalog_v1`**（`build_local_catalog_payload`）与 **`cai-agent ecc catalog`**，统一输出本地资产目录、items 计数、hooks 解析状态与 plugin surface 摘要，作为跨 harness home-sync / catalog 的最小机读基线 | `ECC-03c` | pytest `test_ecc_layout_cli` + `test_plugin_compat_matrix` + smoke |
| `ECC-N03-D02` | `Done` | `ECC-N03` | home sync / export manifest 补强 | `export --target` 生成的 manifest 现携带 `local_catalog_schema_version`，并在导出目录新增 **`cai-local-catalog.json`**（`local_catalog_v1`），把 home sync 所需的本地资产清单与导出目标绑定到同一份机读输出 | `ECC-N03-D01` | pytest `test_cli_misc` + `test_ecc_layout_cli` + `test_plugin_compat_matrix` + smoke |
| `ECC-N03-D03` | `Done` | `ECC-N03` | harness 导出目标 inventory（机读） | **`ecc_harness_target_inventory_v1`**（`build_ecc_harness_target_inventory_v1`）、**`cai-agent ecc inventory --json`**、**`doctor_v1.ecc_harness_target_inventory`**；与 **`local_catalog_v1`** 互补（侧重各 harness 导出根与 workspace 源 assets 可观测性） | `ECC-N03-D02` | pytest `test_ecc_layout_cli` + `test_doctor_cli` + smoke |
| `HM-N07-D01` | `Done` | `HM-N07` | workspace federation schema 基线 | `gateway_maps_summarize_v1` 新增 **`gateway_workspace_federation_v1`**（workspaces/platforms/bindings/allowlist 汇总），并由 `gateway_production_summary_v1` 透传 `federation` 字段，形成多工作区聚合的统一机读入口 | `HM-N05-D05` | pytest `test_gateway_maps_summarize` + `test_gateway_lifecycle_cli` + smoke |
| `HM-N07-D02` | `Done` | `HM-N07` | channel monitoring 字段补齐 | `gateway_production_summary_v1.platforms[*]` 新增 `channel_monitoring`（`gateway_channel_monitoring_v1`），统一输出 `last_seen` / `latency_ms` / `error_count` / `owner`，并带 summary 统计，作为后续 proxy/routing 观测基础 | `HM-N07-D01` | pytest `test_gateway_lifecycle_cli` + gateway suites + smoke |
| `HM-N07-D03` | `Done` | `HM-N07` | gateway proxy / routing 最小方案 | 新增 **`gateway_proxy_route_v1`** dry-run 路由契约：CLI `gateway route-preview` 与 API `POST /v1/gateway/route-preview`（仅 dry_run）统一输出 source/route 决策载荷，为后续真实 proxy/routing 执行链路提供稳定入口 | `HM-N07-D02` | pytest `test_gateway_lifecycle_cli` + `test_api_http_server` + smoke |
| `HM-N07-D04` | `Done` | `HM-N07` | CLI/API 联邦汇总输出 | 新增 **`gateway_federation_summary_v1`**：CLI `gateway federation-summary --json` 与 API `GET /v1/gateway/federation-summary` 复用 federation/channel-monitoring 数据，提供统一聚合读口径（platforms/channels/errors 汇总） | `HM-N07-D03` | pytest `test_gateway_lifecycle_cli` + `test_api_http_server` + smoke |
| `HM-N08-D01` | `Done` | `HM-N08` | voice provider contract + doctor 集成 | 新增 **`voice_provider_contract_v1`**（`voice.py`，STT/TTS/health 字段）并接入 doctor 输出（`doctor_v1.voice` + `api_doctor_summary_v1.voice`），形成 voice provider 的统一机读诊断入口 | `HM-07a` | pytest `test_voice_contract` + `test_doctor_cli` + smoke |
| `HM-N08-D02` | `Done` | `HM-N08` | voice config/check CLI | 新增 `cai-agent voice config|check`：`config` 输出 `voice_provider_contract_v1`，`check` 输出 `voice_check_v1` 并按 provider 配置状态返回 0/2；复用同一 voice contract，确保 CLI 与 doctor 口径一致 | `HM-N08-D01` | pytest `test_voice_cli` + `test_voice_contract` + `test_doctor_cli` + smoke |
| `HM-N08-D03` | `Done` | `HM-N08` | gateway voice reply 最小闭环（Telegram） | 新增 `cai-agent gateway telegram voice-reply`：复用 `voice_provider_contract_v1` 输出 provider/health，基于 Telegram `sendVoice` + `voice_file_id` 实现最小语音回发链路；支持 `--voice-file-id`/`CAI_TELEGRAM_VOICE_FILE_ID`、`--telegram-bot-token`/`CAI_TELEGRAM_BOT_TOKEN`，返回 `gateway_telegram_voice_reply_v1` 并按发送结果返回 0/2 | `HM-N08-D02` | pytest `test_gateway_telegram_cli` + `test_voice_cli` + `test_voice_contract` + smoke |
| `HM-N08-D04` | `Done` | `HM-N08` | voice OOS/可用边界文档与成本提示 | 更新 `docs/rfc/HM_07A_VOICE_BOUNDARY.zh-CN.md`：明确“当前可用能力 vs OOS 边界”、`voice config/check` 与 `gateway telegram voice-reply` 的适用范围、以及 provider 成本/合规/上线建议，避免将 Voice 误解为默认实时语音产品线 | `HM-N08-D03` | 文档校对 + changelog/todo/roadmap 回写一致性检查 |
| `HM-N09-D01` | `Done` | `HM-N09` | memory provider registry（list/use/test） | 在保留 `memory provider --json`（`memory_provider_contract_v1`）兼容输出的同时，新增 `memory provider list/use/test`：`list` 输出 `memory_provider_registry_v1`（含 active provider）、`use` 写入 `.cai/memory-provider.json` 切换 active provider、`test` 输出 `memory_provider_test_v1` 做本地 provider 可用性检查，完成 provider 从“只读契约”到“可操作注册表”的最小闭环 | `HM-N08-D04` | pytest `test_memory_provider_contract_cli` + `test_memory_user_model_store_cli` + `test_memory_user_model_export` + smoke |
| `HM-N09-D02` | `Done` | `HM-N09` | builtin local provider 显式注册 | 在 `memory_provider_contract_v1` / `memory_provider_registry_v1` 中新增 `builtin_registry`（`memory_provider_builtin_registry_v1`），集中声明 builtin provider id/default；将 local entries / local user-model 两个本地 provider 的注册信息从隐式硬编码升级为显式注册元数据，便于后续外部 provider 增量接入复用同一注册面 | `HM-N09-D01` | pytest `test_memory_provider_contract_cli` + smoke |
| `HM-N09-D03` | `Done` | `HM-N09` | mock HTTP external provider（contract 验证） | 将 `honcho_external` 从占位升级为可测 mock adapter：`memory provider test --id honcho_external` 现可读取 `CAI_MEMORY_EXTERNAL_MOCK_URL`（可选 `CAI_MEMORY_EXTERNAL_API_KEY`）探测 `/health`，并在 `memory_provider_test_v1.checks` 返回远端 schema/status；同时把 external adapter 状态升级为 `mock_http_available`，满足“无真实服务也可验证 contract” | `HM-N09-D02` | pytest `test_memory_provider_contract_cli` + `test_memory_user_model_store_cli` + `test_memory_user_model_export` + smoke |
| `HM-N09-D04` | `Done` | `HM-N09` | doctor/export/profile 感知 active provider | 新增 `memory_active_provider_v1` 统一视图，并接入 `doctor_v1.memory_provider` / `api_doctor_summary_v1.memory_provider`、`profile_contract_v1.memory_provider`、`export-v2` manifest 的 `active_memory_provider` 字段，使 active memory provider 在诊断、profile 契约、导出产物三处保持一致可观测 | `HM-N09-D03` | pytest `test_doctor_cli` + `test_api_http_server` + `test_model_profiles_cli` + `test_cli_misc` + smoke |
| `HM-N10-D01` | `Done` | `HM-N10` | tool provider contract（web/image/browser/tts） | 新增 `tool_provider_contract_v1`（`tool_provider.py`）统一描述 web/image/browser/tts 的配置状态、权限键与 provider surface；新增 CLI `tools contract --json` 读口，并接入 `doctor_v1.tool_provider` / `api_doctor_summary_v1.tool_provider`，形成 Tool Gateway 的统一机读入口 | `HM-N09-D04` | pytest `test_tool_provider_contract_cli` + `test_doctor_cli` + `test_api_http_server` + smoke |
| `HM-N10-D02` | `Done` | `HM-N10` | 四类工具 registry（list/enable/disable） | 在 `tool_provider.py` 新增 `tool_provider_registry_v1` 与状态持久化（`.cai/tool-providers.json`），支持 web/image/browser/tts 四类 registry 的 `list`/`enable`/`disable`；CLI 新增 `tools list`、`tools enable <category>`、`tools disable <category>`，可按类别切换启用状态并回读 `enabled_source`，完成 Tool Gateway 的最小可操作注册表 | `HM-N10-D01` | pytest `test_tool_provider_contract_cli` + `test_doctor_cli` + `test_api_http_server` + smoke |
| `HM-N10-D03` | `Done` | `HM-N10` | MCP bridge 复用现有 presets | 新增 `tools bridge --preset <websearch|notebook|websearch/notebook> --json`，直接复用 `mcp_presets.py` 中的 `expand_mcp_preset_choice` + `build_mcp_preset_report` 与现有 `mcp_list_tools` 调用链，输出 `tool_mcp_bridge_v1`（matched/missing/reports/hint）；实现 Tool Gateway 与既有 MCP preset 的桥接而非重复实现 | `HM-N10-D02` | pytest `test_tool_provider_contract_cli` + `test_mcp_presets_tui_quickstart` + `test_doctor_cli` + `test_api_http_server` + smoke |
| `HM-N10-D04` | `Done` | `HM-N10` | 至少一类真实 provider 接入 | 新增真实 web provider 端到端示例 `tools web-fetch --url ... --json`：复用既有 `fetch_url` 工具链做真实抓取，并受 Tool Gateway registry 的 `web` 启停状态控制（禁用时快速失败）。输出 `tool_provider_web_fetch_v1`，形成“contract → registry → bridge → real provider”闭环中的真实执行链路示例 | `HM-N10-D03` | pytest `test_tool_provider_contract_cli` + `test_tools_fetch_url` + `test_doctor_cli` + `test_api_http_server` + smoke |
| `HM-N10-D05` | `Done` | `HM-N10` | approval / policy / cost guard | 新增 `tools guard --json` 输出 `tool_gateway_guard_v1`（approval/policy/cost 三段门禁），并在 `tools web-fetch` 增加 `--estimated-tokens` 与 `cost_budget_max_tokens` 校验（超预算返回 `cost_guard_exceeded`）；同时将 guard 汇总内嵌到 `tool_provider_contract_v1.guard`，确保高风险执行与成本上限都有显式门禁而非静默放行 | `HM-N10-D04` | pytest `test_tool_provider_contract_cli` + `test_tools_fetch_url` + `test_doctor_cli` + `test_api_http_server` + smoke |
| `HM-N11-D01` | `Done` | `HM-N11` | 云后端需求门槛文档 | 更新 `docs/CLOUD_RUNTIME_OOS.zh-CN.md`：新增 `HM-N11-D01` 条件立项门槛清单（授权/安全/合规/产品/工程）与“本轮不做”边界；同步英文伴随文档 `docs/CLOUD_RUNTIME_OOS.md`，明确 cloud runtime 仍为 `Conditional`，未满足门槛前不进入真实云后端实现 | `HM-N10-D05` | 文档一致性校对（ROADMAP/TODOS/CHANGELOG/CLOUD_RUNTIME_OOS） |
| `HM-N11-D02` | `Done` | `HM-N11` | runtime backend interface 与 docker/ssh 对齐 | 在 `runtime/registry.py` 新增 `runtime_backend_interface_v1` 并接入 `runtime_registry_v1.interface`：统一声明 `exec/exists/describe/ensure_workspace` 操作面、各 backend 配置键，以及 docker/ssh 与基线接口的对齐字段（`base_ops_aligned` + describe field 集）；保证未来云后端接入时复用同一接口契约而不破坏现有 local/docker/ssh 路径 | `HM-N11-D01` | pytest `test_runtime_local.py` + `test_runtime_docker_mock.py` + `test_runtime_ssh_mock.py` + smoke |
| `ECC-N04-D01` | `Done` | `ECC-N04` | 资产生态 ingest registry schema 草案 | 新增 `docs/schema/ecc_asset_registry_v1.snapshot.json`（`ecc_asset_registry_v1`）作为最小机读草案，覆盖 `source/license/signature/version/trust` 字段；同步 `docs/schema/README.zh-CN.md` 与 `docs/schema/README.md` 说明该草案为 `draft_snapshot` 且仅 metadata，不进入执行链路，作为后续 `ECC-N04-D02/D03` 的输入基线 | `HM-N11-D02` | registry schema snapshot 校对（`docs/schema` + roadmap/todos/changelog 一致性） |
| `ECC-N04-D02` | `Done` | `ECC-N04` | ingest sanitizer 方案（危险 hook 隔离） | 新增 `docs/ECC_04B_INGEST_SANITIZER_POLICY.zh-CN.md`（及英文伴随文档）定义 `deny-exec`、`metadata-first`、`workspace-only` 的最小策略，并新增 `docs/schema/ecc_ingest_sanitizer_policy_v1.snapshot.json` 作为机读草案（`decision/checks/blocked_patterns`）；与现有 `hook_runtime.py` 的危险命令与路径边界语义对齐，确保不可信资产默认不直接执行 | `ECC-N04-D01` | sanitizer 文档审查 + schema snapshot 校对 + smoke |
| `ECC-N04-D03` | `Done` | `ECC-N04` | provenance / signature / trust 策略与机读草案 | 新增 `docs/ECC_04C_INGEST_PROVENANCE_TRUST.zh-CN.md`（及英文伴随文档）与 `docs/schema/ecc_ingest_provenance_trust_v1.snapshot.json`（`ecc_ingest_provenance_trust_v1`）：定义与 `ecc_asset_registry_v1` 字段对齐的来源/完整性/签名/信任语义，及与 `ecc_ingest_sanitizer_policy_v1` 合流的保守门禁（v1 仍不开放自动执行）；更新 `ecc_asset_registry_v1.snapshot.json` 的 `boundaries.provenance_policy_included` 与 `docs/schema/README*` 索引 | `ECC-N04-D02` | 文档审查 + `pytest -q cai-agent/tests/test_ecc_ingest_schema_snapshots.py` + smoke |
| `HM-N01-D02` | `Done` | `HM-N01` | profile clone / clone-all（dry-run、家目录、冲突） | 新增 **`cai-agent models clone`** / **`clone-all`**：`profile_home_clone_result_v1`、`models_clone_plan_v1`、`models_clone_all_plan_v1`；支持 **`--dry-run`**、**`--no-copy-home`**、**`--force-home`**、clone 的 **`--set-active`**；实现见 **`profiles.clone_profile_home_tree`** 与 **`__main__._cmd_models`** | `HM-N01-D01` | pytest `test_profile_clone_alias_cli.py` + smoke `models clone --dry-run --json` |
| `HM-N01-D04` | `Done` | `HM-N01` | models alias 可复制命令 | 新增 **`cai-agent models alias`**，输出 **`models_alias_v1`**（POSIX / PowerShell 的 `cd` + `models use` 与示例 `run`） | `HM-N01-D02` | pytest `test_profile_clone_alias_cli.py` + smoke `models alias --json` |
| `HM-N01-D05` | `Done` | `HM-N01` | profile home migration doctor | **`doctor_v1`** / **`api_doctor_summary_v1`** 增加 **`profile_home_migration`**（**`profile_home_migration_diag_v1`**：孤儿 `.cai/profiles/*`、各 profile 标准子目录缺失、legacy explicit 提示）；文本 doctor 增加摘要行 | `HM-N01-D02` | pytest `test_profile_clone_alias_cli.py` + `doctor --json` 字段存在性 |
| `HM-N01-D03` | `Done` | `HM-N01` | active profile 多入口对齐（gateway 收口） | 新增 **`config.load_agent_settings_for_workspace`**（与 API server 加载语义一致）；**`gateway discord`** / **`gateway slack`** 增加 **`--config`**；**`serve_discord_polling`** / **`serve_slack_webhook`** 执行链路改用显式 TOML + 固定 workspace（此前 **`api serve --config`** 与 TUI 已对齐） | `HM-N01-D05` | pytest `test_api_http_server` + 全量 `cai-agent/tests` + smoke |
| `ECC-N01-D02` | `Done` | `ECC-N01` | home sync dry-run / apply | 新增 **`cai-agent ecc sync-home`**（**`ecc_home_sync_result_v1`** / **`ecc_home_sync_plan_v1`**）；**`export --dry-run`** 输出单 harness 计划；**`--apply`** 路径复用 **`export_target`** | `ECC-N03-D02` | pytest `test_ecc_layout_cli` + smoke |
| `ECC-N01-D03` | `Done` | `ECC-N01` | doctor drift 聚合 | **`doctor_v1.ecc_home_sync_drift`**（**`ecc_home_sync_drift_v1`**）；**`export_ecc_dir_diff_v1`** 扩展到 **codex/opencode**；**`api_doctor_summary_v1.ecc_home_sync_drift_targets`** | `ECC-N01-D02` | pytest `test_ecc_layout_cli` + `test_doctor_cli` |
| `ECC-N01-D04` | `Done` | `ECC-N01` | repair 建议 | **`repair_plan_v1`** 增补 **`ecc_sync_commands`** / **`ecc_home_sync_drift_targets`**；无 drift 时回落 **`ecc sync-home --all-targets --dry-run --json`** | `ECC-N01-D03` | pytest `test_repair_cli` |
| `ECC-N02-D01` | `Done` | `ECC-N02` | pack manifest v1 | **`cai-agent ecc pack-manifest`** 输出 **`ecc_asset_pack_manifest_v1`**（per-target 源文件 sha256 + synthetic catalog digest、**`pack_sha256`**） | `ECC-N01-D02` | pytest `test_ecc_layout_cli` + smoke |
| `ECC-N02-D02` | `Done` | `ECC-N02` | export pack dry-run / checksum | 与 D01 共用 manifest 计算；**`export --dry-run`** 与 **`ecc sync-home --dry-run`** 提供计划型 dry-run 出口 | `ECC-N02-D01` | pytest + smoke |
| `CC-N01-D04` | `Done` | `CC-N01` | upgrade 叙事命令面 | **`doctor_v1.upgrade_hints`**（**`doctor_upgrade_hints_v1`**）：统一列出 repair / ecc / export 与文档指针 | `CC-N01-D05` | pytest `test_doctor_cli` |
| `CC-N03-D02` | `Done` | `CC-N03` | plugins sync-home dry-run | 新增 **`cai-agent plugins sync-home`**（**`plugins_sync_home_plan_v1`**）：按 harness 预览将 repo 根 **rules/skills/agents/commands** 同步到与 **`export`/`ecc sync-home`** 一致的导出根；**codex** 标记 **manifest_only**（与 `export_target` 行为对齐） | `ECC-N03-D02` | pytest `test_plugin_compat_matrix` + smoke |
| `CC-N03-D03` | `Done` | `CC-N03` | plugins home drift（doctor/repair/API） | 新增 **`plugins_home_sync_drift_v1`**：复用 **`ecc_home_sync_drift_v1`** 的 **`export_ecc_dir_diff_v1`** 聚合；**`doctor_v1.plugins.home_sync_drift`**；人类 **`doctor`** 插件区漂移摘要；**`repair_plan_v1.plugins_sync_home_preview_commands`**；**`api_doctor_summary_v1.plugins_home_sync_drift_targets`** | `CC-N03-D02` | pytest `test_plugin_compat_matrix` + `test_doctor_cli` + `test_repair_cli` + `test_api_http_server` + smoke |
| `CC-N03-D04` | `In progress` | `CC-N03` | plugins sync-home safe apply | 新增 **`plugins_sync_home_result_v1`** 与 **`plugins sync-home --apply`**：默认阻断目标目录已存在且内容不同的写入，返回 `conflicts[]`；显式 **`--force`** 时先写 `.backup-*` 再替换，`--no-backup` 可关闭备份 | `CC-N03-D03` | 已补 `test_plugin_compat_matrix` 用例；当前沙箱 Python/uv 执行被拒，待复跑 pytest / smoke 后转 Done |
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

*文档版本：2026-04-25。若三上游产品面发生明显变化，先更新 [`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md) 与本页，再决定是否进入新周期。*
