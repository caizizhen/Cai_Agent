# NEXT_ACTIONS.zh-CN.md

> 会话短入口（精简版）。  
> 详细任务以 `DEVELOPER_TODOS.zh-CN.md` 与 `TEST_TODOS.zh-CN.md` 为基准。  
> 已完成功能只记录到 `CHANGELOG.md` / `CHANGELOG.zh-CN.md` 与 `COMPLETED_TASKS_ARCHIVE.zh-CN.md`。
> 完成任一任务后，必须运行验证并用 `scripts/finalize_task.py` 把完成证据写入已完成记录，再更新本短入口的下一步。

## 当前目标

- **解限安全**：[`SAFETY_UNRESTRICTED_BACKLOG.zh-CN.md`](SAFETY_UNRESTRICTED_BACKLOG.zh-CN.md) 清单 **P4 已全部 Done**；**`SAFETY-N07-D01`** 已交付关键写 **noop 启发式**（可关）；后续 **Explore** 为更深 `write_file` diff 语义（见 backlog）。

## 现在做

| 顺位 | 任务 | 状态 | 验收 |
|---|---|---|---|
| - | - | Clear | 解限 P4（含 Slack/Discord 网关前缀放行契约）已收口 |

## 下一步（解限）

- **Explore**：结构化 / 破坏性 diff 才触发关键写确认等（MVP noop 见 **`dangerous_critical_write_skip_if_unchanged`**）；详见 [`SAFETY_UNRESTRICTED_BACKLOG.zh-CN.md`](SAFETY_UNRESTRICTED_BACKLOG.zh-CN.md) Explore 段。

## 后续队列

- `CTX-COMPACT-N09`：安全/隐私过滤
- `CTX-COMPACT-N10`：真实模型回归样本集
- Gateway 深化（候选）：slash command 深化、多 workspace federation 的真实部署检查
- Ops operator 路由深化（候选）：在 RBAC / workspaces 发现基础上继续补跨 workspace 操作路由与租户边界

## 条件与边界

- 原生 WebSearch / Notebook：保持 MCP 优先，不做内置重写
- Browser automation：MCP first；先接 Playwright MCP，原生 provider 只做受控契约与显式入口
- 默认云 runtime：授权、安全、计费、隔离门槛明确后才实现
- Voice 默认交付：继续 OOS / MCP
- 商业插件市场、签名分成、公证体系：当前不做

## 刚完成

| 任务 | 日期 | 摘要 | 验证 |
|---|---|---|---|
| `SAFETY-N07-D01` | 2026-05-01 | Critical write_file noop heuristic: skip basename dangerous confirmation when disk file exists and normalized UTF-8 matches; doctor/guard/smoke/tests. | python -m pytest -q cai-agent/tests: PASS (976 passed, 20 subtests)<br>python scripts/smoke_new_features.py: NEW_FEATURE_CHECKS_OK |
| `SAFETY-N06-D01` | 2026-05-01 | P4-4：gateway_danger goal 前缀放行；Slack/Discord 执行路径接入；tools guard danger_gateway_contract_v1。 | python -m pytest -q cai-agent/tests: PASS (971 passed, 20 subtests)<br>python scripts/smoke_new_features.py: NEW_FEATURE_CHECKS_OK |
| `SAFETY-N05-D01` | 2026-05-01 | 解限 P4-1～P4-3：fetch 私网 DNS 放行强制确认、拒绝 file://；write_file 关键 basename；run_command_extra_danger_basenames；doctor/guard 计数。 | python -m pytest -q cai-agent/tests: PASS (965 passed, 20 subtests)<br>python scripts/smoke_new_features.py: NEW_FEATURE_CHECKS_OK |
| `SAFETY-N04-D01` | 2026-05-01 | 解限 P3-3/P3-4：会话 MCP/http 放行（斜杠+Modal）、dangerous_audit_log_enabled 与 .cai/dangerous-approve.jsonl；dispatch 会话豁免不耗 budget；grant 可记审计。 | python -m pytest -q cai-agent/tests: PASS (961 passed, 20 subtests)<br>python scripts/smoke_new_features.py: NEW_FEATURE_CHECKS_OK |
| `SAFETY-N03-D01` | 2026-05-01 | 解限危险工具：Graph 下发 danger_confirm_prompt 与 prepare_interactive_dangerous_dispatch 串联；TUI Modal 确认；pytest 含 test_tools_prepare_interactive_dangerous_dispatch；schedule fake_build_app 接受 **kwargs。 | python -m pytest -q cai-agent/tests: PASS (955 passed, 20 subtests)<br>python scripts/smoke_new_features.py: NEW_FEATURE_CHECKS_OK |
| `CTX-COMPACT-N08` | 2026-04-30 | Show recent context compaction status in TUI | compileall context_compaction/graph/tui/__main__: PASS; pytest tui_slash_suggester + context_compaction + graph_context_compaction + sessions_compact_eval_cli + compact_policy_explain_v1: 51 passed |
| `CTX-COMPACT-N07` | 2026-04-30 | Add tool-aware evidence extraction for context compaction summaries | compileall context_compaction/graph/tui/__main__: PASS; pytest context_compaction + graph_context_compaction + sessions_compact_eval_cli + compact_policy_explain_v1: 22 passed |
| `CTX-COMPACT-N06` | 2026-04-30 | Merge existing context summaries during repeated compaction | compileall context_compaction/graph/tui/__main__: PASS; pytest context_compaction + graph_context_compaction + sessions_compact_eval_cli + compact_policy_explain_v1: 21 passed |
| `CTX-COMPACT-N05` | 2026-04-30 | Add context compaction JSON schemas and fixture checks | compileall context_compaction/graph/tui/__main__: PASS; pytest context_compaction + graph_context_compaction + sessions_compact_eval_cli + compact_policy_explain_v1: 20 passed |
| `CTX-COMPACT-N04` | 2026-04-30 | Add LLM compaction retention gate with heuristic fallback | compileall context_compaction/graph/tui: PASS; pytest context_compaction + graph_context_compaction + sessions_compact_eval_cli + compact_policy_explain_v1: 16 passed |
| `CTX-COMPACT-N03` | 2026-04-30 | Add sessions compact-eval quality gate for context compaction regressions | compileall context_compaction/__main__: PASS; pytest context_compaction + graph_context_compaction + sessions_compact_eval_cli: 13 passed |
| `CTX-COMPACT-N02` | 2026-04-30 | Add compact_mode off/heuristic/llm with LLM summary compaction and heuristic fallback | compileall context compaction/graph/config/tui/cost/main: PASS; pytest context_compaction + graph_context_compaction + compact_policy_explain_v1: 10 passed |
| `CTX-COMPACT-N01` | 2026-04-30 | Add heuristic context_summary_v1 compaction with graph auto-trigger and TUI /compress | compileall context compaction/graph/config/tui/cost: PASS; pytest context_compaction + graph_context_compaction: 4 passed; pytest compact_policy_explain_v1: PASS |
| `GW-SLASH-N01` | 2026-04-29 | Add Gateway offline slash/command catalog CLI and API for Discord, Slack, and Teams with schema/OpenAPI/docs coverage | compileall gateway_production/__main__/api_http_server/gateway_lifecycle_cli/api_http_server tests: PASS; manual CLI/API slash-catalog verification: GW_SLASH_MANUAL_OK; OpenAPI route verification: GW_SLASH_OPENAPI_OK; pytest slash catalog focused tests: 2 passed |
| `GW-CHAN-N01` | 2026-04-29 | Add standalone gateway channel-monitor CLI/API surface with platform and only-errors filtering plus schema/OpenAPI/docs coverage | compileall gateway_production/__main__/api_http_server/gateway_lifecycle_cli/api_http_server tests: PASS; manual CLI/API channel-monitor verification: GW_CHAN_MANUAL_OK; OpenAPI route verification: GW_CHAN_OPENAPI_OK; pytest gateway/api subset blocked by Windows temp directory PermissionError in sandbox |
| `OPS-MW-N01` | 2026-04-29 | Add ops serve allowlist multi-workspace discovery with optional dashboard summary aggregation and OpenAPI/docs coverage | compileall ops_http_server/api_http_server/test_ops_http_server: PASS; manual HTTP workspaces verification: OPS_MW_MANUAL_OK; OpenAPI route verification: OPS_MW_OPENAPI_OK |
| `OPS-RBAC-N01` | 2026-04-29 | Add ops serve RBAC roles, actor/role request context, workspace-scoped audit fields, and OpenAPI/docs coverage | compileall ops_http_server/ops_dashboard/api_http_server/__main__/test_ops_http_server: PASS; manual HTTP RBAC verification: OPS_RBAC_MANUAL_OK; pytest test_ops_http_server blocked by Windows temp directory PermissionError in sandbox |
| `BRW-N05` | 2026-04-29 | Add Browser MCP audit JSONL and artifact manifest for refused and confirmed execution paths | uv run --project cai-agent --extra dev python -m pytest -q -p no:cacheprovider cai-agent/tests/test_browser_provider_cli.py cai-agent/tests/test_browser_mcp_cli.py cai-agent/tests/test_cli_workflow.py cai-agent/tests/test_memory_provider_contract_cli.py cai-agent/tests/test_runtime_local.py cai-agent/tests/test_runtime_docker_mock.py cai-agent/tests/test_runtime_ssh_mock.py cai-agent/tests/test_runtime_tool_dispatch.py: 42 passed |
| `BRW-N04` | 2026-04-29 | Add confirmed Browser MCP executor mapping for browser_task_v1 steps with dry-run, refusal, and audited mcp_call_tool execution | uv run --project cai-agent --extra dev python -m pytest -q -p no:cacheprovider cai-agent/tests/test_browser_provider_cli.py cai-agent/tests/test_browser_mcp_cli.py cai-agent/tests/test_cli_workflow.py cai-agent/tests/test_memory_provider_contract_cli.py cai-agent/tests/test_runtime_local.py cai-agent/tests/test_runtime_docker_mock.py cai-agent/tests/test_runtime_ssh_mock.py cai-agent/tests/test_runtime_tool_dispatch.py: 42 passed |
| `SYNC-N01,MEM-N01,RT-N01,WF-N01` | 2026-04-29 | Close product status sync, memory provider adapter contracts, runtime verification matrix, and workflow branch/retry/aggregate execution semantics | uv run --project cai-agent --extra dev python -m pytest -q cai-agent/tests/test_cli_workflow.py cai-agent/tests/test_memory_provider_contract_cli.py cai-agent/tests/test_runtime_local.py cai-agent/tests/test_runtime_docker_mock.py cai-agent/tests/test_runtime_ssh_mock.py cai-agent/tests/test_runtime_tool_dispatch.py: 33 passed |
| `ECC-N06` | 2026-04-29 | Close productization backlog items already implemented across OpenAPI, controlled ops interactions, install recovery, gateway readiness, marketplace-lite, and trust gates | python -m pytest -q cai-agent/tests/test_api_http_server.py cai-agent/tests/test_ops_http_server.py cai-agent/tests/test_gateway_lifecycle_cli.py cai-agent/tests/test_ecc_layout_cli.py cai-agent/tests/test_ecc_pack_ingest_gate.py cai-agent/tests/test_doctor_cli.py cai-agent/tests/test_repair_cli.py cai-agent/tests/test_cli_misc.py: 110 passed |
| `ECC-N05` | 2026-04-29 | Close productization backlog items already implemented across OpenAPI, controlled ops interactions, install recovery, gateway readiness, marketplace-lite, and trust gates | python -m pytest -q cai-agent/tests/test_api_http_server.py cai-agent/tests/test_ops_http_server.py cai-agent/tests/test_gateway_lifecycle_cli.py cai-agent/tests/test_ecc_layout_cli.py cai-agent/tests/test_ecc_pack_ingest_gate.py cai-agent/tests/test_doctor_cli.py cai-agent/tests/test_repair_cli.py cai-agent/tests/test_cli_misc.py: 110 passed |
| `GW-N01` | 2026-04-29 | Close productization backlog items already implemented across OpenAPI, controlled ops interactions, install recovery, gateway readiness, marketplace-lite, and trust gates | python -m pytest -q cai-agent/tests/test_api_http_server.py cai-agent/tests/test_ops_http_server.py cai-agent/tests/test_gateway_lifecycle_cli.py cai-agent/tests/test_ecc_layout_cli.py cai-agent/tests/test_ecc_pack_ingest_gate.py cai-agent/tests/test_doctor_cli.py cai-agent/tests/test_repair_cli.py cai-agent/tests/test_cli_misc.py: 110 passed |
| `CC-N05` | 2026-04-29 | Close productization backlog items already implemented across OpenAPI, controlled ops interactions, install recovery, gateway readiness, marketplace-lite, and trust gates | python -m pytest -q cai-agent/tests/test_api_http_server.py cai-agent/tests/test_ops_http_server.py cai-agent/tests/test_gateway_lifecycle_cli.py cai-agent/tests/test_ecc_layout_cli.py cai-agent/tests/test_ecc_pack_ingest_gate.py cai-agent/tests/test_doctor_cli.py cai-agent/tests/test_repair_cli.py cai-agent/tests/test_cli_misc.py: 110 passed |
| `OPS-N01` | 2026-04-29 | Close productization backlog items already implemented across OpenAPI, controlled ops interactions, install recovery, gateway readiness, marketplace-lite, and trust gates | python -m pytest -q cai-agent/tests/test_api_http_server.py cai-agent/tests/test_ops_http_server.py cai-agent/tests/test_gateway_lifecycle_cli.py cai-agent/tests/test_ecc_layout_cli.py cai-agent/tests/test_ecc_pack_ingest_gate.py cai-agent/tests/test_doctor_cli.py cai-agent/tests/test_repair_cli.py cai-agent/tests/test_cli_misc.py: 110 passed |
| `API-N01` | 2026-04-29 | Close productization backlog items already implemented across OpenAPI, controlled ops interactions, install recovery, gateway readiness, marketplace-lite, and trust gates | python -m pytest -q cai-agent/tests/test_api_http_server.py cai-agent/tests/test_ops_http_server.py cai-agent/tests/test_gateway_lifecycle_cli.py cai-agent/tests/test_ecc_layout_cli.py cai-agent/tests/test_ecc_pack_ingest_gate.py cai-agent/tests/test_doctor_cli.py cai-agent/tests/test_repair_cli.py cai-agent/tests/test_cli_misc.py: 110 passed |
| `UX-CONTEXT-OFFICIAL-MODEL-TABLE` | 2026-04-29 | Refresh hosted-model context-window inference with official defaults across OpenAI/Claude/Gemini/DeepSeek/GLM/Qwen/Kimi/MiniMax/Grok/Groq/Mistral/Cohere/Perplexity and router prefixes; keep explicit/local manual behavior. | pytest profile/context/provider subset: PASS; full pytest + smoke pending |
| `UX-CONTEXT-OFFICIAL-PRESET-MAP` | 2026-04-29 | Scan and pin official context windows for built-in hosted third-party presets; keep localhost/self-hosted context manual. | python -m pytest -q cai-agent/tests: PASS; python scripts/smoke_new_features.py: PASS |
| `UX-CONTEXT-THIRDPARTY-DEFAULT` | 2026-04-29 | Legacy `[llm]` third-party models now auto-infer context window from provider/model defaults; localhost/self-hosted remains manual/unknown by default | `python -m pytest -q cai-agent/tests/test_context_usage_bar.py cai-agent/tests/test_model_profiles_config.py cai-agent/tests/test_provider_registry.py`: 54 passed<br>`python -m pytest -q cai-agent/tests`: 899 passed, 3 subtests passed<br>`python scripts/smoke_new_features.py`: NEW_FEATURE_CHECKS_OK |
| `BRW-N03` | 2026-04-29 | Document browser governance, audit, artifact, and license boundaries | pytest browser MCP/provider tests: 8 passed<br>rg browser RFC/product/schema references: PASS |
| `BRW-N02` | 2026-04-29 | Add browser provider readiness and task JSON contracts | pytest browser provider/browser MCP/mcp-check subset: 13 passed<br>compileall browser_provider/mcp_presets/tool_provider/__main__: PASS |
| `BRW-N01` | 2026-04-29 | Browser MCP preset and Playwright isolated onboarding | pytest test_browser_mcp_cli.py + test_mcp_presets_tui_quickstart.py: 5 passed<br>pytest test_cli_misc.py -k mcp_check: 6 passed<br>compileall mcp_presets/tool_provider/__main__: PASS |
