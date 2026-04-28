# NEXT_ACTIONS.zh-CN.md

> 会话短入口（精简版）。  
> 详细任务以 `DEVELOPER_TODOS.zh-CN.md` 与 `TEST_TODOS.zh-CN.md` 为基准。  
> 已完成功能只记录到 `CHANGELOG.md` / `CHANGELOG.zh-CN.md` 与 `COMPLETED_TASKS_ARCHIVE.zh-CN.md`。
> 完成任一任务后，必须运行验证并用 `scripts/finalize_task.py` 把完成证据写入已完成记录，再更新本短入口的下一步。

## 当前目标

- Browser automation 入口链已完成（MCP preset、provider 契约、治理 RFC）。下一步回到“三 repo 融合”产品化主线：优先补齐外部接入面、受控运营面、安装/升级/恢复体验。

## 现在做

| 顺位 | 任务 | 状态 | 验收 |
|---|---|---|---|
| 1 | `API-N01` | Ready | OpenAPI + API/ops 统一网关；新增可验证的非敏感外部契约；pytest + smoke |
| 2 | `OPS-N01` | Ready | dashboard interactions 从 preview 推进到受控 apply/audit；pytest |
| 3 | `CC-N05` | Ready | 安装、升级、恢复体验收口；doctor/repair/onboarding 给出一致下一步 |

## 后续队列

- `GW-N01`：Gateway 生产化第二阶段（Discord/Slack/Teams readiness、故障诊断、workspace 路由预览）
- `ECC-N05`：asset marketplace-lite（资产目录、安装、更新建议、trust 摘要）
- `ECC-N06`：provenance/trust 策略进入 pack/import/install 执行链
- `MEM-N01` / `RT-N01` / `WF-N01`：先 Design，补契约或测试矩阵后再进入 Ready

## 条件与边界

- 原生 WebSearch / Notebook：保持 MCP 优先，不做内置重写
- Browser automation：MCP first；先接 Playwright MCP，原生 provider 只做受控契约与显式入口
- 默认云 runtime：授权、安全、计费、隔离门槛明确后才实现
- Voice 默认交付：继续 OOS / MCP
- 商业插件市场、签名分成、公证体系：当前不做

## 刚完成

| 任务 | 日期 | 摘要 | 验证 |
|---|---|---|---|
| `UX-CONTEXT-OFFICIAL-PRESET-MAP` | 2026-04-29 | Scan and pin official context windows for built-in hosted third-party presets; keep localhost/self-hosted context manual. | python -m pytest -q cai-agent/tests: PASS; python scripts/smoke_new_features.py: PASS |
| `UX-CONTEXT-THIRDPARTY-DEFAULT` | 2026-04-29 | Legacy `[llm]` third-party models now auto-infer context window from provider/model defaults; localhost/self-hosted remains manual/unknown by default | `python -m pytest -q cai-agent/tests/test_context_usage_bar.py cai-agent/tests/test_model_profiles_config.py cai-agent/tests/test_provider_registry.py`: 54 passed<br>`python -m pytest -q cai-agent/tests`: 899 passed, 3 subtests passed<br>`python scripts/smoke_new_features.py`: NEW_FEATURE_CHECKS_OK |
| `BRW-N03` | 2026-04-29 | Document browser governance, audit, artifact, and license boundaries | pytest browser MCP/provider tests: 8 passed<br>rg browser RFC/product/schema references: PASS |
| `BRW-N02` | 2026-04-29 | Add browser provider readiness and task JSON contracts | pytest browser provider/browser MCP/mcp-check subset: 13 passed<br>compileall browser_provider/mcp_presets/tool_provider/__main__: PASS |
| `BRW-N01` | 2026-04-29 | Browser MCP preset and Playwright isolated onboarding | pytest test_browser_mcp_cli.py + test_mcp_presets_tui_quickstart.py: 5 passed<br>pytest test_cli_misc.py -k mcp_check: 6 passed<br>compileall mcp_presets/tool_provider/__main__: PASS |
