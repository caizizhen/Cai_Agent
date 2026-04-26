# 测试 TODO（未完成项）

> 开发对齐页：[`DEVELOPER_TODOS.zh-CN.md`](DEVELOPER_TODOS.zh-CN.md)。产品判断页：[`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md)。  
> **已完成测试 backlog 行**见 [`TODOS_DONE_ARCHIVE.zh-CN.md`](TODOS_DONE_ARCHIVE.zh-CN.md) §4～§6。  
> 任务完成后的验证记录仍由 `scripts/finalize_task.py` 追加到本页「自动验证记录」，并同步写入 `docs/qa/runs/`。

本页**仅列未完成**能力与其原子测试缺口；`MODEL-P0` 与已 Done 能力级/原子行已拆至归档页。

## 1. 当前测试基线

2026-04-26 在仓库根 `D:\gitrepo\Cai_Agent` 复核结果：

| 检查项 | 命令 | 结果 |
|---|---|---|
| 全量单测 | `python -m pytest -q cai-agent/tests` | **834 passed**, **3 subtests passed** |
| 冒烟 | `python scripts/smoke_new_features.py` | **PASS**，输出 `NEW_FEATURE_CHECKS_OK` |
| 回归 | `QA_SKIP_LOG=1 python scripts/run_regression.py` | **PASS**，compileall / unittest / smoke / CLI 子集全绿 |

结论：与 [`DEVELOPER_TODOS.zh-CN.md`](DEVELOPER_TODOS.zh-CN.md) §11 QA 基线一致。

### 1.1 当前测试开工队列

| 顺位 | 能力 | 当前测试动作 |
|---|---|---|
| 1 | `CC-N03` | 仍缺 **D04**（`plugins sync-home --apply`）专用用例 |
| 2 | `HM-N01` | **`D01`**：schema 深化后的契约测试 |
| 3 | `ECC-N02` | **`D03`/`D04`** 仍待用例（import/repair） |
| 4 | `ECC-N03` | target inventory / 结构化 diff 快照测试 |

## 2. 使用规则

每个未完成项至少补齐下面三层中的两层：`pytest`、smoke/regression、手工/真机（视改动面而定）。

必须补自动化的改动面：CLI 退出码与 JSON、`schema_version`、API 路由、gateway 状态、doctor/repair 输出等。

## 3. 模型接入（MODEL-P0）

`MODEL-P0-01`～`P0-07` 与 §7.1 原子表已迁至 [`TODOS_DONE_ARCHIVE.zh-CN.md`](TODOS_DONE_ARCHIVE.zh-CN.md) §4。

## 4. Claude Code 线测试 backlog（未完成）

| ID | 状态 | 测试重点 | 现有测试入口 | 需新增自动化 | 手工 / 真机 | 通过标准 |
|---|---|---|---|---|---|---|
| `CC-N03` | `Ready` | plugin / sync-home **`D04`** | `test_plugin_compat_matrix.py` 等 | **`--apply`** 冲突/备份套件、`test_marketplace_manifest_cli.py`（占位） | 手工验证冲突确认 | 默认不覆盖用户修改 |
| `CC-N04` | `Design` | recap / resume / task UX | `test_tui_task_board_render.py`、`test_tui_session_strip.py`、`test_tui_model_panel.py` | `test_session_recap_cli.py` 等 | 长会话恢复体验 | resume 不要求重读整段历史 |
| `CC-N05` | `Explore` | local GUI / desktop | 现有无专门主入口 | 设计/PoC 校验 | 本地原型 | 先形成方案 |
| `CC-N06` | `OOS` | WebSearch / Notebook 原生 | MCP 相关测试 | 无 | MCP 走查 | 替代路径可用 |
| `CC-N07` | `Conditional` | remote / cloud surfaces | 无 | 无 | 立项后定义 | 默认不进测试线 |

## 5. Hermes 线测试 backlog（未完成）

| ID | 状态 | 测试重点 | 现有测试入口 | 需新增自动化 | 手工 / 真机 | 通过标准 |
|---|---|---|---|---|---|---|
| `HM-N01` | `Ready` | profile home **`D01`** 与隔离 | `test_model_profiles_config.py`、`test_model_profiles_cli.py`、`test_doctor_cli.py` | `test_profile_home_isolation.py` 等 | 多 profile 手工抽检 | 状态不串 |
| `HM-N03` | `Design` | API 扩路由 / OpenAPI / auth | `test_api_http_server.py` | `test_api_status_routes.py`、`test_api_auth_config.py`、OpenAPI snapshot | 文档/schema 走查 | 路由与 auth 不打架 |
| `HM-N04` | `Design` | dashboard preview/apply/audit | `test_ops_http_server.py`、`test_ops_dashboard_html.py` | `test_ops_apply_actions.py`、`test_ops_audit_log.py` | 浏览器 apply | 至少一个写动作可回归 |
| `HM-N06` | `Explore` | 第二批 gateway | 现有无 | 预研记录 | 预研 | 优先级明确 |
| `HM-N11` | `Conditional` | cloud runtime | `test_runtime_docker_mock.py` 等仅供参考 | 立项后补 | 云端验证 | 默认不进测试线 |

## 6. ECC 线测试 backlog（未完成）

| ID | 状态 | 测试重点 | 现有测试入口 | 需新增自动化 | 手工 / 真机 | 通过标准 |
|---|---|---|---|---|---|---|
| `ECC-N02` | `Ready` | pack **D03/D04** | `test_ecc_layout_cli.py` + smoke | **`test_asset_pack_import_export.py`**、**`test_asset_pack_repair.py`**（待开发对齐） | 导入/破坏 pack 手工 | 安装前可预览；损坏可定位 |
| `ECC-N03` | `Ready` | cross-harness doctor / diff | `test_plugin_compat_matrix.py`、`test_ecc_layout_cli.py` | `test_harness_doctor_diff.py`、`test_export_sync_diff.py` | 两 harness 手工 diff | 差分可读 |
| `ECC-N04` | `Design` | ingest **执行链**（文档/快照已交付） | `test_ecc_ingest_schema_snapshots.py` 等 | import/install 自动化（待立项） | 评审 | 执行面另立验收 |
| `ECC-N05` | `Explore` | operator / desktop | 现有无 | 无 | 原型 | 先判断是否立项 |

## 7. 原子级测试拆解（仅未完成）

### 7.1 模型接入原子测试

`MODEL-P0-D01`～`D14` 已迁至 [`TODOS_DONE_ARCHIVE.zh-CN.md`](TODOS_DONE_ARCHIVE.zh-CN.md) §4.1。

### 7.2 Claude Code 线原子测试

| 开发子任务 | 自动化覆盖 | 手工 / 真机覆盖 | 通过标准 |
|---|---|---|---|
| `CC-N03-D01` | `test_marketplace_manifest_cli.py` 覆盖 catalog schema 校验 | 检查生成 catalog 可读性 | catalog 可版本化、可解析 |
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
| `HM-N03-D01` | `test_api_status_routes.py` 覆盖 health/status/profiles | `curl` 读状态 | 状态字段稳定 |
| `HM-N03-D02` | OpenAPI snapshot test | 手工检查 schema 可读性 | schema 与实际路由一致 |
| `HM-N03-D03` | `test_api_auth_config.py` 覆盖 API/ops auth 组合 | 同时启动 api/ops | 安全策略一致 |
| `HM-N03-D04` | docs 示例命令 smoke | 按文档跑 `curl` 示例 | 文档命令可运行 |
| `HM-N04-D01` | `test_ops_apply_actions.py` 覆盖 preview/apply/audit contract | 浏览器确认 preview 页面 | 写动作先 preview |
| `HM-N04-D02` | `test_ops_apply_actions.py` 覆盖 2 到 3 个写动作 | 手工 apply 并查看状态变化 | 写动作真实生效 |
| `HM-N04-D03` | `test_ops_audit_log.py` 覆盖 audit record | 检查本地 audit 文件 | 可追踪操作者和结果 |
| `HM-N04-D04` | `test_ops_dashboard_html.py` 覆盖 pending/success/failed/diff 文案 | 浏览器操作 | UI 能看懂后果 |
| `HM-N06-D01` | 文档/矩阵检查 | 评审平台优先级 | 下一批平台排序明确 |
| `HM-N06-D02` | adapter contract test 可复用性检查 | 评审 auth/webhook/polling/media 差异 | 共用抽象明确 |
| `HM-N06-D03` | 暂无自动化 | PoC 评审 | 未立项平台不进入实现 |

**回归入口**：`HM-N02`～`HM-N11` 已交付原子的测试映射见 [`TODOS_DONE_ARCHIVE.zh-CN.md`](TODOS_DONE_ARCHIVE.zh-CN.md) §6；契约变更时再回写本页对应行。

### 7.4 Everything Claude Code 线原子测试

| 开发子任务 | 自动化覆盖 | 手工 / 真机覆盖 | 通过标准 |
|---|---|---|---|
| `ECC-N01-D01` | `test_catalog_snapshot_cli.py` 覆盖 schema 校验 | 打开 catalog 检查可读性 | catalog 稳定 |
| `ECC-N02-D03` | `test_asset_pack_import_export.py` 覆盖 import/install | 新 workspace 手工安装 | 安装前能预览影响 |
| `ECC-N02-D04` | `test_asset_pack_repair.py` 覆盖缺失/schema drift | 手工破坏 pack 后 repair | 能定位损坏原因 |
| `ECC-N03-D01` | `test_harness_doctor_diff.py` 覆盖 target inventory | 检查输出路径 | 支持目标清晰 |
| `ECC-N03-D02` | `test_export_sync_diff.py` 覆盖 home diff | 两个 harness home 手工 diff | add/update/skip/conflict 可读 |
| `ECC-N03-D03` | `test_harness_doctor_diff.py` 覆盖 compat drift | 构造不兼容资产 | 缺口定位到资产 |
| `ECC-N03-D04` | human/json snapshot | 自动化消费 JSON | 两种格式一致 |
| `ECC-N05-D01` | 文档范围检查 | 产品/开发/测试评审 | GUI 范围可控 |
| `ECC-N05-D02` | 如有 PoC，补 ops dashboard smoke | 打开本地 operator 原型 | 复用路径成立 |
| `ECC-N05-D03` | 发布风险 checklist | 评审升级/权限/日志 | 有 go/no-go 结论 |

## 8. 推荐测试顺序

1. `CC-N03`（**`D04`**）
2. `ECC-N02`（**`D03`/`D04`**）
3. `HM-N01`（**`D01`**）
4. `HM-N03` / `HM-N04`
5. `ECC-N03`
6. `CC-N04`
7. 契约变更时跑 [`TODOS_DONE_ARCHIVE.zh-CN.md`](TODOS_DONE_ARCHIVE.zh-CN.md) §6.2 所列已交付 Hermes 原子测试子集

## 9. 合入前统一命令

```powershell
python -m pytest -q cai-agent/tests
python scripts/smoke_new_features.py
$env:QA_SKIP_LOG='1'; python scripts/run_regression.py
```

## 自动验证记录

| 日期 | 任务 | 验证 | 记录 |
|---|---|---|---|
| 2026-04-26 | `DOC-AUTO-FINALIZE` | pytest -q -p no:cacheprovider cai-agent/tests/test_finalize_task_script.py: 1 passed | [`docs/qa/runs/task-finalize-20260426-194030-DOC-AUTO-FINALIZE.md`](qa/runs/task-finalize-20260426-194030-DOC-AUTO-FINALIZE.md) |
| 2026-04-26 | `ECC-N04-D03` | python -m pytest -q cai-agent/tests: 817 passed, 3 subtests passed<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | [`docs/qa/runs/task-finalize-20260426-203353-ECC-N04-D03.md`](qa/runs/task-finalize-20260426-203353-ECC-N04-D03.md) |
| 2026-04-26 | `CC-N02-D04` | python -m pytest -q cai-agent/tests/test_feedback_cli.py cai-agent/tests/test_feedback_export.py cai-agent/tests/test_feedback_bundle_cli.py cai-agent/tests/test_doctor_cli.py: PASS<br>python -m pytest -q cai-agent/tests: 820 passed, 3 subtests passed<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | [`docs/qa/runs/task-finalize-20260426-212531-CC-N02-D04.md`](qa/runs/task-finalize-20260426-212531-CC-N02-D04.md) |
| 2026-04-26 | `HM-N01-D02`, `HM-N01-D04`, `HM-N01-D05` | python -m pytest -q cai-agent/tests: PASS (825 passed, 3 subtests)<br>python scripts/smoke_new_features.py: PASS (NEW_FEATURE_CHECKS_OK) | [`docs/qa/runs/task-finalize-20260426-214419-HM-N01-D02-HM-N01-D04-HM-N01-D05.md`](qa/runs/task-finalize-20260426-214419-HM-N01-D02-HM-N01-D04-HM-N01-D05.md) |
