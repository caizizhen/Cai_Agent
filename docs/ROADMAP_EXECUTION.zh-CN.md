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

完整 issue 草案见 [`ISSUE_BACKLOG.zh-CN.md`](ISSUE_BACKLOG.zh-CN.md)。

- `Done`：本轮已经收口，不再单独开开发单，只保留回归和维护。
- `Ready`：边界清晰，可以直接开开发 issue。
- `Design`：先定契约或数据结构，再开实现 issue。
- `Explore`：保留调研或预研，不进入当前默认交付。

| Issue | 状态 | 对应 To-do | 建议标题 | 主要输出 | 依赖 | 验证 |
|---|---|---|---|---|---|---|
| `DOC-01a` | `Done` | `DOC-01` | 统一根 README 与 docs 入口 | 中英文入口统一、主文档收敛 | — | 手工检查 + 链接检查 |
| `DOC-01b` | `Done` | `DOC-01` | 删除重复 roadmap / backlog 文档 | 删除历史重复页并清理引用 | `DOC-01a` | `rg` 无残链 |
| `REL-01a` | `Done` | `REL-01` | 收口 release-ga / doctor / changelog 回写流程 | 一条固定发版 runbook，明确输入输出 | — | `doctor` + smoke + checklist |
| `REL-01b` | `Ready` | `REL-01` | 统一 feedback、doctor 与发布摘要出口 | `feedback`、`doctor --json`、发版摘要字段同源 | `REL-01a` | JSON schema + smoke |
| `CC-01a` | `Done` | `CC-01` | 收口 MCP 预设与 WebSearch/Notebook 接入入口 | `mcp-check` preset、模板、文档、onboarding 入口统一 | — | 预设探测 + 文档示例 |
| `CC-01b` | `Ready` | `CC-01` | 在 CLI/TUI 暴露 WebSearch/Notebook 推荐入口 | `/mcp`、`/tasks`、帮助信息中补最短路径 | `CC-01a` | TUI / CLI 手工冒烟 |
| `CC-02a` | `Done` | `CC-02` | 梳理安装、更新与版本提示体验 | 安装/升级路径、版本差异提示、常见错误指引 | — | onboarding walkthrough |
| `CC-02b` | `Ready` | `CC-02` | 设计 /bug 等价反馈入口 | 明确命令、字段、落盘位置、脱敏策略 | `REL-01b` | 命令冒烟 + 文档 |
| `CC-03a` | `Ready` | `CC-03` | 统一任务板、状态栏与会话继续体验 | `board`、`/tasks`、会话状态模型统一 | — | CLI/TUI 截面检查 |
| `CC-03b` | `Design` | `CC-03` | 收口模型切换与状态提示 | `/models`、`/status`、profile 反馈更一致 | `HM-01a` | TUI/CLI 手测 |
| `HM-01a` | `Done` | `HM-01` | 定义 profile 数据模型与持久化结构 | profile schema、切换规则、默认项、迁移策略 | — | schema review |
| `HM-01b` | `Ready` | `HM-01` | 落地 profile 管理命令与测试夹具 | CLI/TUI profile 增删改查 + fixture | `HM-01a` | pytest + smoke |
| `HM-02a` | `Design` | `HM-02` | 设计最小 API / server 契约 | 路由、鉴权、输入输出 schema、版本策略 | — | 契约评审 |
| `HM-02b` | `Ready` | `HM-02` | 实现最小只读或任务触发型 API 面 | 最小 server 主路径与文档 | `HM-02a` | integration smoke |
| `HM-03a` | `Done` | `HM-03` | 把 Discord 从 MVP 推到生产路径 | slash / mapping / health / 故障排查收口 | — | gateway smoke + doctor |
| `HM-03b` | `Ready` | `HM-03` | 把 Slack 从 MVP 推到生产路径 | webhook / block kit / mapping / allowlist 收口 | — | gateway smoke + doctor |
| `HM-03c` | `Explore` | `HM-03` | 评估下一批 gateway 平台 | 输出平台优先级与接入边界，不急着实现 | `HM-03a` `HM-03b` | 评估结论文档 |
| `HM-04a` | `Done` | `HM-04` | 统一 ops/gateway/status 聚合载荷 | `board` / `observe` / `ops` 同源字段收口 | — | JSON snapshot |
| `HM-04b` | `Ready` | `HM-04` | 增加只读动态 dashboard 能力 | 先做 SSE 或轮询刷新，不做写操作 | `HM-04a` | 浏览器手测 |
| `HM-05a` | `Done` | `HM-05` | 补齐 user-model store/query/learn 主链路 | 从 `behavior_extract/export` 推到闭环 | — | pytest + smoke |
| `HM-05b` | `Ready` | `HM-05` | 建 recall 评估与负样本机制 | `recall --evaluate`、负样本、报告 schema | `HM-05a` | benchmark/report |
| `HM-05c` | `Ready` | `HM-05` | 把 memory policy 接进 doctor / release gate | policy、TTL、修复命令、发版门禁一致 | `HM-05a` | doctor + release-ga |
| `ECC-01a` | `Done` | `ECC-01` | 统一 rules/skills/hooks 资产目录与模板 | 目录约定、模板、安装说明 | — | 文档 + sample asset |
| `ECC-01b` | `Ready` | `ECC-01` | 收口导出/安装/共享流转 | install/export/share/compatibility 说明统一 | `ECC-01a` | smoke + docs |
| `ECC-02a` | `Done` | `ECC-02` | 把 routing/profile/budget 变成稳定产品路径 | `models routing-test`、wizard、默认策略收口 | — | CLI smoke |
| `ECC-02b` | `Ready` | `ECC-02` | 补齐成本视图与 compact 策略解释 | cost report / profile rollup / compact 触发说明 | `ECC-02a` | JSON/text report |
| `ECC-03a` | `Explore` | `ECC-03` | 插件矩阵与版本治理方案 | 先输出版本语义和兼容策略 | — | 设计文档 |
| `HM-06a` | `Explore` | `HM-06` | Runtime backend 产品化评估 | 明确本地/Docker/SSH 优先级与交付边界 | — | 评估结论 |
| `HM-07a` | `Explore` | `HM-07` | Voice 能力边界评估 | 列清输入输出、平台依赖、是否 OOS | — | 评估结论 |

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
