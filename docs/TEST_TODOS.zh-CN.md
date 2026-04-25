# 测试 TODO（全量未完成功能版）

> 开发对齐页：[`DEVELOPER_TODOS.zh-CN.md`](DEVELOPER_TODOS.zh-CN.md)。产品判断页：[`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md)。

这份文档按三条能力线维护**尽量全量**的测试 backlog，目标是让开发和测试围绕同一批“未完成功能”推进，而不是只盯少数优先项。

## 1. 当前测试基线

2026-04-25 在仓库根 `D:\gitrepo\Cai_Agent` 复核结果：

| 检查项 | 命令 | 结果 |
|---|---|---|
| 全量单测 | `python -m pytest -q cai-agent/tests` | **742 passed**, **3 subtests passed** |
| 冒烟 | `python scripts/smoke_new_features.py` | **PASS**，输出 `NEW_FEATURE_CHECKS_OK` |
| 回归 | `QA_SKIP_LOG=1 python scripts/run_regression.py` | **PASS**，compileall / unittest / smoke / CLI 子集全绿 |

结论：当前主干测试健康，可以在绿基线上继续扩展未完成功能。

## 2. 使用规则

每个未完成项至少补齐下面三层中的两层：

1. `pytest`
2. `smoke / regression`
3. `手工 / 真机 / 浏览器 / 外部客户端`

必须补自动化的改动面：

- CLI 文案、退出码、状态字段
- JSON payload / schema_version
- API 路由
- gateway 状态与 map
- doctor / repair / install 诊断输出

必须补手工的改动面：

- 浏览器 dashboard
- 真机消息平台
- 语音输入输出
- 外部 OpenAI-compatible client 接入

## 3. 模型接入最高优先级测试 backlog

模型接入优化现在是最高优先级。测试侧要优先保证：新增 provider 不破坏旧调用路径，模型能力元数据不泄漏密钥，健康检查能区分常见失败，routing explain 能解释为什么选某个模型。

| ID | 状态 | 测试重点 | 现有测试入口 | 需新增自动化 | 手工 / 真机 | 通过标准 |
|---|---|---|---|---|---|---|
| `MODEL-P0-01` | `Done` | Model Gateway contract 不破坏旧 adapter | `test_llm_factory_dispatch.py`、`test_model_gateway.py` | 已覆盖 gateway response / adapter contract 与 `model_response_v1` schema 文件 | 无 | 旧 `chat_completion` 行为不变，新 response envelope 稳定 |
| `MODEL-P0-02` | `Done` | capabilities 元数据与脱敏 | `test_model_gateway.py`、`test_model_profiles_cli.py` | 已覆盖 provider/model 能力推断 | 手工检查真实配置输出 | 不暴露 `api_key` / `base_url` |
| `MODEL-P0-03` | `Done` | `/models` ping + chat smoke + doctor 建议 | `test_model_profiles_cli.py`、`test_doctor_cli.py` | 已覆盖 chat smoke 与 doctor model gateway 摘要 | 至少 OpenAI-compatible 和 Anthropic 真 key 各跑一次 | 常见失败有稳定 status |
| `MODEL-P0-04` | `Done` | `model_response_v1` 统一响应 | `test_model_gateway.py`、`test_api_http_server.py` | 已覆盖 direct/API response 与 SSE wrapper | 无 | content/usage/latency/provider/model/profile 字段稳定 |
| `MODEL-P0-05` | `Done` | routing explain + capabilities + fallback candidates | `test_model_routing.py` | 已覆盖 fallback candidate / capability constraint 测试 | 手工跑复杂 routing 规则 | 用户能看懂选型原因 |
| `MODEL-P0-06` | `Done` | 模型接入 UX 闭环 | `test_model_profiles_cli.py`、smoke | 已补 add -> capabilities -> ping -> chat-smoke -> use -> routing-test onboarding flow | 手工接一个本地模型和一个远端模型 | 新模型接入流程可复现 |
| `MODEL-P0-07` | `Done` | API Server 复用 Model Gateway | `test_api_http_server.py` | 已补 `/v1/models`、非流式 `/v1/chat/completions`、`stream=true` SSE 与 profile-aware 请求 | OpenAI-compatible client 接入 | API server 不重复 provider 分支 |

## 4. Claude Code 线测试 backlog

| ID | 状态 | 测试重点 | 现有测试入口 | 需新增自动化 | 手工 / 真机 | 通过标准 |
|---|---|---|---|---|---|---|
| `CC-N01` | `Ready` | init / doctor / repair / upgrade 路径 | `test_init_presets.py`、`test_doctor_cli.py` | `test_repair_cli.py`、`test_install_surface_cli.py`、smoke 补 `init -> doctor -> repair` | 空目录初始化、缺配置修复、旧配置残留提示 | 新用户与坏环境都能恢复到最小可用 |
| `CC-N02` | `Ready` | 反馈与自助 triage 链路 | `test_feedback_cli.py`、`test_feedback_export.py`、`test_doctor_cli.py` | `test_feedback_bundle_cli.py`、`test_doctor_feedback_hints.py` | 手工走一遍 `doctor -> repair -> feedback bug` | 反馈前诊断、反馈导出、提示链路一致 |
| `CC-N03` | `Design` | plugin / marketplace / sync-home | `test_plugin_compat_matrix.py`、`test_ecc_layout_cli.py` | `test_plugins_sync_home.py`、`test_plugins_home_drift.py`、`test_marketplace_manifest_cli.py` | `.claude` / `.codex` 两目标 dry-run diff | sync 不误删文件，doctor 能发现漂移 |
| `CC-N04` | `Design` | recap / resume / task UX | `test_tui_task_board_render.py`、`test_tui_session_strip.py`、`test_tui_model_panel.py` | `test_session_recap_cli.py`、`test_tui_resume_hints.py`、`test_task_board_filters.py` | 长会话恢复体验手工验证 | 长会话 resume 不再要求重读整段历史 |
| `CC-N05` | `Explore` | local GUI / desktop 包装层 | 现有无专门主入口 | 暂不新建正式自动化，先保留设计/PoC 校验 | 本地原型验证 | 先形成方案，再决定是否进入正式测试线 |
| `CC-N06` | `OOS` | WebSearch / Notebook 原生实现 | `test_mcp_presets_tui_quickstart.py`、`test_mcp_serve_roundtrip.py` | 无；继续维护 preset / MCP 路径 | MCP 接入手工走查 | 保持替代路径可用即可 |
| `CC-N07` | `Conditional` | remote / cloud / mobile / web surfaces | 无 | 无 | 仅在立项后定义 | 默认不进入测试线 |

## 5. Hermes 线测试 backlog

| ID | 状态 | 测试重点 | 现有测试入口 | 需新增自动化 | 手工 / 真机 | 通过标准 |
|---|---|---|---|---|---|---|
| `HM-N01` | `Ready` | profile home 隔离、alias command、状态跟随 | `test_model_profiles_config.py`、`test_model_profiles_cli.py`、`test_doctor_cli.py` | `test_profile_home_isolation.py`、`test_profile_alias_cli.py`、smoke 补 create/clone/use | 创建新 profile 后验证 session/memory/gateway map 隔离 | 不同 profile 间状态不串 |
| `HM-N02` | `Done` | OpenAI-compatible API、streaming、profile-aware request | `test_api_http_server.py` | 已覆盖 `/v1/models`、非流式 chat、SSE chunk / `[DONE]`、Bearer 鉴权、profile-aware `model` 选择 | `curl` 和至少一个 OpenAI-compatible client 接入 | 外部客户端能直接连本地 CAI Agent |
| `HM-N03` | `Design` | API 扩路由 / OpenAPI / auth 收口 | `test_api_http_server.py` | `test_api_status_routes.py`、`test_api_auth_config.py`、OpenAPI snapshot test | API 文档页或本地 schema 输出手工检查 | 路由、文档、auth 配置不打架 |
| `HM-N04` | `Design` | dashboard preview/apply/audit、安全边界 | `test_ops_http_server.py`、`test_ops_dashboard_html.py` | `test_ops_apply_actions.py`、`test_ops_audit_log.py`、smoke 补 preview/apply | 浏览器执行真实 apply，并确认审计记录 | 至少一个写动作可自动化回归 |
| `HM-N05` | `Design` | Signal / Email / Matrix 平台适配 | `test_gateway_maps_summarize.py`、`test_gateway_lifecycle_cli.py` | `test_gateway_signal_cli.py`、`test_gateway_email_cli.py`、`test_gateway_matrix_cli.py` | 至少一个新平台真机消息链路 | 至少 2 个新平台具备最小 CLI + map + health |
| `HM-N06` | `Explore` | 第二批平台优先级与抽象复用 | 现有无 | 暂不新建正式自动化 | 预研记录 | 先形成优先级和适配器复用设计 |
| `HM-N07` | `Design` | gateway federation / channel monitoring / proxy | `test_gateway_maps_summarize.py`、`test_gateway_lifecycle_cli.py` | `test_gateway_federation_summary.py`、`test_gateway_proxy_routes.py` | 多 workspace 状态聚合手工验证 | 多工作区、多平台状态可统一汇总和路由 |
| `HM-N08` | `Design` | voice provider contract、CLI voice mode、gateway voice reply | 现有无稳定主入口 | `test_voice_cli.py`、`test_voice_provider_contract.py`、`test_gateway_voice_settings.py` | CLI 音频输入输出、Telegram/Discord voice reply | 自动化覆盖配置/错误语义，手工覆盖真实音频链路 |
| `HM-N09` | `Ready` | provider registry、provider test、active provider exposure | `test_memory_provider_contract_cli.py`、`test_memory_user_model_store_cli.py`、`test_doctor_cli.py` | `test_memory_provider_registry.py`、`test_memory_provider_http_mock.py`、smoke 补 provider switch | local -> mock external provider 切换 | provider 可列出、切换、测试，不只是 contract 说明 |
| `HM-N10` | `Design` | web/image/browser/tts 统一工具层 | `test_mcp_presets_tui_quickstart.py`、插件相关测试 | `test_tool_gateway_contract.py`、`test_tool_provider_registry.py` | 至少一类工具 provider 实机验证 | 四类工具至少有统一 contract 和一类真实接入 |
| `HM-N11` | `Conditional` | cloud runtime backends | `test_runtime_docker_mock.py`、`test_runtime_ssh_mock.py` 仅供参考 | 立项后再加真实云后端测试 | 云端执行环境验证 | 默认不进入测试线 |

## 6. ECC 线测试 backlog

| ID | 状态 | 测试重点 | 现有测试入口 | 需新增自动化 | 手工 / 真机 | 通过标准 |
|---|---|---|---|---|---|---|
| `ECC-N01` | `Design` | local catalog、sync-home、doctor drift、repair 建议 | `test_plugin_compat_matrix.py`、`test_ecc_layout_cli.py` | `test_catalog_snapshot_cli.py`、`test_home_sync_doctor.py` | home sync dry-run 与 drift 手工核对 | 分发、同步、修复口径统一 |
| `ECC-N02` | `Design` | pack import/export/install/repair | `test_ecc_layout_cli.py`、相关 export 测试 | `test_asset_pack_manifest.py`、`test_asset_pack_import_export.py`、`test_asset_pack_repair.py` | 打包后导入到新 workspace 手工验证 | 资产生命周期可自动化回归 |
| `ECC-N03` | `Ready` | cross-harness doctor / diff | `test_plugin_compat_matrix.py`、`test_ecc_layout_cli.py` | `test_harness_doctor_diff.py`、`test_export_sync_diff.py` | 至少两个 harness home 手工 diff | 用户可看懂“还差什么、会改什么、不会改什么” |
| `ECC-N04` | `Explore` | registry format / ecosystem ingest | 现有无 | 暂不新建正式自动化 | 预研记录 | 先产出 registry / ingest 方案 |
| `ECC-N05` | `Explore` | operator / desktop control plane | 现有无 | 暂不新建正式自动化 | 本地原型验证 | 先判断是否值得立项 |

## 7. 原子级测试拆解

下面按开发页的 `*-Dxx` 原子任务补测试入口。测试任务不一定要求每个子任务都新建一个测试文件，但必须能在 PR 里清楚说明“这个开发子任务由哪些自动化和手工步骤覆盖”。

### 7.1 模型接入原子测试

| 开发子任务 | 自动化覆盖 | 手工 / 真机覆盖 | 通过标准 |
|---|---|---|---|
| `MODEL-P0-D01` | `test_model_gateway.py` 覆盖 contract 和 capabilities | 无 | 新模块不影响旧 adapter |
| `MODEL-P0-D02` | `test_llm_factory_dispatch.py` 补 response wrapper | 无 | role-aware response 字段稳定 |
| `MODEL-P0-D03` | `test_model_profiles_cli.py` 覆盖 `models capabilities --json`；`test_model_gateway.py` 覆盖 `model_capabilities_v1` / `model_capabilities_list_v1` schema | 真实配置手工检查 | 不泄漏密钥或 base_url |
| `MODEL-P0-D04` | `test_api_http_server.py` 覆盖 `/v1/models/capabilities` 和 bearer | 浏览器/curl 走查 | API 只读且鉴权一致 |
| `MODEL-P0-D05` | `test_model_profiles_cli.py` 覆盖 `ping --chat-smoke` | 真 key 显式 smoke | 默认不消耗 token，显式 smoke 可诊断 |
| `MODEL-P0-D06` | `test_model_profiles_cli.py` 补 429/404 status 映射 | 无 | 常见 HTTP 失败不全是 `NET_FAIL` |
| `MODEL-P0-D07` | `test_model_routing.py` 覆盖 capabilities 出现在 routing-test JSON | 手工读 explain | 选型解释包含能力信息 |
| `MODEL-P0-D08` | `test_provider_registry.py` 覆盖 `provider_registry_v1` / readiness 的 `capabilities_hint` 与 schema 文件；onboarding flow 测试 | 新 provider 文档评审 | preset 更新不破坏旧配置 |
| `MODEL-P0-D09` | `test_doctor_cli.py` 覆盖 `doctor_model_gateway_v1` | 坏 key / 缺 env 手工走查 | doctor 建议可执行 |
| `MODEL-P0-D10` | `test_tui_model_panel.py` 覆盖模型面板行内 capabilities / health / cost / local 提示 | TUI 手工查看 | CLI/TUI 状态一致 |
| `MODEL-P0-D11` | `test_model_routing.py` 覆盖 `model_fallback_candidates_v1` | 手工模拟失败模型 | 默认 explain，不静默切换 |
| `MODEL-P0-D12` | API server OpenAI-compatible contract 测试（已覆盖 `/v1/models`、非流式与 SSE `/v1/chat/completions`） | OpenAI-compatible client 实测 | API 复用 gateway |
| `MODEL-P0-D13` | metrics snapshot 测试（已覆盖 `api.chat_completions`） | 跑一次真实调用检查指标 | provider/model/profile/latency/usage 可追踪 |
| `MODEL-P0-D14` | `scripts/smoke_new_features.py` 覆盖 onboarding flow；`test_model_profiles_cli.py` 覆盖 `model_onboarding_flow_v1` schema；`test_model_onboarding_docs.py` 覆盖 runbook 可发现性与命令链；文档见 `MODEL_ONBOARDING_RUNBOOK.zh-CN.md` | 按 runbook 接 OpenAI/Anthropic/本地模型 | 新用户能复现 |

### 7.2 Claude Code 线原子测试

| 开发子任务 | 自动化覆盖 | 手工 / 真机覆盖 | 通过标准 |
|---|---|---|---|
| `CC-N01-D01` | `test_repair_cli.py` 覆盖 `--dry-run`、`--apply`、`--json`、退出码 | 构造坏 home 后执行 repair | dry-run 不写文件，apply 后配置恢复 |
| `CC-N01-D02` | `test_doctor_cli.py` 增加 `doctor.install` JSON snapshot | 新机器或干净 venv 走查 | install 诊断字段稳定、建议可执行 |
| `CC-N01-D03` | `test_install_surface_cli.py` 覆盖 `doctor.sync` drift 场景 | 手工制造模板缺失/旧 schema | 能区分 error/warning/action |
| `CC-N01-D04` | docs link check 或 smoke 中校验 onboarding 命令存在 | 按 README 从零跑一遍 | 新旧用户路径没有冲突文案 |
| `CC-N02-D01` | `test_feedback_bundle_cli.py` 覆盖 bundle schema、脱敏字段、doctor 摘要 | 打开导出的 bundle 检查内容 | bundle 可复现问题且不泄漏敏感字段 |
| `CC-N02-D02` | `test_feedback_cli.py` 覆盖 bug 模板字段和 JSON 输出 | 手工填写一次反馈流程 | human/json 两种输出结构一致 |
| `CC-N02-D03` | `test_doctor_feedback_hints.py` 覆盖 triage hint | 手工走 `doctor -> repair -> feedback bug` | 常见错误先给修复建议再导出反馈 |
| `CC-N02-D04` | `test_feedback_export.py` 补 path/token/email 脱敏断言 | 检查真实导出目录 | 敏感信息不会出现在明文 bundle |
| `CC-N03-D01` | `test_marketplace_manifest_cli.py` 覆盖 catalog schema 校验 | 检查生成 catalog 可读性 | catalog 可版本化、可解析 |
| `CC-N03-D02` | `test_plugins_sync_home.py` 覆盖 dry-run add/update/skip/conflict | 对 `.claude` / `.codex` 目标执行 dry-run | dry-run 不写文件，diff 清楚 |
| `CC-N03-D03` | `test_plugins_home_drift.py` 覆盖缺失/过期/冲突资产 | 手工制造 home drift | doctor 能指出漂移和目标 |
| `CC-N03-D04` | `test_plugins_sync_home.py` 补覆盖保护和备份断言 | 手工验证冲突确认提示 | 默认不覆盖用户修改 |
| `CC-N04-D01` | `test_session_recap_cli.py` 覆盖 recap 生成和持久化 | 构造长会话后恢复 | recap 足够短且能定位上下文 |
| `CC-N04-D02` | `test_tui_resume_hints.py` 覆盖 resume hints 字段 | 手工恢复最近会话 | 下一步提示准确、不误导 |
| `CC-N04-D03` | `test_task_board_filters.py` 覆盖状态过滤和排序 | TUI 中操作任务板 | 任务多时仍可扫描 |
| `CC-N04-D04` | `test_tui_session_strip.py` 补 restore 状态 | 手工退出再进入会话 | 恢复路径可见且不丢任务 |
| `CC-N05-D01` | 暂无正式自动化，产出设计评审 checklist | 评审 GUI 技术路线 | 有明确 go/no-go |
| `CC-N05-D02` | 如有 PoC，补 `test_ops_http_server.py` 启动入口断言 | 本地打开 dashboard | 非技术用户能启动 |
| `CC-N05-D03` | 文档审查 | 产品/开发/测试共同评审风险 | 风险项有 owner 和结论 |
| `CC-N06-D01` | `test_mcp_presets_tui_quickstart.py` 覆盖 preset health | 手工接一个 MCP preset | 替代路径仍可用 |
| `CC-N06-D02` | 文档链接检查 | 检查 OOS 说明是否清晰 | 用户能理解边界 |
| `CC-N07-D01` | 暂无自动化 | 只有授权后进入测试设计 | 未授权不进入默认测试线 |

### 7.3 Hermes 线原子测试

| 开发子任务 | 自动化覆盖 | 手工 / 真机覆盖 | 通过标准 |
|---|---|---|---|
| `HM-N01-D01` | `test_profile_home_isolation.py` 覆盖 config/session/memory/gateway 目录隔离 | 建两个 profile 手工检查 home | 状态不串 |
| `HM-N01-D02` | `test_profile_alias_cli.py` 或 profile clone 测试覆盖 dry-run/conflict | clone 一个真实 profile | clone 后可启动 |
| `HM-N01-D03` | smoke 补 create/use/API/gateway profile resolution | 手工切 profile 后跑 TUI/API/gateway | 所有入口读同一 active profile |
| `HM-N01-D04` | `test_profile_alias_cli.py` 覆盖 alias command 输出 | 复制 alias 命令执行 | alias 可直接进入 profile |
| `HM-N01-D05` | `test_doctor_cli.py` 覆盖 profile migration hint | 用旧配置跑 doctor | 老配置有安全迁移路径 |
| `HM-N02-D01` | `test_api_openai_chat_completions.py` 覆盖 `/v1/models` | `curl /v1/models` | 返回 OpenAI 风格模型列表 |
| `HM-N02-D02` | `test_api_openai_chat_completions.py` 覆盖非流式 chat | OpenAI-compatible client 发请求 | 响应字段兼容 |
| `HM-N02-D03` | `test_api_http_server.py` 覆盖 SSE chunk / done | 客户端读取 streaming | 流式能结束且不丢 chunk |
| `HM-N02-D04` | `test_api_auth_config.py` 覆盖 token、无 token、错误码 | 手工验证 localhost 默认安全策略 | 未授权请求被拒绝 |
| `HM-N02-D05` | `test_api_openai_chat_completions.py` 补 profile-aware 参数 | 两个 profile 分别请求 | profile 上下文不串 |
| `HM-N03-D01` | `test_api_status_routes.py` 覆盖 health/status/profiles | `curl` 读状态 | 状态字段稳定 |
| `HM-N03-D02` | OpenAPI snapshot test | 手工检查 schema 可读性 | schema 与实际路由一致 |
| `HM-N03-D03` | `test_api_auth_config.py` 覆盖 API/ops auth 组合 | 同时启动 api/ops | 安全策略一致 |
| `HM-N03-D04` | docs 示例命令 smoke | 按文档跑 `curl` 示例 | 文档命令可运行 |
| `HM-N04-D01` | `test_ops_apply_actions.py` 覆盖 preview/apply/audit contract | 浏览器确认 preview 页面 | 写动作先 preview |
| `HM-N04-D02` | `test_ops_apply_actions.py` 覆盖 2 到 3 个写动作 | 手工 apply 并查看状态变化 | 写动作真实生效 |
| `HM-N04-D03` | `test_ops_audit_log.py` 覆盖 audit record | 检查本地 audit 文件 | 可追踪操作者和结果 |
| `HM-N04-D04` | `test_ops_dashboard_html.py` 覆盖 pending/success/failed/diff 文案 | 浏览器操作 | UI 能看懂后果 |
| `HM-N05-D01` | gateway adapter contract 单测 | 新平台配置走查 | adapter 复用有效 |
| `HM-N05-D02` | `test_gateway_signal_cli.py` 覆盖 config/health/map | Signal 真机链路可选 | skeleton 可诊断 |
| `HM-N05-D03` | `test_gateway_email_cli.py` 覆盖 SMTP/IMAP 或 mock | 邮箱沙箱收发 | Email 最小链路可用 |
| `HM-N05-D04` | `test_gateway_matrix_cli.py` 覆盖 room map/send/health | Matrix room 真机验证 | 进入 prod-status |
| `HM-N05-D05` | `test_gateway_maps_summarize.py` 补新平台 prod-status | 至少一个新平台真机消息 | 至少 2 个新平台 CLI + map + health 可用 |
| `HM-N06-D01` | 文档/矩阵检查 | 评审平台优先级 | 下一批平台排序明确 |
| `HM-N06-D02` | adapter contract test 可复用性检查 | 评审 auth/webhook/polling/media 差异 | 共用抽象明确 |
| `HM-N06-D03` | 暂无自动化 | PoC 评审 | 未立项平台不进入实现 |
| `HM-N07-D01` | `test_gateway_federation_summary.py` 覆盖 federation schema | 多 workspace fixture 走查 | 聚合输出稳定 |
| `HM-N07-D02` | `test_gateway_federation_summary.py` 覆盖 channel health 字段 | 手工制造错误/延迟 | 频道级健康可见 |
| `HM-N07-D03` | `test_gateway_proxy_routes.py` 覆盖 routing 决策 | 本地多 workspace 路由 | 消息能到目标 workspace/profile |
| `HM-N07-D04` | CLI/API JSON snapshot | 运营脚本读取 JSON | 输出可被脚本消费 |
| `HM-N08-D01` | `test_voice_provider_contract.py` 覆盖 STT/TTS/health | 无 provider/错 provider 手工检查 | 错误语义清楚 |
| `HM-N08-D02` | `test_voice_cli.py` 覆盖 voice config/check | 本地音频配置检查 | 无 provider 时不崩 |
| `HM-N08-D03` | `test_gateway_voice_settings.py` 覆盖 gateway voice 开关 | Telegram 或 Discord 真机 voice reply | 至少一个语音闭环可用 |
| `HM-N08-D04` | 文档检查 | 评审成本、OOS、可用能力说明 | 用户不误解能力范围 |
| `HM-N09-D01` | `test_memory_provider_registry.py` 覆盖 list/use/test | CLI 切 provider | provider 体系可操作 |
| `HM-N09-D02` | `test_memory_provider_registry.py` 覆盖 builtin local provider | 现有 memory 流程不回退 | 旧行为保持 |
| `HM-N09-D03` | `test_memory_provider_http_mock.py` 覆盖 mock HTTP provider | 本地 mock 服务 | 外部 provider contract 可验证 |
| `HM-N09-D04` | `test_doctor_cli.py` / export 测试覆盖 active provider | 切 provider 后导出 | doctor/export 能识别 provider |
| `HM-N10-D01` | `test_tool_gateway_contract.py` 覆盖 provider contract | 配置高风险工具 | 权限字段稳定 |
| `HM-N10-D02` | `test_tool_provider_registry.py` 覆盖四类 registry | CLI list/enable/disable | web/image/browser/tts 可列出 |
| `HM-N10-D03` | MCP bridge 测试复用 existing preset tests | 手工跑 MCP 工具 | 不重复实现已有 MCP |
| `HM-N10-D04` | 至少一个真实 provider 的端到端测试 | 实机调用一个 provider | 端到端可用 |
| `HM-N10-D05` | approval/policy/cost guard 单测 | 手工触发高风险工具 | 高风险动作需显式允许 |
| `HM-N11-D01` | 文档检查 | 授权/成本/部署评审 | 未授权不写云后端 |
| `HM-N11-D02` | `test_runtime_docker_mock.py` / `test_runtime_ssh_mock.py` 保持接口兼容 | 本地 runtime smoke | 本地路径不被云接口破坏 |

### 7.4 Everything Claude Code 线原子测试

| 开发子任务 | 自动化覆盖 | 手工 / 真机覆盖 | 通过标准 |
|---|---|---|---|
| `ECC-N01-D01` | `test_catalog_snapshot_cli.py` 覆盖 schema 校验 | 打开 catalog 检查可读性 | catalog 稳定 |
| `ECC-N01-D02` | `test_home_sync_doctor.py` 覆盖 Claude/Codex/Cursor/OpenCode dry-run | 对至少两个 harness home 执行 dry-run | add/update/skip/conflict 清楚 |
| `ECC-N01-D03` | `test_home_sync_doctor.py` 覆盖 drift 检测 | 手工制造缺失/冲突资产 | doctor 能指出问题 |
| `ECC-N01-D04` | repair 建议 snapshot | 按建议命令手工执行 | 诊断能转成行动 |
| `ECC-N02-D01` | `test_asset_pack_manifest.py` 覆盖 manifest v1 | 检查 pack metadata | manifest 可校验 |
| `ECC-N02-D02` | `test_asset_pack_import_export.py` 覆盖 export/checksum/dry-run | 打包后解压检查 | 打包可复现 |
| `ECC-N02-D03` | `test_asset_pack_import_export.py` 覆盖 import/install | 新 workspace 手工安装 | 安装前能预览影响 |
| `ECC-N02-D04` | `test_asset_pack_repair.py` 覆盖缺失/schema drift | 手工破坏 pack 后 repair | 能定位损坏原因 |
| `ECC-N03-D01` | `test_harness_doctor_diff.py` 覆盖 target inventory | 检查输出路径 | 支持目标清晰 |
| `ECC-N03-D02` | `test_export_sync_diff.py` 覆盖 home diff | 两个 harness home 手工 diff | add/update/skip/conflict 可读 |
| `ECC-N03-D03` | `test_harness_doctor_diff.py` 覆盖 compat drift | 构造不兼容资产 | 缺口定位到资产 |
| `ECC-N03-D04` | human/json snapshot | 自动化消费 JSON | 两种格式一致 |
| `ECC-N04-D01` | registry schema snapshot | 方案评审 | registry 能作为后续入口 |
| `ECC-N04-D02` | sanitizer policy 单测或文档审查 | 审查危险 hook 场景 | 不可信资产不直接执行 |
| `ECC-N04-D03` | provenance 字段校验 | 评审 trust level | 来源可信度可表达 |
| `ECC-N05-D01` | 文档范围检查 | 产品/开发/测试评审 | GUI 范围可控 |
| `ECC-N05-D02` | 如有 PoC，补 ops dashboard smoke | 打开本地 operator 原型 | 复用路径成立 |
| `ECC-N05-D03` | 发布风险 checklist | 评审升级/权限/日志 | 有 go/no-go 结论 |

## 8. 推荐测试顺序

建议跟开发同步按下面顺序推进：

1. `MODEL-P0-01`
2. `MODEL-P0-02`
3. `MODEL-P0-03`
4. `MODEL-P0-04`
5. `MODEL-P0-05`
6. `MODEL-P0-06`
7. `MODEL-P0-07`
8. `HM-N01`
9. `HM-N02`
10. `CC-N01`
11. `CC-N02`
12. `HM-N04`
13. `HM-N05`
14. `HM-N07`
15. `CC-N03`
16. `ECC-N01`
17. `ECC-N03`
18. `HM-N09`
19. `HM-N10`
20. `CC-N04`
21. `ECC-N02`
22. `HM-N08`

## 9. 合入前统一命令

每个任务合入前，建议至少执行：

```powershell
python -m pytest -q cai-agent/tests
python scripts/smoke_new_features.py
$env:QA_SKIP_LOG='1'; python scripts/run_regression.py
```

如果只是局部模块，也允许先跑子集；但涉及共享 CLI / API / gateway / dashboard / memory provider / sync-home 的改动，不建议跳过 smoke 和 regression。
