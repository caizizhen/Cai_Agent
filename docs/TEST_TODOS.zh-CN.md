# 测试 TODO（当前执行基准）

> 与 `DEVELOPER_TODOS.zh-CN.md` 一起作为开发与测试的双基准。  
> 仅维护未完成测试任务；已完成项统一记录到 `CHANGELOG.md` / `CHANGELOG.zh-CN.md`（并保留 QA run 记录）。  
> 每完成一项任务，必须把验证命令与结果写入已完成记录：优先通过 `scripts/finalize_task.py` 追加 `COMPLETED_TASKS_ARCHIVE.zh-CN.md` 与 `docs/qa/runs/`，需要对外说明时同步 `CHANGELOG.md` / `CHANGELOG.zh-CN.md`。

## 当前测试队列

| 顺位 | 子任务 ID | 状态 | 测试目标 | 主要测试入口 | 通过门槛 |
|---|---|---|---|---|---|
| 1 | `SYNC-N01` | In Progress | 产品状态清账验证：确认已归档任务不再留在当前 TODO，且 roadmap/parity 与代码能力一致 | `rg` 文档一致性检查、`test_api_http_server.py`、`test_ops_http_server.py`、`test_gateway_lifecycle_cli.py`、`test_ecc_layout_cli.py`、`test_ecc_pack_ingest_gate.py`、`test_doctor_cli.py`、`test_repair_cli.py`、`test_cli_misc.py` | 旧 Ready 项只出现在完成记录/历史说明中；窄 pytest 通过 |
| 2 | `MEM-N01` | Design | memory provider adapter 契约验证设计 | 待定：`test_memory_provider_contract_cli.py` 或新增 provider adapter 测试 | mock/filesystem 或 sqlite adapter 可测；`memory provider test --json` schema 稳定 |
| 3 | `RT-N01` | Design | Docker/SSH runtime 真机矩阵验证设计 | 待定：runtime mock + opt-in real smoke | CI 默认不依赖外部 Docker/SSH；真实 smoke 可手动或条件启用 |
| 4 | `WF-N01` | Design | workflow/subagent 条件分支、汇总、失败恢复验证设计 | 待定：`test_workflow*.py` schema 与执行用例 | happy path、branch/retry/aggregate、失败恢复均有覆盖 |
| 5 | `BRW-N04` | Ready after SYNC | Browser MCP executor 映射验证 | 待定：browser provider / MCP preset 映射测试 | dry-run、拒绝、显式确认、成功映射都有测试 |

## 自动验证记录（由 finalize 脚本追加）

| 日期 | 任务 | 验证 | 记录 |
|---|---|---|---|
| 2026-04-28 | `UX-N01-D06` | python -m pytest -q cai-agent/tests: 881 passed, 3 subtests passed<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | 本轮会话验证 |
| 2026-04-28 | `UX-N01-D05` | python -m pytest -q cai-agent/tests: 880 passed, 3 subtests passed<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | 本轮会话验证 |
| 2026-04-28 | `UX-N01-D04` | python -m pytest -q cai-agent/tests: 878 passed, 3 subtests passed<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | 本轮会话验证 |
| 2026-04-28 | `UX-N01-D03` | python -m pytest -q cai-agent/tests: 876 passed, 3 subtests passed<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | 本轮会话验证 |
| 2026-04-28 | `UX-N01-D02` | python -m pytest -q cai-agent/tests: 874 passed, 3 subtests passed<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | 本轮会话验证 |
| 2026-04-28 | `UX-N01-D01` | python -m pytest -q cai-agent/tests: 872 passed, 3 subtests passed<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | 本轮会话验证 |
| 2026-04-26 | `DOC-AUTO-FINALIZE` | pytest -q -p no:cacheprovider cai-agent/tests/test_finalize_task_script.py: 1 passed | [`docs/qa/runs/task-finalize-20260426-194030-DOC-AUTO-FINALIZE.md`](qa/runs/task-finalize-20260426-194030-DOC-AUTO-FINALIZE.md) |
| 2026-04-26 | `ECC-N04-D03` | python -m pytest -q cai-agent/tests: 817 passed, 3 subtests passed<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | [`docs/qa/runs/task-finalize-20260426-203353-ECC-N04-D03.md`](qa/runs/task-finalize-20260426-203353-ECC-N04-D03.md) |
| 2026-04-26 | `CC-N02-D04` | python -m pytest -q cai-agent/tests/test_feedback_cli.py cai-agent/tests/test_feedback_export.py cai-agent/tests/test_feedback_bundle_cli.py cai-agent/tests/test_doctor_cli.py: PASS<br>python -m pytest -q cai-agent/tests: 820 passed, 3 subtests passed<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | [`docs/qa/runs/task-finalize-20260426-212531-CC-N02-D04.md`](qa/runs/task-finalize-20260426-212531-CC-N02-D04.md) |
| 2026-04-26 | `HM-N01-D02`, `HM-N01-D04`, `HM-N01-D05` | python -m pytest -q cai-agent/tests: PASS (825 passed, 3 subtests)<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | [`docs/qa/runs/task-finalize-20260426-214419-HM-N01-D02-HM-N01-D04-HM-N01-D05.md`](qa/runs/task-finalize-20260426-214419-HM-N01-D02-HM-N01-D04-HM-N01-D05.md) |
| 2026-04-27 | `CC-N03-D04` + `HM-N01-D01`（增量并行） | python -m pytest -q cai-agent/tests/test_plugin_compat_matrix.py cai-agent/tests/test_model_profiles_config.py cai-agent/tests/test_profile_home_isolation.py: 46 passed<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | 本轮并行增量验证（未 finalize 归档） |
| 2026-04-27 | `CC-N03-D04` | python -m pytest -q cai-agent/tests: PASS (841 passed, 3 subtests passed); python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | [`docs/qa/runs/task-finalize-20260427-225218-CC-N03-D04.md`](docs/qa/runs/task-finalize-20260427-225218-CC-N03-D04.md) |
| 2026-04-27 | `HM-N01-D01` | python -m pytest -q cai-agent/tests: PASS (841 passed, 3 subtests passed); python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | [`docs/qa/runs/task-finalize-20260427-225222-HM-N01-D01.md`](docs/qa/runs/task-finalize-20260427-225222-HM-N01-D01.md) |
| 2026-04-28 | `ECC-N03-D03` | python -m pytest -q cai-agent/tests/test_ecc_layout_cli.py cai-agent/tests/test_doctor_cli.py: 20 passed<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | 本轮会话验证（未跑 finalize_task） |
| 2026-04-28 | `ECC-N03-D04` | python -m pytest -q cai-agent/tests/test_export_sync_diff.py cai-agent/tests/test_doctor_cli.py cai-agent/tests/test_repair_cli.py: PASS<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | 本轮会话验证 |
| 2026-04-28 | `HM-N03-D01` | python -m pytest -q cai-agent/tests/test_api_http_server.py cai-agent/tests/test_api_status_routes.py: PASS | 本轮会话验证 |
| 2026-04-28 | `HM-N04-D01` | python -m pytest -q cai-agent/tests/test_ops_http_server.py: PASS | 本轮会话验证 |
| 2026-04-28 | `CC-N04` | python -m pytest -q cai-agent/tests/test_session_recap.py cai-agent/tests/test_tui_session_strip.py: PASS | 本轮会话验证 |
| 2026-04-28 | `ECC-N02-D05` | python -m pytest -q cai-agent/tests: 866 passed, 3 subtests passed<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | 本轮会话验证 |
| 2026-04-28 | `ECC-N02-D06` | pytest `test_doctor_cli` + `test_api_http_server`（doctor JSON / `/v1/doctor/summary` 含 **`ecc_pack_ingest_gate`**） | 本轮会话验证 |
| 2026-04-28 | `ECC-N02-D07` | python -m pytest -q cai-agent/tests: 869 passed, 3 subtests passed | 本轮会话验证 |
| 2026-04-28 | `ECC-N02-D08` | pytest `test_skills_lint_cli` + `scripts/smoke_new_features.py`（skills hub install ingest 门禁） | 本轮会话验证 |
| 2026-04-29 | `BRW-N01` | pytest test_browser_mcp_cli.py + test_mcp_presets_tui_quickstart.py: 5 passed<br>pytest test_cli_misc.py -k mcp_check: 6 passed<br>compileall mcp_presets/tool_provider/__main__: PASS | [`docs/qa/runs/task-finalize-20260429-023248-BRW-N01.md`](docs/qa/runs/task-finalize-20260429-023248-BRW-N01.md) |
| 2026-04-29 | `BRW-N02` | pytest browser provider/browser MCP/mcp-check subset: 13 passed<br>compileall browser_provider/mcp_presets/tool_provider/__main__: PASS | [`docs/qa/runs/task-finalize-20260429-024251-BRW-N02.md`](docs/qa/runs/task-finalize-20260429-024251-BRW-N02.md) |
| 2026-04-29 | `BRW-N03` | pytest browser MCP/provider tests: 8 passed<br>rg browser RFC/product/schema references: PASS | [`docs/qa/runs/task-finalize-20260429-024641-BRW-N03.md`](docs/qa/runs/task-finalize-20260429-024641-BRW-N03.md) |
| 2026-04-29 | Browser chain full regression | python -m pytest -q -p no:cacheprovider --basetemp .tmp/pytest-full-basetemp cai-agent/tests: 897 passed, 3 subtests passed<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | [`docs/qa/runs/browser-full-regression-20260429.md`](docs/qa/runs/browser-full-regression-20260429.md) |
| 2026-04-29 | `UX-CONTEXT-THIRDPARTY-DEFAULT` | python -m pytest -q cai-agent/tests: PASS; python scripts/smoke_new_features.py: PASS | [`docs/qa/runs/task-finalize-20260429-035043-UX-CONTEXT-THIRDPARTY-DEFAULT.md`](docs/qa/runs/task-finalize-20260429-035043-UX-CONTEXT-THIRDPARTY-DEFAULT.md) |
| 2026-04-29 | `UX-CONTEXT-OFFICIAL-PRESET-MAP` | python -m pytest -q cai-agent/tests: PASS; python scripts/smoke_new_features.py: PASS | [`docs/qa/runs/task-finalize-20260429-035835-UX-CONTEXT-OFFICIAL-PRESET-MAP.md`](docs/qa/runs/task-finalize-20260429-035835-UX-CONTEXT-OFFICIAL-PRESET-MAP.md) |
| 2026-04-29 | `API-N01`, `OPS-N01`, `CC-N05`, `GW-N01`, `ECC-N05`, `ECC-N06` | python -m pytest -q cai-agent/tests/test_api_http_server.py cai-agent/tests/test_ops_http_server.py cai-agent/tests/test_gateway_lifecycle_cli.py cai-agent/tests/test_ecc_layout_cli.py cai-agent/tests/test_ecc_pack_ingest_gate.py cai-agent/tests/test_doctor_cli.py cai-agent/tests/test_repair_cli.py cai-agent/tests/test_cli_misc.py: 110 passed | [`docs/qa/runs/task-finalize-20260429-184615-API-N01-OPS-N01-CC-N05-GW-N01-ECC-N05-ECC-N06.md`](docs/qa/runs/task-finalize-20260429-184615-API-N01-OPS-N01-CC-N05-GW-N01-ECC-N05-ECC-N06.md) |
