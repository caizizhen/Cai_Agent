# NEXT_ACTIONS.zh-CN.md

> 会话短入口（精简版）。  
> 详细任务以 `DEVELOPER_TODOS.zh-CN.md` 与 `TEST_TODOS.zh-CN.md` 为基准。  
> 已完成功能只记录到 `CHANGELOG.md` / `CHANGELOG.zh-CN.md` 与 `COMPLETED_TASKS_ARCHIVE.zh-CN.md`。
> 完成任一任务后，必须运行验证并用 `scripts/finalize_task.py` 把完成证据写入已完成记录，再更新本短入口的下一步。

## 当前目标

- `GW-SLASH-N01` 已完成并归档；当前默认开发队列清空。下一轮建议在 Gateway slash command 真实注册/部署检查与 Ops operator 路由深化中选择。

## 现在做

| 顺位 | 任务 | 状态 | 验收 |
|---|---|---|---|
| - | - | Clear | `GW-SLASH-N01` 已完成；完成证据见 `COMPLETED_TASKS_ARCHIVE.zh-CN.md` 与 `docs/qa/runs/task-finalize-20260429-234407-GW-SLASH-N01.md` |

## 后续队列

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
