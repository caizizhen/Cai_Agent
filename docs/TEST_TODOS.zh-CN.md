# 测试起步清单（基于 2026-04-24 实测）

这份清单给测试同学和开发自测回答 3 个问题：

1. **当前仓库的自动化基线是否健康？**
2. **第一批优先任务分别该补哪些测试？**
3. **哪些要补自动化，哪些必须走手工 / 真机 / 发版门禁？**

产品与排期边界仍以：

- [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md)
- [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md)
- [`ISSUE_BACKLOG.zh-CN.md`](ISSUE_BACKLOG.zh-CN.md)

为准；本页只做测试执行翻译。

---

## 1. 当前测试基线

2026-04-25 在仓库根 `D:\gitrepo\Cai_Agent` 实测结果：

| 检查项 | 命令 | 结果 |
|---|---|---|
| 全量单测 | `python -m pytest -q cai-agent/tests` | **714 passed**, **3 subtests passed** |
| 冒烟 | `python scripts/smoke_new_features.py` | **PASS**，输出 `NEW_FEATURE_CHECKS_OK` |
| 回归 | `QA_SKIP_LOG=1 python scripts/run_regression.py` | **PASS**，compileall / unittest / smoke / CLI 子集全绿 |

**结论**：当前主线测试基线健康，可以在不修红的前提下继续推进第一批开发任务。

---

## 2. 测试统一约定

开始测试或配合开发前，统一遵守：

1. 不单独维护另一套“测试优先级”，一律跟 [`DEVELOPER_TODOS.zh-CN.md`](DEVELOPER_TODOS.zh-CN.md) 中仍未完成或未来立项的任务走；已完成任务证据归档到 [`COMPLETED_TASKS_ARCHIVE.zh-CN.md`](COMPLETED_TASKS_ARCHIVE.zh-CN.md)。
2. 每项任务至少补齐下面四层中的两层：
   - pytest 子集
   - smoke / regression 路径
   - 手工场景
   - 发版门禁 / runbook
3. 凡是改动 CLI JSON、schema_version、帮助文本、状态字段的任务，必须补自动化。
4. 凡是改动 gateway、dashboard、安装升级、值班/发版流程的任务，必须补手工或真机检查。

---

## 3. 测试分层

| 层级 | 目的 | 典型入口 |
|---|---|---|
| `L1` pytest 子集 | 保证模块、CLI、schema、失败路径可回归 | `cai-agent/tests/test_*.py` |
| `L2` smoke | 保证关键 CLI 契约仍然可调用 | `scripts/smoke_new_features.py` |
| `L3` regression | 保证近期能力不会在主链路回退 | `scripts/run_regression.py` |
| `L4` 手工 / 真机 | 保证真实交互、浏览器、平台接入、安装体验可用 | `docs/qa/*testplan*`、runbook |
| `L5` 发版门禁 | 保证对外发版前的产品、文档、契约一致 | [`docs/qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md`](qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md) |

---

## 4. 第一批测试待办

### 4.1 第一优先组

| ID | 对应开发项 | 现有测试入口 | 本轮测试 To-do | 手工 / 真机 | 完成定义 |
|---|---|---|---|---|---|
| `REL-01a` | 收口 release-ga / doctor / changelog 回写流程 | `test_release_ga_cli.py`、`test_doctor_cli.py`、`test_release_changelog_cli.py`、`test_feedback_cli.py`、`test_feedback_export.py`、`test_metrics_jsonl.py` | 已补 `release-ga` / `doctor --json` 同源断言、`release-changelog --json --semantic` smoke、文本模式 writeback targets 断言 | 走一遍 [`T7_RELEASE_GATE_CHECKLIST.zh-CN.md`](qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md) 的最小链路 | 发版闭环相关输出可自动回归，且手工 gate 路径清晰 |
| `CC-01a` | 收口 MCP 预设与 WebSearch/Notebook 接入入口 | `test_cli_misc.py`、`test_mcp_serve_roundtrip.py`、`scripts/smoke_new_features.py` | 已补 `mcp-check --preset websearch/notebook` 的帮助文案、模板输出、错误提示与 quickstart 断言，smoke 也覆盖 preset 输出字段 | 按 [`WEBSEARCH_NOTEBOOK_MCP.zh-CN.md`](WEBSEARCH_NOTEBOOK_MCP.zh-CN.md) 手工走一次 preset 接入路径 | 新用户可按文档 + CLI 提示完成接入，错误时有明确 fallback |
| `CC-02a` | 梳理安装、更新与版本提示体验 | `test_init_presets.py`、`test_doctor_cli.py`、`test_metrics_jsonl.py` | 已补 `init` / onboarding 相关 JSON 与文本行为断言，`doctor` 同步暴露安装/升级指引 | 手工从安装 -> `init` -> `doctor` -> `run` 走一遍 | 首次使用与升级路径可验证，不只停留在文档表述 |

### 4.2 第二优先组

| ID | 对应开发项 | 现有测试入口 | 本轮测试 To-do | 手工 / 真机 | 完成定义 |
|---|---|---|---|---|---|
| `HM-01a` | 定义 profile 数据模型与持久化结构 | `test_model_profiles_config.py`、`test_model_profiles_cli.py`、`test_tui_model_panel.py`、`test_model_routing.py`、`test_context_usage_bar.py`、`test_llm_factory_dispatch.py` | 已补 `profile_contract_v1` 在 `doctor --json` / `models list --json` 的断言，并把同源信息接进 TUI `/status` | 手工检查 TUI `/models` 与 `/status` 一致性 | profile 契约稳定，CLI/TUI/配置写回不分叉 |
| `HM-03a` | 把 Discord 从 MVP 推到生产路径 | `test_gateway_discord_slash_commands.py`、`test_gateway_discord_slack_cli.py`、`test_gateway_maps_summarize.py`、`test_doctor_cli.py` | 已补 **`gateway discord health`**、**`register-commands`/`list-commands`**（无 Token exit 2）、**`discord_gateway_health_v1`** 单测、**`doctor` `discord_map_summary`** 断言；**`smoke_new_features`** 覆盖 **discord list/health** | 真机走 **serve-polling** + 可选 Slash 注册 | 主路径 CLI 与排障文档可回归；真机消息链路仍建议手工值班验证 |
| `HM-04` | 统一 ops/gateway/status 聚合载荷 + 动态只读 dashboard | `test_ops_dashboard_html.py`、`test_ops_http_server.py`、`test_ops_gateway_skills_cli.py`、`scripts/smoke_new_features.py` | 已补 `gateway_summary_v1` 同源字段断言、`ops serve` / `dashboard/events` / `live_mode=sse|poll` 覆盖，并扩了 smoke | 浏览器手工打开 `ops serve` 或 HTML 输出，确认动态刷新消费体验 | 只读运营面板相关载荷与动态刷新路径都可稳定消费，不会多套口径打架 |
| `HM-05a` | 补齐 user-model store/query/learn 主链路 | `test_user_model_store.py`、`test_memory_user_model_export.py`、`test_memory_user_model_store_cli.py`、`test_gateway_user_model_skills_evolution.py`、`scripts/smoke_new_features.py` | 已补 **`store init/list`**、**`learn`/`query`**、**`export --with-store`** 与空 belief exit **`2`**；smoke 串 **store→learn→query→list→export** | 手工检查空工作区、已有 overlay、异常输入三类场景 | SQLite store 与 bundle 可选快照可回归 |
| `ECC-01a` | 统一 rules/skills/hooks 资产目录与模板 | `test_ecc_layout_cli.py`、`test_hooks_cli.py`、`test_hook_runtime.py`、… | 已补 **`ecc layout`/`scaffold`** JSON 与 **`ecc_layout`** 路径单测；smoke 含 **`ecc layout`** | 手工跑一次 **`ecc scaffold`** 后检查目录 | 约定集中在 **`ecc_asset_layout_v1`** + **`CROSS_HARNESS`** 表 |
| `ECC-02a` | 把 routing/profile/budget 变成稳定产品路径 | `test_model_routing.py`、`test_cli_misc.py`（cost budget）、`test_cost_aggregate.py`、`test_factory_routing_and_security.py`、`scripts/smoke_new_features.py` | 已补 **`routing-test`** 文本模式、JSON **`explain`**；**`cost budget`** 的 **`explain`** / **`active_profile_id`**；smoke 校验 budget 载荷 | 手工对照 TOML 跑 **`routing-test`** 与 **`cost budget`** | 路由/预算 CLI 有可回归解释块 |

---

## 5. 真机 / 手工补测清单

这几类场景不建议只靠自动化：

| 场景 | 为什么要手工 | 参考文档 |
|---|---|---|
| Discord / Slack 接入 | 涉及平台权限、签名、真实消息链路 | `docs/GATEWAY_*.zh-CN.md`、`docs/qa/*gateway*` |
| `ops serve` / HTML 面板 | 浏览器消费、刷新体验、只读路由体验 | [`OPS_DYNAMIC_WEB_API.zh-CN.md`](OPS_DYNAMIC_WEB_API.zh-CN.md) |
| 安装 / 升级 / onboarding | 用户视角路径长，文档和 CLI 提示要一起看 | [`ONBOARDING.zh-CN.md`](ONBOARDING.zh-CN.md) |
| 发版闭环 | 涉及文档回写、CHANGELOG、Parity、T7 勾选 | [`docs/qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md`](qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md) |

---

## 6. 推荐测试分工

如果开发与测试并行，建议这么拆：

| 测试线 | 建议任务 | 主要文件 |
|---|---|---|
| CLI / Release QA | `REL-01a`、`CC-01a`、`CC-02a` | `test_release_ga_cli.py`、`test_doctor_cli.py`、`test_release_changelog_cli.py`、`test_cli_misc.py`、`test_init_presets.py`、smoke/regression |
| Profiles / Routing QA | `HM-01a`、`ECC-02a` | `test_model_profiles_*`、`test_model_routing.py`、`test_cost_aggregate.py`、`test_llm_factory_dispatch.py` |
| Gateway / Ops QA | `HM-03a`、`HM-04a` | `test_gateway_*`、`test_ops_*`、相关 runbook |
| Memory / Ecosystem QA | `HM-05a`、`ECC-01a` | `test_user_model_store.py`、`test_memory_user_model_export.py`、`test_hooks_*`、`test_skills_*` |

---

## 7. 每项测试任务的最小模板

测试开工时，建议至少拆成这 5 步：

1. **确定覆盖层级**
   - 这次要补 pytest、smoke、regression、手工中的哪几层
2. **补 happy path**
   - 主路径必须先能验证通过
3. **补 fail path**
   - 至少补一条最可能回退或误用的失败场景
4. **补文档入口**
   - 若测试方式有变化，更新 testplan、runbook 或主文档
5. **补回归命令**
   - 确保合入前别人知道该跑什么

---

## 8. 建议测试顺序

最推荐的测试跟进顺序：

1. `REL-01a`
2. `CC-01a`
3. `CC-02a`
4. `HM-01a`
5. `HM-03a`
6. `HM-04a`
7. `HM-05a`
8. `ECC-01a`
9. `ECC-02a`

如果只打算先支持一个 Sprint，建议先覆盖前 3 到 5 项。

---

## 9. 合入前统一测试命令

每项任务合入前，至少执行：

```powershell
& 'C:\Users\win11\AppData\Local\Programs\Python\Python313\python.exe' -m pytest -q cai-agent/tests
& 'C:\Users\win11\AppData\Local\Programs\Python\Python313\python.exe' scripts/smoke_new_features.py
$env:QA_SKIP_LOG='1'; & 'C:\Users\win11\AppData\Local\Programs\Python\Python313\python.exe' scripts/run_regression.py
```

如果改动只影响局部模块，可以先跑相关 pytest 子集；但合入前建议至少补一遍 smoke。
