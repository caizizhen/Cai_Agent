# 开发起步清单（基于 2026-04-24 实测）

这份清单给开发同学回答 3 个问题：

1. **当前仓库能不能开始开发？**
2. **先做哪几项最划算？**
3. **每项应该从哪些文件入手，做完怎么验收？**

产品与排期边界仍以：

- [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md)
- [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md)
- [`ISSUE_BACKLOG.zh-CN.md`](ISSUE_BACKLOG.zh-CN.md)

为准；本页只做开发执行翻译。

---

## 1. 当前测试结论

2026-04-24 在仓库根 `D:\gitrepo\Cai_Agent` 实测结果：

| 检查项 | 命令 | 结果 |
|---|---|---|
| 全量单测 | `python -m pytest -q cai-agent/tests` | **620 passed**, **3 subtests passed** |
| 冒烟 | `python scripts/smoke_new_features.py` | **PASS**，输出 `NEW_FEATURE_CHECKS_OK` |
| 回归 | `QA_SKIP_LOG=1 python scripts/run_regression.py` | **PASS**，compileall / unittest / smoke / CLI 子集全绿 |

**结论**：当前主线可继续开发，暂时没有“先修红再开发”的阻塞项。

---

## 2. 开发统一约定

开始开发前统一做这几件事：

1. 先看本页的“第一批任务”，不要跳着做 `Explore` 项。
2. 开发前跑一次：
   - `python -m pytest -q cai-agent/tests`
   - `python scripts/smoke_new_features.py`
3. 开发完成后至少回归：
   - 相关 pytest 子集
   - `python scripts/smoke_new_features.py`
   - 必要时 `QA_SKIP_LOG=1 python scripts/run_regression.py`
4. 合入前至少回写：
   - `PRODUCT_PLAN`
   - `PRODUCT_GAP_ANALYSIS`
   - `PARITY_MATRIX`
   - `CHANGELOG`

---

## 3. 第一批直接开干

这 9 项已经按“最适合现在进入开发”的顺序排好。

### 3.1 第一优先组

| ID | 任务 | 为什么先做 | 主要代码入口 | 主要文档入口 | 完成定义 | 验证 |
|---|---|---|---|---|---|---|
| `REL-01a` | 收口 release-ga / doctor / changelog 回写流程 | 发版闭环越晚补，后面维护成本越高 | `cai-agent/src/cai_agent/__main__.py`、`doctor.py`、`feedback.py`、`changelog_sync.py`、`changelog_semantic.py` | `CHANGELOG_SYNC.zh-CN.md`、`docs/qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md` | 发版前检查路径统一，维护者不再靠经验补流程 | `doctor`、smoke、T7 checklist |
| `CC-01a` | 收口 MCP 预设与 WebSearch/Notebook 接入入口 | 这是 Claude Code 体验线里最容易快速收口的一项 | `cai-agent/src/cai_agent/__main__.py`（`mcp-check`）、`scripts/smoke_new_features.py` | `WEBSEARCH_NOTEBOOK_MCP.zh-CN.md`、`ONBOARDING.zh-CN.md` | 用户能靠 CLI 帮助和文档完成 preset 检查和模板接入 | `mcp-check --preset websearch/notebook` |
| `CC-02a` | 梳理安装、更新与版本提示体验 | 首次使用成本决定后面所有反馈质量 | `cai-agent/src/cai_agent/__main__.py`（`init` / 帮助）、`templates/cai-agent.example.toml`、`templates/cai-agent.starter.toml` | `README.md`、`README.zh-CN.md`、`ONBOARDING.zh-CN.md` | 新用户能从安装走到 `doctor` 和首次 `run`，升级用户知道去哪里看差异 | walkthrough 一遍 onboarding |

### 3.2 第二优先组

| ID | 任务 | 为什么现在做 | 主要代码入口 | 主要文档入口 | 完成定义 | 验证 |
|---|---|---|---|---|---|---|
| `HM-01a` | 定义 profile 数据模型与持久化结构 | 后续 `/models`、`/status`、路由、API 都会依赖它 | `config.py`、`profiles.py`、`__main__.py`、`doctor.py`、`tui_model_panel.py`、`tui.py` | `ISSUE_BACKLOG.zh-CN.md`、`MODEL_ROUTING_RULES.zh-CN.md` | profile 契约稳定，后续实现不再口径分叉 | schema review + 相关 pytest |
| `HM-03a` | 把 Discord 从 MVP 推到生产路径 | 多平台 gateway 是 Hermes 线里最能体现产品差异的一项 | `gateway_discord.py`、`gateway_maps.py`、`gateway_platforms.py`、`doctor.py` | `GATEWAY_DISCORD_TELEGRAM_PARITY.zh-CN.md` | Discord 主路径可接入、可排障、可值班 | gateway smoke + `doctor` |
| `HM-04a` | 统一 ops/gateway/status 聚合载荷 | Dashboard 再往前做，必须先解决多套状态源问题 | `ops_dashboard.py`、`ops_http_server.py`、`board_state.py`、`__main__.py` | `OPS_DYNAMIC_WEB_API.zh-CN.md` | `board` / `ops` / gateway 状态字段同源 | JSON snapshot + 本地消费检查 |
| `HM-05a` | 补齐 user-model store/query/learn 主链路 | 这是记忆线里最关键的“从已有功能走向产品化”一步 | `user_model.py`、`user_model_store.py`、`__main__.py` | `docs/rfc/HONCHO_USER_MODEL_EPIC.zh-CN.md`、`MEMORY_TTL_CONFIDENCE_POLICY.zh-CN.md` | 用户模型具备最小闭环：抽取、存储、查询、学习、导出 | pytest + smoke |
| `ECC-01a` | 统一 rules/skills/hooks 资产目录与模板 | 治理线要落地，先让团队知道资产怎么组织 | `rules.py`、`skills.py`、`hook_runtime.py`、`hooks.py`、`skill_registry.py`、`exporter.py` | `CROSS_HARNESS_COMPATIBILITY.zh-CN.md` | 新增资产时，团队知道放哪、怎么复用、怎么导出 | sample asset + 文档走查 |
| `ECC-02a` | 把 routing/profile/budget 变成稳定产品路径 | 当前能力已存在，但还不够“可解释、可操作” | `model_routing.py`、`cost_aggregate.py`、`config.py`、`doctor.py`、`__main__.py` | `MODEL_ROUTING_RULES.zh-CN.md`、`CONTEXT_AND_COMPACT.zh-CN.md` | 使用者能理解并验证路由和预算行为 | CLI smoke + JSON 输出检查 |

---

## 4. 推荐分工

如果团队要并行开工，建议按下面 4 条线拆：

| 开发线 | 建议任务 | 主要文件 |
|---|---|---|
| CLI / Docs / Release | `REL-01a`、`CC-01a`、`CC-02a` | `__main__.py`、`doctor.py`、README、onboarding、release docs |
| Profiles / Routing | `HM-01a`、`ECC-02a` | `config.py`、`profiles.py`、`model_routing.py`、`doctor.py`、`tui*.py` |
| Gateway / Ops | `HM-03a`、`HM-04a` | `gateway_discord.py`、`gateway_maps.py`、`ops_dashboard.py`、`ops_http_server.py` |
| Memory / Ecosystem | `HM-05a`、`ECC-01a` | `user_model*.py`、`skills.py`、`rules.py`、`hook_runtime.py`、`exporter.py` |

并行时注意：

- `HM-01a` 和 `ECC-02a` 都会碰 `config.py` / `doctor.py`，最好同一个人或同一小组负责。
- `REL-01a` 和 `CC-02a` 都会碰 README / onboarding，避免并行改同一段。
- `HM-03a` 和 `HM-04a` 可以并行，但要先约好 gateway 状态字段命名。

---

## 5. 每项任务的最小子任务模板

开发开工时，不要直接写成一句大标题，建议拆成下面这种格式：

1. **契约**
   - 先定义 schema、字段、状态码、帮助文案或 runbook 结构
2. **实现**
   - 再改 `__main__.py`、核心模块和必要数据结构
3. **测试**
   - 补 pytest
   - 更新 `scripts/smoke_new_features.py` 或 regression 路径
4. **文档**
   - 回写主文档和相关专题文档

---

## 6. 建议开发顺序

最推荐的开工顺序：

1. `REL-01a`
2. `CC-01a`
3. `CC-02a`
4. `HM-01a`
5. `HM-03a`
6. `HM-04a`
7. `HM-05a`
8. `ECC-01a`
9. `ECC-02a`

如果你只打算先拉一个开发 Sprint，建议只放前 3 到 5 项。

---

## 7. 开发完成后的统一回归

每项任务合入前，至少执行：

```powershell
& 'C:\Users\win11\AppData\Local\Programs\Python\Python313\python.exe' -m pytest -q cai-agent/tests
& 'C:\Users\win11\AppData\Local\Programs\Python\Python313\python.exe' scripts/smoke_new_features.py
$env:QA_SKIP_LOG='1'; & 'C:\Users\win11\AppData\Local\Programs\Python\Python313\python.exe' scripts/run_regression.py
```

若只改局部模块，允许先跑子集，但合入前建议至少补一遍 smoke。
