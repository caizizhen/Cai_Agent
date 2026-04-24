# 执行 issue 草案（优先 9 项）

本页把 [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md) §10 里的优先 backlog，整理成可以直接复制到 GitHub Issue 的草案。

使用规则：

- 范围、依赖、验收以本页为准。
- 状态变化先改 `ROADMAP_EXECUTION`，再回写本页。
- 每个 issue 合入后，至少同步 [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md)、[`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md)、[`PARITY_MATRIX.zh-CN.md`](PARITY_MATRIX.zh-CN.md)、`CHANGELOG` 中相关项。

## 摘要

| ID | 建议标题 | 里程碑 | 优先级 |
|---|---|---|---|
| `REL-01a` | 收口 release-ga / doctor / changelog 回写流程 | `M1` / `M5` | `P0` |
| `CC-01a` | 收口 MCP 预设与 WebSearch/Notebook 接入入口 | `M2` | `P1` |
| `CC-02a` | 梳理安装、更新与版本提示体验 | `M2` | `P1` |
| `HM-01a` | 定义 profile 数据模型与持久化结构 | `M3` | `P1` |
| `HM-03a` | 把 Discord 从 MVP 推到生产路径 | `M3` | `P1` |
| `HM-04a` | 统一 ops/gateway/status 聚合载荷 | `M3` | `P1` |
| `HM-05a` | 补齐 user-model store/query/learn 主链路 | `M3` | `P1` |
| `ECC-01a` | 统一 rules/skills/hooks 资产目录与模板 | `M4` | `P1` |
| `ECC-02a` | 把 routing/profile/budget 变成稳定产品路径 | `M4` | `P1` |

## REL-01a 收口 release-ga / doctor / changelog 回写流程

| 字段 | 内容 |
|---|---|
| 建议标签 | `type:feature` `area:release` `priority:p0` |
| 背景 | 当前已有 `release-ga`、`doctor`、T7 checklist、CHANGELOG 约定，但仍偏分散，发版闭环对维护者经验依赖较高。 |
| 目标 | 把发版流程收口成一条固定 runbook，明确命令顺序、输入输出和文档回写点。 |
| In scope | 统一 `release-ga`、`doctor`、smoke、CHANGELOG、Parity、反馈摘要之间的关系；明确 runbook；补齐必要字段或说明。 |
| Out of scope | 不在本 issue 中引入新的发布平台、安装器或云部署方案。 |
| 交付物 | 发版 runbook；必要的 CLI 输出说明；回写约定；最小示例流程。 |
| 验收标准 | 维护者可以按单一路径完成一次标准发版前检查；不再依赖口头流程。 |
| 验证 | `doctor`、`python scripts/smoke_new_features.py`、T7 checklist 手工走查。 |
| 回写 | `PRODUCT_PLAN`、`PRODUCT_GAP_ANALYSIS`、`PARITY_MATRIX`、`CHANGELOG_SYNC`。 |
| 依赖 | 无。 |

## CC-01a 收口 MCP 预设与 WebSearch/Notebook 接入入口

| 字段 | 内容 |
|---|---|
| 建议标签 | `type:feature` `area:ux` `area:mcp` `priority:p1` |
| 背景 | 当前 WebSearch / Notebook 已经明确 `MCP 优先`，但入口仍散落在 `mcp-check`、专题文档和使用者经验里。 |
| 目标 | 让用户能从同一个入口完成“发现能力 -> 自检 -> 套模板 -> 开始使用”。 |
| In scope | 收口 `mcp-check --preset websearch/notebook`、模板输出、onboarding 入口、帮助文案、最短接入路径。 |
| Out of scope | 不内置 WebSearch API，不实现原生 notebook 编辑器。 |
| 交付物 | 命令帮助优化；模板说明；onboarding / docs 入口统一；最短路径示例。 |
| 验收标准 | 新用户能够只靠仓库文档和 CLI 帮助完成一次 preset 检查和模板接入。 |
| 验证 | `mcp-check --preset websearch --list-only`、`mcp-check --preset notebook --print-template` 手工冒烟。 |
| 回写 | `PRODUCT_PLAN`、`PRODUCT_GAP_ANALYSIS`、`PARITY_MATRIX`、`WEBSEARCH_NOTEBOOK_MCP`。 |
| 依赖 | 无。 |

## CC-02a 梳理安装、更新与版本提示体验

| 字段 | 内容 |
|---|---|
| 建议标签 | `type:feature` `area:ux` `priority:p1` |
| 背景 | 当前 `init` / `doctor` / `run` 主链路已可用，但安装、升级、版本差异和常见错误处理仍偏工程化。 |
| 目标 | 给出更接近产品化的安装与更新体验，让首次使用和升级过程更顺。 |
| In scope | 安装/升级路径梳理；版本提示；常见错误指引；必要的 onboarding 调整。 |
| Out of scope | 不在本 issue 中实现官方安装器，不改包管理分发策略。 |
| 交付物 | 文档化安装/升级路径；版本提示约定；常见错误排查说明。 |
| 验收标准 | 新用户可以按统一文档从安装走到 `doctor` 和首次 `run`；升级用户知道版本差异要看哪里。 |
| 验证 | 按 onboarding 走通一遍；检查 README 与 docs 入口一致。 |
| 回写 | `README.md`、`README.zh-CN.md`、`ONBOARDING.zh-CN.md`、`PRODUCT_GAP_ANALYSIS`。 |
| 依赖 | 无。 |

## HM-01a 定义 profile 数据模型与持久化结构

| 字段 | 内容 |
|---|---|
| 建议标签 | `type:design` `area:profiles` `source:hermes` `priority:p1` |
| 背景 | 当前已有 `[[models.profile]]` 和相关 CLI/TUI，但与 Hermes 的 profile 产品面相比，还缺少更统一的数据结构和迁移口径。 |
| 目标 | 先把 profile 的契约定清楚，再推进命令、TUI、持久化和迁移。 |
| In scope | profile schema、默认项、激活规则、命名、迁移策略、与 session/status 的关系。 |
| Out of scope | 不在本 issue 中完成全部 profile 命令实现。 |
| 交付物 | profile 契约说明；建议 schema；迁移与兼容规则；后续实现拆分点。 |
| 验收标准 | 团队能基于统一 schema 开发 `HM-01b`，不会再出现 profile 字段口径分叉。 |
| 验证 | 设计评审；示例配置；与现有 `models` / `/models` / `/status` 对齐检查。 |
| 回写 | `ROADMAP_EXECUTION`、`PRODUCT_GAP_ANALYSIS`、必要时补 schema 文档。 |
| 依赖 | 无。 |

## HM-03a 把 Discord 从 MVP 推到生产路径

| 字段 | 内容 |
|---|---|
| 建议标签 | `type:feature` `area:gateway` `source:hermes` `priority:p1` |
| 背景 | 当前 Discord 已经有 MVP，但离生产路径还缺 slash、mapping 健康、值班与排障资料。 |
| 目标 | 把 Discord 从“能跑”推进到“可接入、可排障、可值班”。 |
| In scope | Slash / interaction 主路径、映射健康、`doctor` 指标、运行说明、故障排查入口。 |
| Out of scope | 不在本 issue 中引入更多平台，也不处理 Voice。 |
| 交付物 | Discord 生产路径命令/文档；健康检查；最小 runbook。 |
| 验收标准 | 能跑通至少一条真实消息链路，并且故障排查文档完整。 |
| 验证 | gateway smoke、`doctor`、手工真实链路。 |
| 回写 | `PRODUCT_PLAN`、`PARITY_MATRIX`、gateway 相关文档、CHANGELOG。 |
| 依赖 | 无。 |

## HM-04a 统一 ops/gateway/status 聚合载荷

| 字段 | 内容 |
|---|---|
| 建议标签 | `type:feature` `area:ops` `source:hermes` `priority:p1` |
| 背景 | 当前 `board`、`observe`、`ops dashboard`、gateway 状态各自可用，但还没有完全同源的聚合口径。 |
| 目标 | 先把只读运营面板所需的核心载荷统一，减少多套状态源。 |
| In scope | `board` / `observe` / `ops` / gateway 状态聚合字段；状态命名；最小 JSON snapshot。 |
| Out of scope | 不在本 issue 中做写操作、RBAC 或复杂前端交互。 |
| 交付物 | 统一聚合字段；载荷说明；消费方约定；必要的 snapshot 或示例。 |
| 验收标准 | `ops serve`、`board`、gateway 状态说明不再互相打架，消费方能依赖单一口径。 |
| 验证 | JSON snapshot 对照；CLI 输出检查；浏览器或本地消费演示。 |
| 回写 | `OPS_DYNAMIC_WEB_API`、`PRODUCT_PLAN`、`PARITY_MATRIX`、`ROADMAP_EXECUTION`。 |
| 依赖 | 无。 |

## HM-05a 补齐 user-model store/query/learn 主链路

| 字段 | 内容 |
|---|---|
| 建议标签 | `type:feature` `area:memory` `source:hermes` `priority:p1` |
| 背景 | 当前用户模型已经有 `behavior_extract` 和 `export`，但还没有真正闭环的 store/query/learn 产品路径。 |
| 目标 | 把用户模型推进到“能抽取、能存、能查、能学、能导出”的闭环。 |
| In scope | `user_model_store_v1` 最小持久化；query/learn 命令；与 export/overview 的关系。 |
| Out of scope | 不在本 issue 中做完整图谱层或多 provider 抽象。 |
| 交付物 | store/query/learn 主链路；最小 schema；回归测试。 |
| 验收标准 | 用户模型具备完整最小闭环，后续 recall/memory provider 工作能接在其上。 |
| 验证 | pytest、smoke、JSON 输出检查。 |
| 回写 | `PRODUCT_PLAN`、`PRODUCT_GAP_ANALYSIS`、`MEMORY_TTL_CONFIDENCE_POLICY`、CHANGELOG。 |
| 依赖 | 无。 |

## ECC-01a 统一 rules/skills/hooks 资产目录与模板

| 字段 | 内容 |
|---|---|
| 建议标签 | `type:feature` `area:ecosystem` `source:ecc` `priority:p1` |
| 背景 | 当前 rules / skills / hooks 已经有能力基础，但资产目录、模板、安装说明还不够统一。 |
| 目标 | 把这些能力从“功能点”推进成“可被团队稳定复用的资产”。 |
| In scope | 目录约定、模板、示例、安装说明、导出与引用关系。 |
| Out of scope | 不在本 issue 中做大规模社区市场或远程仓库治理。 |
| 交付物 | 统一目录和模板；示例资产；最小安装/复用说明。 |
| 验收标准 | 新增一个 skills/hooks/rules 资产时，团队知道该放哪、怎么描述、怎么复用。 |
| 验证 | 示例资产创建；导出/安装路径检查；文档走查。 |
| 回写 | `PRODUCT_PLAN`、`PRODUCT_GAP_ANALYSIS`、相关专题文档、CHANGELOG。 |
| 依赖 | 无。 |

## ECC-02a 把 routing/profile/budget 变成稳定产品路径

| 字段 | 内容 |
|---|---|
| 建议标签 | `type:feature` `area:model-routing` `source:ecc` `priority:p1` |
| 背景 | 当前已有 routing、budget、compact、suggest 等能力，但入口仍偏开发者导向，产品路径不够清晰。 |
| 目标 | 把模型路由、profile 选择和预算治理变成可解释、可使用、可验证的产品能力。 |
| In scope | `models routing-test`、wizard、默认策略、budget 与 profile 的关联说明。 |
| Out of scope | 不在本 issue 中引入新的计费后端或复杂商业化报表。 |
| 交付物 | 稳定的命令入口；默认策略说明；必要的帮助与示例。 |
| 验收标准 | 使用者能理解“为什么选这个模型/路由”，而不是只会手调配置。 |
| 验证 | CLI smoke；文本/JSON 输出检查；文档示例。 |
| 回写 | `MODEL_ROUTING_RULES`、`PRODUCT_PLAN`、`PARITY_MATRIX`、CHANGELOG。 |
| 依赖 | 无。 |

---

如果继续往下开单，建议下一批是：

- **`HM-03c`** / **`ECC-03a`** / **`HM-06a`** / **`HM-07a`**：Explore 调研项（见 **`ROADMAP_EXECUTION`** §10）
- **`api serve` 扩展**（若产品需要）：OpenAPI 文档、更多只读路由、与 **`ops serve`** 的统一鉴权配置
