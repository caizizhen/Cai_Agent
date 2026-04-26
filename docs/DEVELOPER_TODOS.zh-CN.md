# 开发 TODO（全量未完成功能版）

> 产品判断来源：[`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md)。测试对齐页：[`TEST_TODOS.zh-CN.md`](TEST_TODOS.zh-CN.md)。已完成归档：[`COMPLETED_TASKS_ARCHIVE.zh-CN.md`](COMPLETED_TASKS_ARCHIVE.zh-CN.md)。
> 低 token 当前开发入口：[`NEXT_ACTIONS.zh-CN.md`](NEXT_ACTIONS.zh-CN.md)。每次调整本页优先级或完成状态时，必须同步更新 `NEXT_ACTIONS`。

这份文档的目标不是只列“下一步 3 件事”，而是尽量覆盖**相对 `claude-code` / `hermes-agent` / `everything-claude-code` 三条能力线仍未完成的功能开发面**，方便开发按块推进，测试按同样的块去补验证。

## 1. 当前结论

截至 2026-04-26：

- 上一轮已经立项的内部 backlog 基本已完成，并通过自动化回归。
- 当前真正需要维护的是“**相对三上游当前公开能力面的未完成功能**”。
- 本页现在按三条能力线维护**尽量全量**的未完成项，不再只保留少数方向性条目。

### 1.1 2026-04-26 状态收敛

以 [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md)、[`COMPLETED_TASKS_ARCHIVE.zh-CN.md`](COMPLETED_TASKS_ARCHIVE.zh-CN.md) 与 `CHANGELOG.zh-CN.md` 为准，以下能力已经从“待开发”转为“已落地/持续维护”，后续只保留回归与小步增强：

- `HM-N05`：Gateway adapter contract、Signal、Email、Matrix 与 prod-status/lifecycle 收口已完成。
- `HM-N07`：workspace federation、channel monitoring、route-preview、federation-summary 已完成。
- `HM-N08`：voice provider contract、`voice config/check`、Telegram voice-reply 与边界文档已完成。
- `HM-N09`：memory provider registry、builtin registry、mock HTTP provider、active provider 可观测已完成。
- `HM-N10`：tool provider contract、registry、MCP bridge、web-fetch、guard 已完成。
- `HM-N11`：cloud runtime 条件立项门槛与 runtime backend interface 已完成。
- `ECC-N03-D01/D02`、`ECC-N04-D01`～`ECC-N04-D03`（registry + sanitizer + provenance/trust 策略与机读草案）已完成；`ECC-N03` 仍可继续做 diff/doctor 深化；`ECC-N04` 后续转向 **import/install 执行链** 与 CLI 联调（另立开发项）。

当前实际开工队列收敛为：

| 顺位 | 能力 | 状态 | 下一步原子任务 |
|---|---|---|---|
| 1 | `CC-N03` Plugin / marketplace / home sync | `Design` | `plugins sync-home --dry-run`、home drift doctor、sync apply 保护（见 §4 表） |
| 2 | `ECC-N02` asset pack 生命周期 | `Ready` | **`ECC-N02-D01`/`D02` 已交付**；下一原子项 **`ECC-N02-D03`/`D04`**（import/install pack 与 pack repair） |
| 3 | `HM-N01` Profile home | `Ready` | **`HM-N01-D03` 已交付**；仍缺 **`HM-N01-D01`**（profile home schema 深化）等 |
| 4 | `ECC-N01` home sync / catalog | `Done` | **`ECC-N01-D02`～`D04` 已交付**（`D01` 与 **`ECC-N03-D01`** 同源 local catalog，不再单列阻塞） |
| 5 | `CC-N01` 安装 / 升级 / 修复 | `Done` | **`CC-N01-D01`～`D04` 已交付**（含 **`doctor_upgrade_hints_v1`**）；后续仅维护与小步增强 |

### 1.2 当前执行 TODO（2026-04-26）

本轮按“命令中心 / TUI slash 补全 / doctor-repair 同源诊断”推进，完成后逐项标记 Done：

| ID | 状态 | 任务 | 验收 |
|---|---|---|---|
| `CC-N01-D05a` | `Done（2026-04-26）` | 建立 `command_discovery_v1`，统一 CLI/TUI/doctor 的命令模板发现视图 | 已覆盖搜索路径、命令列表、数量和 repair hint |
| `CC-N01-D05b` | `Done（2026-04-26）` | TUI `/` 下拉菜单显示所有原生命令与 `commands/*.md` 模板命令，并带说明 | `/code-review` 等模板命令已进入聊天框 `/` 菜单 |
| `CC-N01-D05c` | `Done（2026-04-26）` | `doctor --json` / API summary 暴露 `command_center`，`doctor.sync` 覆盖 commands/skills/rules/hooks 缺失诊断 | JSON 字段稳定，能给出 actionable repair |
| `CC-N01-D05d` | `Done（2026-04-26）` | `repair --apply` 创建最小命令中心资产面：`commands/`、`skills/`、`rules/*`、`hooks/hooks.json` | 新 workspace 能恢复到可发现、可诊断、可补全的最小结构 |
| `CC-N01-D05e` | `Done（2026-04-26）` | 补自动化/烟测验证并记录 Windows sandbox 临时目录限制 | `test_command_registry.py` + `test_tui_slash_suggester.py` 通过；repair/doctor CLI smoke 通过 |
| `CC-N02-D02a` | `Done（2026-04-26）` | `feedback bug` 新增结构化复现步骤字段 | CLI 支持 `--step` 多次传入，JSON 输出 `repro_steps` |
| `CC-N02-D02b` | `Done（2026-04-26）` | `feedback bug` 新增期望/实际行为字段 | CLI 支持 `--expected` / `--actual`，JSON 输出同名结构字段 |
| `CC-N02-D02c` | `Done（2026-04-26）` | `feedback bug` 新增附件列表字段 | CLI 支持 `--attachment` 多次传入，落盘前脱敏 |
| `CC-N02-D02d` | `Done（2026-04-26）` | 补测试与文档验收回写 | `test_feedback_cli.py` 补 human/json 同结构断言；CLI smoke 通过 |

状态说明：

- `Ready`：可以直接开做。
- `Design`：方向明确，但需要先补契约、接口或交互边界。
- `Explore`：先做技术预研，不承诺本轮交付。
- `Conditional`：只有在明确业务需求或授权后才进入开发。
- `OOS`：明确不做，只保留替代路径。

## 2. 使用方式

建议用法：

1. 先看 [PRODUCT_GAP_ANALYSIS.zh-CN.md](PRODUCT_GAP_ANALYSIS.zh-CN.md) 判断“为什么要做”。
2. 再看本页判断“做哪些、先后顺序、打开哪些代码文件”。
3. 最后看 [TEST_TODOS.zh-CN.md](TEST_TODOS.zh-CN.md) 判断“测什么、怎么验收”。

## 3. 模型接入最高优先级（MODEL-P0）

`MODEL-P0` 已全部完成并归档，不再作为当前 TODO 的在做项。

- 交付摘要与验证证据：[`COMPLETED_TASKS_ARCHIVE.zh-CN.md`](COMPLETED_TASKS_ARCHIVE.zh-CN.md)（`MODEL-P0a` / `MODEL-P0b` / `MODEL-P0c`）。
- 里程碑状态源：[`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md) §10（`MODEL-P0` 系列均为 `Done`）。
- 当前文档仅保留未完成事项，避免 Done 项反复堆积。

## 4. Claude Code 线未完成项

| ID | 状态 | 优先级 | 功能 | 当前差距 | 主要代码入口 | 本轮目标 | 本轮不做 | 完成标准 |
|---|---|---|---|---|---|---|---|---|
| `CC-N01` | `Done` | `P0` | 安装 / 升级 / 修复一体化入口 | **`CC-N01-D01`～`D05` 已交付**（repair、`doctor.install`/`doctor.sync`、命令中心、**`doctor_upgrade_hints_v1`**） | `__main__.py`、`doctor.py`、`templates/`、`plugin_registry.py`、`command_registry.py` | 后续仅回归与小步增强（更多密钥形态脱敏等） | 不做平台签名安装器，不做 GUI 安装器 | 新用户可从零跑通；旧用户配置损坏时能用 CLI 恢复最小可用状态 |
| `CC-N02` | `Done` | `P0` | `/bug` 等价反馈与自助诊断链路 | **`CC-N02-D01`～`D04` 已交付**（bundle、triage、结构化 bug、`sanitize_feedback_text` 强化、**bundle/export 路径策略** 与 **JSONL 导出行级再脱敏**） | `feedback.py`、`doctor.py`、`__main__.py`、`release_runbook.py` | 后续仅回归与小步增强（例如更多密钥形态） | 不做在线反馈平台，不做遥测后台 | 用户可在本地完成“诊断 -> 修复尝试 -> bug 反馈导出”一条链路 |
| `CC-N03` | `Design` | `P1` | Plugin / marketplace / home sync | 现在有 plugin compat 与 export，但没有 Claude Code 风格的 marketplace / install / sync 统一表面 | `plugin_registry.py`、`exporter.py`、`ecc_layout.py`、`__main__.py` | 落地 `plugins sync-home --dry-run`、本地 catalog snapshot、home drift doctor、最小 marketplace manifest | 不做公共付费 marketplace，不做远程依赖解析服务 | 资产可安全同步到 home，doctor 能发现漂移，插件/导出/同步口径统一 |
| `CC-N04` | `Design` | `P1` | 更完整的 session / task / recap 体验 | 当前 `/tasks`、session strip、模型切换可用，但还缺 long-session recap、resume 提示、任务过滤和更强的继续体验 | `tui.py`、`tui_task_board.py`、`tui_session_strip.py`、`__main__.py` | 增加 recap / resume 摘要、任务筛选、session restore 提示、长会话继续引导 | 不做远程控制，不做官方云端 review 能力 | 用户离开长会话后，能快速恢复上下文并继续任务，不需要重新阅读整段历史 |
| `CC-N05` | `Explore` | `P2` | 本地 Desktop / GUI 入口 | 当前只有 TUI 和只读/轻交互 Web；还没有真正的本地图形入口包装层 | `ops_http_server.py`、`ops_dashboard.py`、`tui.py` | 评估以本地 dashboard / embedded TUI 为基础做轻量 GUI 包装 | 不做跨平台原生桌面发行版 | 给出方案、依赖、风险与是否立项建议 |
| `CC-N06` | `OOS` | `P2` | 原生 WebSearch / Notebook 重实现 | 当前明确走 `MCP 优先`，没有做内建搜索/Notebook 编辑器 | `mcp_presets.py`、`mcp_serve.py`、相关文档 | 保持 preset / onboarding / fallback 最优，而不是重写功能本体 | 不做原生 web search API，不做原生 notebook editor | 继续通过 MCP 路径完成对齐，不进入默认开发线 |
| `CC-N07` | `Conditional` | `P3` | Remote / web / mobile / 云端 review 面 | 上游有越来越强的远程/云端表面，但本仓没有，也不适合作为默认交付 | 新模块待定 | 只有在明确授权时才评估 | 默认不做封闭服务依赖能力 | 有明确商业/部署需求后再立项 |

## 5. Hermes 线能力项（含已交付项，便于与 §7.3 对照）

`HM-N05`～`HM-N10` 及 `HM-N11` 文档/接口子项已在 [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md) §10 标为 `Done`；下表仍保留一行摘要，避免误以为仍在「全未做」状态。

| ID | 状态 | 优先级 | 功能 | 当前差距 | 主要代码入口 | 本轮目标 | 本轮不做 | 完成标准 |
|---|---|---|---|---|---|---|---|---|
| `HM-N01` | `Ready` | `P0` | Profiles 独立家目录 + alias command | **`HM-N01-D02`/`D03`/`D04`/`D05` 已交付**；仍缺 **`HM-N01-D01`**（profile home schema 深化）与跨组件联调硬验收 | `profiles.py`、`__main__.py`、`doctor.py`、`api_http_server.py`、`gateway_maps.py` | 补齐 **D01** 级 schema/文档，并持续验证 clone/gateway/API/TUI 同源 | 不做多机 profile 同步 | 不同 profile 间的状态、会话、gateway map 真正隔离 |
| `HM-N03` | `Design` | `P1` | API server 扩路由 / OpenAPI / auth 收口 | `api`/`ops` 已共享 **`server_auth`** bearer 解析基线（见 `test_server_auth.py`）；仍缺更完整路由族、OpenAPI 草案与文档化边界 | `api_http_server.py`、`ops_http_server.py`、`server_auth.py`、`doctor.py` | 扩更多只读/状态路由、OpenAPI 草案、与扩路由一起完整收口 auth 叙事 | 不一次性铺满所有 OpenAI API | API 面从“能接”升级到“可管理、可文档化、可演进” |
| `HM-N04` | `Design` | `P1` | Dashboard 安全可写化 | 当前 dashboard 以只读和 dry-run 预览为主，还不是 Hermes 那种可管理界面 | `ops_dashboard.py`、`ops_http_server.py`、`gateway_maps.py`、`doctor.py` | 增加 preview/apply/audit 三段式，先做 2 到 3 个真实写动作 | 不做公网管理台，不做多租户 RBAC | 本机 dashboard 能安全完成有限写操作，并保留审计记录 |
| `HM-N05` | `Done` | `P1` | Gateway 第一批平台扩展 | **已于 ROADMAP §10 交付**（adapter contract、Signal/Email/Matrix、`prod-status`/lifecycle）；后续新平台走 `HM-N06` | `gateway_signal.py`、`gateway_email.py`、`gateway_matrix.py`、`gateway_platforms.py`、`gateway_production.py` | 仅回归与小步增强 | 不重复作为 P0 排期项 | 见 `HM-N05-D01`～`D05` 验收 |
| `HM-N06` | `Explore` | `P2` | Gateway 第二批平台扩展 | Hermes 还有 WhatsApp、Mattermost、Feishu、WeCom、Weixin、BlueBubbles、QQ 等大量平台 | 相关新模块待定 | 第二批平台做技术评估、优先级与抽象复用设计 | 不在本轮同时落地全部平台 | 给出“下一批优先级 + 适配器抽象”方案 |
| `HM-N07` | `Done` | `P1` | Gateway 联邦 / 频道监控 / proxy 模式 | **已于 ROADMAP §10 交付**（federation、channel monitoring、`route-preview`、federation-summary） | `gateway_production.py`、`gateway_maps.py`、`gateway_lifecycle.py`、`api_http_server.py` | 仅回归与小步增强 | 不做跨公网大规模网关编排 | 见 `HM-N07-D01`～`D04` 验收 |
| `HM-N08` | `Done` | `P2` | Voice mode | **已于 ROADMAP §10 交付**（voice contract、CLI、`gateway telegram voice-reply`、边界文档）；高级实时语音等仍按边界文档为 OOS/条件 | `voice.py`、`tui.py`、`gateway_telegram.py`、`doctor.py` | 仅回归与小步增强 | 不做 Discord voice channel bot，不做高级降噪系统 | 见 `HM-N08-D01`～`D04` 验收 |
| `HM-N09` | `Done` | `P2` | External memory providers | **已于 ROADMAP §10 交付**（registry、builtin、mock HTTP、doctor/export/profile 可观测） | `memory.py`、`user_model_store.py`、`profiles.py`、`doctor.py` | 仅回归与小步增强 | 不直接接真实商业记忆服务 | 见 `HM-N09-D01`～`D04` 验收 |
| `HM-N10` | `Done` | `P2` | Tool Gateway 等价能力 | **已于 ROADMAP §10 交付**（contract、registry、MCP bridge、web-fetch、guard） | `tool_provider.py`、`mcp_presets.py`、`plugin_registry.py` | 仅回归与小步增强 | 不做 Nous 订阅式网关，不做云托管工具层 | 见 `HM-N10-D01`～`D05` 验收 |
| `HM-N11` | `Conditional` | `P3` | Cloud runtime backends | **`HM-N11-D01/D02` 已交付**（条件立项文档、runtime backend interface 与 docker/ssh 对齐）；真实 Modal/Daytona 等仍为授权后项 | `runtime/registry.py`、`runtime/modal_stub.py`、`runtime/daytona_stub.py`、`docs/CLOUD_RUNTIME_OOS*.md` | 未授权前不进入真实云后端实现 | 默认不做云执行默认交付 | 有明确远程执行需求后再立项 |

## 6. ECC 线未完成项

| ID | 状态 | 优先级 | 功能 | 当前差距 | 主要代码入口 | 本轮目标 | 本轮不做 | 完成标准 |
|---|---|---|---|---|---|---|---|---|
| `ECC-N01` | `Done` | `P1` | home sync / local catalog / install-repair 收口 | **`ECC-N01-D02`～`D04` 已交付**（`ecc sync-home`、`ecc_home_sync_drift_v1`、`repair_plan_v1.ecc_sync_commands`）；catalog 基线见 **`ECC-N03-D01`** | `plugin_registry.py`、`ecc_layout.py`、`exporter.py`、`doctor.py` | 后续与 **`ECC-N03`** diff 叙事对齐即可 | 不做公共付费 marketplace | 资产分发、同步、修复入口统一，不再是三套叙事 |
| `ECC-N02` | `Ready` | `P1` | asset pack import/export/install/repair | **`ECC-N02-D01`/`D02` 已交付**（`ecc_asset_pack_manifest_v1`、dry-run/checksum）；仍缺 **D03/D04** import/install 与 pack repair | `exporter.py`、`ecc_layout.py`、`templates/ecc/*`、`plugin_registry.py` | 落地 import/install pack 与 pack repair，并与 ingest 执行链衔接 | 不做复杂依赖求解器 | 规则/技能/hooks 可以打包、导入、修复，并保留兼容信息 |
| `ECC-N03` | `Ready` | `P1` | cross-harness doctor / diff | 当前有 compat matrix，但缺“面向 Claude/Codex/Cursor/OpenCode 的差异诊断与一键 diff” | `exporter.py`、`plugin_registry.py`、`doctor.py`、`ecc_layout.py` | 增加 target-aware doctor、home diff、compat drift 输出 | 不做全部 harness 的完整安装器 | 用户可以看懂“本仓资产和目标 harness home 之间还差什么” |
| `ECC-N04` | `Design` | `P2` | 资产生态 ingest / registry format | **`ECC-N04-D01`～`D03` 已交付**（registry、sanitizer、provenance/trust 中英策略 + 三份机读快照）；**缺口**在 ingest **import/install 与执行链** 产品化（与 `ECC-N02` 衔接） | `docs/schema/ecc_*`、`docs/ECC_04B_*`、`docs/ECC_04C_*`、`ecc_layout.py`、`plugin_registry.py` | 将草案接入未来 import 流程与联调测试 | 不做社区市场运营 | 文档—机读—ROADMAP 一致；执行链另单验收 |
| `ECC-N05` | `Explore` | `P2` | 本地 operator / desktop control plane | ECC 已经在探索 dashboard GUI / ecc2 控制面，本仓只有 ops/dashboard 雏形 | `ops_dashboard.py`、`ops_http_server.py`、新 GUI 包装层待定 | 评估本地 operator console 的技术路径 | 不做独立产品线级 GUI 重构 | 输出是否值得立项与复用现有 dashboard 的建议 |

## 7. 原子级开发拆解

下面的 `*-Dxx` 是可直接拆 issue / sprint task 的原子任务。能力级 ID 仍然用于产品口径，原子任务用于开发排期、并行分工和验收回写。

### 7.1 模型接入原子任务

`MODEL-P0-D01`～`MODEL-P0-D14` 已全部完成并归档，不再保留在当前 TODO。

- 归档位置：[`COMPLETED_TASKS_ARCHIVE.zh-CN.md`](COMPLETED_TASKS_ARCHIVE.zh-CN.md)（`MODEL-P0a/b/c` 及 2026-04-25 迁移说明）。

### 7.2 Claude Code 线原子任务

| 子任务 ID | 对应能力 | 交付物 | 主要入口 | 验收点 |
|---|---|---|---|---|
| `CC-N01-D01` | 安装 / 升级 / 修复 | **`Done（2026-04-26）`**：`repair --dry-run|--apply --json`（`repair_plan_v1` / `repair_result_v1`） | `__main__.py`、`doctor.py` | pytest `test_repair_cli.py` |
| `CC-N01-D02` | 安装 / 升级 / 修复 | **`Done（2026-04-26）`**：`doctor_install_v1` | `doctor.py`、`templates/` | pytest `test_doctor_cli.py` |
| `CC-N01-D03` | 安装 / 升级 / 修复 | **`Done（2026-04-26）`**：`doctor_sync_v1` | `doctor.py`、`plugin_registry.py` | pytest `test_doctor_cli.py` |
| `CC-N01-D04` | 安装 / 升级 / 修复 | **`Done（2026-04-26）`**：`doctor_upgrade_hints_v1`（统一 repair/ecc/export 与文档指针） | `doctor.py` | pytest `test_doctor_cli.py` |
| `CC-N01-D05` | 安装 / 升级 / 修复 | 命令中心发现链路：TUI slash 菜单、`commands/*.md`、doctor/repair 诊断同源 | `command_registry.py`、`tui.py`、`doctor.py`、`tests/` | **Done（2026-04-26）**：`/code-review` 等模板命令可补全；doctor/repair 能发现并修复命令资产面 |
| `CC-N02-D01` | 反馈与诊断 | feedback bundle schema，自动附带 doctor 摘要、版本、平台、配置摘要 | `feedback.py`、`doctor.py` | **Done（2026-04-26）**：`feedback bundle --dest ... --json` 输出 `feedback_bundle_v1` / `feedback_bundle_export_v1` |
| `CC-N02-D02` | 反馈与诊断 | `feedback bug` 模板补齐复现步骤、期望行为、实际行为、附件列表 | `feedback.py`、`__main__.py` | **Done（2026-04-26）**：CLI 交互和 JSON 输出都能表达同一结构 |
| `CC-N02-D03` | 反馈与诊断 | 反馈前 triage 提示，串起 `doctor -> repair -> feedback bug` | `doctor.py`、`feedback.py` | **Done（2026-04-26）**：`doctor_feedback_triage_v1` 指向 doctor / repair / feedback bug / feedback bundle 流程 |
| `CC-N02-D04` | 反馈与诊断 | 脱敏策略和导出目录策略收口 | `feedback.py`、`release_runbook.py` | **Done（2026-04-26）**：`sanitize_feedback_text` 扩展；`append_feedback`/JSONL export/bundle 递归脱敏；`feedback_bundle_export_v1` 不泄露绝对 workspace；`dest_placement` + `redaction.warnings`；见 ROADMAP `CC-N02-D04` |
| `CC-N03-D01` | Plugin / marketplace / home sync | 本地 catalog schema，描述 plugin / skill / hook / rule 资产 | `plugin_registry.py`、`ecc_layout.py` | catalog 可生成、可校验、可版本化 |
| `CC-N03-D02` | Plugin / marketplace / home sync | `plugins sync-home --dry-run`，展示将写入/跳过/冲突的文件 | `__main__.py`、`plugin_registry.py` | dry-run 不写文件，diff 可读 |
| `CC-N03-D03` | Plugin / marketplace / home sync | home drift doctor，检测 `.claude` / `.codex` / 目标 harness 漂移 | `doctor.py`、`ecc_layout.py` | 能输出目标、差异、建议命令 |
| `CC-N03-D04` | Plugin / marketplace / home sync | sync apply 的覆盖保护、备份、回滚提示 | `plugin_registry.py`、`exporter.py` | 默认不覆盖用户手改内容，冲突需显式确认 |
| `CC-N04-D01` | Session / task / recap | 长会话 recap 生成与持久化 | `tui_session_strip.py`、`__main__.py` | resume 前能拿到短摘要 |
| `CC-N04-D02` | Session / task / recap | resume hints，根据最近任务、模型、profile、失败命令给提示 | `tui.py`、`tui_task_board.py` | 重新进入会话能看到下一步建议 |
| `CC-N04-D03` | Session / task / recap | `/tasks` 过滤、状态分组、最近变更高亮 | `tui_task_board.py` | 长任务列表可扫描、可定位 |
| `CC-N04-D04` | Session / task / recap | session restore UI 文案和命令出口 | `tui.py`、`__main__.py` | 用户不需要重读历史就能继续工作 |
| `CC-N05-D01` | Desktop / GUI 探索 | 本地 GUI 方案文档，比较 dashboard wrapper、Tauri/Electron、浏览器入口 | `ops_http_server.py`、`ops_dashboard.py`、`docs/` | 输出是否立项建议 |
| `CC-N05-D02` | Desktop / GUI 探索 | 本地 dashboard 启动体验 PoC，减少启动参数和路径暴露 | `ops_http_server.py`、`__main__.py` | 非技术用户能打开本地界面 |
| `CC-N05-D03` | Desktop / GUI 探索 | GUI 包装风险清单：升级、权限、日志、崩溃恢复 | `docs/` | 风险能被产品/开发共同评估 |
| `CC-N06-D01` | MCP 替代路径 | WebSearch / Notebook 的 MCP preset 健康检查 | `mcp_presets.py`、`mcp_serve.py` | 替代路径可被 doctor 发现 |
| `CC-N06-D02` | MCP 替代路径 | 文档明确“原生不做、MCP 优先”的边界 | `docs/` | 用户不会误以为缺失是 bug |
| `CC-N07-D01` | Remote / cloud / mobile 条件项 | 需求触发模板：授权、部署、数据边界、成本、运维 | `docs/` | 未授权前不进入实现 |

### 7.3 Hermes 线原子任务

| 子任务 ID | 对应能力 | 交付物 | 主要入口 | 验收点 |
|---|---|---|---|---|
| `HM-N01-D01` | Profiles | profile home schema，定义 config/session/memory/gateway 的隔离目录 | `profiles.py`、`doctor.py` | 不同 profile 的状态不串 |
| `HM-N01-D02` | Profiles | **`Done（2026-04-26）`**：`models clone` / `clone-all`（dry-run、家目录复制、`--force-home`） | `__main__.py`、`profiles.py` | pytest `test_profile_clone_alias_cli.py` + smoke |
| `HM-N01-D03` | Profiles | **`Done（2026-04-26）`**：`load_agent_settings_for_workspace`；**`gateway discord`/`slack`** 增加 **`--config`** 并在执行链路使用与 **`api serve --config`** 一致的加载语义 | `config.py`、`api_http_server.py`、`gateway_discord.py`、`gateway_slack.py`、`__main__.py` | pytest 全量 + smoke |
| `HM-N01-D04` | Profiles | **`Done（2026-04-26）`**：`models alias`（`models_alias_v1`） | `__main__.py`、`profiles.py` | pytest `test_profile_clone_alias_cli.py` + smoke |
| `HM-N01-D05` | Profiles | **`Done（2026-04-26）`**：`profile_home_migration` 诊断（doctor JSON + 文本摘要） | `doctor.py`、`profiles.py` | pytest `test_profile_clone_alias_cli.py` |
| `HM-N03-D01` | API 扩展 | `/health`、`/v1/status`、`/v1/profiles` 等状态路由 | `api_http_server.py` | ops 和外部工具能读状态 |
| `HM-N03-D02` | API 扩展 | OpenAPI schema 草案或 machine-readable route manifest | `api_http_server.py`、`docs/` | 路由可文档化、可快照测试 |
| `HM-N03-D03` | API 扩展 | API 与 `ops serve` auth 配置收口 | `api_http_server.py`、`ops_http_server.py`、`server_auth.py` | **部分落地**：`server_auth.resolve_bearer_token` 等统一 bearer 解析（`test_server_auth.py`）；**仍待**：与扩路由、OpenAPI、运维文档一起完整收口「如何配 token、哪些路由受保护」 |
| `HM-N03-D04` | API 扩展 | curl / client 示例和故障排查文档 | `docs/` | 开发者能按文档接入 |
| `HM-N04-D01` | Dashboard 可写化 | dashboard action contract：`preview` / `apply` / `audit` | `ops_dashboard.py`、`ops_http_server.py` | 每个写动作必须先 preview |
| `HM-N04-D02` | Dashboard 可写化 | 首批真实写动作：gateway enable/disable、profile switch、map update 中选 2 到 3 个 | `ops_http_server.py`、`gateway_maps.py`、`profiles.py` | 写动作可回归、可回滚或可修复 |
| `HM-N04-D03` | Dashboard 可写化 | audit log，记录操作者、动作、payload 摘要、结果 | `ops_http_server.py`、`doctor.py` | 出问题能追踪 |
| `HM-N04-D04` | Dashboard 可写化 | UI 状态：pending、success、failed、dry-run diff | `ops_dashboard.py` | 浏览器里能看懂动作后果 |
| `HM-N05-D01` | Gateway 平台扩展 | 抽出平台 adapter contract，统一 send/receive/health/map | `gateway_platforms.py`、`gateway_production.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N05-D01` |
| `HM-N05-D02` | Gateway 平台扩展 | Signal adapter skeleton 与 CLI 配置 | `gateway_signal.py`、`__main__.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N05-D02` |
| `HM-N05-D03` | Gateway 平台扩展 | Email adapter，覆盖 SMTP/IMAP 或等价最小方案 | `gateway_email.py`、`gateway_platforms.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N05-D03` |
| `HM-N05-D04` | Gateway 平台扩展 | Matrix adapter，覆盖 room map、send、health | `gateway_matrix.py`、`gateway_maps.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N05-D04` |
| `HM-N05-D05` | Gateway 平台扩展 | 新平台纳入 lifecycle、prod-status、docs | `gateway_lifecycle.py`、`gateway_production.py`、`docs/` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N05-D05` |
| `HM-N06-D01` | Gateway 第二批 | 平台优先级矩阵：WhatsApp、Mattermost、Feishu、WeCom、Weixin、BlueBubbles、QQ | `docs/` | 明确下一批先做什么 |
| `HM-N06-D02` | Gateway 第二批 | 复用 adapter 层的差异点清单：auth、webhook、polling、media | `gateway_platforms.py`、`docs/` | 能判断哪些平台共用实现 |
| `HM-N06-D03` | Gateway 第二批 | 第二批平台 PoC 选择标准 | `docs/` | 未立项平台不会挤占 P0/P1 |
| `HM-N07-D01` | Gateway 联邦 | workspace federation schema，描述多个 workspace/platform/channel 状态 | `gateway_maps.py`、`gateway_production.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N07-D01` |
| `HM-N07-D02` | Gateway 联邦 | channel monitoring 字段：last_seen、latency、error_count、owner | `gateway_production.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N07-D02` |
| `HM-N07-D03` | Gateway 联邦 | gateway proxy / routing 最小方案 | `api_http_server.py`、`gateway_lifecycle.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N07-D03` |
| `HM-N07-D04` | Gateway 联邦 | CLI/API 汇总命令和 JSON 输出 | `__main__.py`、`api_http_server.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N07-D04` |
| `HM-N08-D01` | Voice mode | voice provider contract，定义 STT/TTS/provider health | `voice.py`、`doctor.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N08-D01` |
| `HM-N08-D02` | Voice mode | CLI voice config/check 命令 | `__main__.py`、`voice.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N08-D02` |
| `HM-N08-D03` | Voice mode | 一个 gateway voice reply 最小闭环，优先 Telegram 或 Discord | `gateway_telegram.py`、`gateway_discord.py`、`voice.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N08-D03` |
| `HM-N08-D04` | Voice mode | voice OOS/可用边界文档和成本提示 | `docs/` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N08-D04` |
| `HM-N09-D01` | Memory providers | provider registry，支持 list/use/test | `memory.py`、`user_model_store.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N09-D01` |
| `HM-N09-D02` | Memory providers | builtin local provider 显式注册 | `memory.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N09-D02` |
| `HM-N09-D03` | Memory providers | mock HTTP external provider，用于 contract 验证 | `memory.py`、`doctor.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N09-D03` |
| `HM-N09-D04` | Memory providers | doctor/export/profile 感知 active provider | `doctor.py`、`profiles.py`、`user_model_store.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N09-D04` |
| `HM-N10-D01` | Tool Gateway | tool provider contract，统一 web/image/browser/tts 的配置和权限 | `tool_provider.py`、`plugin_registry.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N10-D01` |
| `HM-N10-D02` | Tool Gateway | 四类工具 registry：web、image、browser、tts | `tool_provider.py`、`mcp_presets.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N10-D02` |
| `HM-N10-D03` | Tool Gateway | MCP bridge，优先复用现有 MCP preset | `mcp_presets.py`、`mcp_serve.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N10-D03` |
| `HM-N10-D04` | Tool Gateway | 至少一类真实 provider 接入 | `tool_provider.py` 等 | **Done（2026-04-25～26）**：见 ROADMAP `HM-N10-D04` |
| `HM-N10-D05` | Tool Gateway | approval / policy / cost guard | `doctor.py`、`plugin_registry.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N10-D05` |
| `HM-N11-D01` | Cloud runtime 条件项 | 云后端需求门槛文档 | `docs/` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N11-D01` |
| `HM-N11-D02` | Cloud runtime 条件项 | runtime backend interface 与现有 docker/ssh 对齐 | `runtime/registry.py` | **Done（2026-04-25～26）**：见 ROADMAP `HM-N11-D02` |

### 7.4 Everything Claude Code 线原子任务

| 子任务 ID | 对应能力 | 交付物 | 主要入口 | 验收点 |
|---|---|---|---|---|
| `ECC-N01-D01` | home sync / catalog | local catalog schema，统一描述 rules/skills/hooks/plugins | `plugin_registry.py`、`ecc_layout.py` | catalog 可校验、可导出 |
| `ECC-N01-D02` | home sync / catalog | **`Done（2026-04-26）`**：`ecc sync-home`（`ecc_home_sync_result_v1`）、`export --dry-run`（`ecc_home_sync_plan_v1`） | `exporter.py`、`__main__.py` | pytest `test_ecc_layout_cli.py` + smoke |
| `ECC-N01-D03` | home sync / catalog | **`Done（2026-04-26）`**：`ecc_home_sync_drift_v1`；`export_ecc_dir_diff_v1` 支持 codex/opencode | `exporter.py`、`doctor.py` | pytest `test_ecc_layout_cli.py` + `test_doctor_cli.py` |
| `ECC-N01-D04` | home sync / catalog | **`Done（2026-04-26）`**：`repair_plan_v1.ecc_sync_commands` | `doctor.py` | pytest `test_repair_cli.py` |
| `ECC-N02-D01` | Asset pack | **`Done（2026-04-26）`**：`ecc pack-manifest` → `ecc_asset_pack_manifest_v1` | `exporter.py`、`__main__.py` | pytest `test_ecc_layout_cli.py` + smoke |
| `ECC-N02-D02` | Asset pack | **`Done（2026-04-26）`**：与 D01 同源 checksum；`export --dry-run` / `ecc sync-home --dry-run` | `exporter.py` | pytest + smoke |
| `ECC-N02-D03` | Asset pack | import/install pack，写入目标 workspace/home | `plugin_registry.py`、`ecc_layout.py` | 安装前能预览影响 |
| `ECC-N02-D04` | Asset pack | pack repair，检测缺失文件、schema drift、兼容性问题 | `doctor.py`、`exporter.py` | 资产包坏了能定位原因 |
| `ECC-N03-D01` | cross-harness doctor | target inventory，列出当前支持的 harness 与 home path | `ecc_layout.py`、`doctor.py` | 输出对开发和用户都可读 |
| `ECC-N03-D02` | cross-harness doctor | home diff，比较 repo asset 与目标 home | `exporter.py`、`doctor.py` | 清楚显示 add/update/skip/conflict |
| `ECC-N03-D03` | cross-harness doctor | compat drift，按 Claude/Codex/Cursor/OpenCode 输出兼容缺口 | `plugin_registry.py`、`ecc_layout.py` | 兼容问题可定位到资产 |
| `ECC-N03-D04` | cross-harness doctor | human/json 双格式报告 | `doctor.py`、`__main__.py` | CLI 和自动化都能消费 |
| `ECC-N04-D01` | 资产生态 ingest | registry schema 草案，包含来源、license、签名、版本 | `docs/schema/` | **Done（2026-04-25～26）**：`ecc_asset_registry_v1` snapshot，见 ROADMAP `ECC-N04-D01` |
| `ECC-N04-D02` | 资产生态 ingest | ingest sanitizer 方案，隔离不可信脚本和危险 hook | `plugin_registry.py`、`docs/` | **Done（2026-04-25～26）**：政策文档 + `ecc_ingest_sanitizer_policy_v1`，见 ROADMAP `ECC-N04-D02` |
| `ECC-N04-D03` | 资产生态 ingest | provenance / signature / trust level 设计与 sanitizer 合流门禁 | `docs/`、`docs/schema/` | **Done（2026-04-26）**：`ECC_04C_*` 中英文档 + `ecc_ingest_provenance_trust_v1.snapshot.json`；见 ROADMAP `ECC-N04-D03` |
| `ECC-N05-D01` | operator / desktop | operator console 范围说明：资产、gateway、profile、dashboard 哪些可管 | `ops_dashboard.py`、`docs/` | 避免 GUI 范围无限扩张 |
| `ECC-N05-D02` | operator / desktop | 复用现有 ops dashboard 的 PoC 路径 | `ops_dashboard.py`、`ops_http_server.py` | 有低成本演进方案 |
| `ECC-N05-D03` | operator / desktop | 包装/发布/升级风险评估 | `docs/` | 决定是否进入正式项目 |

## 8. 推荐开发顺序

如果目标是“尽量贴近三上游”，建议按下面顺序推进（**已交付的 `HM-N05`～`HM-N10` 不再排入主序列**，与 [`NEXT_ACTIONS.zh-CN.md`](NEXT_ACTIONS.zh-CN.md) 一致）：

1. `CC-N03`（plugin / **`plugins sync-home`**、home drift、sync apply 保护）
2. `HM-N01`（**`HM-N01-D01`**：profile home schema 深化；其余子项已交付）
3. `HM-N03`（API 路由族、OpenAPI、`HM-N03-D03` 与文档化一并收口）
4. `HM-N04`（dashboard 可写化）
5. `ECC-N02`（**`ECC-N02-D03`/`D04`**：pack import/repair；D01/D02 已交付）
6. `ECC-N03`（cross-harness doctor / diff；与已交付 **`ecc_home_sync_drift_v1`** 对齐深化）
7. `CC-N04`（session / recap）
8. `HM-N06`（第二批 gateway 平台，Explore）
9. `HM-N11`（真实云 runtime，仅授权后）

（**`CC-N01`/`CC-N02`/`ECC-N01` 能力线本轮已收口为 Done**；**`ECC-N02` 仍剩 D03/D04**。）

解释：

- **P0 先补外部入口**：安装与自修复、反馈闭环、profiles、API 可管理性。
- **P1 再补产品外壳**：dashboard 可写、plugin/home sync、ECC 资产与 pack。
- **P2 差异化**：第二批 gateway、ingest **import/install** 与 pack 生命周期等；ingest **信任策略文档（D01～D03）** 已齐；voice / memory / tool gateway 主路径已在 `HM-N08`～`HM-N10` 交付，此处仅维护与增量。

### 8.1 第一批建议直接开工的原子任务

第一批建议优先开这些原子任务。已完成的大块 HM 项、**`CC-N01`/`CC-N02`**、**`HM-N01-D02`～`D05` 与 `D03`**、**`ECC-N01-D02`～`D04`**、**`ECC-N02-D01`/`D02`** 与 **`ECC-N04-D01`～`D03` 文档基线** 不再重复排入第一批：

1. `CC-N03-D01`
2. `CC-N03-D02`
3. `HM-N01-D01`
4. `ECC-N02-D03`
5. `ECC-N02-D04`
6. `ECC-N03-D01`
7. `ECC-N03-D02`

## 9. OOS / 条件立项边界

这些能力虽然上游有，但本仓默认不进入当前开发线：

| ID | 当前结论 | 替代路径 |
|---|---|---|
| `CC-N06` | `OOS` | 继续走 MCP presets / onboarding |
| `CC-N07` | `Conditional` | 只有明确授权后再评估 |
| `HM-N11` | `Conditional` | 继续 local / docker / ssh 默认路径 |

## 10. 开发统一要求

每个任务进入实现前，至少补齐：

1. 一处主代码入口。
2. 一处自动化验证入口。
3. 一处文档回写入口。
4. 一条“本轮不做什么”的边界说明。

需要同步回写的主文档通常包括：

- `PRODUCT_PLAN`
- `PRODUCT_GAP_ANALYSIS`
- `ROADMAP_EXECUTION`
- `PARITY_MATRIX`
- `TEST_TODOS`
- 相关专题文档

## 11. 当前 QA 基线

2026-04-26 在仓库根 `D:\gitrepo\Cai_Agent` 实测结果：

| 检查项 | 命令 | 结果 |
|---|---|---|
| 全量单测 | `python -m pytest -q cai-agent/tests` | **826 passed**, **3 subtests passed** |
| 冒烟 | `python scripts/smoke_new_features.py` | **PASS**，输出 `NEW_FEATURE_CHECKS_OK` |
| 回归 | `QA_SKIP_LOG=1 python scripts/run_regression.py` | **PASS**，compileall / unittest / smoke / CLI 子集全绿 |
