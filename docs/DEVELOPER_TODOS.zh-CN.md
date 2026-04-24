# 开发起步清单（基于 2026-04-24 实测）

这份清单给开发同学回答 3 个问题：

1. **当前仓库能不能开始开发？**
2. **先做哪几项最划算？**
3. **每项应该从哪些文件入手，做完怎么验收？**

产品与排期边界仍以：

- [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md)
- [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md)
- [`ISSUE_BACKLOG.zh-CN.md`](ISSUE_BACKLOG.zh-CN.md)

为准；本页只做开发执行翻译。

测试同学与开发自测配套清单见 [`TEST_TODOS.zh-CN.md`](TEST_TODOS.zh-CN.md)。

---

## 0. 整体执行 TODO（当前建议）

本节不是新的规划源，只是把当前 roadmap/backlog 翻成适合直接开工的执行视图。

使用规则：

- 状态变化先改 [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md)，再同步本页。
- `Doing` 代表已经进入开发；`Ready` 代表边界清楚可直接开干；`Design` 代表先定契约；`Explore` 不进入当前默认交付。

| 状态 | 阶段 | ID | 本轮最小输出 | 验证 |
|---|---|---|---|---|
| `Done` | Sprint A | `REL-01a` | 收口 `release-ga` / `doctor` / `release-changelog` / 回写路径，形成固定 runbook | `doctor`、smoke、T7 checklist |
| `Done` | Sprint A | `CC-01a` | 收口 `mcp-check --preset websearch/notebook`、模板、onboarding 入口 | `mcp-check --preset websearch/notebook` |
| `Done` | Sprint A | `CC-02a` | 梳理安装、升级、版本差异提示与 onboarding | walkthrough 一遍 onboarding |
| `Done` | Sprint B | `HM-01a` | 先定 profile schema、默认项、激活规则、迁移口径 | schema review + pytest |
| `Done` | Sprint B | `HM-03a` | 把 Discord 主路径、mapping、health、排障文档收口 | gateway smoke + `doctor` |
| `Done` | Sprint B | `HM-04a` | 把 `board` / `ops` / gateway 状态字段收成同源 JSON | JSON snapshot + 本地消费检查 |
| `Done` | Sprint C | `HM-05a` | 补齐 user-model store/query/learn 最小闭环 | pytest + smoke |
| `Done` | Sprint C | `ECC-01a` | 统一 rules/skills/hooks 目录、模板、导出说明 | sample asset + 文档走查 |
| `Done` | Sprint C | `ECC-02a` | 收口 routing/profile/budget 产品路径与解释性输出 | CLI smoke + JSON 检查 |

建议执行顺序：

1. 先做 Sprint A，只放 `REL-01a`、`CC-01a`、`CC-02a`。
2. Sprint A 合完后，再开 Sprint B 的 schema 与 gateway/ops 产品化。
3. Memory / Ecosystem 放在 Sprint C，避免与前两轮的 `config.py` / `doctor.py` / README 冲突。

---

## 0.1 逐步开发看板（按当前推进节奏）

下面这张表是“做成一个 TODO、逐步推进”的执行面。每轮开发完成后，优先更新这里。

| 顺序 | 任务 | 当前状态 | 当前轮次 To-do | 完成后同步 |
|---|---|---|---|---|
| `1` | `REL-01a` | `Done` | `doctor` / `release-ga` / `release-changelog` / runbook / writeback 已同源，文本与 JSON 路径都可回归 | `DEVELOPER_TODOS`、`CHANGELOG_SYNC`、schema 文档 |
| `2` | `CC-01a` | `Done` | `mcp-check --preset websearch/notebook`、模板、fallback、quickstart、onboarding 入口已收口 | `DEVELOPER_TODOS`、`WEBSEARCH_NOTEBOOK_MCP`、`ONBOARDING` |
| `3` | `CC-02a` | `Done` | `init` / `doctor` / README / onboarding 的安装、升级、版本差异提示已串成可走通路径 | `DEVELOPER_TODOS`、README、`ONBOARDING`、schema 文档 |
| `4` | `HM-01a` | `Done` | `profile_contract_v1` 已进入 `doctor` / `models list` / `/status`，显式/隐式来源与迁移口径固定 | `DEVELOPER_TODOS`、issue backlog、相关 schema 文档 |
| `5` | `HM-03a` | `Done` | `gateway discord health` / `register-commands` / `list-commands` CLI 已落地；`discord_gateway_health_v1`；`doctor` 含 `discord_map_summary`；排障见 `GATEWAY_DISCORD_TELEGRAM_PARITY` | `DEVELOPER_TODOS`、gateway 文档、CHANGELOG |
| `6` | `HM-04a` | `Done` | `board` / `ops dashboard` / `gateway status` 已共享 `gateway_summary_v1`，状态口径与最小 snapshot 已同源 | `DEVELOPER_TODOS`、`OPS_DYNAMIC_WEB_API` |
| `7` | `HM-05a` | `Done` | **`store init`/`list`**、**`learn`/`query`** 字段与 **`export --with-store`**；**`test_memory_user_model_store_cli.py`**；smoke 闭环 | `DEVELOPER_TODOS`、schema 文档、CHANGELOG |
| `8` | `ECC-01a` | `Done` | **`ecc_layout`** 单源路径；**`ecc layout`/`scaffold`** CLI；**`templates/ecc/*`**；**`CROSS_HARNESS`** 资产表；exporter README 指针 | `DEVELOPER_TODOS`、schema 文档、CHANGELOG |
| `9` | `ECC-02a` | `Done` | **`routing-test`** 默认文本摘要 + JSON **`explain`**；**`cost budget`** 嵌 **`cost_budget_explain_v1`**；文档/schema 已同步 | `DEVELOPER_TODOS`、`MODEL_ROUTING_RULES`、CHANGELOG |

当前默认做法：

1. 每次只推进一项主任务，但顺手把相关文档一起回写。
2. **下一批排期**以 **§0.2** 全量看板与 [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md) §10 为准；§0.0 / §0.1 中 Sprint A～C 的 `*a` 项已全部 `Done`。
3. 当某项从 `Doing` 进入“可回归、可文档化”状态时，再把下一项切到 `Doing`。

本轮同步更新（2026-04-24）：

- `REL-01a`：补上 `release-changelog --json --semantic` 的统一报告 `release_changelog_report_v1`，并把 runbook 提示带回文本输出与 smoke。
- `CC-01a`：`mcp-check --preset` 文本模式现在会直接打印 `preset quickstart`，降低 CLI 首次接入成本。
- `HM-01a`：开始把 profile 契约收成共享 `profile_contract_v1`，先暴露到 `doctor --json` 与 `models list --json`，固定显式/隐式 profile 来源、激活优先级、fallback 与迁移状态。
- `CC-02a`：`init` 文本模式补上建议顺序与文档指针，安装/升级 walkthrough 不再只靠 README 自己串。
- `REL-01a`：`release-ga` 文本模式补上 writeback targets，终端里就能继续完成 changelog / parity / plan 回写。
- `HM-01a`：TUI `/status` 现在也会显示 `profile_contract` 来源与迁移状态，CLI/TUI 口径对齐。
- `HM-01b`：`models add/edit/rm/use/route/list` 的 profile 管理闭环已补进 pytest 与 smoke，`models_list_v1` 会稳定暴露 `profile_contract_v1`、active/subagent/planner 与编辑后的 notes。
- `HM-04a`：`board` / `ops dashboard` / `gateway status` 现在共享 `gateway_summary_v1`，把 `status / bindings_count / webhook_running / allowlist_enabled` 收成同一套读侧字段。
- 文档同步：已将 `HM-04a` 在执行看板中的状态统一回写为 `Done`，并把下一批候选项统一标记为 `Ready`，避免 `Ready/Next` 混用造成误读。

---

## 0.3 剩余任务 Checklist（执行入口）

- [x] `HM-01b`：profile 管理命令与测试夹具
- [x] `HM-03b`：Slack 生产路径收口
- [ ] `HM-04b`：只读动态 dashboard（SSE 或轮询）
- [ ] `HM-05b`：recall 评估与负样本机制
- [ ] `HM-05c`：memory policy 接入 `doctor` / `release-ga`
- [ ] `ECC-01b`：导出 / 安装 / 共享流转说明统一
- [ ] `ECC-02b`：成本视图与 compact 策略解释
- [ ] `HM-02a`：最小 API / server 契约设计
- [ ] `CC-03b`：模型切换与 `/status` 提示统一

执行规则：

1. 先从 `Ready` 项开始，`Design` 只做契约，不直接扩实现。
2. 每次只把一个 issue 做到 `Done`，包含代码、测试、文档、状态回写。
3. 当前默认顺序：`HM-04b` → `HM-05b` → `HM-05c` → `ECC-01b` → `ECC-02b`。

---

## 0.2 文档全量开发任务 To-do 看板（与 ROADMAP §10 / §3 对齐）

**规划源**：[`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md) §3（父级 To-do）、§10（issue 级 backlog）；[`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md) §三之二（演进方向）；[`IMPLEMENTATION_STATUS.zh-CN.md`](IMPLEMENTATION_STATUS.zh-CN.md)（滚动摘要）。

**维护规则**：issue 状态以 **`ROADMAP_EXECUTION` §10** 为准；本表为开发执行翻译，变更时先改 roadmap，再同步本小节。

### 0.2.1 父级 To-do（路线图 §3，里程碑见 ROADMAP §4）

| ID | 优先级 | 能力线 | 本阶段交付（摘要） |
|---|---|---|---|
| `DOC-01` | P0 | 共享 | 文档收敛；主入口中英一致；减少重复 backlog |
| `REL-01` | P0 | 共享 | `release-ga` / `doctor` / `feedback` / CHANGELOG / Parity 固定流程 |
| `CC-01` | P1 | Claude Code | WebSearch/Notebook **MCP 优先**下的预设、自检、模板与任务入口 |
| `CC-02` | P1 | Claude Code | 安装/更新/版本提示与反馈体验 |
| `CC-03` | P1 | Claude Code | CLI/TUI 任务板、继续会话、模型与状态提示统一 |
| `HM-01` | P1 | Hermes | Profiles 数据模型、切换、持久化与 QA |
| `HM-02` | P1 | Hermes | 最小 API/server 面，支持外部驱动 |
| `HM-03` | P1 | Hermes | 多平台 gateway 生产路径（Telegram 外 Discord/Slack 等） |
| `HM-04` | P1 | Hermes | Dashboard 产品化：同源 schema → 只读动态视图 |
| `HM-05` | P1 | Hermes | Memory providers / 用户模型 / recall 治理 |
| `HM-06` | P2 | Hermes | Runtime backends 产品化（云后端条件立项） |
| `HM-07` | P2 | Hermes | Voice 评估与边界，不默认交付 |
| `ECC-01` | P1 | ECC | rules/skills/hooks 资产化与安装叙事 |
| `ECC-02` | P1 | ECC | model-route / 成本与 compact 可解释路径 |
| `ECC-03` | P2 | ECC | 插件/分发/版本治理 |

### 0.2.2 Issue 级全表（与 ROADMAP §10 一致，2026-04-24）

| Issue ID | 状态 | 父 To-do | 主要输出 | 依赖 | 验证 |
|---|---|---|---|---|---|
| `DOC-01a` | `Done` | `DOC-01` | 根 README 与 docs 入口统一 | — | 链接与入口手查 |
| `DOC-01b` | `Done` | `DOC-01` | 删除重复 roadmap/backlog、清残链 | `DOC-01a` | `rg` 无悬空引用 |
| `REL-01a` | `Done` | `REL-01` | 发版 runbook / changelog 回写同源 | — | `doctor`、smoke、T7 |
| `REL-01b` | `Done` | `REL-01` | **`feedback stats`**；**`doctor --json`** 的 **`feedback`** 与 **`release_runbook.feedback`** 同源 | `REL-01a` | pytest + smoke |
| `CC-01a` | `Done` | `CC-01` | `mcp-check` preset、模板、onboarding | — | preset + 文档 |
| `CC-01b` | `Done` | `CC-01` | **`/mcp-presets`**；**`format_tui_mcp_web_notebook_quickstart`**；**`mcp-check` epilog** | `CC-01a` | pytest |
| `CC-02a` | `Done` | `CC-02` | 安装/升级/版本提示/onboarding | — | walkthrough |
| `CC-02b` | `Done` | `CC-02` | **`cai-agent feedback bug`**；**`feedback_bug_report_v1`**；**`sanitize_feedback_text`** | `REL-01b` | pytest |
| `CC-03a` | `Done` | `CC-03` | **`tui_session_strip`** 单源文案 + **`#context-label`** profile 前缀 | — | pytest |
| `CC-03b` | `Design` | `CC-03` | 模型切换与 `/status` 提示与 profile 一致 | `HM-01a` | TUI/CLI 手测 |
| `HM-01a` | `Done` | `HM-01` | profile schema、迁移与默认项 | — | schema review |
| `HM-01b` | `Done` | `HM-01` | **`models add/edit/rm/use/route/list`** 闭环、`profile_contract_v1`、CLI fixture 与 smoke 回归 | `HM-01a` | pytest + smoke |
| `HM-02a` | `Design` | `HM-02` | 最小 API/server 契约 | — | 契约评审 |
| `HM-02b` | `Ready` | `HM-02` | 最小只读或任务触发型 API | `HM-02a` | integration smoke |
| `HM-03a` | `Done` | `HM-03` | Discord 生产路径 | — | gateway smoke + `doctor` |
| `HM-03b` | `Done` | `HM-03` | Slack 生产路径收口 | `gateway slack health`、form Slash/Interactivity 分发、`bind --team-id/--label`、`serve-webhook --execute-on-slash`、测试与文档同步 | gateway smoke + `doctor` |
| `HM-03c` | `Explore` | `HM-03` | 下一批 gateway 平台评估 | `HM-03a` `HM-03b` | 评估文档 |
| `HM-04a` | `Done` | `HM-04` | ops/gateway/status 同源聚合 | — | JSON snapshot |
| `HM-04b` | `Ready` | `HM-04` | 只读动态 dashboard（SSE 或轮询） | `HM-04a` | 浏览器手测 |
| `HM-05a` | `Done` | `HM-05` | user-model store/query/learn 闭环 | — | pytest + smoke |
| `HM-05b` | `Ready` | `HM-05` | recall 评估与负样本机制 | `HM-05a` | benchmark/report |
| `HM-05c` | `Ready` | `HM-05` | memory policy 接入 doctor / release gate | `HM-05a` | `doctor` + `release-ga` |
| `ECC-01a` | `Done` | `ECC-01` | 资产目录、模板、`ecc layout` | — | 文档 + 样例 |
| `ECC-01b` | `Ready` | `ECC-01` | 导出/安装/共享流转说明统一 | `ECC-01a` | smoke + docs |
| `ECC-02a` | `Done` | `ECC-02` | routing-test / cost explain 产品路径 | — | CLI smoke |
| `ECC-02b` | `Ready` | `ECC-02` | 成本视图与 compact 策略解释 | `ECC-02a` | JSON/text report |
| `ECC-03a` | `Explore` | `ECC-03` | 插件矩阵与版本治理方案 | — | 设计文档 |
| `HM-06a` | `Explore` | `HM-06` | Runtime backend 交付边界评估 | — | 评估结论 |
| `HM-07a` | `Explore` | `HM-07` | Voice 边界与 OOS 评估 | — | 评估结论 |

### 0.2.3 建议执行波次（默认交付 = Ready + Design；Explore 单独立项）

**波次 0 — 契约（Design，可与波次 1 并行由不同人做）**

1. `HM-02a`（阻塞 `HM-02b`）
2. `CC-03b`（依赖 `HM-01a` 已 Done，可进入设计与评审）

**波次 1 — 高杠杆 Ready（依赖已满足的优先开）**

1. ~~`REL-01b`~~ / ~~`CC-02b`~~ / ~~`CC-01b`~~ / ~~`CC-03a`~~ / ~~`HM-01b`~~ / ~~`HM-03b`~~（Done）
2. `HM-04b`（依赖 `HM-04a` 已 Done），随后 `HM-05b` / `HM-05c`
3. `HM-05b`、`HM-05c`、`ECC-01b`、`ECC-02b`（记忆/ECC 线可与 gateway/ops 并行，注意冲突面：`doctor`、`__main__.py`）

**波次 2 — API 实现**

- `HM-02b`（须在 `HM-02a` 评审通过后）

**波次 3 — 依赖链尾部**

- ~~`CC-02b`~~、~~`CC-03a`~~（Done）

**Explore（不进入当前默认排期，立项后再迁入波次）**：`HM-03c`、`ECC-03a`、`HM-06a`、`HM-07a`。

### 0.2.4 与 `PRODUCT_PLAN` §三之二「后续演进」的对应关系

| 演进主题 | 主要覆盖 Issue |
|---|---|
| Claude Code 线 | **`CC-03b`**（Design；**`CC-03a`** 已 Done） |
| Hermes 线 | ~~`HM-01b`~~ / ~~`HM-03b`~~（Done）、`HM-02a`/`HM-02b`、`HM-04b`、`HM-05b`、`HM-05c`；Explore：`HM-03c`、`HM-06a`、`HM-07a` |
| ECC 线 | `ECC-01b`、`ECC-02b`；Explore：`ECC-03a` |
| 共享 | `REL-01b`；文档持续收敛见父级 `DOC-01`（`DOC-01a/b` 已 Done，后续以 ROADMAP 新增 issue 为准） |

---

## 1. 当前测试结论

2026-04-24 在仓库根 `D:\gitrepo\Cai_Agent` 实测结果：

| 检查项 | 命令 | 结果 |
|---|---|---|
| 全量单测 | `python -m pytest -q cai-agent/tests` | **626 passed**, **3 subtests passed** |
| 冒烟 | `python scripts/smoke_new_features.py` | **PASS**，输出 `NEW_FEATURE_CHECKS_OK` |
| 回归 | `QA_SKIP_LOG=1 python scripts/run_regression.py` | **PASS**，compileall / unittest / smoke / CLI 子集全绿 |

**结论**：当前主线可继续开发，暂时没有“先修红再开发”的阻塞项。

---

## 2. 开发统一约定

开始开发前统一做这几件事：

1. 先看本页的“第一批任务”，不要跳着做 `Explore` 项。
2. 开发前跑一次：
   - `python -m pytest -q cai-agent/tests`
   - `python scripts/smoke_new_features.py`
3. 开发完成后至少回归：
   - 相关 pytest 子集
   - `python scripts/smoke_new_features.py`
   - 必要时 `QA_SKIP_LOG=1 python scripts/run_regression.py`
4. 合入前至少回写：
   - `PRODUCT_PLAN`
   - `PRODUCT_GAP_ANALYSIS`
   - `PARITY_MATRIX`
   - `CHANGELOG`

---

## 3. 第一批直接开干

这 9 项已经按“最适合现在进入开发”的顺序排好。

### 3.1 第一优先组

| ID | 任务 | 为什么先做 | 主要代码入口 | 主要文档入口 | 完成定义 | 验证 |
|---|---|---|---|---|---|---|
| `REL-01a` | 收口 release-ga / doctor / changelog 回写流程 | 发版闭环越晚补，后面维护成本越高 | `cai-agent/src/cai_agent/__main__.py`、`doctor.py`、`feedback.py`、`changelog_sync.py`、`changelog_semantic.py` | `CHANGELOG_SYNC.zh-CN.md`、`docs/qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md` | 发版前检查路径统一，维护者不再靠经验补流程 | `doctor`、smoke、T7 checklist |
| `CC-01a` | 收口 MCP 预设与 WebSearch/Notebook 接入入口 | 这是 Claude Code 体验线里最容易快速收口的一项 | `cai-agent/src/cai_agent/__main__.py`（`mcp-check`）、`scripts/smoke_new_features.py` | `WEBSEARCH_NOTEBOOK_MCP.zh-CN.md`、`ONBOARDING.zh-CN.md` | 用户能靠 CLI 帮助和文档完成 preset 检查和模板接入 | `mcp-check --preset websearch/notebook` |
| `CC-02a` | 梳理安装、更新与版本提示体验 | 首次使用成本决定后面所有反馈质量 | `cai-agent/src/cai_agent/__main__.py`（`init` / 帮助）、`templates/cai-agent.example.toml`、`templates/cai-agent.starter.toml` | `README.md`、`README.zh-CN.md`、`ONBOARDING.zh-CN.md` | 新用户能从安装走到 `doctor` 和首次 `run`，升级用户知道去哪里看差异 | walkthrough 一遍 onboarding |

### 3.2 第二优先组

| ID | 任务 | 为什么现在做 | 主要代码入口 | 主要文档入口 | 完成定义 | 验证 |
|---|---|---|---|---|---|---|
| `HM-01a` | 定义 profile 数据模型与持久化结构 | 后续 `/models`、`/status`、路由、API 都会依赖它 | `config.py`、`profiles.py`、`__main__.py`、`doctor.py`、`tui_model_panel.py`、`tui.py` | `ISSUE_BACKLOG.zh-CN.md`、`MODEL_ROUTING_RULES.zh-CN.md` | profile 契约稳定，后续实现不再口径分叉 | schema review + 相关 pytest |
| `HM-03a` | 把 Discord 从 MVP 推到生产路径 | 多平台 gateway 是 Hermes 线里最能体现产品差异的一项 | `gateway_discord.py`、`gateway_maps.py`、`gateway_platforms.py`、`doctor.py` | `GATEWAY_DISCORD_TELEGRAM_PARITY.zh-CN.md` | Discord 主路径可接入、可排障、可值班 | gateway smoke + `doctor` |
| `HM-04a` | 统一 ops/gateway/status 聚合载荷 | Dashboard 再往前做，必须先解决多套状态源问题 | `ops_dashboard.py`、`ops_http_server.py`、`board_state.py`、`__main__.py` | `OPS_DYNAMIC_WEB_API.zh-CN.md` | `board` / `ops` / gateway 状态字段同源 | JSON snapshot + 本地消费检查 |
| `HM-05a` | 补齐 user-model store/query/learn 主链路 | 这是记忆线里最关键的“从已有功能走向产品化”一步 | `user_model.py`、`user_model_store.py`、`__main__.py` | `docs/rfc/HONCHO_USER_MODEL_EPIC.zh-CN.md`、`MEMORY_TTL_CONFIDENCE_POLICY.zh-CN.md` | 用户模型具备最小闭环：抽取、存储、查询、学习、导出 | pytest + smoke |
| `ECC-01a` | 统一 rules/skills/hooks 资产目录与模板 | 治理线要落地，先让团队知道资产怎么组织 | **`ecc_layout.py`**、`rules.py`、`skill_registry.py`、`hook_runtime.py`、`exporter.py`、`templates/ecc/*` | `CROSS_HARNESS_COMPATIBILITY.zh-CN.md` | 新增资产时，团队知道放哪、怎么复用、怎么导出 | **`ecc layout`/`scaffold`** + 文档走查 |
| `ECC-02a` | 把 routing/profile/budget 变成稳定产品路径 | 当前能力已存在，但还不够“可解释、可操作” | **`model_routing.build_routing_explain_v1`**、**`cost_aggregate.build_cost_budget_explain_v1`**、`__main__.py` | `MODEL_ROUTING_RULES*.md`、schema README | CLI 能用人话/JSON 双语解释路由与预算 | CLI smoke + JSON 输出检查 |

---

## 4. 推荐分工

如果团队要并行开工，建议按下面 4 条线拆：

| 开发线 | 建议任务 | 主要文件 |
|---|---|---|
| CLI / Docs / Release | `REL-01a`、`CC-01a`、`CC-02a` | `__main__.py`、`doctor.py`、README、onboarding、release docs |
| Profiles / Routing | `HM-01a`、`ECC-02a` | `config.py`、`profiles.py`、`model_routing.py`、`doctor.py`、`tui*.py` |
| Gateway / Ops | `HM-03a`、`HM-04a` | `gateway_discord.py`、`gateway_maps.py`、`ops_dashboard.py`、`ops_http_server.py` |
| Memory / Ecosystem | `HM-05a`、`ECC-01a` | `user_model*.py`、`skills.py`、`rules.py`、`hook_runtime.py`、`exporter.py` |

并行时注意：

- `HM-01a` 和 `ECC-02a` 都会碰 `config.py` / `doctor.py`，最好同一个人或同一小组负责。
- `REL-01a` 和 `CC-02a` 都会碰 README / onboarding，避免并行改同一段。
- `HM-03a` 和 `HM-04a` 可以并行，但要先约好 gateway 状态字段命名。

---

## 5. 每项任务的最小子任务模板

开发开工时，不要直接写成一句大标题，建议拆成下面这种格式：

1. **契约**
   - 先定义 schema、字段、状态码、帮助文案或 runbook 结构
2. **实现**
   - 再改 `__main__.py`、核心模块和必要数据结构
3. **测试**
   - 补 pytest
   - 更新 `scripts/smoke_new_features.py` 或 regression 路径
4. **文档**
   - 回写主文档和相关专题文档

---

## 6. 建议开发顺序

最推荐的开工顺序：

1. `REL-01a`
2. `CC-01a`
3. `CC-02a`
4. `HM-01a`
5. `HM-03a`
6. `HM-04a`
7. `HM-05a`
8. `ECC-01a`
9. `ECC-02a`

如果你只打算先拉一个开发 Sprint，建议只放前 3 到 5 项。

---

## 7. 开发完成后的统一回归

每项任务合入前，至少执行：

```powershell
& 'C:\Users\win11\AppData\Local\Programs\Python\Python313\python.exe' -m pytest -q cai-agent/tests
& 'C:\Users\win11\AppData\Local\Programs\Python\Python313\python.exe' scripts/smoke_new_features.py
$env:QA_SKIP_LOG='1'; & 'C:\Users\win11\AppData\Local\Programs\Python\Python313\python.exe' scripts/run_regression.py
```

若只改局部模块，允许先跑子集，但合入前建议至少补一遍 smoke。
