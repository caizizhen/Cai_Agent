# 开发 TODO（未完成项）

> 产品判断来源：[`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md)。测试对齐页：[`TEST_TODOS.zh-CN.md`](TEST_TODOS.zh-CN.md)。  
> **已完成项**（从本页拆出）：[`TODOS_DONE_ARCHIVE.zh-CN.md`](TODOS_DONE_ARCHIVE.zh-CN.md)；叙述型归档：[`COMPLETED_TASKS_ARCHIVE.zh-CN.md`](COMPLETED_TASKS_ARCHIVE.zh-CN.md)。  
> 低 token 当前开发入口：[`NEXT_ACTIONS.zh-CN.md`](NEXT_ACTIONS.zh-CN.md)。每次调整优先级或完成状态时，必须同步更新 `NEXT_ACTIONS`。

本页**仅列未完成**（`Ready` / `Design` / `Explore` / `Conditional` / `OOS`）。已交付的能力与原子任务见 **`TODOS_DONE_ARCHIVE.zh-CN.md`**。

## 1. 当前结论

截至 2026-04-27：

- 主干能力（模型、安装修复反馈、gateway、memory、tool、runtime、home sync、ingest 文档、plugins dry-run/drift 等）已交付；日常以回归与小步增强为主。
- 当前增量主线见下表与 [`NEXT_ACTIONS.zh-CN.md`](NEXT_ACTIONS.zh-CN.md)。
- 当前可开发功能池按能力级约 **9 条**：`Ready` 3 条（`CC-N03`、`ECC-N02`、`ECC-N03`），`Design` 4 条（`CC-N04`、`HM-N03`、`HM-N04`、`ECC-N04`），`Explore/Conditional/OOS` 约 6 条仅保留边界或预研，不进入默认实现。
- 本轮执行 TODO：`CC-N03-D04` **In progress**，目标是把 `plugins sync-home` 从 dry-run/drift 推进到安全 `--apply`，默认拒绝覆盖冲突，显式 `--force` 时先备份再替换。

### 1.1 当前开工队列

| 顺位 | 能力 | 状态 | 下一步原子任务 |
|---|---|---|---|
| 1 | `CC-N03` Plugin / marketplace / home sync | `Ready` | **`CC-N03-D02`/`D03` 已交付**（见归档）；下一 **`CC-N03-D04`** sync apply 保护 |
| 2 | `ECC-N02` asset pack 生命周期 | `Ready` | **`ECC-N02-D01`/`D02` 已交付**（见归档）；下一 **`ECC-N02-D03`/`D04`** |
| 3 | `HM-N01` Profile home | `Ready` | **`HM-N01-D02`～`D05`/`D03` 已交付**（见归档）；仍缺 **`HM-N01-D01`** |

状态：`Ready` 可直接开发；`Design` 先定契约；`Explore` 预研；`Conditional` 授权后；`OOS` 不做。

## 2. 使用方式

1. 先看 [PRODUCT_GAP_ANALYSIS.zh-CN.md](PRODUCT_GAP_ANALYSIS.zh-CN.md) 判断“为什么要做”。
2. 再看本页判断“做哪些、先后顺序、打开哪些代码文件”。
3. 最后看 [TEST_TODOS.zh-CN.md](TEST_TODOS.zh-CN.md) 判断“测什么、怎么验收”。

## 3. 模型接入最高优先级（MODEL-P0）

`MODEL-P0` 已全部完成；条目已迁至 [`TODOS_DONE_ARCHIVE.zh-CN.md`](TODOS_DONE_ARCHIVE.zh-CN.md) §3。证据：`COMPLETED_TASKS_ARCHIVE`、`ROADMAP_EXECUTION` §10。

## 4. Claude Code 线未完成项

| ID | 状态 | 优先级 | 功能 | 当前差距 | 主要代码入口 | 本轮目标 | 本轮不做 | 完成标准 |
|---|---|---|---|---|---|---|---|---|
| `CC-N03` | `Ready` | `P1` | Plugin / marketplace / home sync | 仍缺 **D04**（sync apply 保护）与可选 marketplace 叙事 | `plugin_registry.py`、`exporter.py`、`ecc_layout.py`、`__main__.py` | 落地 **D04**；可选 catalog（`CC-N03-D01`） | 不做公共付费 marketplace | 资产可安全同步；冲突可感知 |
| `CC-N04` | `Design` | `P1` | 更完整的 session / task / recap 体验 | 缺 long-session recap、resume 提示、任务过滤等 | `tui.py`、`tui_task_board.py`、`tui_session_strip.py`、`__main__.py` | recap / resume / 筛选 / restore 提示 | 不做远程控制 | 长会话可恢复上下文 |
| `CC-N05` | `Explore` | `P2` | 本地 Desktop / GUI 入口 | 仅 TUI / 轻 Web | `ops_http_server.py`、`ops_dashboard.py`、`tui.py` | 方案与 PoC | 不做跨平台原生发行版 | 有立项建议 |
| `CC-N06` | `OOS` | `P2` | 原生 WebSearch / Notebook | MCP 优先 | `mcp_presets.py`、`mcp_serve.py` | 维护 preset 路径 | 不做原生搜索 API | MCP 可用 |
| `CC-N07` | `Conditional` | `P3` | Remote / web / mobile / 云端 review | 默认不交付 | 新模块待定 | 授权后评估 | 默认不做封闭依赖 | 授权后立项 |

## 5. Hermes 线未完成项

| ID | 状态 | 优先级 | 功能 | 当前差距 | 主要代码入口 | 本轮目标 | 本轮不做 | 完成标准 |
|---|---|---|---|---|---|---|---|---|
| `HM-N01` | `Ready` | `P0` | Profiles 独立家目录 + alias | 仍缺 **`HM-N01-D01`**（profile home schema 深化） | `profiles.py`、`__main__.py`、`doctor.py`、`api_http_server.py`、`gateway_maps.py` | 补齐 **D01** 与联调硬验收 | 不做多机 profile 同步 | profile 状态隔离 |
| `HM-N03` | `Design` | `P1` | API server 扩路由 / OpenAPI / auth | 路由族、OpenAPI、auth 叙事仍待收口 | `api_http_server.py`、`ops_http_server.py`、`server_auth.py`、`doctor.py` | 扩只读路由、OpenAPI 草案、auth 文档 | 不一次性铺满 OpenAI API | 可管理、可文档化 |
| `HM-N04` | `Design` | `P1` | Dashboard 安全可写化 | 以只读 / dry-run 为主 | `ops_dashboard.py`、`ops_http_server.py`、`gateway_maps.py`、`doctor.py` | preview/apply/audit、少量写动作 | 不做公网管理台 | 写动作可审计 |
| `HM-N06` | `Explore` | `P2` | Gateway 第二批平台 | 平台矩阵与预研 | 相关新模块待定 | 优先级与抽象 | 不一轮落地全部 | 有方案 |
| `HM-N11` | `Conditional` | `P3` | Cloud runtime backends | 文档与接口基线已交付；真实云后端授权后 | `runtime/registry.py`、`docs/CLOUD_RUNTIME_OOS*.md` | 未授权不实现云执行 | 默认不云交付 | 授权后立项 |

## 6. ECC 线未完成项

| ID | 状态 | 优先级 | 功能 | 当前差距 | 主要代码入口 | 本轮目标 | 本轮不做 | 完成标准 |
|---|---|---|---|---|---|---|---|---|
| `ECC-N02` | `Ready` | `P1` | asset pack import/repair | 缺 **D03/D04** | `exporter.py`、`ecc_layout.py`、`plugin_registry.py` | import/install 与 repair | 不做复杂依赖求解 | 可打包、导入、修复 |
| `ECC-N03` | `Ready` | `P1` | cross-harness doctor / diff | target inventory、结构化 diff、compat 深化 | `exporter.py`、`plugin_registry.py`、`doctor.py`、`ecc_layout.py` | target-aware doctor、home diff、compat drift | 不做全 harness 安装器 | 用户可读懂差分 |
| `ECC-N04` | `Design` | `P2` | ingest 执行链 | **D01～D03** 文档与快照已交付；缺 **import/install 产品化** | `docs/schema`、`plugin_registry.py` | 与 `ECC-N02` 衔接的执行链 | 不做社区市场运营 | 执行链可测 |
| `ECC-N05` | `Explore` | `P2` | operator / desktop 控制面 | 评估阶段 | `ops_dashboard.py`、`ops_http_server.py` | 技术路径评估 | 不做大 GUI 重构 | 有立项建议 |

## 7. 原子级开发拆解（仅未完成）

### 7.1 模型接入原子任务

`MODEL-P0-D01`～`D14` 已归档，见 [`TODOS_DONE_ARCHIVE.zh-CN.md`](TODOS_DONE_ARCHIVE.zh-CN.md) §3。

### 7.2 Claude Code 线原子任务

| 子任务 ID | 对应能力 | 交付物 | 主要入口 | 验收点 |
|---|---|---|---|---|
| `CC-N03-D01` | Plugin / marketplace / home sync | 本地 catalog schema，描述 plugin / skill / hook / rule 资产 | `plugin_registry.py`、`ecc_layout.py` | catalog 可生成、可校验、可版本化 |
| `CC-N03-D04` | Plugin / marketplace / home sync | sync apply 的覆盖保护、备份、回滚提示 | `plugin_registry.py`、`exporter.py` | 默认不覆盖用户手改内容，冲突需显式确认 |
| `CC-N04-D01` | Session / task / recap | 长会话 recap 生成与持久化 | `tui_session_strip.py`、`__main__.py` | resume 前能拿到短摘要 |
| `CC-N04-D02` | Session / task / recap | resume hints | `tui.py`、`tui_task_board.py` | 重新进入会话能看到下一步建议 |
| `CC-N04-D03` | Session / task / recap | `/tasks` 过滤、状态分组、最近变更高亮 | `tui_task_board.py` | 长任务列表可扫描、可定位 |
| `CC-N04-D04` | Session / task / recap | session restore UI 文案和命令出口 | `tui.py`、`__main__.py` | 用户不需要重读历史就能继续工作 |
| `CC-N05-D01` | Desktop / GUI 探索 | 本地 GUI 方案文档 | `ops_http_server.py`、`ops_dashboard.py`、`docs/` | 输出是否立项建议 |
| `CC-N05-D02` | Desktop / GUI 探索 | 本地 dashboard 启动体验 PoC | `ops_http_server.py`、`__main__.py` | 非技术用户能打开本地界面 |
| `CC-N05-D03` | Desktop / GUI 探索 | GUI 包装风险清单 | `docs/` | 风险能被产品/开发共同评估 |
| `CC-N06-D01` | MCP 替代路径 | WebSearch / Notebook 的 MCP preset 健康检查 | `mcp_presets.py`、`mcp_serve.py` | 替代路径可被 doctor 发现 |
| `CC-N06-D02` | MCP 替代路径 | 文档明确“原生不做、MCP 优先”的边界 | `docs/` | 用户不会误以为缺失是 bug |
| `CC-N07-D01` | Remote / cloud / mobile 条件项 | 需求触发模板 | `docs/` | 未授权前不进入实现 |

### 7.3 Hermes 线原子任务

| 子任务 ID | 对应能力 | 交付物 | 主要入口 | 验收点 |
|---|---|---|---|---|
| `HM-N01-D01` | Profiles | profile home schema，定义 config/session/memory/gateway 的隔离目录 | `profiles.py`、`doctor.py` | 不同 profile 的状态不串 |
| `HM-N03-D01` | API 扩展 | `/health`、`/v1/status`、`/v1/profiles` 等状态路由 | `api_http_server.py` | ops 和外部工具能读状态 |
| `HM-N03-D02` | API 扩展 | OpenAPI schema 草案或 machine-readable route manifest | `api_http_server.py`、`docs/` | 路由可文档化、可快照测试 |
| `HM-N03-D03` | API 扩展 | API 与 `ops serve` auth 配置收口 | `api_http_server.py`、`ops_http_server.py`、`server_auth.py` | **部分落地**；与扩路由、OpenAPI、运维文档完整收口仍待 |
| `HM-N03-D04` | API 扩展 | curl / client 示例和故障排查文档 | `docs/` | 开发者能按文档接入 |
| `HM-N04-D01` | Dashboard 可写化 | dashboard action contract：`preview` / `apply` / `audit` | `ops_dashboard.py`、`ops_http_server.py` | 每个写动作必须先 preview |
| `HM-N04-D02` | Dashboard 可写化 | 首批真实写动作 2～3 个 | `ops_http_server.py`、`gateway_maps.py`、`profiles.py` | 写动作可回归、可回滚或可修复 |
| `HM-N04-D03` | Dashboard 可写化 | audit log | `ops_http_server.py`、`doctor.py` | 出问题能追踪 |
| `HM-N04-D04` | Dashboard 可写化 | UI 状态：pending、success、failed、dry-run diff | `ops_dashboard.py` | 浏览器里能看懂动作后果 |
| `HM-N06-D01` | Gateway 第二批 | 平台优先级矩阵 | `docs/` | 明确下一批先做什么 |
| `HM-N06-D02` | Gateway 第二批 | adapter 层差异点清单 | `gateway_platforms.py`、`docs/` | 能判断哪些平台共用实现 |
| `HM-N06-D03` | Gateway 第二批 | 第二批平台 PoC 选择标准 | `docs/` | 未立项平台不会挤占 P0/P1 |

### 7.4 Everything Claude Code 线原子任务

| 子任务 ID | 对应能力 | 交付物 | 主要入口 | 验收点 |
|---|---|---|---|---|
| `ECC-N01-D01` | home sync / catalog | local catalog schema，统一描述 rules/skills/hooks/plugins | `plugin_registry.py`、`ecc_layout.py` | catalog 可校验、可导出 |
| `ECC-N02-D03` | Asset pack | import/install pack，写入目标 workspace/home | `plugin_registry.py`、`ecc_layout.py` | 安装前能预览影响 |
| `ECC-N02-D04` | Asset pack | pack repair，检测缺失文件、schema drift、兼容性问题 | `doctor.py`、`exporter.py` | 资产包坏了能定位原因 |
| `ECC-N03-D01` | cross-harness doctor | target inventory | `ecc_layout.py`、`doctor.py` | 输出对开发和用户都可读 |
| `ECC-N03-D02` | cross-harness doctor | home diff | `exporter.py`、`doctor.py` | 清楚显示 add/update/skip/conflict |
| `ECC-N03-D03` | cross-harness doctor | compat drift | `plugin_registry.py`、`ecc_layout.py` | 兼容问题可定位到资产 |
| `ECC-N03-D04` | cross-harness doctor | human/json 双格式报告 | `doctor.py`、`__main__.py` | CLI 和自动化都能消费 |
| `ECC-N05-D01` | operator / desktop | operator console 范围说明 | `ops_dashboard.py`、`docs/` | 避免 GUI 范围无限扩张 |
| `ECC-N05-D02` | operator / desktop | 复用现有 ops dashboard 的 PoC 路径 | `ops_dashboard.py`、`ops_http_server.py` | 有低成本演进方案 |
| `ECC-N05-D03` | operator / desktop | 包装/发布/升级风险评估 | `docs/` | 决定是否进入正式项目 |

## 8. 推荐开发顺序

1. `CC-N03`（**`D04`**：`plugins sync-home --apply` 保护）
2. `HM-N01`（**`D01`**：profile home schema）
3. `HM-N03` / `HM-N04`（API / dashboard）
4. `ECC-N02`（**`D03`/`D04`**）
5. `ECC-N03`（doctor / diff 深化）
6. `CC-N04`（session / recap）
7. `HM-N06`（Explore）/ `HM-N11`（Conditional 云 runtime）

### 8.1 第一批建议直接开工的原子任务

1. `CC-N03-D04`
2. `CC-N03-D01`（可选，与 catalog 叙事并行）
3. `HM-N01-D01`
4. `ECC-N02-D03`
5. `ECC-N02-D04`
6. `ECC-N03-D01`
7. `ECC-N03-D02`

## 9. OOS / 条件立项边界

| ID | 当前结论 | 替代路径 |
|---|---|---|
| `CC-N06` | `OOS` | 继续走 MCP presets / onboarding |
| `CC-N07` | `Conditional` | 只有明确授权后再评估 |
| `HM-N11` | `Conditional` | 继续 local / docker / ssh 默认路径 |

## 10. 开发统一要求

每个任务进入实现前，至少补齐：

1. 一处主代码入口。
2. 一处自动化验证入口。
3. 一处文档回写入口。
4. 一条“本轮不做什么”的边界说明。

需要同步回写的主文档通常包括：`PRODUCT_PLAN`、`PRODUCT_GAP_ANALYSIS`、`ROADMAP_EXECUTION`、`PARITY_MATRIX`、`TEST_TODOS`、相关专题文档。

## 11. 当前 QA 基线

2026-04-26 在仓库根 `D:\gitrepo\Cai_Agent` 实测结果：

| 检查项 | 命令 | 结果 |
|---|---|---|
| 全量单测 | `python -m pytest -q cai-agent/tests` | **834 passed**, **3 subtests passed** |
| 冒烟 | `python scripts/smoke_new_features.py` | **PASS**，输出 `NEW_FEATURE_CHECKS_OK` |
| 回归 | `QA_SKIP_LOG=1 python scripts/run_regression.py` | **PASS**，compileall / unittest / smoke / CLI 子集全绿 |
