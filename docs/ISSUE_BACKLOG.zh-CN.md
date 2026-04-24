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
| `HM-03d-teams` | Teams Gateway 生产路径 | `M3` | `P1` |
| `HM-04a` | 统一 ops/gateway/status 聚合载荷 | `M3` | `P1` |
| `HM-05a` | 补齐 user-model store/query/learn 主链路 | `M3` | `P1` |
| `HM-06b-docker` | Runtime docker 后端产品化 | `M5` | `P1` |
| `HM-06c-ssh` | Runtime SSH 后端产品化 | `M5` | `P1` |
| `ECC-01a` | 统一 rules/skills/hooks 资产目录与模板 | `M4` | `P1` |
| `ECC-02a` | 把 routing/profile/budget 变成稳定产品路径 | `M4` | `P1` |
| `ECC-03c` | 插件兼容矩阵 CI snapshot | `M5` | `P1` |

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

## HM-03d-teams Teams Gateway 生产路径

| 字段 | 内容 |
|---|---|
| 建议标签 | `type:feature` `area:gateway` `source:hermes` `priority:p1` |
| 状态 | `Done`（2026-04-25） |
| 背景 | `HM-03c` 已将 Microsoft Teams 评为下一批企业协作平台第一顺位；现有 Slack / Discord gateway 已形成可复用的本地映射、白名单、健康检查与 webhook 模式。 |
| 目标 | 在不引入 Bot Framework SDK 的前提下，先落地 Teams Gateway 的仓内最小生产路径，支持应用注册前 manifest 检查、本地会话映射、Activity webhook 收发与运维自检。 |
| In scope | `gateway teams bind/get/list/unbind`、`allow`、`health`、`manifest`、`serve-webhook`；`gateway_teams_map_v1` / `gateway_teams_health_v1` / `gateway_teams_manifest_v1`；纳入 `gateway platforms` 与 `gateway maps`。 |
| Out of scope | 不内置 Bot Framework JWT 完整校验 SDK；真实云部署的反向代理、AAD 应用注册与 Secret 轮换由部署侧完成，本仓仅提供 manifest 与本地接收器。 |
| 交付物 | `cai_agent.gateway_teams`、CLI 子命令、gateway 汇总入口、pytest 覆盖、文档回写。 |
| 验收标准 | 本地可用 CLI 创建/查询 Teams conversation 映射；health 能显示配置存在性；manifest 可输出 Teams app 草案；Activity `ping` / `status` 可同步响应；gateway 汇总能看到 Teams。 |
| 验证 | `pytest test_gateway_discord_slack_cli.py test_gateway_maps_summarize.py`，全量 pytest，smoke。 |
| 回写 | `ROADMAP_EXECUTION`、`DEVELOPER_TODOS`、`PRODUCT_GAP_ANALYSIS`、`PARITY_MATRIX`、`schema/README`、CHANGELOG。 |
| 依赖 | `HM-03b`、`HM-03c`。 |

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

## HM-06b-docker Runtime docker 后端产品化

| 字段 | 内容 |
|---|---|
| 建议标签 | `type:feature` `area:runtime` `priority:p1` |
| 状态 | `Done`（2026-04-25） |
| 背景 | `HM-06a` 将 docker 列为本地之后的第一优先 runtime 后端；原实现已有 `docker exec` MVP，但镜像、卷挂载、资源限制与 doctor 诊断口径不够完整。 |
| 目标 | 让 docker 后端可用于团队 CI / 可复现构建的最小产品路径，同时继续避免默认云后端。 |
| In scope | `[runtime.docker] image` / `workdir` / `volume_mounts`；保留 `container` 模式；`cpus` / `memory` 限额；`doctor_runtime_v1.describe` 诊断字段；pytest 与 smoke。 |
| Out of scope | 不提供托管云 runtime，不内置镜像构建流水线，不保证本机无 Docker 时可真实执行 docker 后端。 |
| 交付物 | `runtime/docker.py`、`runtime/registry.py`、`config.py`、runtime 单测、schema/changelog/roadmap 回写。 |
| 验收标准 | 配置 `image` 时可生成 `docker run --rm` 命令；配置 `container` 时继续走 `docker exec`；doctor JSON 能看到 mode/image/workdir/volumes/limits。 |
| 验证 | `pytest test_runtime_docker_mock.py test_runtime_tool_dispatch.py test_runtime_local.py`、smoke、全量 pytest。 |
| 回写 | `ROADMAP_EXECUTION`、`DEVELOPER_TODOS`、`PRODUCT_PLAN`、`PRODUCT_GAP_ANALYSIS`、`PARITY_MATRIX`、schema README、CHANGELOG。 |
| 依赖 | `HM-06a`。 |

## HM-06c-ssh Runtime SSH 后端产品化

| 字段 | 内容 |
|---|---|
| 建议标签 | `type:feature` `area:runtime` `priority:p1` |
| 状态 | `Done`（2026-04-25） |
| 背景 | `HM-06a` 将 SSH 列为 docker 之后的第二个默认产品化 runtime 后端；原实现已有 system `ssh` 执行路径，但 key、known_hosts、超时与审计可见性不足。 |
| 目标 | 补齐 SSH runtime 的运维诊断与可选审计，让远程开发/跳板机场景具备可排障入口。 |
| In scope | `doctor_runtime_v1.describe` 暴露 `ssh_binary_present`、key/known_hosts 存在性、严格 host key、连接超时；新增 `runtime_ssh_audit_v1` JSONL 审计，默认不记录命令明文。 |
| Out of scope | 不做真实远端集群编排、不自动分发密钥、不放宽 host key 默认安全策略。 |
| 交付物 | `runtime/ssh.py`、`runtime/registry.py`、`config.py`、SSH 单测、schema/changelog/roadmap 回写。 |
| 验收标准 | 配置 SSH 后端时 doctor JSON 可诊断 key/known_hosts/audit 状态；执行路径能写入审计 JSONL；默认审计不包含命令明文。 |
| 验证 | `pytest test_runtime_ssh_mock.py test_runtime_docker_mock.py test_runtime_tool_dispatch.py test_runtime_local.py`、smoke、全量 pytest。 |
| 回写 | `ROADMAP_EXECUTION`、`DEVELOPER_TODOS`、`PRODUCT_PLAN`、`PRODUCT_GAP_ANALYSIS`、`PARITY_MATRIX`、schema README、CHANGELOG。 |
| 依赖 | `HM-06a`。 |

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

## ECC-03c 插件兼容矩阵 CI snapshot

| 字段 | 内容 |
|---|---|
| 建议标签 | `type:feature` `area:ecosystem` `area:ci` `priority:p1` |
| 状态 | `Done`（2026-04-25） |
| 背景 | `ECC-03b` 已提供 `plugin_compat_matrix_check_v1`，但缺少可纳入 CI 的稳定快照文件与 `--check` 入口。 |
| 目标 | 将插件兼容矩阵治理门禁变成可版本化、可 dry-run 的 snapshot 检查。 |
| In scope | `scripts/gen_plugin_compat_snapshot.py` 写入/校验 `docs/schema/plugin_compat_matrix_v1.snapshot.json`；snapshot 内嵌 `plugin_compat_matrix_v1` 与 `plugin_compat_matrix_check_v1`；pytest 与 smoke 覆盖 `--check`。 |
| Out of scope | 不引入第三方 CI 平台配置，不做插件市场/签名/付费分发。 |
| 交付物 | 生成脚本、snapshot JSON、测试、schema README/changelog/roadmap 回写。 |
| 验收标准 | 修改矩阵后若未刷新 snapshot，`python scripts/gen_plugin_compat_snapshot.py --check` 退出 `2`；当前仓库 snapshot check 退出 `0`。 |
| 验证 | `pytest test_plugin_compat_matrix.py`；`python scripts/gen_plugin_compat_snapshot.py --check`；smoke。 |
| 回写 | `ROADMAP_EXECUTION`、`DEVELOPER_TODOS`、`PARITY_MATRIX`、schema README、CHANGELOG。 |
| 依赖 | `ECC-03b`。 |

---

如果继续往下开单，建议下一批是：

- **Gateway 生产化深化**（Slash/频道监控/多工作区）：以 **`HM-03e-prod`** 为输入单独立项
- **`api serve` 扩展**（若产品需要）：OpenAPI、更多只读路由、与 **`ops serve`** 统一鉴权配置
- **Runtime 云后端**：继续按 OOS/条件立项处理，默认本机 / docker / ssh
