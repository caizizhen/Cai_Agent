# 能力 parity 矩阵（维护中）

本表用于 **版本发布评审**：每一行对应「完全体」愿景中的一块能力；列 **状态** 取以下之一（可在 PR 中随功能更新勾选）。

| 状态代码 | 含义 |
|----------|------|
| `Done` | 已在本仓库默认路径落地 |
| `Next` | 已排入 [PRODUCT_PLAN.zh-CN.md](PRODUCT_PLAN.zh-CN.md) 的近期里程碑 |
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
| WebFetch（HTTPS 只读 GET） | claude-code | `Done` | 内置 `fetch_url` + `[fetch_url]` / `[permissions]`；**`max_redirects`**（**1–50**，默认 **20**）/ **`CAI_FETCH_URL_MAX_REDIRECTS`**；**解析后 IP 校验**（反 DNS rebinding）+ **`allow_private_resolved_ips`** 逃逸；工具表见 [TOOLS_REGISTRY.zh-CN.md](TOOLS_REGISTRY.zh-CN.md)（**`gen_tools_registry_zh.py`** 生成）；见 [MCP_WEB_RECIPE.zh-CN.md](MCP_WEB_RECIPE.zh-CN.md) 作 MCP 并行方案 |
| WebSearch / 结构化搜索 API | claude-code | `Next` / `MCP` | 定案见 [WEBSEARCH_NOTEBOOK_MCP.zh-CN.md](WEBSEARCH_NOTEBOOK_MCP.zh-CN.md)（默认 MCP）；新增 `mcp-check --preset websearch --list-only` 预检输出（命中/缺失关键词 + fallback_hint），并支持 `--print-template` 生成最小配置片段 |
| Notebook 编辑 | claude-code | `Next` / `MCP` | 同上；新增 `mcp-check --preset notebook --list-only` 预检输出（含 fallback_hint），并支持 `--print-template` 生成最小配置片段 |
| 任务看板 / 富任务 UI | claude-code | `Done` / `Next` | 已落地 `board --json`（`board_v1`）内嵌 `observe` 与 `observe_schema_version`，支持 `--failed-only` / `--task-id` / `--status` 组合过滤、`--failed-top` 最近失败 TopN 配置，新增 `failed_summary.recent`（按最近会话优先）、`status_summary` 状态分组统计、`group_summary`（模型/任务 TopN 聚合）以及 `trend_summary`（recent vs baseline 时间窗对比）；TUI **`/tasks`**（**`render_task_board_markup`**）已与 **`board`** 默认 observe 摘要及 **`schedule list`** enrich 对齐；更完整富 UI（实时筛选器、子任务交互）仍在后续迭代 |
| 语音 / Bridge / 企业门控特性 | claude-code | `OOS` | 依赖官方封闭能力或单独商务 |

## L2 — 架构完备度（对照 analysis 文档骨架）

| 能力项 | 参考 | 状态 | 备注 |
|--------|------|------|------|
| Query 式主循环 | claude-code-analysis | `Done` | `graph.py` |
| 工具注册与权限 | claude-code-analysis | `Done` | `tools.py` + `[permissions]` |
| 会话与历史 | claude-code-analysis | `Done` | 已落地：`workflow` 事件流、`run`/`continue` 的 `run_schema_version=1.1` + `events` 信封（`run_events_envelope_v1`）；`observe` 汇总 `run_events_total`、`sessions_with_events`、逐文件 `events_count`；`progress_ring` 阶段分布（`phase_distribution`）；`hooks` 执行结果状态摘要；TUI task board（`/tasks` + `Ctrl+B`）|
| 跨会话 recall | claude-code / Hermes | `Done` / `Next` | `recall` / `recall-index`；JSON `schema_version=1.3`，`--sort recent|density|combined`；0 命中时 `no_hit_reason`。`recall-index doctor [--fix]`（`recall_index_doctor_v1`，exit 0/2）。性能基准：`scripts/perf_recall_bench.py`（Markdown → `docs/qa/runs/`） |
| 上下文压缩策略 | claude-code-analysis | `Done` | compact 触发时若 tokens > 85% `cost_budget_max_tokens` 自动追加成本提示；`[context]` 配置 `compact_after_iterations` / `compact_min_messages` |
| 成本 / token 策略 | claude-code-analysis | `Done` | `cost budget --check`；`compact + cost budget` 联动；`models suggest`；声明式 **`[models.routing]`**（**`goal_*`** + **`cost_budget_remaining_tokens_below`** 与 **`get_usage_counters`/`[cost].budget_max_tokens`**）；**`models routing-test`**；[MODEL_ROUTING_RULES.zh-CN.md](MODEL_ROUTING_RULES.zh-CN.md) / [MODEL_ROUTING_RULES.md](MODEL_ROUTING_RULES.md) |
| 钩子扩展 | claude-code-analysis | `Done` | 已落地：`hooks.json` 外部 `command` + `script`（`.py`/`.sh`/`.ps1`/`.cmd`/`.bat`）钩子；profile `minimal|standard|strict`、禁用列表、危险命令阻断；`hooks/hooks.json` 与 `.cai/hooks/hooks.json` 双路径；`hooks list` / `hooks run-event`（`--dry-run`）；`CAI_SKILLS_AUTO_SUGGEST=1` 在 `session_end` 触发 skills 自进化草稿落盘 |
| 定时任务 / 跨轮次失败重试 | Hermes Scheduler 2.0 | `Done` | **S4-01**：`.cai-schedule.json` 任务含 `max_retries`（CLI `--max-retries`）、`retry_count`、`next_retry_at`；失败后 `last_status=retrying`，退避 `60*2^(retry_count-1)` 秒再入队，用尽为 `failed_exhausted`；`retry_max_attempts`/`retry_backoff_sec` 仍为单次执行内连跑重试。**S4-02**：`schedule daemon --max-concurrent`（默认 1），超限任务本跳过并记 `skipped_due_to_concurrency`。**S4-03**：`depends_on` 有向环写入前拒绝；`schedule list` 展示 `depends_on_chain` / `dependency_blocked` / `dependents`（JSON 仅展示字段，不落盘）。**S4-04**：`.cai-schedule-audit.jsonl` 与 `daemon --jsonl-log` 统一 `schema_version=1.0` 与 `task.*`/`daemon.*` 事件名；见 `docs/schema/SCHEDULE_AUDIT_JSONL.zh-CN.md`。**S4-05**：`schedule stats --json` 聚合 `success_rate` / `avg_elapsed_ms` / `p95_elapsed_ms` 等；见 `docs/schema/SCHEDULE_STATS_JSON.zh-CN.md` |

## L3 — ECC 式治理与跨 harness

| 能力项 | 参考 | 状态 | 备注 |
|--------|------|------|------|
| 质量门禁 | ECC / 官方 CI 习惯 | `Done` | `quality-gate` |
| 安全扫描 | ECC | `Done` | `security-scan` |
| 记忆 / 本能 | ECC | `Done` | 已落地：单行 **v1 schema** 校验 + **整文件洁净性门禁**（`append_memory_entry` / `import_memory_entries_bundle` 追加前；`memory extract` 写条目前预检；脏文件拒绝写入，救急 `CAI_MEMORY_ALLOW_DIRTY_ENTRIES_JSONL=1`）；`memory validate-entries`（`memory_entries_file_validate_v1`）；`memory extract --structured` LLM/启发式双模结构化抽取；`memory import-entries`（dry-run + error-report）；`memory prune`（TTL/置信度/overflow/non-active）；`memory nudge` schema `1.1`；`memory health`（评分/grade/freshness/conflict/coverage）；`memory user-model`（行为偏好抽取：工具频率、错误率、goal 摘要）；`memory state` 状态机；**`auto_extract_skill_after_task`** 可选传入 **Settings** 走 **LLM** 生成草稿（`draft_method`=`llm`\|`template`） |
| 成本预算 | ECC | `Done` / `Next` | `cost budget`；新增 `release-ga` 汇总 budget 与会话失败率门禁；策略深化见 L2 |
| 跨工具导出 | ECC | `Done` | `export --target cursor|codex|opencode`；`export --ecc-diff`（`export_ecc_dir_diff_v1` 对比 vs `.cursor/cai-agent-export`）；`skills hub install`（按 manifest 选择性拷贝技能包）；见 [CROSS_HARNESS_COMPATIBILITY.zh-CN.md](CROSS_HARNESS_COMPATIBILITY.zh-CN.md) |
| 插件兼容矩阵（机读） | ECC / 多 harness | `Done` | **`plugin_compat_matrix_v1`**：`plugins --json --with-compat-matrix`；**`doctor --json`** 内 **`plugins`** 捆绑；说明 [PLUGIN_COMPAT_MATRIX.zh-CN.md](PLUGIN_COMPAT_MATRIX.zh-CN.md) / [PLUGIN_COMPAT_MATRIX.md](PLUGIN_COMPAT_MATRIX.md)；Schema `cai-agent/src/cai_agent/schemas/plugin_compat_matrix_v1.schema.json` |
| 可视化运营面板 | ECC | `Done` / `Next` | **已对齐**：CLI **`ops dashboard`**（JSON/text/html，**`--html-refresh-seconds`**）；**`ops serve`** 只读 HTTP（**`/v1/ops/dashboard`** / **`dashboard.html`**，**`CAI_OPS_API_TOKEN`** 可选），见 [`OPS_DYNAMIC_WEB_API.zh-CN.md`](OPS_DYNAMIC_WEB_API.zh-CN.md)。**仍为 Next**：Phase C（SSE、拖拽队列、RBAC、多租户路由等） |
| 云运行后端（Modal / Daytona 等按需沙箱） | Hermes / 平台化 | `OOS` | 默认交付为本机 **`cai-agent`** 进程；安全与范围理由、替代路径见 [CLOUD_RUNTIME_OOS.zh-CN.md](CLOUD_RUNTIME_OOS.zh-CN.md) |
| 大规模社区技能库本体 | ECC | `MCP` / `Next` | 以导出格式与外部包渐进吸收，不阻塞核心发版 |

---

**维护约定**：发版前至少更新一行「`Next` → `Done`」或新增一行 `MCP` 配方文档链接；若降级为 `OOS` 须在备注中写清理由并在 [PRODUCT_GAP_ANALYSIS.zh-CN.md](PRODUCT_GAP_ANALYSIS.zh-CN.md) 发布门禁中备案。
