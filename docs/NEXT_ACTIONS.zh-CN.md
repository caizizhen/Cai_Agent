# NEXT_ACTIONS.zh-CN.md

> 会话短入口（精简版）。  
> 详细任务以 `DEVELOPER_TODOS.zh-CN.md` 与 `TEST_TODOS.zh-CN.md` 为基准。  
> 已完成功能只记录到 `CHANGELOG.md` / `CHANGELOG.zh-CN.md` 与 `COMPLETED_TASKS_ARCHIVE.zh-CN.md`。
> 完成任一任务后，必须运行验证并用 `scripts/finalize_task.py` 把完成证据写入已完成记录，再更新本短入口的下一步。

## 当前目标

- 已完成 API/ops/install/gateway/ECC 产品化队列的代码与窄测试核验；当前先做 `SYNC-N01` 产品状态清账，把 TODO、roadmap、parity 与完成归档同步干净，再进入下一轮真实开发。

## 现在做

| 顺位 | 任务 | 状态 | 验收 |
|---|---|---|---|
| 1 | `SYNC-N01` | In Progress | 已归档 `API-N01`/`OPS-N01`/`CC-N05`/`GW-N01`/`ECC-N05`/`ECC-N06`；当前开发队列切到真实未完成项；文档一致性检查 + 窄 pytest |

## 后续队列

- `MEM-N01`：外部 memory provider adapter，先补 RFC/schema 与 mock/filesystem 或 sqlite adapter 测试契约
- `RT-N01`：Docker/SSH runtime 真机矩阵，先补分层 smoke / mock 测试矩阵
- `WF-N01`：workflow/subagent 编排增强，先定 branch/retry/aggregate schema 与失败恢复语义
- `BRW-N04`：Browser MCP executor（P2），把 `browser_task_v1.steps[]` 映射到显式确认的 Playwright MCP 调用

## 条件与边界

- 原生 WebSearch / Notebook：保持 MCP 优先，不做内置重写
- Browser automation：MCP first；先接 Playwright MCP，原生 provider 只做受控契约与显式入口
- 默认云 runtime：授权、安全、计费、隔离门槛明确后才实现
- Voice 默认交付：继续 OOS / MCP
- 商业插件市场、签名分成、公证体系：当前不做

## 刚完成

| 任务 | 日期 | 摘要 | 验证 |
|---|---|---|---|
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
