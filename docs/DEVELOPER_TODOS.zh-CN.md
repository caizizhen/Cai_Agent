# 开发 TODO（全量未完成功能版）

> 产品判断来源：[`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md)。测试对齐页：[`TEST_TODOS.zh-CN.md`](TEST_TODOS.zh-CN.md)。已完成归档：[`COMPLETED_TASKS_ARCHIVE.zh-CN.md`](COMPLETED_TASKS_ARCHIVE.zh-CN.md)。

这份文档的目标不是只列“下一步 3 件事”，而是尽量覆盖**相对 `claude-code` / `hermes-agent` / `everything-claude-code` 三条能力线仍未完成的功能开发面**，方便开发按块推进，测试按同样的块去补验证。

## 1. 当前结论

截至 2026-04-25：

- 上一轮已经立项的内部 backlog 基本已完成，并通过自动化回归。
- 当前真正需要维护的是“**相对三上游当前公开能力面的未完成功能**”。
- 本页现在按三条能力线维护**尽量全量**的未完成项，不再只保留少数方向性条目。

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
| `CC-N01` | `Ready` | `P0` | 安装 / 升级 / 修复一体化入口 | 现在 `init`、`doctor`、文档提示还不够像完整安装面，坏环境自修复能力弱 | `__main__.py`、`doctor.py`、`templates/`、`plugin_registry.py` | 落地 `repair` 或等价命令，补 `doctor.install` / `doctor.sync` 诊断块，收口 onboarding 与 upgrade 路径 | 不做平台签名安装器，不做 GUI 安装器 | 新用户可从零跑通；旧用户配置损坏时能用 CLI 恢复最小可用状态 |
| `CC-N02` | `Ready` | `P0` | `/bug` 等价反馈与自助诊断链路 | `feedback bug` 已有，但还没形成“反馈前先诊断、反馈后可回传上下文”的完整产品面 | `feedback.py`、`doctor.py`、`__main__.py`、`release_runbook.py` | 收口反馈模板、自动附带 doctor 摘要、最小问题 bundle 导出、用户自助 triage 提示 | 不做在线反馈平台，不做遥测后台 | 用户可在本地完成“诊断 -> 修复尝试 -> bug 反馈导出”一条链路 |
| `CC-N03` | `Design` | `P1` | Plugin / marketplace / home sync | 现在有 plugin compat 与 export，但没有 Claude Code 风格的 marketplace / install / sync 统一表面 | `plugin_registry.py`、`exporter.py`、`ecc_layout.py`、`__main__.py` | 落地 `plugins sync-home --dry-run`、本地 catalog snapshot、home drift doctor、最小 marketplace manifest | 不做公共付费 marketplace，不做远程依赖解析服务 | 资产可安全同步到 home，doctor 能发现漂移，插件/导出/同步口径统一 |
| `CC-N04` | `Design` | `P1` | 更完整的 session / task / recap 体验 | 当前 `/tasks`、session strip、模型切换可用，但还缺 long-session recap、resume 提示、任务过滤和更强的继续体验 | `tui.py`、`tui_task_board.py`、`tui_session_strip.py`、`__main__.py` | 增加 recap / resume 摘要、任务筛选、session restore 提示、长会话继续引导 | 不做远程控制，不做官方云端 review 能力 | 用户离开长会话后，能快速恢复上下文并继续任务，不需要重新阅读整段历史 |
| `CC-N05` | `Explore` | `P2` | 本地 Desktop / GUI 入口 | 当前只有 TUI 和只读/轻交互 Web；还没有真正的本地图形入口包装层 | `ops_http_server.py`、`ops_dashboard.py`、`tui.py` | 评估以本地 dashboard / embedded TUI 为基础做轻量 GUI 包装 | 不做跨平台原生桌面发行版 | 给出方案、依赖、风险与是否立项建议 |
| `CC-N06` | `OOS` | `P2` | 原生 WebSearch / Notebook 重实现 | 当前明确走 `MCP 优先`，没有做内建搜索/Notebook 编辑器 | `mcp_presets.py`、`mcp_serve.py`、相关文档 | 保持 preset / onboarding / fallback 最优，而不是重写功能本体 | 不做原生 web search API，不做原生 notebook editor | 继续通过 MCP 路径完成对齐，不进入默认开发线 |
| `CC-N07` | `Conditional` | `P3` | Remote / web / mobile / 云端 review 面 | 上游有越来越强的远程/云端表面，但本仓没有，也不适合作为默认交付 | 新模块待定 | 只有在明确授权时才评估 | 默认不做封闭服务依赖能力 | 有明确商业/部署需求后再立项 |

## 5. Hermes 线未完成项

| ID | 状态 | 优先级 | 功能 | 当前差距 | 主要代码入口 | 本轮目标 | 本轮不做 | 完成标准 |
|---|---|---|---|---|---|---|---|---|
| `HM-N01` | `Ready` | `P0` | Profiles 独立家目录 + alias command | 当前 `models/profile` 能切模型，但不是完整独立 agent home | `profiles.py`、`__main__.py`、`doctor.py`、`api_http_server.py`、`gateway_maps.py` | 支持 profile home、clone/clone-all、active profile 绑定 session/memory/gateway，生成 alias command | 不做多机 profile 同步 | 不同 profile 间的状态、会话、gateway map 真正隔离 |
| `HM-N03` | `Design` | `P1` | API server 扩路由 / OpenAPI / auth 收口 | 就算有 `HM-N02`，也还缺更完整的文档、路由族和与 `ops serve` 的统一边界 | `api_http_server.py`、`ops_http_server.py`、`doctor.py` | 扩更多只读/状态路由、OpenAPI 草案、统一 auth 配置 | 不一次性铺满所有 OpenAI API | API 面从“能接”升级到“可管理、可文档化、可演进” |
| `HM-N04` | `Design` | `P1` | Dashboard 安全可写化 | 当前 dashboard 以只读和 dry-run 预览为主，还不是 Hermes 那种可管理界面 | `ops_dashboard.py`、`ops_http_server.py`、`gateway_maps.py`、`doctor.py` | 增加 preview/apply/audit 三段式，先做 2 到 3 个真实写动作 | 不做公网管理台，不做多租户 RBAC | 本机 dashboard 能安全完成有限写操作，并保留审计记录 |
| `HM-N05` | `Design` | `P1` | Gateway 第一批平台扩展 | 当前 Telegram full；Discord/Slack/Teams 仍偏 MVP；与 Hermes 的平台宽度差距仍大 | 新增 `gateway_signal.py`、`gateway_email.py`、`gateway_matrix.py`；修改 `gateway_platforms.py`、`gateway_production.py`、`__main__.py` | 第一批优先做 `Signal` / `Email` / `Matrix` | 不一次性铺满全部 15+ 平台 | 至少 2 个新平台进入可用路径，并出现在 `gateway prod-status` |
| `HM-N06` | `Explore` | `P2` | Gateway 第二批平台扩展 | Hermes 还有 WhatsApp、Mattermost、Feishu、WeCom、Weixin、BlueBubbles、QQ 等大量平台 | 相关新模块待定 | 第二批平台做技术评估、优先级与抽象复用设计 | 不在本轮同时落地全部平台 | 给出“下一批优先级 + 适配器抽象”方案 |
| `HM-N07` | `Design` | `P1` | Gateway 联邦 / 频道监控 / proxy 模式 | 当前 `prod-status` 是本地只读摘要，还没有多工作区联邦、频道级监控、gateway proxy | `gateway_production.py`、`gateway_maps.py`、`gateway_lifecycle.py`、`api_http_server.py` | 增加 workspace federation、channel monitoring 字段、gateway proxy / routing 方案 | 不做跨公网大规模网关编排 | 多工作区/多平台状态可以被统一汇总和路由 |
| `HM-N08` | `Design` | `P2` | Voice mode | 当前 voice 仍是 OOS 边界，未形成真实语音产品面 | 新增 `voice.py`、修改 `tui.py`、`gateway_telegram.py`、`gateway_discord.py`、`doctor.py` | Phase A 先做 CLI voice contract + provider 检查；Phase B 再做 Telegram/Discord voice reply | 不做 Discord voice channel bot，不做高级降噪系统 | 至少有 CLI voice 配置能力和一个 gateway voice reply 最小闭环 |
| `HM-N09` | `Ready` | `P2` | External memory providers | 当前 `memory_provider_contract_v1` 已有，但还只是 contract，不是真实 provider 体系 | `memory.py`、`user_model_store.py`、`profiles.py`、`doctor.py` | 建 provider registry，显式注册 builtin provider，再补一个 mock external provider | 不直接接真实商业记忆服务 | provider 可列出、切换、测试，doctor 与 export 能识别 active provider |
| `HM-N10` | `Design` | `P2` | Tool Gateway 等价能力 | Hermes 现在把 web search、image generation、browser automation、TTS 放进 Tool Gateway；本仓尚未成体系 | `mcp_presets.py`、`plugin_registry.py`、新工具模块待定 | 先做“本地 provider / MCP / 第三方服务”的统一 contract，覆盖 web/image/browser/tts 四类 | 不做 Nous 订阅式网关，不做云托管工具层 | 工具扩展面从零散能力变成可配置的统一产品面 |
| `HM-N11` | `Conditional` | `P3` | Cloud runtime backends | 当前 docker / ssh 已产品化，云后端仍是 stub / OOS | `runtime/modal_stub.py`、`runtime/daytona_stub.py`、`runtime/registry.py` | 只有在明确授权时才做 Modal/Daytona 等真实后端 | 默认不做云执行默认交付 | 有明确远程执行需求后再立项 |

## 6. ECC 线未完成项

| ID | 状态 | 优先级 | 功能 | 当前差距 | 主要代码入口 | 本轮目标 | 本轮不做 | 完成标准 |
|---|---|---|---|---|---|---|---|---|
| `ECC-N01` | `Design` | `P1` | home sync / local catalog / install-repair 收口 | 当前 compat matrix、layout、export 都有，但 home sync、catalog、修复链路还分散 | `plugin_registry.py`、`ecc_layout.py`、`exporter.py`、`doctor.py` | 收口本地 catalog、sync-home、doctor drift、repair 建议 | 不做公共付费 marketplace | 资产分发、同步、修复入口统一，不再是三套叙事 |
| `ECC-N02` | `Design` | `P1` | asset pack import/export/install/repair | 当前 export 存在，但缺真正的 pack/import/install/repair 生命周期 | `exporter.py`、`ecc_layout.py`、`templates/ecc/*`、`plugin_registry.py` | 定义 pack manifest、import/install/repair 流程、dry-run diff | 不做复杂依赖求解器 | 规则/技能/hooks 可以打包、导入、修复，并保留兼容信息 |
| `ECC-N03` | `Ready` | `P1` | cross-harness doctor / diff | 当前有 compat matrix，但缺“面向 Claude/Codex/Cursor/OpenCode 的差异诊断与一键 diff” | `exporter.py`、`plugin_registry.py`、`doctor.py`、`ecc_layout.py` | 增加 target-aware doctor、home diff、compat drift 输出 | 不做全部 harness 的完整安装器 | 用户可以看懂“本仓资产和目标 harness home 之间还差什么” |
| `ECC-N04` | `Explore` | `P2` | 资产生态 ingest / registry format | ECC 仓本体有更大规模的 agent/skill/rule 生态，而本仓目前只有自有资产面 | `ecc_layout.py`、`plugin_registry.py`、新 registry 模块待定 | 评估外部 pack ingest、registry schema、签名/来源信息 | 不做社区市场运营 | 给出资产生态化吸收的最小技术方案 |
| `ECC-N05` | `Explore` | `P2` | 本地 operator / desktop control plane | ECC 已经在探索 dashboard GUI / ecc2 控制面，本仓只有 ops/dashboard 雏形 | `ops_dashboard.py`、`ops_http_server.py`、新 GUI 包装层待定 | 评估本地 operator console 的技术路径 | 不做独立产品线级 GUI 重构 | 输出是否值得立项与复用现有 dashboard 的建议 |

## 7. 原子级开发拆解

下面的 `*-Dxx` 是可直接拆 issue / sprint task 的原子任务。能力级 ID 仍然用于产品口径，原子任务用于开发排期、并行分工和验收回写。

### 7.1 模型接入原子任务

`MODEL-P0-D01`～`MODEL-P0-D14` 已全部完成并归档，不再保留在当前 TODO。

- 归档位置：[`COMPLETED_TASKS_ARCHIVE.zh-CN.md`](COMPLETED_TASKS_ARCHIVE.zh-CN.md)（`MODEL-P0a/b/c` 及 2026-04-25 迁移说明）。

### 7.2 Claude Code 线原子任务

| 子任务 ID | 对应能力 | 交付物 | 主要入口 | 验收点 |
|---|---|---|---|---|
| `CC-N01-D01` | 安装 / 升级 / 修复 | 新增或收口 `repair` 等价 CLI，支持 `--dry-run`、`--apply`、`--json` | `__main__.py`、`doctor.py` | 坏环境下能输出明确修复计划，`--apply` 后最小配置可用 |
| `CC-N01-D02` | 安装 / 升级 / 修复 | `doctor.install` 诊断块，覆盖 Python、依赖、home、配置、模板 | `doctor.py`、`templates/` | `doctor --json` 中有稳定字段和建议动作 |
| `CC-N01-D03` | 安装 / 升级 / 修复 | `doctor.sync` 诊断块，发现 home drift、缺失模板、旧 schema | `doctor.py`、`plugin_registry.py` | 能区分 warning / error / actionable repair |
| `CC-N01-D04` | 安装 / 升级 / 修复 | upgrade / onboarding 文案与命令路径统一 | `__main__.py`、`docs/` | 新用户和老用户看到的是同一条安装叙事 |
| `CC-N02-D01` | 反馈与诊断 | feedback bundle schema，自动附带 doctor 摘要、版本、平台、配置摘要 | `feedback.py`、`doctor.py` | bundle 可导出、可脱敏、字段稳定 |
| `CC-N02-D02` | 反馈与诊断 | `feedback bug` 模板补齐复现步骤、期望行为、实际行为、附件列表 | `feedback.py`、`__main__.py` | CLI 交互和 JSON 输出都能表达同一结构 |
| `CC-N02-D03` | 反馈与诊断 | 反馈前 triage 提示，串起 `doctor -> repair -> feedback bug` | `doctor.py`、`feedback.py` | 常见问题能先给本地修复建议 |
| `CC-N02-D04` | 反馈与诊断 | 脱敏策略和导出目录策略收口 | `feedback.py`、`release_runbook.py` | token、path、email 等敏感字段不会直接出现在 bundle |
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
| `HM-N01-D02` | Profiles | `profile clone` / `clone-all`，支持 dry-run 和冲突提示 | `__main__.py`、`profiles.py` | clone 后配置完整、敏感项处理明确 |
| `HM-N01-D03` | Profiles | active profile 解析链路，覆盖 CLI、TUI、API、gateway | `profiles.py`、`api_http_server.py`、`gateway_maps.py` | 所有入口读取同一个 active profile |
| `HM-N01-D04` | Profiles | alias command 生成，例如按 profile 输出可复制的启动命令 | `__main__.py`、`profiles.py` | 用户能用 alias 固定进入某个 profile |
| `HM-N01-D05` | Profiles | profile doctor / migration，识别旧模型 profile 与新 profile home 的关系 | `doctor.py`、`profiles.py` | 老配置可迁移，不丢状态 |
| `HM-N03-D01` | API 扩展 | `/health`、`/v1/status`、`/v1/profiles` 等状态路由 | `api_http_server.py` | ops 和外部工具能读状态 |
| `HM-N03-D02` | API 扩展 | OpenAPI schema 草案或 machine-readable route manifest | `api_http_server.py`、`docs/` | 路由可文档化、可快照测试 |
| `HM-N03-D03` | API 扩展 | API 与 `ops serve` auth 配置收口 | `api_http_server.py`、`ops_http_server.py` | 两个 server 的安全边界一致 |
| `HM-N03-D04` | API 扩展 | curl / client 示例和故障排查文档 | `docs/` | 开发者能按文档接入 |
| `HM-N04-D01` | Dashboard 可写化 | dashboard action contract：`preview` / `apply` / `audit` | `ops_dashboard.py`、`ops_http_server.py` | 每个写动作必须先 preview |
| `HM-N04-D02` | Dashboard 可写化 | 首批真实写动作：gateway enable/disable、profile switch、map update 中选 2 到 3 个 | `ops_http_server.py`、`gateway_maps.py`、`profiles.py` | 写动作可回归、可回滚或可修复 |
| `HM-N04-D03` | Dashboard 可写化 | audit log，记录操作者、动作、payload 摘要、结果 | `ops_http_server.py`、`doctor.py` | 出问题能追踪 |
| `HM-N04-D04` | Dashboard 可写化 | UI 状态：pending、success、failed、dry-run diff | `ops_dashboard.py` | 浏览器里能看懂动作后果 |
| `HM-N05-D01` | Gateway 平台扩展 | 抽出平台 adapter contract，统一 send/receive/health/map | `gateway_platforms.py`、`gateway_production.py` | 新平台接入不再复制大量逻辑 |
| `HM-N05-D02` | Gateway 平台扩展 | Signal adapter skeleton 与 CLI 配置 | `gateway_signal.py`、`__main__.py` | 可配置、可 health check |
| `HM-N05-D03` | Gateway 平台扩展 | Email adapter，覆盖 SMTP/IMAP 或等价最小方案 | `gateway_email.py`、`gateway_platforms.py` | 能发送/读取最小消息链路 |
| `HM-N05-D04` | Gateway 平台扩展 | Matrix adapter，覆盖 room map、send、health | `gateway_matrix.py`、`gateway_maps.py` | 能进入 `prod-status` |
| `HM-N05-D05` | Gateway 平台扩展 | 新平台纳入 lifecycle、prod-status、docs | `gateway_lifecycle.py`、`gateway_production.py`、`docs/` | 至少 2 个新平台具备最小可用链路 |
| `HM-N06-D01` | Gateway 第二批 | 平台优先级矩阵：WhatsApp、Mattermost、Feishu、WeCom、Weixin、BlueBubbles、QQ | `docs/` | 明确下一批先做什么 |
| `HM-N06-D02` | Gateway 第二批 | 复用 adapter 层的差异点清单：auth、webhook、polling、media | `gateway_platforms.py`、`docs/` | 能判断哪些平台共用实现 |
| `HM-N06-D03` | Gateway 第二批 | 第二批平台 PoC 选择标准 | `docs/` | 未立项平台不会挤占 P0/P1 |
| `HM-N07-D01` | Gateway 联邦 | workspace federation schema，描述多个 workspace/platform/channel 状态 | `gateway_maps.py`、`gateway_production.py` | 聚合输出稳定 |
| `HM-N07-D02` | Gateway 联邦 | channel monitoring 字段：last_seen、latency、error_count、owner | `gateway_production.py` | 频道级健康可见 |
| `HM-N07-D03` | Gateway 联邦 | gateway proxy / routing 最小方案 | `api_http_server.py`、`gateway_lifecycle.py` | 可把消息路由到目标 workspace/profile |
| `HM-N07-D04` | Gateway 联邦 | CLI/API 汇总命令和 JSON 输出 | `__main__.py`、`api_http_server.py` | 运营脚本可消费 |
| `HM-N08-D01` | Voice mode | voice provider contract，定义 STT/TTS/provider health | `voice.py`、`doctor.py` | provider 可检测、可报错 |
| `HM-N08-D02` | Voice mode | CLI voice config/check 命令 | `__main__.py`、`voice.py` | 无 provider 时有清晰提示 |
| `HM-N08-D03` | Voice mode | 一个 gateway voice reply 最小闭环，优先 Telegram 或 Discord | `gateway_telegram.py`、`gateway_discord.py`、`voice.py` | 真机能收到语音回复 |
| `HM-N08-D04` | Voice mode | voice OOS/可用边界文档和成本提示 | `docs/` | 用户知道哪些语音能力可用 |
| `HM-N09-D01` | Memory providers | provider registry，支持 list/use/test | `memory.py`、`user_model_store.py` | provider 不再只是 contract |
| `HM-N09-D02` | Memory providers | builtin local provider 显式注册 | `memory.py` | 当前行为可被 provider 体系表达 |
| `HM-N09-D03` | Memory providers | mock HTTP external provider，用于 contract 验证 | `memory.py`、`doctor.py` | 无真实服务也能测试外部 provider |
| `HM-N09-D04` | Memory providers | doctor/export/profile 感知 active provider | `doctor.py`、`profiles.py`、`user_model_store.py` | 切 provider 后状态可诊断 |
| `HM-N10-D01` | Tool Gateway | tool provider contract，统一 web/image/browser/tts 的配置和权限 | 新模块待定、`plugin_registry.py` | 工具接入有统一入口 |
| `HM-N10-D02` | Tool Gateway | 四类工具 registry：web、image、browser、tts | 新模块待定、`mcp_presets.py` | 能 list/enable/disable |
| `HM-N10-D03` | Tool Gateway | MCP bridge，优先复用现有 MCP preset | `mcp_presets.py`、`mcp_serve.py` | 不重复造已有 MCP 能力 |
| `HM-N10-D04` | Tool Gateway | 至少一类真实 provider 接入 | 新模块待定 | 有一个端到端示例 |
| `HM-N10-D05` | Tool Gateway | approval / policy / cost guard | `doctor.py`、`plugin_registry.py` | 高风险工具不会静默执行 |
| `HM-N11-D01` | Cloud runtime 条件项 | 云后端需求门槛文档 | `docs/` | 没有授权不写真实云后端 |
| `HM-N11-D02` | Cloud runtime 条件项 | runtime backend interface 与现有 docker/ssh 对齐 | `runtime/registry.py` | 未来接云后端不破坏本地路径 |

### 7.4 Everything Claude Code 线原子任务

| 子任务 ID | 对应能力 | 交付物 | 主要入口 | 验收点 |
|---|---|---|---|---|
| `ECC-N01-D01` | home sync / catalog | local catalog schema，统一描述 rules/skills/hooks/plugins | `plugin_registry.py`、`ecc_layout.py` | catalog 可校验、可导出 |
| `ECC-N01-D02` | home sync / catalog | `sync-home` dry-run/apply，支持 Claude/Codex/Cursor/OpenCode 目标 | `exporter.py`、`ecc_layout.py`、`__main__.py` | 不同 harness 输出差异可见 |
| `ECC-N01-D03` | home sync / catalog | doctor drift，发现目标 home 中缺失、过期、冲突资产 | `doctor.py`、`ecc_layout.py` | 用户知道该同步什么 |
| `ECC-N01-D04` | home sync / catalog | repair 建议，把 drift 转成可执行命令 | `doctor.py`、`plugin_registry.py` | 诊断能落到行动 |
| `ECC-N02-D01` | Asset pack | pack manifest v1，包含资产、目标、兼容性、来源 | `exporter.py`、`templates/ecc/` | manifest 可校验 |
| `ECC-N02-D02` | Asset pack | export pack，支持 dry-run diff 和 checksum | `exporter.py`、`ecc_layout.py` | 打包结果稳定可复现 |
| `ECC-N02-D03` | Asset pack | import/install pack，写入目标 workspace/home | `plugin_registry.py`、`ecc_layout.py` | 安装前能预览影响 |
| `ECC-N02-D04` | Asset pack | pack repair，检测缺失文件、schema drift、兼容性问题 | `doctor.py`、`exporter.py` | 资产包坏了能定位原因 |
| `ECC-N03-D01` | cross-harness doctor | target inventory，列出当前支持的 harness 与 home path | `ecc_layout.py`、`doctor.py` | 输出对开发和用户都可读 |
| `ECC-N03-D02` | cross-harness doctor | home diff，比较 repo asset 与目标 home | `exporter.py`、`doctor.py` | 清楚显示 add/update/skip/conflict |
| `ECC-N03-D03` | cross-harness doctor | compat drift，按 Claude/Codex/Cursor/OpenCode 输出兼容缺口 | `plugin_registry.py`、`ecc_layout.py` | 兼容问题可定位到资产 |
| `ECC-N03-D04` | cross-harness doctor | human/json 双格式报告 | `doctor.py`、`__main__.py` | CLI 和自动化都能消费 |
| `ECC-N04-D01` | 资产生态 ingest | registry schema 草案，包含来源、license、签名、版本 | 新模块待定、`docs/` | 能作为后续生态入口 |
| `ECC-N04-D02` | 资产生态 ingest | ingest sanitizer 方案，隔离不可信脚本和危险 hook | `plugin_registry.py`、`docs/` | 外部资产不会直接执行 |
| `ECC-N04-D03` | 资产生态 ingest | provenance / signature / trust level 设计 | `docs/` | 用户能判断资产可信度 |
| `ECC-N05-D01` | operator / desktop | operator console 范围说明：资产、gateway、profile、dashboard 哪些可管 | `ops_dashboard.py`、`docs/` | 避免 GUI 范围无限扩张 |
| `ECC-N05-D02` | operator / desktop | 复用现有 ops dashboard 的 PoC 路径 | `ops_dashboard.py`、`ops_http_server.py` | 有低成本演进方案 |
| `ECC-N05-D03` | operator / desktop | 包装/发布/升级风险评估 | `docs/` | 决定是否进入正式项目 |

## 8. 推荐开发顺序

如果目标是“尽量贴近三上游”，建议按下面顺序推进：

1. `HM-N01`
2. `CC-N01`
3. `CC-N02`
4. `HM-N03`
5. `HM-N04`
6. `HM-N05`
7. `HM-N07`
8. `CC-N03`
9. `ECC-N01`
10. `ECC-N03`
11. `HM-N09`
12. `HM-N10`
13. `CC-N04`
14. `ECC-N02`
15. `HM-N08`

解释：

- **P0 先补外部入口**：安装、自修复、profiles、API 扩展能力。
- **P1 再补产品外壳**：dashboard 可写、gateway 扩展、plugin/home sync。
- **P2 补差异化能力**：voice、external memory provider、tool gateway 等。

### 8.1 第一批建议直接开工的原子任务

第一批建议优先开这些原子任务，它们能最快把“别人怎么安装、怎么接入、怎么隔离状态”补齐：

1. `CC-N01-D01`
2. `CC-N01-D02`
3. `CC-N01-D03`
4. `CC-N02-D01`
5. `CC-N02-D03`
6. `HM-N01-D01`
7. `HM-N01-D03`
8. `HM-N03-D01`
9. `HM-N03-D02`
10. `HM-N03-D03`
11. `HM-N04-D01`
12. `HM-N05-D01`
13. `ECC-N03-D01`
14. `ECC-N03-D02`

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

2026-04-25 在仓库根 `D:\gitrepo\Cai_Agent` 实测结果：

| 检查项 | 命令 | 结果 |
|---|---|---|
| 全量单测 | `python -m pytest -q cai-agent/tests` | **742 passed**, **3 subtests passed** |
| 冒烟 | `python scripts/smoke_new_features.py` | **PASS**，输出 `NEW_FEATURE_CHECKS_OK` |
| 回归 | `QA_SKIP_LOG=1 python scripts/run_regression.py` | **PASS**，compileall / unittest / smoke / CLI 子集全绿 |
