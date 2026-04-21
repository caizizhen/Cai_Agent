# 能力 parity 矩阵（维护中）

本表用于 **版本发布评审**：每一行对应「完全体」愿景中的一块能力；列 **状态** 取以下之一（可在 PR 中随功能更新勾选）。

| 状态代码 | 含义 |
|----------|------|
| `Done` | 已在本仓库默认路径落地 |
| `Next` | 已排入 [ROADMAP_EXECUTION.zh-CN.md](ROADMAP_EXECUTION.zh-CN.md) 的近期里程碑 |
| `MCP` | 不内置，以 **经文档认证的 MCP 配方** 作为等价能力（需在 `docs/` 或示例配置中可复现） |
| `OOS` | **Out of scope**：明确不做，或依赖封闭/商业能力（简短理由见备注） |

愿景分层见 [PRODUCT_VISION_FUSION.zh-CN.md](PRODUCT_VISION_FUSION.zh-CN.md)。

## L1 — 官方能力环（体验）

| 能力项 | 参考 | 状态 | 备注 |
|--------|------|------|------|
| 工作区文件读写与搜索 | claude-code | `Done` | `tools.py` + 沙箱 |
| 受限 Shell | claude-code | `Done` | 白名单 `run_command` |
| 只读 Git | claude-code | `Done` | |
| MCP 调用 | claude-code | `Done` | `mcp_list_tools` / `mcp_call_tool` |
| 计划 → 执行 | claude-code | `Done` | `plan` / `plan --json`（`plan_schema_version`）/ `run --plan-file` |
| 会话延续 | claude-code | `Done` | `run --save-session` / `continue` |
| 多步工作流 | claude-code / ECC | `Done` | `workflow`；任务看板类 UI 见下行 |
| 多模型 profile / TUI 面板 / `/use-model` / session `profile` 字段 | claude-code / ECC | `Done` | `[[models.profile]]` + `cai-agent models`；TUI `Ctrl+M` / `/models` 面板（列表、a/e/d/t）；`/status` 与 `--save-session` 含 `profile`；跨 provider 切换提示 `/compact`；见 [MODEL_SWITCHER_DEVPLAN.zh-CN.md](MODEL_SWITCHER_DEVPLAN.zh-CN.md) §4 |
| WebFetch（HTTPS 只读 GET） | claude-code | `Done` | 内置 `fetch_url` + `[fetch_url]` / `[permissions]`；见 [MCP_WEB_RECIPE.zh-CN.md](MCP_WEB_RECIPE.zh-CN.md) 作 MCP 并行方案 |
| WebSearch / 结构化搜索 API | claude-code | `Next` / `MCP` | 定案见 [WEBSEARCH_NOTEBOOK_MCP.zh-CN.md](WEBSEARCH_NOTEBOOK_MCP.zh-CN.md)（默认 MCP） |
| Notebook 编辑 | claude-code | `Next` / `MCP` | 同上 |
| 任务看板 / 富任务 UI | claude-code | `Next` | `board --json`（`board_v1`）内嵌 `observe` 与 `observe_schema_version`；与 `observe` 共用聚合 schema；见 [WEBSEARCH_NOTEBOOK_MCP.zh-CN.md](WEBSEARCH_NOTEBOOK_MCP.zh-CN.md) |
| 语音 / Bridge / 企业门控特性 | claude-code | `OOS` | 依赖官方封闭能力或单独商务 |

## L2 — 架构完备度（对照 analysis 文档骨架）

| 能力项 | 参考 | 状态 | 备注 |
|--------|------|------|------|
| Query 式主循环 | claude-code-analysis | `Done` | `graph.py` |
| 工具注册与权限 | claude-code-analysis | `Done` | `tools.py` + `[permissions]` |
| 会话与历史 | claude-code-analysis | `Done` / `Next` | 已落地：`workflow` 事件流、`run`/`continue` 的 `run_schema_version` + `events`、`observe` 汇总 `run_events_total`、`sessions_with_events`、逐文件 `events_count`；新增 `hooks` 执行结果状态摘要（stderr）与 release-ga 聚合门禁。TUI/全量 Dashboard 深化仍待办 |
| 上下文压缩策略 | claude-code-analysis | `Next` | 与 `[context]`、`observe` 联动深化 |
| 成本 / token 策略 | claude-code-analysis | `Next` | 由统计升级为可配置策略 |
| 钩子扩展 | claude-code-analysis | `Next` | 另含 `security_scan_*`、`memory_*`、`export_*`、`observe_*`、`cost_budget_*`；执行器与 `hooks.json` 深度集成仍待办 |

## L3 — ECC 式治理与跨 harness

| 能力项 | 参考 | 状态 | 备注 |
|--------|------|------|------|
| 质量门禁 | ECC / 官方 CI 习惯 | `Done` | `quality-gate` |
| 安全扫描 | ECC | `Done` | `security-scan` |
| 记忆 / 本能 | ECC | `Done` / `Next` | 已落地：`entries.jsonl` 写入前 **v1 schema** 校验；`memory nudge` schema 升级到 `1.1`（`threshold_policy` / `risk_score` / `trend`）+ `nudge-report` 趋势汇总。TTL/自动化提炼仍待办 |
| 成本预算 | ECC | `Done` / `Next` | `cost budget`；新增 `release-ga` 汇总 budget 与会话失败率门禁；策略深化见 L2 |
| 跨工具导出 | ECC | `Done` / `Next` | `export`；manifest 维度持续对齐 [CROSS_HARNESS_COMPATIBILITY.zh-CN.md](CROSS_HARNESS_COMPATIBILITY.zh-CN.md) |
| 可视化运营面板 | ECC | `Next` | P2+，见路线图 |
| 大规模社区技能库本体 | ECC | `MCP` / `Next` | 以导出格式与外部包渐进吸收，不阻塞核心发版 |

---

**维护约定**：发版前至少更新一行「`Next` → `Done`」或新增一行 `MCP` 配方文档链接；若降级为 `OOS` 须在备注中写清理由并在 [PRODUCT_GAP_ANALYSIS.zh-CN.md](PRODUCT_GAP_ANALYSIS.zh-CN.md) 发布门禁中备案。
