# 测试 TODO（当前执行基准）

> 与 `DEVELOPER_TODOS.zh-CN.md` 一起作为开发与测试的双基准。  
> 仅维护未完成测试任务；已完成项统一记录到 `CHANGELOG.md` / `CHANGELOG.zh-CN.md`（并保留 QA run 记录）。

## 当前测试队列

| 顺位 | 子任务 ID | 状态 | 测试目标 | 主要测试入口 | 通过门槛 |
|---|---|---|---|---|---|
| 1 | `HM-N04-D01` | Design | dashboard preview/apply/audit contract 测试 | `test_ops_apply_actions.py`（新增） | 写动作先 preview |

## 自动验证记录（由 finalize 脚本追加）

| 日期 | 任务 | 验证 | 记录 |
|---|---|---|---|
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
