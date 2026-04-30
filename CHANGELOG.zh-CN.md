## 更新日志

> 默认英文变更记录见 **[CHANGELOG.md](CHANGELOG.md)**。以下为完整中文变更说明（本文件）。

> 根目录 **`README.md`** 为默认英文说明，**`README.zh-CN.md`** 为完整中文说明；**`CHANGELOG.md`** 为默认英文变更记录，**`CHANGELOG.zh-CN.md`** 为完整中文变更记录。

### Unreleased

- **SAFETY-N07-D01 解限关键写 noop 启发式**：解限且要求确认时，若 `write_file` 目标在工作区内已存在 UTF-8 文件（≤512KiB），规范化正文（换行统一、去行尾空白、外围 strip）与写入内容一致，则跳过「关键配置文件 basename」级二次确认；`[safety].dangerous_critical_write_skip_if_unchanged`（默认 true）与 `CAI_DANGEROUS_CRITICAL_WRITE_SKIP_IF_UNCHANGED`；`doctor`/`tools guard` policy 字段；扩展 `test_unrestricted_danger_dispatch_extended.py`、`test_unrestricted_mode_config.py`；smoke 校验 doctor JSON 含布尔字段。

- **SAFETY-N06-D01 解限 P4-4 网关危险确认契约**：新增 `gateway_danger.py`（goal 行前缀 `[danger-approve]` / `/danger-approve`，`CAI_GATEWAY_DANGER_APPROVE_TOKENS`）；Slack `execute_on_event` 与 Discord `execute_on_message` 路径剥离前缀并 `grant_dangerous_approval_once`；`tools guard --json` 增加 `danger_gateway_contract_v1`；回归 `test_gateway_danger_contract.py`。

- **SAFETY-N05-D01 解限 P4 规则细化（fetch/write/run）**：解限且要求确认时，`allow_private_resolved_ips=true` 对 http/https `fetch_url` 追加二次确认；显式拒绝 `file://`；`write_file` 内置关键 basename 清单 + `dangerous_write_file_critical_basenames`；`run_command_extra_danger_basenames`；`doctor`/`tools guard` 报表字段计数；回归扩展 `test_unrestricted_danger_dispatch_extended.py` 等。

- **SAFETY-N04-D01 解限会话放行与危险审计 JSONL**：进程内 `register_session_mcp_tool_danger_approval` / `register_session_fetch_http_host_danger_approval`；`dispatch` 与 `prepare_interactive_dangerous_dispatch` 识别会话放行且不消耗一次性 budget；TUI 斜杠命令与确认框「本会话放行」；`[safety].dangerous_audit_log_enabled` + `CAI_DANGEROUS_AUDIT_LOG` 写入 `.cai/dangerous-approve.jsonl`；`grant_dangerous_approval_once(..., settings=, audit_via=)`；`doctor`/`tools guard` 暴露 `dangerous_audit_log_enabled`。回归：`test_danger_session_and_audit.py` 等。

- **SAFETY-N03-D01 解限危险操作 TUI 自动确认与 Graph 串联**：`build_app(..., dangerous_confirm=...)`；`tools_node` 在交互确认路径上先广播 `danger_confirm_prompt` 再调用 `prepare_interactive_dangerous_dispatch`；TUI 使用 `ModalScreen` + `call_from_thread` 弹出允许/取消；新增 `reset_dangerous_approval_budget_for_testing()`；清单 P3-1/P3-2 标 Done（[`docs/SAFETY_UNRESTRICTED_BACKLOG.zh-CN.md`](docs/SAFETY_UNRESTRICTED_BACKLOG.zh-CN.md)）；回归含 `test_tools_prepare_interactive_dangerous_dispatch.py`、schedule `fake_build_app` 兼容 `**kwargs`。

- **SAFETY-N02-D01 解限模式扩大危险确认**：解限且 `dangerous_confirmation_required=true` 时，`mcp_call_tool` 每次调用与明文 `http` 的 `fetch_url` 需二次确认（TUI `/danger-approve` 或 `CAI_DANGEROUS_APPROVE=1`）；`README.zh-CN.md` 增补说明；全景清单 [`docs/SAFETY_UNRESTRICTED_BACKLOG.zh-CN.md`](docs/SAFETY_UNRESTRICTED_BACKLOG.zh-CN.md)。

- **SAFETY-N01-D01 解限模式配置开关**：新增 `[safety].unrestricted_mode`（默认 `false`）与 `[safety].dangerous_confirmation_required`（默认 `true`），环境变量 `CAI_UNRESTRICTED_MODE` / `CAI_DANGEROUS_CONFIRMATION_REQUIRED` 可覆盖；`doctor --json` 与 `tool_gateway_guard_v1.policy` 同步暴露字段；example/starter 模板均新增 `[safety]` 段。

- **SAFETY-N01-D02 TUI 开关与危险二次确认闭环**：TUI 新增 `/unrestricted [on|off]`（可写回 TOML）与 `/danger-approve`（放行下一次危险操作）；`/status` 展示解限与确认状态。解限模式下 `dispatch` 对高危 `run_command` 与敏感目标 `write_file` 执行二次确认，非交互场景可用 `CAI_DANGEROUS_APPROVE=1` 显式放行。

- **GW-SLASH-N01 Gateway slash catalog**：新增 `gateway slash-catalog --json` 与 `GET /v1/gateway/slash-catalog`（`gateway_slash_catalog_v1`），离线公开 Discord application commands、Slack `/cai` 子命令与 Teams command list，并统计可执行型命令数量，便于 operator 审核。

- **GW-CHAN-N01 Gateway channel-monitor 独立入口**：新增 `gateway channel-monitor --json` 与 `GET /v1/gateway/channel-monitor`（`gateway_channel_monitor_v1`），从 `gateway_production_summary_v1` 派生紧凑频道监控视图。该入口支持平台过滤与 `only_errors` 过滤，便于运维脚本不解析完整 prod-status 即可读取频道状态。

- **OPS-MW-N01 ops serve 多 workspace 发现**：新增 `GET /v1/ops/workspaces`（`ops_workspaces_v1`），只枚举服务端 `--allow-workspace` 根目录；每个 workspace 返回 dashboard/html/interactions 路由 URL，并支持 `include_summary=1` 聚合 dashboard summary。OpenAPI 与 ops 文档已暴露该路由。

- **OPS-RBAC-N01 ops serve RBAC 与 workspace 作用域审计**：`cai-agent ops serve` 新增 `--role viewer|operator|admin` 作为服务端最大角色。Dashboard interaction 请求可带 `X-CAI-Actor` 与 `X-CAI-Role`；`viewer` 只能读/preview/audit，`operator` 可 apply 调度重排与 gateway binding 编辑，`admin` 额外可 apply profile 切换。RBAC 拒绝返回 `rbac_forbidden`，并追加含 `actor`、`role`、`workspace_scope` 的 `ops_dashboard_action_audit_v1` 审计行；OpenAPI 发现已登记新 header。

- **产品队列清账与下一批能力落地**：完成 `SYNC-N01`、`MEM-N01`、`RT-N01`、`WF-N01`、`BRW-N04`。Memory provider 契约补齐 `list/use/test` 与 `honcho_external` mock HTTP adapter 的 schema/测试说明；runtime 文档补齐 mock / doctor / opt-in real smoke 分层矩阵；workflow 新增步骤级 `when`、`retry.max_attempts` 与 `workflow_aggregate_v1`；browser task 现在可将 `browser_task_v1.steps[]` 映射为显式确认的 Playwright MCP `mcp_call_tool` 调用（`browser_mcp_execution_v1`），覆盖 dry-run、拒绝执行与审计执行状态。测试：`test_browser_provider_cli.py`、`test_browser_mcp_cli.py`、`test_cli_workflow.py`、`test_memory_provider_contract_cli.py` 与 runtime mock 测试。

- **BRW-N05 Browser 审计与产物 manifest**：非 dry-run 的 browser 执行尝试现在会追加 `.cai/browser/audit.jsonl`（`browser_audit_event_v1`），并在拒绝/确认路径刷新 `.cai/browser/artifacts-manifest.json`（`browser_artifact_manifest_v1`）。manifest 枚举 screenshots、downloads、traces 下的路径、相对路径、大小与 mtime 元数据；执行载荷返回 `browser_audit_summary_v1` 与 manifest 摘要。测试覆盖拒绝执行、确认执行与 artifact 发现。

- **托管模型官方上下文窗口表刷新**：`infer_default_context_window()` 现在先按有序模型前缀表命中，再进入 provider 兜底，覆盖 OpenAI GPT-5.5/5.4/5.2 家族、Claude、Gemini、DeepSeek、GLM、Qwen、Kimi、MiniMax、Grok、Groq 托管开源模型、Mistral、Cohere Command、Perplexity Sonar 等当前官方默认值。OpenRouter 与聚合路由会剥离厂商前缀后复用同一张表；显式 `context_window` 仍优先，本地/自托管端点仍保持手动配置。

- **上下文窗口自动推断扩展到更广的大模型接入家族**：新增 OpenRouter 厂商前缀路由与模型家族规则，覆盖主流可接入生态（含 Qwen、MiniMax、Kimi、智谱 GLM、Mistral、火山/Doubao、Meta Llama、Perplexity 等）的默认上下文窗口自动推断；未知模型与 localhost/自建端点仍保持手动配置。

- **内置第三方预设改为官方上下文窗口默认值**：为仓库内置托管第三方 preset（`nous_portal`、`nvidia_nim`、`xiaomi_mimo`、`kimi_moonshot`、`minimax`、`huggingface`）补齐显式 `context_window`，接入与 onboarding 流程会自动带入 provider 官方模型上限；并同步收敛这些模型 ID 的推断规则。本地/自建端点仍保持手动配置，不做自动钉死。

- **legacy 第三方 `[llm]` 配置默认上下文窗口自动推断**：`synthesize_default_profile` 现在会对托管第三方模型调用 `infer_default_context_window()`，因此单模型 legacy 接入无需手填 `[llm].context_window` 也会自动使用 provider/model 默认值（例如 `gpt-4o` → `128000`）。本地/自建 OpenAI 兼容端点保持不变（未显式配置时仍为未知）。测试已同步到 `test_context_usage_bar.py` 与 `test_model_profiles_config.py`。

- **MiMo provider 预设/文档更新**：`xiaomi_mimo` 默认模型更新为 `MiMo-V2.5-Pro`；README 补充官方 OpenCode 风格 key 映射（`MIMO_API_KEY`）与专属 `base_url` 覆盖流程（`models edit --api-key-env ... --base-url ... --model ...`）。

- **UX-N01-D06 体验层第六阶段（plan/workflow/release-ga 失败提示收口）**：`plan` 的 `config_not_found`/`goal_empty`/`llm_error` 失败返回新增 `hints`（JSON + 文本）；`workflow` 的模板缺失、缺文件、缺配置与执行失败路径补充标准化 `hint:`；`release-ga` 失败态新增 `hints[]`（JSON）并在文本输出 failed checks 后追加 hint 行，统一排障下一步。测试：`test_plan_sessions_cli.py`、`test_cli_workflow.py`、`test_release_ga_cli.py`、`test_cli_misc.py`，并通过全量 `pytest` 与 smoke。

- **UX-N01-D05 体验层第五阶段（run 家族失败提示补齐）**：将统一失败 hints 扩展到 `run/continue/command/agent/fix-build` 家族中的 `config_not_found`、`goal_empty`、`command_not_found`、`agent_not_found` 场景；JSON 失败载荷统一含 `hints[]`，文本 stderr 同步 `hint:` 行，且命令/子代理缺失时直接提示 `commands --json` / `agents --json`。测试：`test_cli_misc.py` 增加 `command_not_found` 与 `agent_not_found` 回归断言，并通过全量 `pytest` 与 smoke。

- **UX-N01-D04 体验层第四阶段（run/continue 失败提示统一）**：`run/continue` 在 `--plan-file` 读取失败、`load_session_failed`、`invalid_session` 场景统一输出下一步 hints；JSON 失败载荷增加 `hints[]`，文本 stderr 同步打印 `hint:` 行，减少失败后排障路径不一致。新增 `_run_continue_failure_hints` 统一维护该语义。测试：`test_cli_misc.py` 增加 continue 失败 JSON/text 提示断言，并通过全量 `pytest` 与 smoke。

- **UX-N01-D03 体验层第三阶段（sessions/continue 可发现性）**：`sessions --help` 与 `continue --help` 新增 quickstart/定位会话提示；`sessions` 文本输出在无会话时补生成路径提示，在有会话时直接给出 `continue` 下一步示例命令，降低“有会话但不知道怎么续聊”的操作成本。测试：`test_cli_misc.py` 新增 `sessions --help`/`continue --help` 断言，并通过全量 `pytest` 与 smoke。

- **UX-N01-D02 体验层第二阶段（失败提示与 help 可发现性）**：顶层 `cai-agent --help` 新增 onboarding quickstart 段；为 `models`/`ecc`/`doctor`/`repair`/`tools` 的缺配置失败统一输出 onboarding 导向提示，减少“报错后无下一步”的断层。新增 `_print_config_not_found_hint` 统一文案收口。测试：`test_cli_misc.py` 增加 root help 与 doctor 缺配置提示断言，并通过全量 `pytest` 与 smoke。

- **UX-N01-D01 体验层第一阶段（Onboarding 优先）**：新增 `cai-agent onboarding` 聚合入口（`onboarding_quickstart_v1`），以 dry-run 指令链统一输出 `init -> doctor -> models onboarding -> run/ui/sessions-recap`；`init`/`doctor`/README/ONBOARDING 文案统一为“先看 onboarding，再执行下一步”；TUI 会话提示补齐 `/recap` 在任务看板场景的高频可见入口。测试：`test_cli_misc.py`（Onboarding CLI）、`test_doctor_cli.py`、`test_tui_session_strip.py`，并通过全量 `pytest` 与 smoke。

- **ECC-N02-D08 ingest 门禁 smoke + CLI 回归补强**：新增 `skills hub install` 的端到端 smoke 覆盖（安全 dry-run JSON + 危险 hooks 拒绝路径，校验 `ingest_gate_rejected` / exit 2），并在 `test_skills_lint_cli.py` 增加 CLI 回归测试。该项把 ingest 门禁从 helper 级验证补强到命令面回归。

- **ECC-N02-D07 skills hub install × ingest 门禁**：**`apply_skills_hub_manifest_selection`** 在 manifest 含待复制 **`hooks.json`** 时调用 **`build_ecc_pack_ingest_gate_for_explicit_hooks_v1`**（**`ingest_scan_kind=explicit_hooks`**）；**`skills_hub_pack_install_v1`** 附带 **`ingest_gate`**；非 **`dry_run`** 且未通过时 **`ok=false`**、**`error=ingest_gate_rejected`** 且不落盘；CLI **`skills hub install`** 对应 **exit 2** 与 stderr 提示。**`ecc_pack_ingest_gate_v1`** 增加 **`ingest_scan_kind`** / **`explicit_scanned_paths`**（显式扫描时）。测试：**`test_skills_hub_install_ingest.py`**、**`test_ecc_pack_ingest_gate`**、**`test_api_http_server`**（summary 含 **`ingest_scan_kind`**）。

- **ECC-N02-D06 README + doctor/API 暴露 pack ingest 预检**：根 **`README.md` / `README.zh-CN.md`** 增补 **`ecc pack-import`** 的 **`ingest_gate`**、**`ingest_gate_rejected`** 与 **`doctor` / `GET /v1/doctor/summary`** 字段说明；**`doctor_v1.ecc_pack_ingest_gate`**（完整 **`ecc_pack_ingest_gate_v1`**）；**`api_doctor_summary_v1.ecc_pack_ingest_gate`**（**`api_ecc_pack_ingest_gate_summary_v1`** 精简计数）；人类 **`doctor`** 增加「ECC / pack-import 源侧 ingest」摘要；**`doctor_upgrade_hints_v1`** 增补 **`ecc pack-import --from-workspace <DIR> --json`**。RFC **`HM_02_MINIMAL_SERVER_CONTRACT.zh-CN.md`** 表格已注明。测试：**`test_doctor_cli`**、**`test_api_http_server`**。

- **ECC-N02-D05 pack ingest 门禁（与 hook_runtime 对齐）**：新增 **`ecc_pack_ingest_gate_v1`**（`ecc_ingest_gate.build_ecc_pack_ingest_gate_v1`），递归扫描源 workspace 的 **`rules`/`skills`/`agents`/`commands`** 下 **`hooks.json`**，对每条可解析 **`command`/`script`** argv 复用 **`hook_runtime`** 危险片段规则（**`list_hook_argv_danger_matches`** / **`hook_argv_matches_ingest_denylist`**），并阻断 **`script_outside_workspace`**；**`ecc pack-import`** 的 **`ecc_asset_pack_import_plan_v1`** 附带 **`ingest_gate`**；**`--apply`** 若 **`ingest_gate.allow`** 为 false 则拒绝写入并返回 **`error=ingest_gate_rejected`**。**`ecc pack-repair`** 仍为只读无 `--apply`**。测试：**`test_ecc_pack_ingest_gate.py`**；smoke 增补 **`ecc pack-import --json`** 校验 **`ingest_gate`**。

- **CC-N04 session/recap 收口**：新增 **`session_recap_v1`**（`context.build_session_recap_v1`）、CLI **`sessions --recap [--json]`** 与 TUI **`/recap`**，统一输出最近会话回放摘要（latest、错误/消耗聚合、replay 命令提示）；并在会话 strip 文案统一暴露 `/recap`。测试：**`test_session_recap.py`**、**`test_tui_session_strip.py`**。

- **HM-N04-D01 dashboard 交互契约收口**：`ops serve` 侧 `GET /v1/ops/dashboard/interactions` 仅支持 `preview|audit`，若传 `mode=apply` 返回 `execute_forbidden`；写动作统一走 `POST /v1/ops/dashboard/interactions`（支持 `mode=apply|preview|audit`），使变更路径显式并与 `ops_dashboard_action_audit_v1` 审计链路一致。测试更新：**`test_ops_http_server.py`**。

- **HM-N03-D01 API 状态路由扩展**：新增 **`GET /v1/health`**（**`api_health_v1`**：版本、工作区、**`auth_enforced`**）与 **`GET /v1/ready`**（**`api_ready_v1`**：基于已加载 **`Settings`** 的就绪摘要，不含密钥）；**`/healthz`** / **`/health`** 现返回 **`api_liveness_v1`**（仍无 Bearer）。更新 **`docs/rfc/HM_02_MINIMAL_SERVER_CONTRACT.zh-CN.md`** 与 **`api serve`** 启动提示。测试：**`test_api_http_server.py`**、**`test_api_status_routes.py`**。

- **ECC-N03-D04 structured home diff**：新增 **`ecc_structured_home_diff_v1`** / **`ecc_structured_home_diff_bundle_v1`**（相对路径级 **add** / **update** / **skip** / **conflict**，内容以 SHA256 对比，与 **`export_ecc_dir_diff_v1`** 路径集合互补）；CLI **`cai-agent ecc home-diff [--target …] --json`**；多 **`--target`** 时输出 **`ecc_structured_home_diff_multi_v1`**；**`doctor --json`** 增加 **`ecc_structured_home_diff`**；**`repair --dry-run --json`** 增加 **`ecc_structured_home_diff_pending_targets`**、**`ecc_home_diff_preview_commands`**；**`doctor_upgrade_hints_v1`** 增补 **`ecc home-diff`**。测试：**`test_export_sync_diff.py`**、**`test_doctor_cli.py`**、**`test_repair_cli.py`**；smoke 执行 **`ecc home-diff --json`**。

- **ECC-N03-D03 harness 导出目标 inventory**：新增 **`ecc_harness_target_inventory_v1`**（**`build_ecc_harness_target_inventory_v1`**，`ecc_layout.py`）：按 **cursor/codex/opencode** 列出导出根、manifest/catalog 是否存在、各组件目录文件数，以及工作区 **`rules`/`skills`/`agents`/`commands`** 源侧摘要（**`workspace_sources`**）。CLI **`cai-agent ecc inventory --json`**；**`doctor --json`** 增加 **`ecc_harness_target_inventory`**；**`doctor_upgrade_hints_v1`** 增补推荐命令。测试：**`test_ecc_layout_cli.py`**、**`test_doctor_cli.py`**；smoke 在独立工作区 **`export`** 后执行 **`ecc inventory --json`**。

- **ECC-N02-D04 asset pack 修复诊断**：新增 **`build_ecc_asset_pack_repair_report_v1`**（**`ecc_asset_pack_repair_report_v1`**），对照 **`ecc pack-manifest`** 与各 harness 导出目录，检测缺失文件、`cai-local-catalog.json` 哈希漂移、`cai-export-manifest.json` 中 catalog schema 过期、manifest JSON 损坏等；CLI **`cai-agent ecc pack-repair [--target …] --json`**；**`doctor --json`** 增加 **`ecc_asset_pack_repair`**；**`repair --dry-run --json`** 增加 **`ecc_pack_repair_suggestions` / `ecc_pack_repair_ok`**；**`doctor_upgrade_hints_v1`** 增补命令。测试：**`test_asset_pack_repair.py`**、**`test_doctor_cli.py`**、**`test_repair_cli.py`**；smoke 在独立 **`cai-agent.toml`** 工作区执行 **`export` + `ecc pack-repair`**。

- **CC-N03-D04 plugins sync-home 安全 apply 启动**：`cai-agent plugins sync-home` 新增 `--apply` 写入路径，JSON 输出 **`plugins_sync_home_result_v1`**；默认遇到目标目录已存在且内容不同会拒绝覆盖并返回 `conflicts[]`，只有显式 `--force` 才替换，且默认先写 `.backup-*` 备份（可用 `--no-backup` 关闭）。已补 `test_plugin_compat_matrix.py` 用例；当前沙箱内 Python/uv 执行被拒，测试命令待可执行环境复跑。

- **文档**：`DEVELOPER_TODOS.zh-CN.md` / `TEST_TODOS.zh-CN.md` 仅保留未完成项；已 **Done** 的表格行迁至 **`docs/TODOS_DONE_ARCHIVE.zh-CN.md`**；`docs/README.zh-CN.md` 与 `AGENTS.md` 已加索引。
- **CC-N03-D03（plugins home drift）**：新增 **`plugins_home_sync_drift_v1`**（与 **`ecc_home_sync_drift_v1`** 同源差分）：**`doctor --json`** 的 **`plugins.home_sync_drift`**、文本 doctor 摘要、**`repair_plan_v1.plugins_sync_home_preview_commands`**、**`api_doctor_summary_v1.plugins_home_sync_drift_targets`**。测试：`test_plugin_compat_matrix.py`、`test_doctor_cli.py`、`test_repair_cli.py`、`test_api_http_server.py`；smoke 校验 doctor JSON。
- **CC-N03-D02（plugins sync-home dry-run）**：新增 **`cai-agent plugins sync-home`**，输出 **`plugins_sync_home_plan_v1`**（与 **`export`/`ecc sync-home`** 同源的 rules/skills/agents/commands → harness 导出根；**codex** 为 manifest_only）；**`doctor_upgrade_hints_v1`** 增补推荐命令；smoke 覆盖 **`plugins sync-home --json`**。测试：`test_plugin_compat_matrix.py`。
- **ECC-N01 / ECC-N02 / CC-N01-D04 / HM-N01-D03（本轮收口）**：新增 **`cai-agent ecc sync-home`**（**`ecc_home_sync_result_v1`** / **`ecc_home_sync_plan_v1`**）、**`cai-agent ecc pack-manifest`**（**`ecc_asset_pack_manifest_v1`**）、**`export --dry-run`**；**`export_ecc_dir_diff_v1`** 支持 **codex/opencode**；**`doctor_v1.ecc_home_sync_drift`**（**`ecc_home_sync_drift_v1`**）、**`repair_plan_v1.ecc_sync_commands`**；**`api_doctor_summary_v1.ecc_home_sync_drift_targets`**；**`doctor_upgrade_hints_v1`**；新增 **`config.load_agent_settings_for_workspace`**，**`gateway discord`/`slack`** 增加 **`--config`** 并在执行链路复用。测试：`test_ecc_layout_cli`、`test_repair_cli`、`test_doctor_cli`、`test_api_http_server`；**830 passed** + smoke **NEW_FEATURE_CHECKS_OK**。
- **HM-N01-D03（部分）HTTP API 与 CLI 配置对齐**：`cai-agent api serve` 新增 **`--config`**，服务端通过 **`load_settings_for_agent_api_server`** 使用显式 TOML，并将 **`Settings.workspace`** 固定为 **`-w`** 根目录，使 **`/v1/profiles`** 等路由的 **`profile_contract.workspace_root`** 与 **`active_profile_id`** 与 CLI **`--config` + `--workspace`** 语义一致。测试：`test_api_http_server.py::test_api_profiles_use_server_config_path_and_workspace`。
- **HM-N01-D02/D04/D05 profile home 用户路径**：新增 `cai-agent models clone`、`clone-all`（`--dry-run` / `--no-copy-home` / `--force-home` / `--set-active`）、`models alias`（`models_alias_v1`）；`profiles.py` 提供 `clone_profile_home_tree`、`build_models_alias_v1`、`build_profile_home_migration_diag_v1`；`doctor --json` 与 API summary 增加 `profile_home_migration`，文本 doctor 摘要输出孤儿 `.cai/profiles/*` 与迁移提示。测试：`test_profile_clone_alias_cli.py`；smoke 增补 `models clone --dry-run --json` 与 `models alias --json`。
- **CC-N02-D04 feedback bundle/export 脱敏与导出路径策略**：扩展 **`sanitize_feedback_text`**（workspace/home 路径、`/home/<user>`、Slack **`xox*`**）；**`append_feedback`** 落盘前脱敏；**`feedback export`** 对每行再脱敏；**`feedback_stats` / `feedback_export_v1` / `feedback_bundle_export_v1`** 的 **`workspace`** 统一为 **`<workspace>`**；**`feedback bundle`** 的 CLI JSON 增加 **`dest_placement`** 与工作区外 **`redaction.warnings`**；**`release_runbook`** 增补 **`feedback bundle`** 步骤。测试：`test_feedback_cli`、`test_feedback_export`、`test_feedback_bundle_cli`、`test_doctor_cli`。
- **ECC-N04-D03 ingest 来源/签名/信任策略草案**：新增中英文 **`docs/ECC_04C_INGEST_PROVENANCE_TRUST*.md`** 与 **`docs/schema/ecc_ingest_provenance_trust_v1.snapshot.json`**（`ecc_ingest_provenance_trust_v1`），定义与 **`ecc_asset_registry_v1`** 字段及 **`ecc_ingest_sanitizer_policy_v1`** 合流的保守门禁；更新 **`ecc_asset_registry_v1.snapshot.json`** 的 `boundaries`、`docs/schema/README*`、`ROADMAP_EXECUTION.zh-CN.md` §10、开发与缺口文档，并新增 **`test_ecc_ingest_schema_snapshots.py`** 保证草案 JSON 可解析。
- **英文产品缺口摘要同步**：扩展 **`docs/PRODUCT_GAP_ANALYSIS.md`**，与中文版优先级表（P0～P3）及 `HM-N05`～`HM-N10` 已交付后的排期口径对齐。
- **CC-N02 feedback bundle 与自助 triage 启动**：新增 `cai-agent feedback bundle --dest ... --json`，导出 `feedback_bundle_v1` 诊断包（最近反馈、`api_doctor_summary_v1`、`repair_plan_v1`、平台信息与脱敏策略），并返回 `feedback_bundle_export_v1`；`doctor --json` 新增 `doctor_feedback_triage_v1`，把 `doctor -> repair -> feedback bug -> feedback bundle` 串成固定本地排障链路。测试：`test_feedback_bundle_cli.py`、`test_feedback_cli.py`、`test_feedback_export.py`、`test_doctor_cli.py`。
- **配置发现顺序修正**：`Settings.from_env()` 现在在当前目录直接配置之后，优先检查 `CAI_WORKSPACE` 与 CLI `workspace_hint`，再沿当前目录父级查找；同时对 `.tmp-*` / `pytest-*` 等临时目录设置父级搜索边界，避免测试/临时工作区误读仓库根配置。测试：`test_model_profiles_config.py`。
- **CC-N01 repair / doctor 安装修复入口启动**：新增 `cai-agent repair --dry-run|--apply --json`，输出 `repair_plan_v1` / `repair_result_v1`，可保守创建缺失的 `.cai/`、`.cai/gateway/`、`hooks/` 与缺失的 `cai-agent.toml` 模板；`doctor --json` 新增 `doctor_install_v1` 与 `doctor_sync_v1`，并在文本 doctor 中展示安装/同步自检与 repair 提示。测试：`test_repair_cli.py`、`test_doctor_cli.py`。
- **后续开发队列文档收敛**：更新 `DEVELOPER_TODOS.zh-CN.md`、`TEST_TODOS.zh-CN.md` 与 `ISSUE_BACKLOG.zh-CN.md`，将已完成的 `HM-N05`、`HM-N07`、`HM-N08`、`HM-N09`、`HM-N10`、`HM-N11` 与部分 `ECC-N03/ECC-N04` 从默认开工队列移出，下一批聚焦 `CC-N01`、`CC-N02`、`HM-N01`、`ECC-N01`、`ECC-N02`。
- **文档状态与完成功能同步收敛**：统一回写 roadmap/todo/archive/implementation status 对最新完成批次（`HM-N11-D01/D02`、`ECC-N04-D01/D02`）的状态口径，并将共享 QA 基线更新为 `803 passed, 3 subtests passed` + smoke 全绿。
- **ECC-N04-D02 ingest sanitizer 策略草案**：新增 `docs/ECC_04B_INGEST_SANITIZER_POLICY.zh-CN.md`（含英文伴随文档）与 `docs/schema/ecc_ingest_sanitizer_policy_v1.snapshot.json`，定义 `metadata-first` + 默认 `deny-exec` 的最小净化基线，并将危险 hook/脚本隔离作为外部资产 ingest 的前置门禁（未完成 trust policy 前不开放自动执行）。
- **ECC-N04-D01 资产生态 ingest registry 草案快照**：新增 `docs/schema/ecc_asset_registry_v1.snapshot.json`（`ecc_asset_registry_v1`）机读草案，覆盖 `source/license/signature/version/trust` 元数据字段；并同步更新 `docs/schema/README.zh-CN.md` 与 `docs/schema/README.md`，明确该文件为仅 metadata 的 `draft_snapshot`，作为后续 `ECC-N04-D02/D03` 的输入基线。
- **HM-N11-D02 runtime backend interface 对齐**：在 `runtime/registry.py` 新增 `runtime_backend_interface_v1` 并接入 `runtime_registry_v1.interface`，统一声明 `exec/exists/describe/ensure_workspace` 操作契约、backend 配置键集合，以及 docker/ssh 对齐标记（`base_ops_aligned` + describe 字段集），确保未来云后端接入复用同一接口面且不破坏现有 `local/docker/ssh` 路径。
- **HM-N11-D01 云后端条件立项门槛文档**：扩展 `docs/CLOUD_RUNTIME_OOS.zh-CN.md`，新增可执行的 go/no-go 门槛清单（授权/安全/合规/产品/工程）与“本轮不做”边界，并同步更新英文伴随文档 `docs/CLOUD_RUNTIME_OOS.md`，明确未满足门槛前不进入真实云后端实现。
- **HM-N10-D05 Tool Gateway 门禁（approval/policy/cost）**：新增 `cai-agent tools guard --json`（`tool_gateway_guard_v1`）并将 guard 汇总接入 `tool_provider_contract_v1.guard`；`tools web-fetch` 新增 `--estimated-tokens` 与预算门禁（`cost_budget_max_tokens`），超预算返回 `cost_guard_exceeded`，避免高风险工具执行静默放行。
- **HM-N10-D04 真实 web provider 端到端示例**：新增 `cai-agent tools web-fetch --url ... --json`，复用既有 `fetch_url` 调用链实现真实抓取，并在执行前受 tool registry 中 `web` 启停状态约束（禁用时快速失败）；输出 `tool_provider_web_fetch_v1`，补齐 Tool Gateway 的真实 provider 示例链路。
- **HM-N10-D03 MCP bridge 复用既有 preset 能力**：新增 `cai-agent tools bridge --preset ... --json`，输出 `tool_mcp_bridge_v1`，并直接复用现有 `mcp_presets` 的匹配/报告逻辑与 `mcp_list_tools` 调用链，避免新造一套并行 bridge 协议。
- **HM-N10-D02 四类工具 registry 可操作化**：新增 `tool_provider_registry_v1` 与状态文件 `.cai/tool-providers.json`，并提供 `cai-agent tools list|enable|disable`（web/image/browser/tts）以支持按类别启停；输出含 `enabled_source`，便于区分默认状态与显式配置状态。
- **HM-N10-D01 Tool provider 契约基线**：新增 `tool_provider_contract_v1`（web/image/browser/tts 统一配置与权限视图），并提供 `cai-agent tools contract --json` 读口；同时接入 `doctor_v1.tool_provider` 与 `api_doctor_summary_v1.tool_provider`，建立 Tool Gateway 的统一机读入口。
- **HM-N09-D04 active memory provider 可观测收口**：新增 `memory_active_provider_v1` 并接入 `doctor_v1`/`api_doctor_summary_v1`、`profile_contract_v1` 与 `export-v2` manifest（`active_memory_provider`、`active_memory_provider_source`），让 active provider 在诊断、profile 契约、导出产物三个面保持同口径可观测。
- **HM-N09-D03 mock HTTP external provider 合约验证链路**：将 `honcho_external` 从占位态升级为可验证 mock adapter：`memory provider test --id honcho_external` 现可探测 `${CAI_MEMORY_EXTERNAL_MOCK_URL}/health`（可选 `CAI_MEMORY_EXTERNAL_API_KEY`），并在 `memory_provider_test_v1` 中返回远端健康与 schema 信息，实现“无真实服务也能做 contract 验证”。
- **HM-N09-D02 builtin local provider 显式注册**：在 memory provider 契约/注册表输出中新增 `builtin_registry`（`memory_provider_builtin_registry_v1`），集中声明 builtin provider id 与 default provider，将本地 provider 注册信息从“仅隐式硬编码”提升为可机读的显式注册面，为后续外部 provider 接入复用同一注册流程。
- **HM-N09-D01 memory provider registry 可操作化**：新增 `cai-agent memory provider list/use/test`，并保持 `memory provider --json` 的既有 `memory_provider_contract_v1` 兼容输出。active provider 现可通过 `use` 持久化到 `.cai/memory-provider.json`，`test` 输出 `memory_provider_test_v1` 以便 CI/运维做 provider 可用性检查。
- **HM-N08-D04 voice 边界与成本提示文档**：更新 `docs/rfc/HM_07A_VOICE_BOUNDARY.zh-CN.md`，明确“当前可用能力 vs OOS 边界”，补充 `voice config/check` 与 Telegram `voice-reply` 的适用范围、provider 成本面、合规注意点与上线建议，降低 Voice 需求沟通歧义。
- **HM-N08-D03 gateway voice-reply 最小闭环（Telegram）**：新增 `cai-agent gateway telegram voice-reply`，复用 `voice_provider_contract_v1` 作为 provider/health 机读口径，并通过 Telegram `sendVoice` + `voice_file_id` 回发语音。命令输出 `gateway_telegram_voice_reply_v1`，并按发送结果返回 `0/2`，便于 CI/运维自动化判断。
- **HM-N08-D02 voice config/check CLI 对齐**：新增 `cai-agent voice config` 与 `cai-agent voice check`。`config` 直接输出 `voice_provider_contract_v1`；`check` 输出 `voice_check_v1` 并按配置健康返回 `0/2`，可直接用于 CI 前置检查；两者与 doctor 复用同一 voice contract，口径保持一致。
- **HM-N08-D01 voice provider 契约基线**：新增 `voice_provider_contract_v1`（`cai_agent.voice`），明确 STT/TTS/health 三段字段，并接入 doctor 输出（`doctor_v1.voice` 与 `api_doctor_summary_v1.voice`）。该改动先建立 voice provider 的机读诊断面，暂不引入真实语音执行链路。
- **HM-N07-D04 联邦汇总统一输出（CLI/API）**：新增 `gateway_federation_summary_v1`，并通过 CLI `cai-agent gateway federation-summary --json` 与 API `GET /v1/gateway/federation-summary` 提供同一份聚合视图。该汇总复用 federation + channel monitoring 数据，稳定输出 platforms/channels/error 等关键统计，便于运维脚本统一消费。
- **HM-N07-D03 gateway proxy/routing 最小入口**：新增 `gateway_proxy_route_v1` dry-run 路由契约，并同时接入 CLI（`cai-agent gateway route-preview`）与 HTTP API（`POST /v1/gateway/route-preview`，仅 dry_run）。该改动先收口 source/route 决策载荷，不扩大写侧执行面，为后续真实 proxy/routing 链路打基础。
- **HM-N07-D02 channel monitoring 字段补齐**：`gateway_production_summary_v1.platforms[*]` 现新增 `channel_monitoring`（`gateway_channel_monitoring_v1`），统一提供每个 channel 的 `last_seen`、`latency_ms`、`error_count`、`owner`，并附带 summary 统计字段，便于后续联邦路由与运维视图复用同一观测口径。
- **HM-N07-D01 workspace federation 契约基线**：`gateway_maps_summarize_v1` 现新增嵌套对象 `gateway_workspace_federation_v1`，统一汇总每个 workspace 下各平台的 bindings/allowlist 统计；`gateway_production_summary_v1` 同步透传 `federation` 字段。该改动为后续 channel monitoring 与跨工作区路由能力提供稳定机读入口。
- **ECC-N03-D02 home-sync manifest 补强**：`export --target <cursor|codex|opencode>` 现在会在导出目录写入 `cai-local-catalog.json`（`local_catalog_v1`），并在 `cai-export-manifest.json` 中记录 `local_catalog_schema_version` 与 `local_catalog_file` 字段。该改动把导出产物与本地 catalog 契约绑定，便于后续 sync/registry 流程稳定消费。
- **ECC-N03-D01 local catalog 契约基线**：新增 `local_catalog_v1`（`build_local_catalog_payload`）并接入 `cai-agent ecc catalog`，统一输出 `rules/skills/hooks/plugins` 本地资产目录、条目计数、hooks 解析状态与 plugin surface 摘要，作为后续 home-sync / catalog 能力的机读基线。
- **HM-N05-D05 新平台 prod-status 收口**：`gateway prod-status --json`（`gateway_production_summary_v1`）现已将 Signal/Email/Matrix 纳入与 Telegram/Discord/Slack/Teams 同口径的 health/env/map 汇总与 production_state 判断。该改动把新接入平台统一收敛到一份 ops 摘要契约，便于后续运营脚本与 dashboard 消费。
- **HM-N05-D04 Matrix adapter 最小 room 路径**：新增 `cai_agent.gateway_matrix` 与 `cai-agent gateway matrix` 子命令（`bind/get/list/unbind`、`allow`、`send`、`receive`、`health`），并落地 `gateway_matrix_map_v1`、`gateway_matrix_health_v1`、`gateway_matrix_messages_v1` 契约。该 MVP 使用本地 spool 完成 room 维度 send/receive 最小链路，并提供 homeserver 配置存在性检查；`gateway platforms list --json` 中 Matrix 已提升为 `mvp`。
- **HM-N05-D03 Email adapter 最小 SMTP/IMAP 路径**：新增 `cai_agent.gateway_email` 与 `cai-agent gateway email` 子命令（`bind/get/list/unbind`、`allow`、`send`、`receive`、`health`），并落地 `gateway_email_map_v1`、`gateway_email_health_v1`、`gateway_email_messages_v1` 机读契约。该 MVP 使用本地 spool 完成最小发送-读取链路，同时提供 SMTP/IMAP 配置存在性检查；`gateway platforms list --json` 中 Email 已提升为 `mvp` 并带统一 adapter contract 元数据。
- **HM-N05-D02 Signal adapter skeleton + CLI 配置面**：新增 `cai_agent.gateway_signal`，落地 `gateway_signal_map_v1` / `gateway_signal_health_v1`，并接入 `cai-agent gateway signal` 子命令（`bind/get/list/unbind`、`allow`、`health`），先提供本地映射与配置存在性校验的最小可用路径。`gateway platforms list --json` 中 Signal 现提升为 `mvp`，并补齐 env 提示与统一 adapter contract 元数据。
- **HM-N05-D01 Gateway adapter 契约统一**：`gateway platforms list --json` 现为每个平台输出 `adapter_contract`（`gateway_platform_adapter_contract_v1`），统一 `send/receive/health/map/lifecycle` 能力面，并增加顶层 `adapter_contract_schema_version` 便于机读校验。`gateway prod-status --json` 也同步透传该契约，方便运维侧跨平台按同一字段消费能力信息。
- **HM-N04-D03 dashboard 审计日志强化**：`ops_dashboard_action_audit_v1` 现补充 actor/result 元数据，并在 `mode=audit` 下支持 `filter_action`、`filter_mode`、`ok` 过滤查询，方便本地运维场景按动作与结果快速排查。
- **HM-N04-D02 首批可写 dashboard 动作**：新增 `profile_switch_preview`（支持 `mode=apply`）用于切换工作区 `cai-agent.toml` 的 `[models].active`，并与已落地的 schedule reorder / gateway binding patch 一起形成“至少两类真实写动作”（profile switch + map update）收口，且复用同一审计日志链路。
- **HM-N04-D01 dashboard 动作契约（preview/apply/audit）**：`GET /v1/ops/dashboard/interactions` 在 `ops_dashboard_interactions_v1` 下新增 `mode=preview|apply|audit` 三段式语义。首批 `apply` 已支持 `schedule_reorder_preview` 与 `gateway_bind_edit_preview` 的最小安全写入，并新增本地审计事件 `ops_dashboard_action_audit_v1`（落盘 `.cai/ops-dashboard-actions.jsonl`，可用 `mode=audit` 查询）。
- **HM-N03-D03 API/OPS 鉴权收口**：新增共享函数 `resolve_bearer_token()`（`server_auth.py`），`api serve` 与 `ops serve` 统一采用同源 token 解析（分别支持 `CAI_API_TOKEN` 与 `CAI_OPS_API_TOKEN` 主次回退），减少两条服务面的鉴权配置分叉。新增 `test_server_auth.py`，API/OPS 测试保持通过。
- **HM-N03-D02 API schema 覆盖补齐**：新增 `GET /v1/profiles` 对应的 `api_profiles_v1.schema.json`，在 `test_api_http_server.py` 增加 schema 常量断言，并同步更新 `docs/schema/README.md` 与 `docs/schema/README.zh-CN.md` 的索引说明，保证路由文档与机器校验契约一致。
- **HM-N03-D01 状态路由扩展**：`api serve` 新增 `/health`（与 `/healthz` 等价，保持免鉴权）并新增 `GET /v1/profiles`（`api_profiles_v1`），统一输出 active/subagent/planner profile、profiles 列表与 `profile_contract_v1`，便于运维脚本与外部工具读取状态。
- **HM-N01-D03 active profile 解析链路统一**：在 `profiles.py` 增加共享解析函数 `get_profile_by_id`、`resolve_role_profile_id`，并让 `llm_factory.resolve_role_profile`、`models.fetch_models`、TUI 模型面板关闭后的 profile 选择都复用同一套解析逻辑，减少 CLI/TUI/API/gateway 相邻运行路径的口径漂移。`test_model_profiles_config.py` 已补覆盖，相关测试与 smoke 通过。
- **HM-N01-D01 profile-home 契约基线**：`profile_contract_v1` 在可解析工作区根目录时，现可输出 `profile_home_layout_v1`（`profile_homes` + `active_profile_home`），统一描述每个 profile 在 `.cai/profiles/<id>/...` 下的隔离目录布局。`doctor`、`api models summary`、`models list` 与 TUI 状态/上下文相关入口已接入同一契约。测试：`test_model_profiles_config.py`、`test_model_profiles_cli.py`。
- **文档 backlog 清理（Done 项迁移出 TODO）**：从 **`docs/DEVELOPER_TODOS.zh-CN.md`** 移除已完成的 `MODEL-P0` / `HM-N02` 能力级与原子级条目，使 TODO 仅保留未完成事项；在 **`docs/COMPLETED_TASKS_ARCHIVE.zh-CN.md`** 增补迁移说明与索引；并同步更新“推荐开发顺序”，避免继续引用已完成任务。
- **MODEL-P0 HTTP 机读 schema（OpenAI 与 capabilities）**：为 **`api serve`** 增加 **`api_models_capabilities_v1`**、**`api_openai_models_v1`**、**`api_openai_chat_completion_v1`**、**`api_openai_chat_completion_chunk_v1`** 独立 JSON Schema，与 `GET /v1/models/capabilities`、`GET /v1/models`、`POST /v1/chat/completions`（非流式与 SSE chunk）响应对齐；**`test_api_http_server.py`** 已固定 const。索引见 `docs/schema/README.md` / `README.zh-CN.md`。
- **MODEL-P0 doctor 模型块 schema**：新增 **`doctor_model_gateway_v1.schema.json`**，与 **`doctor --json`** 中 **`model_gateway`** 嵌套对象一致（capabilities 列表、健康状态枚举、runbook 路径、推荐命令链等）；**`test_doctor_cli.py`** 已固定 const 与必填字段。索引见 `docs/schema/README.md` / `README.zh-CN.md`。
- **MODEL-P0 路由子契约 schema 独立化**：在 `cai-agent/src/cai_agent/schemas/` 新增 **`model_fallback_candidates_v1.schema.json`** 与 **`routing_explain_v1.schema.json`**，与 `models routing-test --json` 中嵌套对象一一对应，便于单文件校验与文档引用；`test_model_routing.py` 已固定两文件的 `schema_version` 与关键字段。索引见 `docs/schema/README.md` / `README.zh-CN.md`。
- **MODEL-P0 收口**：完成模型接入地基：新增 **`models onboarding`**（**`model_onboarding_flow_v1`**）输出 add → capabilities → ping → chat-smoke → use → routing-test 命令链；新增 **`doctor_model_gateway_v1`**，在 doctor 中汇总 capabilities、健康状态枚举与 runbook 建议；**`models routing-test --json`** 增加 **`model_fallback_candidates_v1`**。fallback 仅解释候选（`auto_switch=false`），并附非敏感能力快照。新增 runbook：**`docs/MODEL_ONBOARDING_RUNBOOK.zh-CN.md`**。测试：**`test_model_profiles_cli.py`**、**`test_model_routing.py`**、**`test_doctor_cli.py`**、smoke。
- **MODEL-P0 TUI 收口**：TUI 模型面板现在与 CLI/API/doctor 使用同源非敏感能力视图，行内显示 context、streaming/tools/json、本地/远端 scope、cost hint，并在按 `t` ping 后刷新 `health=`。测试：**`test_tui_model_panel.py`**。
- **MODEL-P0 Provider Registry 硬化**：**`provider_registry_v1`** 与 provider readiness snapshot 现在内嵌由 Model Gateway 推导的非敏感 **`capabilities_hint`**，provider preset 可直接暴露 context / streaming / tools / local / cost hint，且不泄漏 `api_key` 或 `base_url`。测试：**`test_provider_registry.py`**。
- **MODEL-P0 runbook 可发现性**：模型接入 runbook 已挂入中英文 docs 入口与 onboarding 指南，并新增 **`test_model_onboarding_docs.py`** 固定 runbook 命令链与链接。
- **MODEL-P0 onboarding 校验**：**`models onboarding`** 现在会提前拒绝未知 preset，并在 **`model_onboarding_flow_v1`** 中返回非敏感 **`capabilities_hint`**，与 provider registry / Model Gateway 能力视图一致。测试：**`test_model_profiles_cli.py`**。
- **MODEL-P0 schema 硬化**：新增 **`model_onboarding_flow_v1`** 与 **`provider_registry_v1`** 机读 schema，放在 **`cai-agent/src/cai_agent/schemas/`**，并补测试固定 schema const 与 capabilities hint 字段。
- **MODEL-P0 capabilities schema 硬化**：新增 **`model_capabilities_v1`** 与 **`model_capabilities_list_v1`** 机读 schema，并补测试固定 CLI/API/doctor/TUI/provider registry 共用的核心能力字段。
- **MODEL-P0 response schema 硬化**：新增 **`model_response_v1.schema.json`**，与 gateway / OpenAI-compatible chat 内部复用的归一化响应包对齐，并补测试；英文 schema 索引用 [`docs/schema/README.md`](docs/schema/README.md) 汇总 MODEL-P0 相关 schema 路径。
- **OpenAI-compatible API Server 收口（MODEL-P0 / HM-N02）**：**`cai-agent api serve`** 新增 OpenAI-compatible **`GET /v1/models`**（**`api_openai_models_v1`**）与 **`POST /v1/chat/completions`**，底层复用统一 **`ModelResponse`** / **`model_response_v1`**。Chat 同时支持非流式 **`api_openai_chat_completion_v1`** 与最小 **`stream=true`** SSE chunk（**`api_openai_chat_completion_chunk_v1`** + `data: [DONE]`）；响应包含 OpenAI 风格 `choices[]` / `usage`，并在 `cai_model_response` 暴露 provider/model/profile/latency 细节。**`CAI_METRICS_JSONL`** 追加 **`api.chat_completions`**，记录 provider/model/profile 与 usage 元数据。测试：**`test_api_http_server.py`**、**`test_model_gateway.py`**、**`test_llm_factory_dispatch.py`**。
- **双语文档精简**：为当前中文主文档补齐轻量英文伴随摘要，新增中文迁移摘要与英文 schema 索引，将旧 Hermes/progress 文档移动到 **`docs/archive/legacy/`**，并更新活跃文档入口，区分权威文档、未来队列、完成归档与冻结历史记录。
- **Todo 归档清理**：新增 **`docs/COMPLETED_TASKS_ARCHIVE.zh-CN.md`** / **`docs/COMPLETED_TASKS_ARCHIVE.md`** 作为已完成任务归档，并精简 **`docs/DEVELOPER_TODOS.zh-CN.md`**，使其只保留未完成工作、未来方向、OOS/条件立项、执行规则与当前 QA 基线。
- **Design backlog 实现（HM-04c / HM-03e / HM-05d）**：新增只读预览型 **`ops_dashboard_interactions_v1`** HTTP 契约，用于 dashboard 的 schedule reorder / gateway bind-edit dry-run；新增多平台 **`gateway prod-status --json`**（**`gateway_production_summary_v1`**）生产状态摘要；新增 **`memory provider --json`**（**`memory_provider_contract_v1`**）描述 local entries / user-model provider 覆盖。Smoke 现检查 gateway prod-status 与 memory provider 契约。测试：**`test_ops_http_server.py`**、**`test_gateway_lifecycle_cli.py`**、**`test_memory_provider_contract_cli.py`**。
- **双语入口收敛（DOC-01c）**：根 README 与 docs README 入口补充本批已交付的 Teams gateway、docker/SSH runtime 后端诊断、插件兼容矩阵 snapshot，并更清楚地互指中英文实现摘要、测试 TODO、issue backlog 与已入库的 **`plugin_compat_matrix_v1.snapshot.json`**。
- **插件兼容矩阵 CI snapshot（ECC-03c）**：新增 **`scripts/gen_plugin_compat_snapshot.py`**，支持写入与 **`--check`** 校验 **`docs/schema/plugin_compat_matrix_v1.snapshot.json`**。snapshot 同时内嵌 **`plugin_compat_matrix_v1`** 与 **`plugin_compat_matrix_check_v1`**，让 ECC-03b 治理门禁可作为确定性的 CI dry-run 使用。Smoke 现运行 snapshot check。测试：**`test_plugin_compat_matrix.py`**。
- **SSH runtime 后端产品化（HM-06c）**：**`runtime.ssh`** 诊断现在通过 **`doctor_runtime_v1.describe`** 暴露 `ssh_binary_present`、key path 配置/存在性、`known_hosts` 路径/存在性、严格 host key 模式、连接超时与 audit 配置。可通过 **`[runtime.ssh].audit_log_path`** / **`audit_label`** 启用可选 **`runtime_ssh_audit_v1`** JSONL 审计；默认不记录命令明文，除非显式设置 **`audit_include_command=true`**。测试：**`test_runtime_ssh_mock.py`**。
- **Docker runtime 后端产品化（HM-06b）**：**`runtime.docker`** 现在同时支持既有 `container` / `docker exec` 路径与新增 `image` / `docker run --rm` 路径，并解析 **`[runtime.docker].workdir`**、**`volume_mounts`**、**`cpus`**、**`memory`**。**`doctor --json`** / **`doctor_runtime_v1.describe`** 现暴露 mode/image/workdir/volume/limit 详情，方便本地诊断。Smoke 新增 **`runtime list --json`** 检查。测试：**`test_runtime_docker_mock.py`**、**`test_runtime_tool_dispatch.py`**。
- **Microsoft Teams Gateway（HM-03d）**：新增 **`cai-agent gateway teams`**，包含 `bind/get/list/unbind`、`allow`、`health`、`manifest`、`serve-webhook`。新模块 **`cai_agent.gateway_teams`** 将 **`gateway_teams_map_v1`** 落盘到 **`.cai/gateway/teams-session-map.json`**，输出 **`gateway_teams_health_v1`**（本地映射 + app/tenant/webhook-secret 配置存在性），生成 Teams app manifest 草案（**`gateway_teams_manifest_v1`**），并以轻量 Bot Framework Activity webhook 处理 `help` / `ping` / `status` / `new`，不引入 SDK 依赖。**`gateway platforms list`** 与 **`gateway maps`** 已纳入 Teams。测试：**`test_gateway_discord_slack_cli.py`**、**`test_gateway_maps_summarize.py`**。
- **HTTP API 只读扩展（HM-02c）**：**`cai-agent api serve`** 新增 **`GET /v1/models/summary`**（**`api_models_summary_v1`**：`profile_contract_v1` 白名单 + profile ID 列表；不包含 `base_url` / `model` / `api_key`）、**`GET /v1/plugins/surface`**（**`api_plugins_surface_v1`**：只读扩展面；可选 **`?compat=1`** 附加 **`plugin_compat_matrix_v1`**）、**`GET /v1/release/runbook`**（**`api_release_runbook_v1`**：release runbook 白名单，不含仓库/工作区绝对路径）。**`CAI_API_TOKEN`** Bearer 鉴权与既有接口一致。测试：**`test_api_http_server.py`**。
- **模型 / 状态体验对齐（CC-03c）**：TUI **`#context-label`**（经 `cai_agent.tui_session_strip.build_context_label`）在 subagent/planner 与 active 不同时追加 **`· route=sub`** / **`· route=pl`** / **`· route=sub+pl`**；**`profile_contract_v1.migration_state != ready`** 时追加 **`· ⚠ migration`**；整体截断至 80 字符。TUI model-panel、`/use-model` 成功路径与 CLI **`models use`** 现额外打印统一一行 **`profile_switched: <id>`**（`build_profile_switched_line`）。测试：**`test_tui_session_strip.py`**、**`test_model_profiles_cli.py`**。
- **插件/版本治理最小可验证入口（ECC-03b）**：**`build_plugin_compat_matrix()`** 增加 **`governance_rfc`** 与 **`maintenance_checklist`**（与 **`docs/rfc/ECC_03A_PLUGIN_VERSION_GOVERNANCE.zh-CN.md`** §2 单源）。新增 **`build_plugin_compat_matrix_check_v1()`** 与 CLI **`cai-agent plugins --compat-check`**，输出 **`plugin_compat_matrix_check_v1`**（`ok` / `missing_components` / `missing_targets` / `row_mismatches` 等），在默认白名单 `PLUGIN_COMPONENTS` × (cursor/codex/opencode) 漂移时退出码 `2`。Schema：**`plugin_compat_matrix_v1.schema.json`** 增加可选 `governance_rfc` / `maintenance_checklist`。测试：**`test_plugin_compat_matrix.py`**。
- **未开发功能队列（2026-04-25）**：最初将剩余工作整理为 P0/P1/OOS 队列，并同步 **`ROADMAP_EXECUTION`** §10 与 **`GAP_TRACKER.md`**。完成项现已统一归档到 **`docs/COMPLETED_TASKS_ARCHIVE.zh-CN.md`**；当前开发 TODO 只保留未来工作与 OOS/条件方向。
- **Explore 批次收口（HM-03c / ECC-03a / HM-06a / HM-07a）**：在 **`docs/rfc/`** 增补评估/设计结论文档：**`HM_03C_NEXT_GATEWAY_PLATFORMS.zh-CN.md`**、**`ECC_03A_PLUGIN_VERSION_GOVERNANCE.zh-CN.md`**、**`HM_06A_RUNTIME_BACKEND_ASSESSMENT.zh-CN.md`**、**`HM_07A_VOICE_BOUNDARY.zh-CN.md`**；**`ROADMAP_EXECUTION`** §10 对应 issue 标为 **Done**（交付物为文档），并归档到 **`docs/COMPLETED_TASKS_ARCHIVE.zh-CN.md`**。
- **最小只读 HTTP API（HM-02b）**：新增 **`cai-agent api serve`**（**`cai_agent.api_http_server`**）：**`GET /healthz`**、**`GET /v1/status`**（**`api_status_v1`** + **`gateway_summary_v1`**）、**`GET /v1/doctor/summary`**（**`api_doctor_summary_v1`**，不含明文 **`base_url`/`model`**）、**`POST /v1/tasks/run-due`**（**`api_tasks_run_due_v1`**，仅 **dry_run**；真实执行返回 **403**）。环境变量：**`CAI_API_PORT`**（默认 **8788**）、可选 **`CAI_API_TOKEN`**（**Bearer**，**`/healthz`** 免检）。测试：**`test_api_http_server.py`**；smoke 含 **`api serve --help`**。
- **Recall 评估收口（HM-05b）**：**`recall --evaluate`** 不再强制 **`--query`**；**`recall_evaluation_v1`** 语义不变；**`smoke_new_features`** 覆盖 **`recall --evaluate --json`**。
- **Memory policy 可见性（HM-05c）**：文本 **`doctor`** 增加 **`[memory.policy]`** 段落；**`release-ga --with-memory-policy`** 单测覆盖 **`memory_policy_entries`** 门禁。
- **ECC 安装/导出/共享叙事（ECC-01b）**：**`CROSS_HARNESS_COMPATIBILITY*.md`** 增补编号化流转（init → **`ecc layout`** → **`export`** → 共享约定）。
- **成本视图与 compact 解释（ECC-02b）**：**`cost report --json`** 嵌 **`compact_policy_explain_v1`**（与 **`graph`** 中 compact / 约 **85%** 预算提示阈值对齐）；无 **`--json`** 时输出文本摘要而非报错。
- **设计 RFC**：**`docs/rfc/HM_02_MINIMAL_SERVER_CONTRACT.zh-CN.md`**（**HM-02a**）、**`docs/rfc/CC_03B_MODEL_STATUS_UX.zh-CN.md`**（**CC-03b**）。

### 0.7.0（2026-04-23）

- **TUI 任务/状态/会话体验统一（CC-03a）**：新增 **`cai_agent.tui_session_strip`**，**`/help`**、欢迎页、**`/sessions`**、**`/load`** 后提示、**`/retry`**、输入框 placeholder、**`/tasks`** 看板首行与 **`#context-label`**（**`<profile> · 上下文`**）共用同一套「任务看板 / 上下文条 / 继续会话」口径。
- **WebSearch·Notebook TUI 入口（CC-01b）**：TUI 斜杠 **`/mcp-presets`**；**`/help`**、**`/status`** 与 **任务看板** 底部展示 **`format_tui_mcp_web_notebook_quickstart()`**（文档指针 + **`mcp-check`** 最短命令）；**`mcp-check --help`** 增加 epilog 提示预设与专题文档。
- **结构化 /bug 反馈（CC-02b）**：新增 **`cai-agent feedback bug`**（**`--detail`** / **`--detail-file`**、**`--category`**：**`crash`** / **`wrong_result`** / **`ux`** / **`docs`** / **`perf`** / **`security`** / **`other`**、可选 **`--attach-doctor-hint`**），JSON 行为 **`feedback_bug_report_v1`**，与既有反馈同落盘 **`.cai/feedback.jsonl`**。写入前经 **`sanitize_feedback_text`** 脱敏；**`release_runbook_v1.runbook_steps`** 增加可选采集步骤说明。
- **发版反馈摘要同源（REL-01b）**：**`doctor --json`** 顶层 **`feedback`** 与 **`release_runbook.feedback`** 现从同一次 **`build_release_runbook_payload`** 复用（避免重复扫描 **`.cai/feedback.jsonl`**）。新增 **`cai-agent feedback stats`**（**`--json`** 输出 **`feedback_stats_v1`**，与 doctor 机读字段一致）。
- **路由 / 预算解释（ECC-02a）**：**`models routing-test`** 不再强制 **`--json`**（默认打印 **effective_profile + 中文摘要**）；**`--json`** 增加嵌套 **`explain`**（**`routing_explain_v1`**）。**`cost budget`** 的 **`cost_budget_v1`** 增加 **`explain`**（**`cost_budget_explain_v1`**）与 **`active_profile_id`**。实现：**`build_routing_explain_v1`**、**`build_cost_budget_explain_v1`**；**`models_routing_test_v1`** schema 已扩 **`explain`**。测试与 smoke、**`MODEL_ROUTING_RULES*.md`** 已同步。
- **ECC 资产目录（ECC-01a）**：新增 **`cai_agent.ecc_layout`**（rules/skills/hooks 路径单源）；CLI **`cai-agent ecc layout`**（**`ecc_asset_layout_v1`**）、**`ecc scaffold`**（**`ecc_scaffold_result_v1`**，内置 **`templates/ecc/*`**）；**`hook_runtime.resolve_hooks_json_path`** 统一走 **`iter_hooks_json_paths`**；文档 **`CROSS_HARNESS_COMPATIBILITY*.md`**、schema 索引与 metrics；**`smoke_new_features`** 含 **`ecc layout`**。测试：**`test_ecc_layout_cli.py`**。
- **用户模型 SQLite 闭环（HM-05a）**：**`memory user-model store init`/`list`**（**`memory_user_model_store_init_v1`** / **`memory_user_model_store_list_v1`**）；**`learn`/`query`** JSON 增加 **`store_path`**（**`query`** 另含 **`needle`**）；空 belief 的 **`learn`** → exit **`2`**；**`memory user-model export --with-store`** 在 **`user_model_bundle_v1`** 下附加 **`user_model_store`**（**`user_model_store_snapshot_v1`**）。测试：**`test_memory_user_model_store_cli.py`**；**`smoke_new_features`** 已扩闭环。
- **Discord 网关（HM-03a）**：新增 **`cai-agent gateway discord health`**（**`gateway_discord_health_v1`**：本地映射 + 可选 **`GET /users/@me`**）；CLI 落地 **`register-commands`** / **`list-commands`**（与文档 parity 一致）；**`gateway discord bind`** 支持 **`--guild-id`** / **`--label`**；**`doctor`** 的 **`cai_dir_health.discord_map_summary`**；排障见 **`docs/GATEWAY_DISCORD_TELEGRAM_PARITY.zh-CN.md`**；**`smoke_new_features`** 覆盖 **`discord list`** 与 **`discord health`**。
- **安装 / 升级指引**：`init --json` 现在会返回 `support_docs` 与 `next_steps`，`doctor --json` 新增 `installation_guidance`，让新用户和升级用户都能从 CLI 里直接发现 onboarding、文档入口和 changelog 指针。
- **MCP preset onboarding**：`mcp-check --preset` 现在支持组合路径 `websearch/notebook`，会输出 `presets[]` 明细、文档/onboarding 指针，以及更完整的模板与 next-step 提示，方便新用户接入 WebSearch / Notebook。
- **发版 runbook 摘要**：`doctor --json` 与 `release-ga --json` 新增同源 **`release_runbook_v1`**，汇总固定命令顺序、CHANGELOG 双语/结构检查、文档回写目标与 feedback 摘要；`release-ga` 同时把 changelog 同步纳入 GA 门禁，并新增 **`failed_check_details`** 便于人读排障。
- **release-changelog 统一报告**：`release-changelog --json --semantic` 现在会输出专用 **`release_changelog_report_v1`**，把双语检查、语义检查与裁剪后的 runbook 摘要放进同一个载荷；文本模式也会直接打印下一步发版命令提示。
- **profile 契约摘要**：`doctor --json` 与 `models list --json` 现在会输出共享的 **`profile_contract_v1`**，统一描述显式/隐式 profile 来源、激活优先级、fallback 行为与迁移状态，作为 `HM-01` 后续实现的同源口径。
- **ops / gateway 共享摘要**：`board --json`、`ops dashboard --json` 与 `gateway status --json` 现在共享 **`gateway_summary_v1`**，把 `status`、`bindings_count`、`webhook_running`、allowlist 状态这类读侧字段收成同一套口径，作为 `HM-04` 的最小统一载荷。
- **会话 `events` 信封（`run_schema_version=1.1`）**：`run`/`continue`/`command`/`agent`/`fix-build` 的 **`--json`** 将 **`events`** 包在稳定的 **`run_events_envelope_v1`**（`schema_version` + **`items[]`**）内，不再输出裸数组。`observe` / `sessions` 经 **`normalize_session_run_events`** 兼容旧列表与新信封。各失败路径（`goal_empty`、`load_session_failed`、`interrupted` 等）同样输出结构化信封。
- **TUI 任务看板**：**`/tasks`** 与 **`Ctrl+B`** 只读面板（**`.cai-schedule.json`** 与 **`.cai/last-workflow.json`**），实现见 **`tui_task_board.py`**。
- **Hooks `script` 自动执行**：**`hook_runtime.py`** 除 **`command[]`** 外解析 **`script`**（`.py`/`.sh`/`.ps1`/`.cmd`/`.bat`），含路径逃逸防护与平台规范化；**`hooks/README.md`** 已更新。
- **`memory validate-entries`**：新子命令 → **`memory_entries_file_validate_v1`**；无脏行 exit **`0`**，有无效行 exit **`2`**；底层为 **`build_memory_entries_jsonl_validate_report`**。
- **`memory/entries.jsonl` 写入门禁**：**`append_memory_entry`** / **`import_memory_entries_bundle`** 在追加前要求已有文件通过 **`validate-entries`** 同源行级校验（**`require_memory_entries_jsonl_clean_before_write`**）；**`memory extract`** 写条目前预检，脏数据时 stdout JSON **`ok: false`** 且 exit **`2`**。救急：**`CAI_MEMORY_ALLOW_DIRTY_ENTRIES_JSONL=1`**。
- **`auto_extract_skill_after_task` LLM 草稿**：可选 **`settings`**，在具备 **API key** 且非 **mock** 时经 **`chat_completion_by_role`** 生成 Markdown；返回 **`draft_method`**（**`llm`** | **`template`**）。
- **`insights --json --cross-domain`**：**`insights_cross_domain_v1`** 增加 **`recall_hit_rate_metric_kind`**（**`index_probe`**）、**`recall_hit_rate_metric_note`**，且 **`recall_hit_rate_trend`** 每行含 **`metric_kind`**（**`index_probe`/`unavailable`**）与无索引时的 **`metric_unavailability_reason`**，避免将索引子串探测命中率与 **`recall`** 查询命中率混淆。
- **文档**：新增 **`docs/qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md`**（与 **PRODUCT_PLAN** T7 对齐的发版手工门禁清单）。
- **`fetch_url` 重定向上限**：**`[fetch_url].max_redirects`**（整数 **1–50**，默认 **20**）或环境变量 **`CAI_FETCH_URL_MAX_REDIRECTS`**（超出范围会钳制）；传入 **`httpx.Client(max_redirects=…)`**。**`doctor --json`** 增加 **`fetch_url_max_redirects`**；文本 **`doctor`** 在 fetch_url 行展示该值。
- **`fetch_url` 解析后 SSRF 防护**：在发起 **`httpx`** 请求前对 **`socket.getaddrinfo`** 结果校验；**任一** 解析地址为私网/本机/链路本地/保留/组播/未指定则拒绝（缓解 **DNS rebinding**）。内网解析场景：**`[fetch_url].allow_private_resolved_ips=true`** 或 **`CAI_FETCH_URL_ALLOW_PRIVATE_RESOLVED_IPS=1`** 跳过该校验。**`doctor`** JSON/文本输出 **`fetch_url_allow_private_resolved_ips`**。
- **工具注册表文档生成**：**`cai_agent/tools_registry_doc.py`** 维护 **`BUILTIN_TOOLS_DOC_ROWS`**；**`scripts/gen_tools_registry_zh.py`** 写回 **`docs/TOOLS_REGISTRY.zh-CN.md`**；**`tools.DISPATCH_TOOL_NAMES`** 与 **`dispatch`** 工具名对齐；**`test_tools_registry_doc_sync.py`** 与 CI **`gen_tools_registry_zh.py --check`** 防止漂移。
- **文档**：**[`OPS_DYNAMIC_WEB_API.zh-CN.md`](docs/OPS_DYNAMIC_WEB_API.zh-CN.md)** — 只读 HTTP 契约（**`GET /v1/ops/dashboard`** / **`dashboard.html`**）、可选 **`CAI_OPS_API_TOKEN`**、**Phase A–C** 分阶段；**Phase A/B** 已由 **`cai-agent ops serve`** 与 HTML **`meta refresh`** 在仓库内实现，**Phase C** 仍为后续。
- **`ops serve`（只读 HTTP 侧车）**：**`cai-agent ops serve`**，stdlib **`ThreadingHTTPServer`**，路径 **`/v1/ops/dashboard`** / **`/v1/ops/dashboard.html`**；**`--allow-workspace`**（默认可用启动时 cwd）；**`CAI_OPS_API_TOKEN`** 非空时要求 **Bearer**。实现：**`cai_agent.ops_http_server`**；测试：**`test_ops_http_server.py`**。
- **`ops dashboard --format html`**：可选 **`--html-refresh-seconds`**（**Phase A** **`meta refresh`**）；**`ops serve`** 的 **`dashboard.html`** 路由支持 query **`html_refresh_seconds`**。
- **`memory user-model export`**：stdout **`user_model_bundle_v1`**（嵌 **`memory_user_model_v1`** **`overview`**，**`bundle_kind=behavior_overview`**）。测试：**`test_memory_user_model_export.py`**；**`smoke_new_features`** 已覆盖。
- **TUI `/tasks` 看板**：**`render_task_board_markup`** 使用 **`build_board_payload`** + **`attach_failed_summary`** + **`attach_status_summary`**（与 **`board`** 默认同源）、**`enrich_schedule_tasks_for_display`** 展示 **`.cai-schedule.json`**（与 **`schedule list`** 同源），workflow 步骤列表更完整；**`test_tui_task_board_render.py`**。
- **文档**：**[`CLOUD_RUNTIME_OOS.zh-CN.md`](docs/CLOUD_RUNTIME_OOS.zh-CN.md)**（Modal/Daytona 等云运行后端 **默认 OOS**、理由与替代路径）；**[`MODEL_ROUTING_RULES.zh-CN.md`](docs/MODEL_ROUTING_RULES.zh-CN.md)**（**`[models.routing]`** 与 **`models routing-test`** 等）。**`PARITY_MATRIX`** L3 新增云运行 **`OOS`** 行；L2 成本/路由行链至路由文档。
- **文档（波次 α）**：**[`MEMORY_TTL_CONFIDENCE_POLICY.zh-CN.md`](docs/MEMORY_TTL_CONFIDENCE_POLICY.zh-CN.md)**（TTL/置信度与 **`prune`/`state`/`health`**）；**[`CHANGELOG_SYNC.zh-CN.md`](docs/CHANGELOG_SYNC.zh-CN.md)** + **`.github/pull_request_template.md`**（CHANGELOG 双语与 PR 自检）；**[`GATEWAY_500_MSG_STRESS_RUNBOOK.zh-CN.md`](docs/qa/GATEWAY_500_MSG_STRESS_RUNBOOK.zh-CN.md)** + **`docs/qa/runs/TEMPLATE_GATEWAY_S8_AC3.zh-CN.md`**（S8-02 AC3）；**T7** / **sprint8-ga-testplan** / **PRODUCT_PLAN** / **PRODUCT_GAP** / **runs README** 互链更新。
- **`memory extract --structured`**：可选 LLM 结构化抽取；mock/无 key 时回退启发式（**`extract_memory_entries_structured`**）。
- **子 Agent IO schema v1.1**：`workflow` JSON 提升 **`subagent_io_schema_version`** 至 **`1.1`**；每步含 **`agent_template_id`**（与 **`agents/`** 目录匹配）及来自 **`protocol`** 的 **`rpc_step_input`/`rpc_step_output`**。
- **Workflow 后置 quality-gate 联动**：workflow JSON root 新增 **`quality_gate`**（`true` 或对象，可覆盖 **`compile`** / **`test`** / **`lint`** / **`typecheck`** / **`security_scan`** / **`report_dir`**）。当 workflow 本身成功时，`run_workflow` 自动执行一次后置 **`quality-gate`**，输出追加 **`quality_gate`** 摘要与可选 **`post_gate`**（**`quality_gate_result_v1`**），事件流新增 **`workflow.quality_gate.*`**，gate 失败时 `task.error` 为 **`workflow_quality_gate_failed`**。
- **`plan --json` 稳定 schema**：**`goal_empty`** 错误含 **`"task": null`**；各失败分支含 **`plan_schema_version`**。
- **`hooks run-event` 实跑**：非 **`--dry-run`** 时执行匹配脚本/命令（与 **`script`** 字段贯通）。
- **前端 monorepo 质量门禁**：**`CAI_QG_FRONTEND_MONOREPO=1`** 且存在 **`package.json`** 时，自动在 quality-gate 中追加 **`npm run -ws --if-present lint`**。
- **`export --ecc-diff`**：**`export_ecc_dir_diff_v1`**，对比仓库源目录与 **`.cursor/cai-agent-export`**，不写文件。
- **`skills hub install`**：从 **`skills_hub_manifest_v1`** JSON 选择性拷贝技能到目标目录（**`--only`**、**`--dry-run`**）。
- **进度环形缓冲（`progress_ring.py`）**：**`graph.py`** 的 **`_emit`** 同步写入全局 **`ProgressRing`**；**`run --json`** 含 **`progress_ring`**（如 **`phase_distribution`**）；每次调用前 **`reset_global_ring()`**。
- **compact 与成本预算联动**：**`compact_hint`** 触发且累计 token 超过 **`cost_budget_max_tokens`** 约 **85%** 时，向对话注入额外成本提示。
- **`models suggest`**：按任务描述启发式推荐 profile → **`models_suggest_v1`**。
- **`[models.routing]`（声明式）**：TOML **`[[models.routing.rules]]`**（**`roles`** / **`goal_regex`** / **`goal_substring`** / **`cost_budget_remaining_tokens_below`** / **`profile`**）→ **`Settings.model_routing_rules`**；**`chat_completion_by_role`** 自上而下首条 **AND** 命中（goal 来自首条 **`user`**；成本条件来自 **`[cost].budget_max_tokens`** 与 **`get_usage_counters()`** 的 **`total_tokens`**）。**`cai-agent models routing-test`** 支持可选 **`--goal`**、**`--total-tokens-used`**、**`--json`** → **`models_routing_test_v1`**。**`doctor --json`**：**`model_routing_enabled`**、**`model_routing_rules_count`**。实现：**`cai_agent.model_routing`**、**`resolve_effective_profile_for_llm`**。文档：**[`MODEL_ROUTING_RULES.zh-CN.md`](docs/MODEL_ROUTING_RULES.zh-CN.md)** / **[`MODEL_ROUTING_RULES.md`](docs/MODEL_ROUTING_RULES.md)**；契约索引 **`routing-test`** 行已扩成本字段说明；JSON Schema **`cai-agent/src/cai_agent/schemas/models_routing_test_v1.schema.json`**。
- **`security-scan --badge`**：追加 **`security_badge_v1`**（shields.io 兼容）JSON 行；**`message`/`color`** 反映命中数与严重度。
- **`memory user-model` 升级**：由 stub 升级为行为抽取（工具频次、错误率、近期 goal 预览）→ **`honcho_parity: behavior_extract`**。
- **`doctor` `.cai/` 健康**：**`build_doctor_cai_dir_health`** 将网关映射存在性与 **`hooks.json`** 合法性并入 JSON 与文本 **`doctor`** 输出。
- **插件机读兼容矩阵（`plugin_compat_matrix_v1`）**：**`cai-agent plugins --json --with-compat-matrix`** 在 **`plugins_surface_v1`** 顶层附加 **Cursor/Codex/OpenCode** 与各扩展目录能力对照；**`doctor --json`** 的 **`plugins`**（**`doctor_plugins_bundle_v1`**）含同源 **`compat_matrix`**。JSON Schema：**`cai-agent/src/cai_agent/schemas/plugin_compat_matrix_v1.schema.json`**；人读说明：**[`PLUGIN_COMPAT_MATRIX.zh-CN.md`](docs/PLUGIN_COMPAT_MATRIX.zh-CN.md)**、英文 **[`PLUGIN_COMPAT_MATRIX.md`](docs/PLUGIN_COMPAT_MATRIX.md)**；跨 harness 叙事：**[`CROSS_HARNESS_COMPATIBILITY.zh-CN.md`](docs/CROSS_HARNESS_COMPATIBILITY.zh-CN.md)** / **[`CROSS_HARNESS_COMPATIBILITY.md`](docs/CROSS_HARNESS_COMPATIBILITY.md)**。**`compat_matrix`** JSON 在中文 **`doc_anchor`/`detail_doc`** 外增加 **`doc_anchor_en`/`detail_doc_en`**。
- **技能自动建议钩子**：设置 **`CAI_SKILLS_AUTO_SUGGEST=1`** 时在 **`session_end`** 自动 **`build_skill_evolution_suggest`** 并 dry-run 落盘 **`skills/_evolution_*.md`**。
- **文档**：新增 **`docs/ONBOARDING.zh-CN.md`**；**`docs/TOOLS_REGISTRY.zh-CN.md`**（13 工具；见上文「工具注册表文档生成」）。
- **测试**：**`test_memory_validate_entries_cli.py`**、**`test_hook_runtime.py`**（script hook）；**`test_plan_sessions_cli.py`** / **`test_cli_workflow.py`** / **`test_gateway_telegram_execute_goal.py`** / **`test_session_observe.py`** / **`test_stats_json.py`** / **`test_cli_board_and_workflow_snapshot.py`** 等随 schema 版本升级同步，并补齐 workflow 后置 gate 覆盖；**`test_memory_entry_validate.py`** / **`test_memory_state_machine_cli.py`** / **`test_memory_import_entries_cli.py`**（**`entries.jsonl`** 写入门禁）；**`test_skills_auto_extract_hub_serve.py`**（LLM 草稿路径）；**`test_tools_fetch_url.py`**（**`max_redirects`** / 环境变量钳制 / 解析后 SSRF 与 **`allow_private_resolved_ips`**）；**`test_tools_registry_doc_sync.py`**（注册表与 **`DISPATCH_TOOL_NAMES`**）；**`test_tui_task_board_render.py`**（**`/tasks`** markup）；**`test_plugin_compat_matrix.py`**；**`test_doctor_cli.py`**（**`doctor` → `plugins.compat_matrix`**）；**`test_model_routing.py`** + **`test_llm_factory_dispatch.py`**（**`[models.routing]`** 覆盖）；**`test_ops_http_server.py`**；**`test_ops_dashboard_html.py`**（HTML 定时刷新）；**`test_memory_user_model_export.py`**。

### 0.6.18（2026-04-23）

- **多平台网关 / 技能自进化 / 记忆（MVP 切片）**：**`gateway platforms list --json`** 增补 **`telegram_webhook_pid_exists`**、**`telegram_bot_token_env_present`** 及各 stub 平台 **`env_present`**（仅布尔，不落密钥）。新增 **`skills hub suggest`** → **`skills_evolution_suggest_v1`**（可选 **`--write`** 写入 **`skills/_evolution_*.md`** 草稿，已存在则跳过）。新增 **`memory user-model --json`** → **`memory_user_model_v1`**（会话 mtime 窗口 + 可选 **`.cai/user-model.json`**；**`honcho_parity: stub`**）。**`CAI_METRICS_JSONL`**：**`skills.evolution_suggest`**、**`memory.user_model`**。**`smoke_new_features`** 已抽样。
- **测试**：**`test_gateway_user_model_skills_evolution.py`**、**`test_metrics_jsonl`** 增补。

### 0.6.17（2026-04-23）

- **可观测性（Hermes S7-01 AC2 扩展）**：**`CAI_METRICS_JSONL`** 追加 **`init.apply`**、**`models.*`**（按子命令，如 **`models.list`/`models.fetch`** 等）、**`workflow.run`**（含 **`run_workflow` 异常**）、**`release_ga.gate`**、**`ui.tui`**。**`docs/schema/METRICS_JSON.zh-CN.md`** 与索引已同步。
- **测试**：**`test_metrics_jsonl.py`** 覆盖上述路径。

### 0.6.16（2026-04-23）

- **可观测性（Hermes S7-01 AC2 扩展）**：**`CAI_METRICS_JSONL`** 追加 **`sessions.list`**、**`stats.summary`**、**`insights.summary`/`insights.cross_domain`**、**`plugins.surface`**、**`skills.hub_manifest`**、**`commands.list`**、**`agents.list`**、**`doctor.run`**、**`plan.generate`**、**`cost.budget`**、**`export.target`**、**`observe.report`**（独立子命令 **`observe-report`**）、**`ops.dashboard`**、**`board.summary`**、**`hooks.list`**。**`docs/schema/METRICS_JSON.zh-CN.md`** 已同步。
- **测试**：**`test_metrics_jsonl.py`** 覆盖上述路径。

### 0.6.15（2026-04-23）

- **可观测性（Hermes S7-01 AC2 扩展）**：**`CAI_METRICS_JSONL`** 追加 **`mcp.check`**、**`hooks.run_event`**、**`gateway.telegram.serve_webhook`**（**`gateway telegram serve-webhook`** 正常结束一轮后）。**`docs/schema/METRICS_JSON.zh-CN.md`** 已同步。
- **测试**：**`test_metrics_jsonl.py`** 覆盖上述路径。

### 0.6.14（2026-04-23）

- **可观测性（Hermes S7-01 AC2 扩展）**：**`CAI_METRICS_JSONL`** 追加 **`memory.extract`/`list`/`instincts`/`search`/`prune`/`export`/`import`/`export_entries`/`import_entries`**、**`quality_gate.run`**、**`security_scan.run`**、**`gateway.telegram.resolve_update`**、**`schedule.add_memory_nudge`**。**`docs/schema/METRICS_JSON.zh-CN.md`** 已同步。
- **测试**：**`test_metrics_jsonl.py`** 覆盖上述路径。

### 0.6.13（2026-04-23）

- **可观测性（Hermes S7-01 AC2 扩展）**：**`CAI_METRICS_JSONL`** 追加 **`command.invoke` / `agent.invoke` / `fix-build.invoke`**（与 **`run.invoke`** 同形）、**`memory.state` / `memory.nudge` / `memory.nudge_report`**、**`recall_index.benchmark` / `info` / `clear` / `doctor`**、**`schedule.rm` / `schedule.run_due` / `schedule.daemon`**、**`gateway.telegram`** 的 **`bind` / `get` / `unbind` / `continue_hint` / `allow_add` / `allow_list` / `allow_rm`**。**`docs/schema/METRICS_JSON.zh-CN.md`** 已同步。
- **测试**：**`test_metrics_jsonl.py`** 覆盖上述路径。

### 0.6.12（2026-04-23）

- **可观测性（Hermes S7-01 AC2 扩展）**：设置 **`CAI_METRICS_JSONL`** 时，**`_maybe_metrics_cli`** 追加 **`recall_index.build`/`refresh`/`search`**、**`schedule.list`**、**`schedule.add`**、**`gateway.telegram.list`**、**`run.invoke`** / **`continue.invoke`**（**`latency_ms`**、**`tokens`**、**`run`/`continue`** 的 **`success`**）。**`docs/schema/METRICS_JSON.zh-CN.md`** 与契约索引已同步。
- **测试**：**`test_metrics_jsonl.py`** 覆盖上述路径。

### 0.6.11（2026-04-23）

- **可观测性（Hermes S7-01 AC2 扩展）**：设置 **`CAI_METRICS_JSONL`** 时，**`_maybe_metrics_cli`** 追加 **`memory.health`**、**`recall.query`**、**`schedule.stats`**、**`gateway.status`**（**`latency_ms`** + **`tokens`** 粗提示）。**`docs/schema/METRICS_JSON.zh-CN.md`** 与契约索引已同步。
- **测试**：**`test_metrics_jsonl.py`** 覆盖上述四条路径。

### 0.6.10（2026-04-23）

- **GA 压测门禁（Hermes S8-02）**：**[`scripts/perf_ga_gate.py`](scripts/perf_ga_gate.py)** 复用 **`perf_recall_bench`** 逻辑校验 **200** 会话 **scan/index_search** 阈值；可选 **`--pytest-daemon`**。**`tests/test_perf_ga_s8_02.py`**（**PERF-GA-001/002/003**）。**AC3**（gateway **500** 条）仍为 **真机/专项**。
- **GA 安全门禁（Hermes S8-03）**：**[`scripts/security_ga_gate.py`](scripts/security_ga_gate.py)** + **`tests/test_sec_ga_s8_03.py`**；**SEC-GA-004** 见 **`test_gateway_telegram_cli`**。

### 0.6.9（2026-04-23）

- **文档（Hermes S8-04）**：新增 **[`docs/MIGRATION_GUIDE.md`](docs/MIGRATION_GUIDE.md)**（**0.5.x → 0.6.x**：JSON 信封、exit 码、调度审计、recall）。**`README.md` / `README.zh-CN.md`**：版本要求 + 迁移指南入口。**`CHANGELOG.md` / `CHANGELOG.zh-CN.md`** 在 **§0.6.0** 增加 **破坏性变更**、**新 CLI（0.6.x 系列）**、**废弃说明** 小节以满足 GA 文档门禁。
- **测试**：**`test_migration_guide_present.py`** 在 monorepo 布局下守护迁移文档存在与关键锚点。

### 0.6.8（2026-04-23）

- **可观测性（Hermes S7-04）**：**`cai-agent observe export`**（**`--days`**、**`--format` csv|json|markdown**、**`-o`**）→ **`observe_export_v1`**，**`rows`** 为按 UTC 日一行（会话数、成功率、token、**调度** ok/fail、**记忆健康** 分/档）。**`cai_agent.observe_export`**；**`smoke_new_features`** 在同目录写 **`observe-export.json`** 抽样。
- **测试**：**`test_observe_export_cli.py`**。

### 0.6.7（2026-04-23）

- **可观测性（Hermes S7-03）**：**`cai-agent insights --json --cross-domain`** → **`insights_cross_domain_v1`**，含 **`recall_hit_rate_trend`**（**`.cai-recall-index.json`** 子串探测 **`the`** / 无索引 **`index_missing`**）、**`memory_health_trend`**（按日 **`build_memory_health_payload`**，会话 **mtime** 窗）、**`schedule_success_trend`**（**`aggregate_schedule_audit_by_calendar_day_utc`**）。**`build_memory_health_payload`** 增加可选 **`reference_now` / `session_mtime_start` / `session_mtime_end_exclusive`**。**`smoke_new_features`** 已抽样。
- **测试**：**`test_insights_cross_domain.py`**。

### 0.6.6（2026-04-23）

- **可观测性（Hermes S7-01 / S7-02）**：**`cai_agent.metrics`**（**`metrics_schema_v1`**），若设置 **`CAI_METRICS_JSONL`** 则在 **`observe`** / **`observe report`** 成功后追加一行 JSONL。**`cai-agent observe report`**（**`--days`**、**`--format` json|markdown**、**`-o`**）生成 **`observe_ops_report_v1`**（顶层 **`schema_version`=`1.0`**）。**`build_observe_payload`** 支持时间窗过滤，**`aggregates`** 含 **`tool_errors_total` / `tool_errors_top`**。
- **文档 / 冒烟 / 测试**：**`docs/schema/METRICS_JSON.zh-CN.md`**；契约索引与 **`smoke_new_features.py`** 抽样 **`observe report`**；**`test_observe_ops_report_cli.py`**、**`test_metrics_jsonl.py`**。

### 0.6.5（2026-04-23）

- **Gateway（Hermes S6-04）**：**`cai-agent gateway telegram continue-hint`**（**`--json`** → **`gateway_telegram_continue_hint_v1`**），输出 **`continue_cli`**（**`shlex.quote`** 路径）与 **`session_path_resolved`**；**`--chat-id`+`--user-id`** 成对筛选或两者皆省略列出全部。Slash **`/help`**、**`/new`** 文案指向该命令。**`docs/qa/sprint6-gateway-telegram-testplan.md`** 增补 **GTW-CONT-001~003**。
- **测试与冒烟**：**`test_gateway_telegram_cli.py`**；**`smoke_new_features.py`** 抽样 **`continue-hint --json`**。

### 0.6.4（2026-04-23）

- **Gateway（Hermes S6-02）**：**`serve-webhook --execute-on-update`** 改为 **`_execute_gateway_telegram_goal`**：对绑定 **`session_file`** 与 CLI **`run`/`continue`** 同源（加载历史、追加用户 goal、**`invoke`** 后写回同一路径；文件不存在则首次执行后创建）。**`reply_template`** 的 **`{answer}`** 为完整答案（发送层仍 **`_telegram_send_text_chunked`**）。Slash **`/stop`**：默认提示本机执行 **`cai-agent gateway stop`**；仅当 **`CAI_TELEGRAM_STOP_WEBHOOK=1`** 且发令用户的 Telegram **`user_id`** 属于 **`CAI_TELEGRAM_ADMIN_USER_IDS`**（逗号分隔）时，才调用 **`gateway_lifecycle.stop_webhook_subprocess`**。**`/help`** 同步说明。
- **测试**：**`tests/test_gateway_telegram_execute_goal.py`**。

### 0.6.3（2026-04-23）

- **Gateway 生命周期（Hermes S6-01）**：**`cai-agent gateway setup|start|status|stop`**，实现于 **`cai_agent.gateway_lifecycle`**（**`gateway_telegram_config_v1`** 写入 **`.cai/gateway/telegram-config.json`**，PID **`.cai/gateway/telegram-webhook.pid`**）。**`setup`** 与 **`serve-webhook`** 开关/模板对齐，**`--allow-chat-id`** 可重复合并 **`allowed_chat_ids`**。**`start`** 后台拉起 **`gateway telegram serve-webhook`**（日志在 **`.cai/gateway/`**）。**`telegram`**、**`platforms`** 与生命周期子命令支持 **`-w`/`--workspace`** 指定工作区根。
- **Gateway（Hermes S6-02 部分）**：Webhook 拒绝与执行回发使用 **`_telegram_send_text_chunked`**（约 3900 字分块）。以 **`/`** 开头的首 token 走 slash 回复（**`/ping`**、**`/status`**、**`/help`**、**`/start`**、**`/new`** 等），**不**再进入 **`_execute_scheduled_goal`**。
- **测试与冒烟**：**`tests/test_gateway_lifecycle_cli.py`**；**`scripts/smoke_new_features.py`** 校验 **`gateway status --json`**（**`gateway_lifecycle_status_v1`**）。

### 0.6.2（2026-04-23）

- **Gateway（Hermes S6-03）**：映射 JSON 根级可选 **`allowed_chat_ids`**（**`gateway_telegram_map_v1`**）。**`gateway telegram allow add|list|rm`**。**`resolve-update`** / **`serve-webhook`** 在非空白名单且 **`chat_id`** 未命中时返回 **`error`=`not_allowed`**。**`list --json`** 增加 **`allowed_chat_ids`**、**`allowlist_enabled`**。**`serve-webhook`**：补齐此前缺失参数（**`--reply-on-execution`**、**`--telegram-bot-token`** / 环境变量 **`CAI_TELEGRAM_BOT_TOKEN`**、**`--reply-template`**），并新增 **`--reply-on-deny`** / **`--deny-message`**。
- **测试与冒烟**：**`test_gateway_telegram_cli.py`** 白名单用例；冒烟校验 **`list`** 白名单字段。

### 0.6.1（2026-04-23）

- **Gateway（开发项 24 MVP）**：**`cai-agent gateway platforms list --json`** → **`gateway_platforms_v1`**（Telegram **`full`**，Discord/Slack **`stub`**，其余 **`planned`**）。
- **Skills Hub（开发项 25 MVP）**：**`cai-agent skills hub manifest --json`** → **`skills_hub_manifest_v1`**（工作区 **`skills/`** 可分发清单）。**技能自进化 / 自动生成** 仍为后续范围。
- **运营面板（开发项 26 MVP）**：**`cai-agent ops dashboard --json`** → **`ops_dashboard_v1`**（嵌套 **`board_v1`**、**`schedule_stats_v1`**、**`cost_aggregate`** 与顶层 **`summary`**）。**Web 运营 UI** 仍为后续。
- **测试与冒烟**：**`cai-agent/tests/test_ops_gateway_skills_cli.py`**；**`scripts/smoke_new_features.py`** 覆盖上述三条 JSON 路径。

### 0.6.0（2026-04-23）

#### 破坏性变更（自 0.5.x 升级）

- **带版本号的 `--json` stdout**：多数命令不再输出「裸 JSON 数组/字符串」；每条 stdout 含 **`schema_version`** 与稳定根字段（如 **`sessions_list_v1.sessions`**、**`schedule_list_v1.jobs`**）。详见 **[`docs/schema/README.zh-CN.md`](docs/schema/README.zh-CN.md)** 与 **[`docs/MIGRATION_GUIDE.md`](docs/MIGRATION_GUIDE.md)**。
- **Exit 码**：**`init`** 失败路径、**`models ping`** 非 OK、CLI 分发兜底等，若干场景由 **exit `1`** 调整为 **exit `2`**（见 schema README **S1-03**）。
- **`models fetch --json`**：包装为 **`{"schema_version":"models_fetch_v1","models":[…]}`**（非裸数组）。

#### 新 CLI（0.6.x 系列概要）

- **0.6.0 本版**：Workflow **`on_error` / `budget_max_tokens`**；调度 **stats / 审计 schema / 重试 / 并发 / `depends_on` 环检测**；recall **排序 / `no_hit_reason` / doctor`**；**memory health / nudge / nudge-report**；**sessions、commands、agents、schedule、cost budget、export、plugins** 等与 memory list/search 的 JSON 契约（详见下列条目）。
- **0.6.1–0.6.5**：**`gateway platforms`**、**`skills hub manifest`**、**`ops dashboard`**、Telegram **生命周期 / 白名单 / execute-on-update / continue-hint**。
- **0.6.6–0.6.8**：**`CAI_METRICS_JSONL`**、**`observe report`**、**`insights --json --cross-domain`**、**`observe export`**。

#### 废弃说明

- **0.6.0** 无「移除且无替代」的 CLI 旗标；**`models ping --fail-on-any-error`** 保留为与默认行为一致的**无操作别名**（与 **exit `2`** 语义一致）。

- **Workflow（Hermes S5-03）**：JSON 根级 **`on_error`**：**`fail_fast`**（默认）或 **`continue_on_error`**（别名 **`continue-on-error`**）。`fail_fast` 时后续未跑步骤 **`skipped`**（**`fail_fast_prior_batch`**）并产生 **`workflow.step.skipped`**；`continue_on_error` 时 merge/conflict 仅统计成功完成步骤。`summary` 增加 **`on_error`**、**`steps_skipped`**、**`merge_steps_considered`**。
- **Workflow（Hermes S5-04）**：根级可选 **`budget_max_tokens`**；已执行步骤 **`total_tokens`** 在下一批前与预算比较，未启动步骤 **`skipped`/`budget_exceeded`**。`summary` 与 **`workflow.finished`** 含 **`budget_limit`/`budget_used`/`budget_exceeded`**；**`task.error`** 可为 **`workflow_budget_exceeded`**；已提交的并行批仍跑完。
- **Workflow 任务状态**：通过 **`skip_reason=fail_fast_prior_batch`** 识别 fail-fast 中止，避免与预算跳过混淆。
- **冒烟与文档**：**`smoke_new_features.py`** 断言 **`workflow --json`** 的 **`summary.on_error`** 与 **`budget_*`**；**`PRODUCT_PLAN.zh-CN.md`** §3.0 写明 **>20%** 同步基线与 QA；**`QA_SKIP_LOG=1`** 跑 **`run_regression.py`** 可不写 **`docs/qa/runs/*.md`**。Schema / Parity / Sprint5 测试计划文档已同步 S5-03/S5-04。

### 0.5.0 – 0.5.7（累积条目见下）

- **文档**：[`docs/PRODUCT_PLAN.zh-CN.md`](docs/PRODUCT_PLAN.zh-CN.md) **§三之二**（开发项 1–26 状态计数、**未开发项 21–26**、**QA 清单**）及 **§三之二 · 3.0 同步完成度（百分比）**（§二加权、Hermes 34 Story、T1）；[`docs/schema/README.zh-CN.md`](docs/schema/README.zh-CN.md) 增加 **`gateway telegram` / `gateway_telegram_map_v1`**、**`schedule stats` / `schedule_stats_v1`**（S1-02，与 [`SCHEDULE_STATS_JSON.zh-CN.md`](docs/schema/SCHEDULE_STATS_JSON.zh-CN.md) 互链）；归档后的 [`HERMES_PARITY_PROGRESS.zh-CN.md`](docs/archive/legacy/HERMES_PARITY_PROGRESS.zh-CN.md)、[`DEVELOPMENT_PROGRESS_TRACKER.zh-CN.md`](docs/archive/legacy/DEVELOPMENT_PROGRESS_TRACKER.zh-CN.md) 与上述口径交叉引用。
- **CLI `init --json`**：stdout **单行 `init_cli_v1`**（成功时 **`ok`**、**`config_path`**、**`preset`**、**`global`**；失败时 **`error`**（`config_exists` / `template_read_failed` / `mkdir_failed`）及 **`message`** 等）。无 **`--json`** 时仍为原有文本输出。见 **`docs/schema/README.zh-CN.md`**。
- **CLI `init` exit（S1-03）**：**`config_exists`**（无 **`--force`**）、**`template_read_failed`**、**`mkdir_failed`** 等失败路径 **exit `2`**（此前为 **`1`**）；JSON 仍为 **`init_cli_v1`**（**`ok: false`** + **`error`**）。破坏性说明见 **`docs/schema/README.zh-CN.md`**「破坏性变更」。
- **CLI `main()` 分发兜底（S1-03）**：若 **`args.command`** 未被任何分支处理（内部不同步），进程 **exit `2`** 且 stderr 一行诊断（此前 **exit `1`** 且无输出）。见 **`docs/schema/README.zh-CN.md`**。
- **CLI `memory export --json` / `memory export-entries --json`**：可选 JSON stdout **`memory_instincts_export_v1`**（**`output_file`**、**`snapshots_exported`**）与 **`memory_entries_export_result_v1`**（**`output_file`**、**`entries_count`**、**`export_warnings`**）；默认仍仅打印输出路径。见 **`docs/schema/README.zh-CN.md`**。
- **CLI `models ping` exit（S1-03）**：任一 **`status`≠`OK`** 时 **默认 exit `2`**（此前为 **`1`**）；**`--fail-on-any-error`** 保留为与默认一致的显式别名（兼容旧脚本）。破坏性说明见 **`docs/schema/README.zh-CN.md`**。
- **CLI `memory import` / `memory import-entries` stdout**：**`memory_instincts_import_v1`**（**`imported`**）、**`memory_entries_import_result_v1`**（**`imported`**）；**`memory import-entries --dry-run`** 为 **`memory_entries_import_dry_run_v1`**（在原有 `validated` / `errors` 等字段上增加 **`schema_version`**）。见 **`docs/schema/README.zh-CN.md`**。
- **CLI `memory list`/`search`/`instincts --json` 与 `memory extract` stdout**：**`memory_list_v1`**（**`entries`**、`limit`、`sort`）、**`memory_search_v1`**（**`hits`**、`query`、`limit`、`sort`）、**`memory_instincts_list_v1`**（**`paths`**、`limit`）、**`memory_extract_v1`**（**`written`**、**`entries_appended`**）。**`list`/`search`/`instincts` 的 `--json` 为破坏性变更**（此前根节点为裸数组）。见 **`docs/schema/README.zh-CN.md`**。
- **单测（空工作区）**：新增 **`test_sessions_list_json_empty_directory`**（**`sessions_list_v1`**）、**`test_observe_report_json_empty_workspace_state_pass`**（**`observe_report_v1`** / **`state=pass`**）、**`test_memory_state_json_empty_workspace`**（**`memory_state_eval_v1`**）。
- **CLI `insights --json`**：**`_build_insights_payload`** 在**时间窗口内无会话文件**时**立即返回**（**`schema_version`=`1.1`** 形状与零次循环一致，**`sessions_in_window`=`0`**，**`models_top`/`tools_top`** 为空），避免无意义的后续处理；**`test_insights_json_empty_workspace_fast_path`** 与 **`scripts/smoke_new_features.py`** 覆盖。
- **`scripts/smoke_new_features.py`**：在仓库根校验 **`mcp-check --json --list-only`**（**`mcp_check_result_v1`**，exit **0/2**）、**`plugins`/`doctor` --json**；在空临时目录校验 **`sessions`/`observe-report`/`insights`/`board` --json**；在隔离目录校验 **`hooks list` + `run-event --dry-run --json`**；在空工作区校验 **`memory health`/`memory state` --json**；并校验 **`init`/`schedule`/`gateway telegram`/`recall`/`memory …`** 等；入口为 **`python -m cai_agent`** + **`PYTHONPATH=cai-agent/src`**（与 **`run_regression.py`** 一致）。
- **CLI `schedule add`/`list`/`rm`/`add-memory-nudge --json`**：成功 **`schedule_add_v1`**；**`list`** 为 **`schedule_list_v1` + `jobs[]`**（**破坏性变更**：此前 `list` 根为数组）；**`rm`** 为 **`schedule_rm_v1`**；**`add-memory-nudge`** 为 **`schedule_add_memory_nudge_v1`**；**`add` 校验失败** 为 **`schedule_add_invalid_v1`**。见 **`docs/schema/README.zh-CN.md`**。
- **CLI `schedule run-due --json` / `schedule daemon --json`**：stdout 根对象增加 **`schema_version`：`schedule_run_due_v1`** / **`schedule_daemon_summary_v1`**（daemon 锁冲突负载亦含同一 schema）；详见 **`docs/schema/README.zh-CN.md`**。
- **CLI `cost budget`**：stdout 单行 JSON 增加 **`schema_version`：`cost_budget_v1`**（字段仍为 `state` / `total_tokens` / `max_tokens`；无 `--json` 开关）。契约见 **`docs/schema/README.zh-CN.md`**。
- **CLI `sessions --json`**：输出改为 **`sessions_list_v1`** 对象（含 **`pattern`/`limit`/`details`/`sessions`**）；**破坏性变更**（此前根节点为数组）。见 **`docs/schema/README.zh-CN.md`**。
- **CLI `commands --json` / `agents --json`**：输出改为对象 **`commands_list_v1`**（字段 **`commands`**）与 **`agents_list_v1`**（字段 **`agents`**）；**破坏性变更**（此前为裸字符串数组）。见 **`docs/schema/README.zh-CN.md`**。
- **CLI `export`**：单行 JSON 增加 **`schema_version`：`export_cli_v1`**（`export_target` 各 `--target` 分支）。
- **CLI `plugins --json`**：负载增加 **`schema_version`：`plugins_surface_v1`**（与既有 **`plugin_version`** 并存；`cai_agent.plugin_registry.list_plugin_surface`）。
- **CLI `models fetch --json` 契约**：输出固定为 **`{"schema_version":"models_fetch_v1","models":[…]}`**（**破坏性变更**：此前为裸字符串数组；自动化脚本请改为读取 **`models`** 字段）。说明见 **`docs/schema/README.zh-CN.md`**。
- **Schedule stats SLA 聚合（Hermes S4-05）**：新增 **`cai-agent schedule stats`**，支持 **`--json`**、**`--days`**（默认 30，最大 366）、**`--audit-file`**。JSON **`schema_version=schedule_stats_v1`**，**`tasks`** 每项含 **`success_rate`**、**`avg_elapsed_ms`**、**`p95_elapsed_ms`**、**`run_count`**、**`fail_count`** 等，数据源为 **`.cai-schedule-audit.jsonl`** 中的 **`task.completed` / `task.failed` / `task.retrying`**（无 `event` 的旧行会推导后统计）。说明见 **`docs/schema/SCHEDULE_STATS_JSON.zh-CN.md`**。
- **Schedule 审计 JSONL 统一 schema（Hermes S4-04）**：`.cai-schedule-audit.jsonl` 与 **`schedule daemon --jsonl-log`** 每行统一为 **`schema_version=1.0`**、**`event`**（`task.started` / `task.completed` / `task.failed` / `task.retrying` / `task.skipped` / `daemon.cycle` / `daemon.started`）及 **`task_id`**、**`goal_preview`**、**`elapsed_ms`**、**`error`**、**`status`**、**`action`**、**`details`**。`schedule run-due --execute` 在执行前追加 **`task.started`**。字段说明见 **`docs/schema/SCHEDULE_AUDIT_JSONL.zh-CN.md`**。
- **Schedule 依赖环检测与 list 依赖视图（Hermes S4-03）**：`add_schedule_task` 在落盘前检测 **`depends_on` 有向环**（含自依赖），拒绝写入。`schedule add` 失败时 **exit 2**，`--json` 输出 **`schedule_add_invalid`**。`schedule list` 增加 **`depends_on_status`**、**`dependency_blocked`**、**`dependents`**、**`depends_on_chain`**（仅 JSON 展示，不写回 `.cai-schedule.json`）；文本模式增加 **`deps` / `dep_blocked` / `dependents` / `dep_chain`** 列。
- **Schedule daemon 并发上限（Hermes S4-02）**：`cai-agent schedule daemon` 新增 **`--max-concurrent`**（默认 **1**，**0** 视为 **1**）。每轮最多执行 N 个到点任务，其余本跳过、下轮再判；在 **`.cai-schedule-audit.jsonl`** 与可选 **`--jsonl-log`** 中写入 **`skipped_due_to_concurrency`** 事件。汇总 JSON 含 `max_concurrent`、`total_skipped_due_to_concurrency` 及每轮 `skipped_due_to_concurrency` / `skipped_due_to_concurrency_count`。
- **Schedule 跨轮次失败重试（Hermes S4-01）**：`.cai-schedule.json` 任务持久化 **`max_retries`**（默认 3，CLI **`schedule add --max-retries`**）、**`retry_count`**、**`next_retry_at`**。`run-due --execute` / `daemon --execute` 失败后 **`last_status=retrying`**，按 **`60 * 2^(retry_count-1)`** 秒退避再入队，用尽后为 **`failed_exhausted`**；成功则清零重试计数。`compute_due_tasks` 对 `retrying` 仅在 **`now >= next_retry_at`**（或缺失时间戳）时视为到期。执行 JSON 与 `.cai-schedule-audit.jsonl` 的失败行与上述持久化字段对齐。单次执行内连跑仍由 **`--retry-max-attempts` / `--retry-backoff-sec`** 控制。
- **Recall 排序策略（Hermes S3-01）**：`cai-agent recall --json` 与 `recall-index search|benchmark` 支持 **`--sort recent|density|combined`**（默认 `recent`）。包含 `sort` 与 `ranking` 说明；关键词密度评分基于**完整命中消息正文**（而非仅 snippet），排序更稳定。
- **Recall 无命中解释（Hermes S3-02）**：0 命中时 JSON 增加 **`no_hit_reason`**（`window_too_narrow` / `pattern_no_match` / `index_empty` / `all_skipped`），`schema_version` 为 **`1.3`**；非 JSON 模式追加一行可读提示。索引检索的密度分使用索引 `content` 全文。
- **Recall 索引体检（Hermes S3-03）**：新增 **`cai-agent recall-index doctor [--fix] [--json]`**，`schema_version=recall_index_doctor_v1`，输出 `is_healthy`、`issues`、`stale_paths`、`missing_files`、`schema_version_ok`；`--fix` 剔除缺失/相对索引窗口过旧/无效条目后写回并重检；健康 **exit 0**，有问题 **exit 2**（含索引文件不存在、JSON 损坏）。
- **Recall 性能基准（Hermes S3-04）**：新增 **`scripts/perf_recall_bench.py`**，在临时目录生成合成会话并输出 Markdown 表：**scan / index_build / index_search** 中位耗时（毫秒）；可选 **`--include-refresh`** 测量无改动下的 `refresh`；默认报告写入 **`docs/qa/runs/`**；200 条规模在表中标注与参考阈值对比列。
- **Memory health（Hermes Sprint 2）**：新增 `cai-agent memory health --json`（`schema_version=1.0`），输出综合 `health_score` / `grade`（A~D）及 `freshness`、`coverage`、`conflict_rate`，并附带冲突与覆盖的可观测子字段（如 `conflict_pair_count`、`conflict_compared_entries`、`sessions_considered_for_coverage` 等）。支持 `--days`、`--freshness-days`、`--session-pattern`、`--session-limit`、`--conflict-threshold`、`--max-conflict-compare-entries`、`--fail-on-grade`（门禁不通过时 exit 2）。
- **Memory Nudge 历史报告**：新增 `cai-agent memory nudge-report`，从 `memory/nudge-history.jsonl`（或 `--history-file`）聚合历史快照并输出趋势统计（`schema_version=1.2`、`severity_counts`、`severity_trend`、`latest_severity`、`severity_jumps`、`avg_recent_sessions`、`avg_memory_entries`，以及与 `memory health` 同源的 `health_score` / `health_grade` / `freshness`）。支持 `--days`（时间窗口过滤）、`--freshness-days`、`--limit` 与 `--json`，可用于 QA/运维观察记忆健康变化。`memory nudge --write-file` 会同步把同一条 JSON 追加到默认历史文件（可用 `--history-file` 覆盖；若与 `--write-file` 同路径则只写一次）。
- **Schedule Memory Nudge 模板任务**：新增 `cai-agent schedule add-memory-nudge`，一条命令生成标准化巡检任务（自动拼接 `memory nudge --json --write-file ... --fail-on-severity ...` 目标），支持 `--every-minutes`、`--output-file`、`--fail-on-severity`、`--disabled`、`--workspace`、`--model`，减少手工配置成本并提升可复用性。

- **跨会话检索 `recall`（Hermes `/insights` 衍生能力）**：新增 `cai-agent recall <query>`，支持跨会话内容检索并返回命中片段。支持 `--days`（时间窗口）、`--limit`（返回条数）、`--regex`（正则模式）与 `--json`（结构化输出）；默认按最近会话优先。命中结果包含会话路径、文件时间、`task_id`、命中行号与片段预览，无法解析的会话会统计到 `parse_skipped` 且不中断执行。

- **`recall-index` 增量刷新**：新增 `cai-agent recall-index refresh`，在已有 `.cai-recall-index.json`（schema `1.1`）上合并更新：**mtime 未变则跳过 JSON 解析**；未出现在本轮扫描窗口内的旧条目仍保留；`--prune` 可剔除磁盘已不存在或超出 `--days` 窗口的路径。`recall-index build` 仍为全量重建。`recall --use-index` 与 `recall-index` 统一使用 `--index-path` 指定索引文件。

- **schedule daemon 生产护栏（防重 + 日志）**：`cai-agent schedule daemon` 新增单实例锁（默认 `.cai-schedule-daemon.lock`，可用 `--lock-file` 自定义）防止同工作区重复启动；重复启动会安全返回并给出 `daemon_already_running`。新增 `--log-file` 将每轮 JSON 摘要追加到日志，便于 QA 与线上排障。命令参数统一为 `--max-cycles`（README 同步修正），并新增 `docs/qa/schedule-daemon-testplan.md` 作为手工验收清单。

- **schedule 真执行（MVP）**：`cai-agent schedule run-due --execute` 不再仅写元数据，现会对每个到点任务真实触发一次 Agent 运行（基于任务 `goal` 调用主循环），并把结果回写到 `.cai-schedule.json`（`last_run_at` / `last_status` / `last_error` / `run_count`）。返回 JSON 新增执行结果数组（含 `answer` 预览、`iteration`、`finished`）。同时兼容早期 `schedule` 数据：历史任务若缺 `enabled` 字段默认视为启用。

- **智谱（BigModel）OpenAI 兼容路由**：`profiles.PRESETS` 增加 **`zhipu`** 预设（`cai-agent models add --preset zhipu …`）；`normalize_openai_chat_base_url` / `project_base_url` 对 `https://open.bigmodel.cn/api/paas/v4` **不再追加 `/v1`**，与[智谱 OpenAI 兼容文档](https://docs.bigmodel.cn/cn/guide/develop/openai/introduction)一致。示例模板说明 **`ZAI_API_KEY`** 与 **`glm-5.1`**。
- **系统代理与本机 LLM**：`[llm].http_trust_env=true` 时，对 **环回地址**（`localhost`、`127.*`、`::1`）的 OpenAI 兼容 **chat**、**`GET …/models` / profile ping**、以及 **MCP** 的 httpx 客户端仍使用 **`trust_env=false` 直连**，避免企业代理错误转发本机 LM Studio/Ollama 导致 **HTTP 503**。
- **Sprint 3 — TUI 模型面板（M4）**：`Ctrl+M` / `/models` 打开面板；列表列为 `id | model | provider | base_url | notes | [active]`；`Enter` 切换、`t` 连通测试、`a`/`e`/`d` 新增/编辑/删除（写回 `cai-agent.toml`，与 CLI `models` 语义一致）；空列表时给出引导文案。详见 [MODEL_SWITCHER_DEVPLAN.zh-CN.md](docs/MODEL_SWITCHER_DEVPLAN.zh-CN.md) §4。
- **Sprint 3 — `/use-model` 与 provider 提示（M5）**：在 TUI 内切换 profile 若 **provider** 变化，聊天区追加简短提示，建议必要时执行 `/compact` 或 `/clear`，降低跨供应商上下文错位风险。
- **Sprint 3 — `/status` 与 session（M7）**：`/status` 增加 `profile:` 行（与 `profile(active):` 并存，便于与 QA 矩阵表述对齐）；TUI `/save` 与 `run --save-session` 落盘 JSON 增加 **`profile`**（当前 active profile id）及 **`active_profile_id` / `subagent_profile_id` / `planner_profile_id`**；加载会话时支持仅用 **`profile`** 恢复 active。
- **Sprint 3 — 文档与 Parity（M9）+ P1 定案**：`docs/PARITY_MATRIX.zh-CN.md` 增「多模型 profile + TUI」Done 行并链 devplan；新增 [WEBSEARCH_NOTEBOOK_MCP.zh-CN.md](docs/WEBSEARCH_NOTEBOOK_MCP.zh-CN.md)（WebSearch/Notebook **MCP 优先** 与任务看板 schema 说明）；`board --json` 顶层增加 **`observe_schema_version`**（与内嵌 `observe` 同源）。
- **本地多后端与网关一键配置**：新增 `cai-agent init --preset starter`，从内置 `cai-agent.starter.toml` 生成含 LM Studio / Ollama / vLLM / OpenRouter / **智谱 GLM** / 自建 OpenAI 兼容网关等多条 `[[models.profile]]` 的配置；`cai-agent models add --preset` 增加 **`vllm`**、**`gateway`**、**`zhipu`**（`profiles.PRESETS` 约定默认端口与 `VLLM_API_KEY`、`OPENAI_API_KEY`、`ZAI_API_KEY`）。README / README.zh-CN、`docs/ONBOARDING.zh-CN.md` 已补充说明；`doctor` 提示 `init --preset starter` 与新 preset。
- **移除 Cursor Cloud API 集成**：删除 `cai-agent cursor`、`cai_agent.cursor_cloud`、TOML `[cursor]` / 环境变量 `CURSOR_*` 的解析与 `Settings` 字段、TUI 的 **Ctrl+Shift+M** / **`/cursor-launch`**，以及 `doctor` 中的 Cursor 行。**`cai-agent export --target cursor` 保留不变**（仅向 `.cursor/cai-agent-export` 导出规则/技能等目录，与 Cloud Agents HTTP API 无关）。
- **TUI 支持文本选择与一键复制**：在 App 上显式设置 `ALLOW_SELECT=True`（即便 Textual 未来改默认值也不会回归），鼠标拖选聊天区可直接选中文字；新增键位 **`Ctrl+Shift+C`** 通过 `Screen.get_selected_text()` + `App.copy_to_clipboard()` 写入系统剪贴板（并弹出"已复制 N 个字符"提示；未选中时给出「用鼠标拖选或 `Ctrl+Shift+A` 全选」的引导）。**`Ctrl+Shift+A`** 调用 `RichLog.text_select_all()` 一键全选当前聊天区，便于整段拷走。`Ctrl+C` 依然是「停止任务」（终端惯例）。欢迎页与 `/help` 同步提示新快捷键；Windows Terminal 里按住 `Shift + 鼠标` 仍可走系统原生选择。
- **配置发现：用户级全局配置兜底**：`--config` / `CAI_CONFIG` / cwd 向上查找 / `CAI_WORKSPACE` / `-w` 都找不到时，`_resolve_config_file` 现在会再尝试一组**用户级全局路径**，让「从任何目录 `cai-agent ui` 都能读到你的配置」成立。顺序：`%APPDATA%\cai-agent\cai-agent.toml`（Windows）→ `$XDG_CONFIG_HOME/cai-agent/cai-agent.toml`（缺省 `~/.config/cai-agent/cai-agent.toml`）→ `~/.cai-agent.toml` → `~/cai-agent.toml`。`cai-agent init` 新增 **`--global`** 开关，按平台写入对应位置（自动创建父目录）。项目级 `cai-agent.toml` 仍优先于全局；`CAI_CONTEXT_WINDOW` 与 profile 级 `context_window` 仍优先于 `[llm].context_window`。欢迎页 `source=default` 的提示从原来的「请从含该文件的目录启动」改为 **四条具体可操作路径**：从含 TOML 的目录启动、`init --global`、设置 `CAI_CONFIG`、或启动时用 `--config` / `-w`。
- **配置发现：workspace_hint**：`Settings.from_env` / `from_sources` 新增 `workspace_hint` 形参，`__main__.py` 里所有带 `-w/--workspace` 的子命令都已串起；在 cwd 向上查找失败后，继续沿 `CAI_WORKSPACE` 与 `workspace_hint` 各自的父目录链查找，修正「`cd` 到别处 + `-w` 回项目根 + 仍读到 8192」的历史坑。
- **TUI 上下文进度条**：输入框上方新增一行 `ctx ███░░ prompt_tokens / context_window (pct%)`，< 70% 绿、70–89% 黄、≥ 90% 红。每次模型响应后自动取服务端 `prompt_tokens` 刷新；首次响应前用 **CJK 加权估算器**（中日韩字符按 ~1.5 chars/token，其它按 ~4 chars/token，避免中文场景低估 2–3 倍）并加 `~` 前缀与"估算"字样。可配置项：`[llm].context_window`（兜底）、`[[models.profile]].context_window`（优先）、环境变量 `CAI_CONTEXT_WINDOW`；默认 `8192`。`Settings` 新增 `context_window_source`（`profile|llm|env|default`），TUI 欢迎页 + `/status` 都会打印解析值与来源，一眼看出"为啥分母是 8k"。按 Enter 后即刻用估算器重算（不等服务端 round-trip）。新增 Python API：`cai_agent.llm.get_last_usage()` / `estimate_tokens_from_messages()`；`graph.llm_node` 每次 LLM 调用后发 `phase="usage"` 进度事件。
- **空输出兜底**（Qwen3 / DeepSeek-R1 / LM Studio reasoning 模型）：服务端返回 `content=""` 且把所有 token 塞进 `reasoning_content`（推理预算耗尽）时，OpenAI-compat 与 Anthropic 适配器会合成 `{"type":"finish","message":"[empty-completion] …"}` 带诊断信息的 envelope，而不是在 `extract_json_object("")` 崩溃或空转到 `max_iterations`。`<think>…</think>` 前缀也会被透明剥离。Anthropic 两个"空 content 抛异常"的老契约反转为返回 envelope —— 见 `test_llm_empty_content_guard.py`。
- **`plan --json` + 缺失配置**：`--config` 指向不存在文件时输出 JSON 错误体（`error: config_not_found`），不再仅 stderr。
- **`stats`（非 JSON）**：文本摘要增加 `run_events_total`、`sessions_with_events`、`parse_skipped` 一行。
- **钩子**：`observe_start` / `observe_end` 包裹 `observe`；`cost_budget_start` / `cost_budget_end` 包裹 `cost budget`；人类可读 `observe` 行末附带 `run_events_total`。
- **`stats --json`**：增加 `stats_schema_version`（`1.0`）、`run_events_total`、`sessions_with_events`、`parse_skipped` 与 `session_summaries`（逐文件的 `events_count` / `task_id` / token 与工具统计摘要）。
- **`plan --json` 错误路径**：`goal` 为空或 LLM 抛错时仍输出一行 JSON（`ok: false`，`error` 为 `goal_empty` 或 `llm_error`；失败时 `task.status=failed`）；成功体含 `ok: true`。
- **钩子**：`memory_start` / `memory_end` 包裹 `cai-agent memory`；`export_start` / `export_end` 包裹 `cai-agent export`；`export` 子命令增加 `-w` / `--workspace`。
- **`plan --json`**：稳定信封字段 `plan_schema_version`（`1.0`）、`generated_at`（UTC ISO）、`task`（`plan-*` 任务 id）及 `usage` 等。
- **`sessions --json`**：即使未加 `--details`，也会尝试解析会话文件并附带 `events_count`、`run_schema_version`、`task_id`、`total_tokens`、`error_count`；失败时标记 `parse_error`；`--details` 文本行增加 `events=`。
- **`security-scan` 钩子**：`security_scan_start` / `security_scan_end` 包裹 `cai-agent security-scan`（扫描抛错时仍会在退出前触发 `security_scan_end`）。
- **会话落盘**：`--save-session` 现写入 `run_schema_version`、`events`、工具统计（`tool_calls_count` / `used_tools` / `last_tool` / `error_count`）及适用的 `post_gate`，与 `run --json` 对齐。
- **observe**：每条会话摘要增加 `task_id`、`events_count`、`run_schema_version`；聚合增加 `run_events_total` 与 `sessions_with_events`。
- **workflow 钩子**：`cai-agent workflow` 前后触发 `workflow_start` / `workflow_end`（失败退出前仍会触发 `workflow_end`），行为与 `session_*` 钩子一致（非 JSON 模式下 stderr 列出已启用 hook id）。
- **quality-gate 钩子**：独立子命令 `cai-agent quality-gate` 前后触发 `quality_gate_start` / `quality_gate_end`；`quality-gate` 现与共用解析器一致，支持 `-w` / `--workspace`。
- **fetch_url**：在白名单校验前先拒绝常见 SSRF 主机名（如 `localhost`、GCP metadata 域名）。
- **fetch_url 工具**：可选 HTTPS GET，主机白名单、响应体上限与超时；由 `[fetch_url]` 与 `[permissions].fetch_url` 控制（默认关闭且权限为 `deny`）。示例见 `cai-agent/src/cai_agent/templates/cai-agent.example.toml`；纯 MCP 方案见 `docs/MCP_WEB_RECIPE.zh-CN.md`。
- **Run JSON 事件信封**：`run --json` / `continue --json`（及 `command` / `agent` / `fix-build` 共用路径）增加 `run_schema_version` 与 `events`（`run.started` / `run.finished`），与 `workflow` 的 `events` 风格对齐。
- **记忆条目校验**：写入 `memory/entries.jsonl` 前按 v1 形状校验；JSON Schema 见 `cai-agent/src/cai_agent/schemas/memory_entry_v1.schema.json`。
- **doctor**：启用 `fetch_url` 时打印白名单项数与权限模式。
- **QA 回归留痕**：`scripts/run_regression.py` 每次执行后在 `docs/qa/runs/` 生成带时间戳的 Markdown 报告（见 `docs/QA_REGRESSION_LOGGING.zh-CN.md`）；CI 工作流将该目录下的报告作为 artifact 上传。
- **变更记录拆分**：默认 `CHANGELOG.md` 改为英文；原中文全文迁至 `CHANGELOG.zh-CN.md`。
- **文档拆分**：默认 `README.md` 改为英文；原中文全文迁至 `README.zh-CN.md`，两文件顶部互相链接。
- **JSON 诊断补强**：`run --json` / `continue --json` 新增 `last_tool` 与 `error_count` 字段。
- **会话管理增强**：新增 `cai-agent sessions` 子命令；TUI 新增 `/sessions`，`/load latest` 可快速恢复最近会话。
- **会话详情增强**：`cai-agent sessions --details` 可查看每个会话的消息数、工具调用数、错误计数与回答预览。
- **会话匹配修复**：`sessions` 与 `/load latest` 默认匹配 `.cai-session*.json`，兼容 `.cai-session.json` 与自动命名文件。
- **Rules 扩充**：新增通用与 Python 规则文档，覆盖命名/结构、日志/错误、安全/敏感信息、Git/提交、文档/注释、性能/资源、上下文/记忆、MCP/外部工具、类型风格、测试/CI、依赖/打包、CLI/TUI、配置演进等主题。
- **Skills 扩充**：新增计划执行、单模块/多模块重构、新功能+测试、调试诊断、轻量安全扫描、性能评估、依赖升级、API 集成、规则维护、代码评审、发布前检查、workflow 编写、迁移规划等技能文档。
- **README 同步增强**：补充 `rules/` 与 `skills/` 目录现状说明，明确其已从目录骨架演进为可实际复用的内容库。
- **Rules 第二轮扩充**：新增 Hook 自动化、子代理协作、验证评估、research-first、prompt hygiene、Python 并发模型、HTTP 客户端与重试等规则主题。
- **Skills 第二轮扩充**：新增 search-first、TDD、verification loop、Hook 设计、子代理编排、记忆提炼、测试覆盖审计、安全加固、故障复盘、文档同步等技能文档。
- **README 再同步**：更新规则与技能覆盖范围描述，标注新增治理层主题与执行工作流能力。
- **运行层骨架新增**：新增 `commands/`（斜杠命令兼容层）、`agents/`（核心子代理定义）与 `hooks/`（自动化配置骨架与 session 生命周期建议）。
- **README 三次同步**：补充 `commands/agents/hooks` 目录说明，并更新「可复用内容库 → 运行层雏形」的项目定位描述。
- **Bug 修复（工具节点）**：修复 `graph` 工具节点对 `pending` 字段的直接索引风险，改为使用已校验的 `name/args`，降低异常路径下的 KeyError 风险。
- **CLI 新增命令模板能力**：新增 `cai-agent commands` 与 `cai-agent command <name> <goal...>`，可读取仓库 `commands/*.md` 作为执行指令模板。
- **Hook 运行时接入**：新增 `hook_runtime`，在 `run/continue/command` 会话开始与结束时读取 `hooks/hooks.json` 并输出已启用 hook 标识（非 JSON 模式）。
- **README 四次同步**：更新用法示例，补充 `commands`/`command` 命令及 hook 运行时行为说明。
- **Bug 修复（command 会话保存）**：修复 `command` 子命令缺少 `save_session` 属性导致的潜在运行时异常，补齐参数并改为安全读取。
- **CLI 新增子代理执行能力**：新增 `cai-agent agents` 与 `cai-agent agent <name> <goal...>`，可读取 `agents/*.md` 作为角色模板执行任务。
- **自动技能注入**：`cai-agent command` / `cai-agent agent` 会自动匹配 `skills/*.md` 的相关内容并注入执行提示（同名或前缀匹配）。
- **README 五次同步**：补充 `agents` / `agent` 用法示例与「命令/角色 + 技能」组合执行说明。

### 0.4.1

- **TUI 保存优化**：`/save` 支持省略路径，默认生成 `.cai-session-YYYYMMDD-HHMMSS.json`。

### 0.4.0

- **JSON 结果再增强**：`run --json` / `continue --json` 新增 `tool_calls_count` 与 `used_tools` 字段。
- **TUI 加载摘要**：`/load <path>` 成功后自动显示会话摘要（assistant 轮次、工具调用数、最后回答预览）。

### 0.3.9

- **JSON 结果增强**：`run --json` / `continue --json` 新增 `provider`、`model`、`mcp_enabled`、`elapsed_ms` 字段，便于脚本和 CI 诊断。
- **TUI 会话管理**：新增 `/save <path>` 与 `/load <path>`，可在交互界面直接保存/恢复会话。

### 0.3.8

- **README 移至仓库根目录**：统一从根目录查看项目说明，避免 `cai-agent/README.md` 与外层文档双份维护。
- **MCP 探活增强**：`mcp-check` 新增 `--tool` / `--args`，可在列工具后直接做一次真实工具调用测试。

### 0.3.7

- **跨平台文档增强**：新增 macOS/Linux 使用说明（安装、复制配置、环境变量设置、常用命令）。
- **MCP 运维增强**：`mcp-check` 新增 `--force` / `--verbose`；TUI 新增 `/mcp refresh` 与 `/mcp call <name> <json_args>`。

### 0.3.6

- **MCP 可用性增强**：新增 `cai-agent mcp-check` 子命令；`mcp_list_tools` 增加短时缓存（15s，可 `force=true` 强刷）；TUI 增加 `/mcp` 快速查看。

### 0.3.5

- **MCP Bridge 最小集成**：新增 `mcp_list_tools` / `mcp_call_tool`，支持通过配置接入外部工具服务；`doctor` 与 TUI `/status` 展示 MCP 状态。

### 0.3.4

- **Git 只读工具增强**：新增 `git_status` 与 `git_diff` 工具，便于在推理链路中先判断改动范围再读文件，减少无效扫描。

### 0.3.3

- **TUI 模型管理**：新增 `/models` 与 `/use-model <id>`，可在交互界面直接拉取代理模型列表并切换会话模型（无需退出重启）。

### 0.3.2

- **Copilot 手动选模型**：新增 `cai-agent models`（读取 `/v1/models`）与全局 `--model` 参数（`run`/`continue`/`ui`/`doctor`/`models` 均可临时覆盖模型）。

### 0.3.1

- **Copilot 集成（提升优先级）**：新增 `llm.provider`（`openai_compatible` / `copilot`），`doctor` 与 TUI `/status` 会显示当前 provider；新增 `[copilot]` 配置段与 `COPILOT_*` 环境变量支持。

### 0.3.0

- **会话导入导出**：`run` 支持 `--save-session PATH` 与 `--load-session PATH`，可把 `messages` 持久化到 JSON 并恢复继续跑。
- **`cai-agent continue`**：基于历史会话 JSON 继续提问（语义等价于 `run --load-session`），适合做多轮脚本化自动化。
- **`run_command` 增强**：支持 `cwd`（相对工作区），可在子目录执行命令且仍保持沙箱边界。

### 0.2.x

- **`cai-agent doctor`**：打印解析后的配置、工作区、说明文件是否存在、是否在 Git 仓库内；**API Key 打码**；支持 `--config`、`-w` / `--workspace`。
- **`Settings.config_loaded_from`**：记录实际加载的 TOML 绝对路径（无文件则为 `None`）；`cai-agent run --json` 会附带该字段便于脚本排查。
- **`run --json`**：向 stdout 输出一行 JSON（`answer`、`iteration`、`finished`、`config`、`workspace`），并**不再**打印 stderr 上的对话过程片段。
- **LLM 重试**：对 HTTP **429 / 502 / 503 / 504** 自动退避重试（最多 5 次请求）。
- **工具**：`read_file` 支持 **`line_start` / `line_end`**（按行切片，省略 `line_end` 则读到文件尾）；新增 **`list_tree`**（受限深度与条数）。
- **TUI**：**`/status`** 查看当前模型与工作区；**`/reload`** 仅重建首条 system 提示（重读项目说明与 Git 摘要）。

### 0.1.x 及更早能力摘要

- **`cai-agent init`**：生成 `cai-agent.toml`（`--force` 覆盖）。
- **配置**：`temperature`、`timeout_sec`、`project_context`、`git_context` 等；环境变量覆盖。
- **系统提示**：可选 `CAI.md` / `AGENTS.md` / `CLAUDE.md` 与只读 Git 摘要。
- **工具**：`glob_search`、`search_text`；`run` / `ui`；内置示例 TOML 模板。
