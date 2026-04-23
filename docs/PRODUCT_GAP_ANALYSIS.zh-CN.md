# Cai_Agent 功能能力地图与缺口分析

本文档基于以下三类参考面进行对比：

- 官方能力基线：`anthropics/claude-code`
- 架构能力雷达：`ComeOnOliver/claude-code-analysis`
- 生态工作流增强：`affaan-m/everything-claude-code`

产品北极星（三源融合「完全体」、统一运行时）见：[PRODUCT_VISION_FUSION.zh-CN.md](PRODUCT_VISION_FUSION.zh-CN.md)。子系统级勾选与发版约定见：[PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md)。

## 对比维度与当前结论

| 维度 | 参考基线 | Cai_Agent 当前状态 | 缺口等级 |
|---|---|---|---|
| 核心 REPL/CLI | 官方 CLI + 多端 | 已有 CLI + Textual `ui` | 低 |
| 工具系统 | 文件/搜索/Shell/Web/MCP/任务等 | 文件、搜索、白名单 `run_command`、只读 Git、可选 **`fetch_url`（HTTPS 白名单 + `max_redirects` + 解析后 IP 校验）**、MCP Bridge；**[`TOOLS_REGISTRY.zh-CN.md`](TOOLS_REGISTRY.zh-CN.md)** 由 **`gen_tools_registry_zh.py`** 自 **`tools_registry_doc`** 生成 | 中 |
| 插件扩展面 | skills/agents/hooks/MCP 等 | `cai-agent plugins --json` 汇总；**`--with-compat-matrix`** 输出 Cursor/Codex/OpenCode 机读矩阵；**`doctor --json`** 含 **`plugins`** 捆绑；见 [PLUGIN_COMPAT_MATRIX.zh-CN.md](PLUGIN_COMPAT_MATRIX.zh-CN.md) / [PLUGIN_COMPAT_MATRIX.md](PLUGIN_COMPAT_MATRIX.md) | 低 |
| 计划模式 | Plan Mode + 审批 | `plan`（只读规划）、`run --plan-file` | 低 |
| 任务与并行 | 子 Agent/任务状态/后台输出 | `workflow`（多步 + merge_strategy）+ 返回 `task` 与 `events`；`observe` 聚合会话 | 中 |
| 质量门禁 | review/CI/自动验证 | `quality-gate`：compileall、pytest、可选 ruff、可选 mypy、可选 `[[quality_gate.extra]]`、可选内嵌 `security-scan`；`fix-build` | 低 |
| 安全治理 | hooks + 权限 + 秘钥检测 | `security-scan`；`[permissions]`；沙箱与白名单命令 | 低 |
| 记忆学习 | auto memory / instincts | `memory extract/list/search/prune/...`、instincts 路径 | 中 |
| 成本治理 | token/cost 与路由策略 | LLM usage 统计、`cost budget --check`、`[cost] budget_max_tokens`；`[context]` 可配置对话压缩提示（见 `docs/CONTEXT_AND_COMPACT.zh-CN.md`）；**`[models.routing]`** 已含 **`cost_budget_remaining_tokens_below`**（与累计 **`total_tokens`** 比较剩余预算）；**`models routing-test --total-tokens-used`** 干跑；见 [`MODEL_ROUTING_RULES.zh-CN.md`](MODEL_ROUTING_RULES.zh-CN.md) / [`MODEL_ROUTING_RULES.md`](MODEL_ROUTING_RULES.md) | 低 |
| 跨工具适配 | Cursor/Codex/OpenCode 等 | `export --target cursor|codex|opencode` + manifest `schema` / `manifest_version`（见 `docs/CROSS_HARNESS_COMPATIBILITY.zh-CN.md`） | 中 |

## 当前仓库已具备的优势

- 具备可运行的本地 agent 主循环：`cai-agent/src/cai_agent/graph.py`
- 具备清晰的工具安全边界：`cai-agent/src/cai_agent/tools.py` + `cai-agent/src/cai_agent/sandbox.py`
- 具备可扩展内容层：`rules/`、`skills/`、`commands/`、`agents/`、`hooks/`
- 具备会话、统计、工作流与观测：`run` / `continue` / `sessions` / `stats` / `workflow` / `observe`
- 具备质量与安全入口：`quality-gate`、`security-scan`、`doctor`

## 关键缺口（按优先级）

1. **P1 - 工具深度**：无内置 WebFetch/WebSearch、Notebook 编辑等；在「完全体」目标下，**每个小版本**须选择：**内置补齐**、**新增认证 MCP 配方 + 文档**、或在 [PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md) 标注 `OOS` 并写明理由。
2. **P1 - 任务运营面**：缺独立「任务看板」UI；当前以 JSON（`workflow` / `observe`）为主，适合 CI 与二次集成；**动态运营 Web** 的 HTTP 契约与 MVP 分阶段见 [`OPS_DYNAMIC_WEB_API.zh-CN.md`](OPS_DYNAMIC_WEB_API.zh-CN.md)（**Phase B** 已提供 **`cai-agent ops serve`** 只读 HTTP；**Phase A** 为 HTML **`meta refresh`** / **`--html-refresh-seconds`**；**Phase C** 仍为后续）。
3. **P1 - 记忆与学习**：`entries.jsonl` **追加前整文件校验**与 **`auto_extract_skill_after_task` LLM 提炼**已落地（见 `memory.py` / `skills.py`、`PARITY_MATRIX` L3）；**`memory user-model export`** → **`user_model_bundle_v1`**（RFC 首包归档切片，**非**完整 E1 存储引擎）；**`insights --cross-domain`** 已输出 **`recall_hit_rate_metric_kind`/`metric_kind`** 明示索引探测语义（**A3** 诚实标注已落地，**真实 recall 命中率统计**仍为后续项）；**TTL/置信度策略**见 **[`MEMORY_TTL_CONFIDENCE_POLICY.zh-CN.md`](MEMORY_TTL_CONFIDENCE_POLICY.zh-CN.md)**；**Honcho 级用户建模（A1）** 完整 E1–E4 仍为后续项。
4. **P2 - 分发与反馈闭环**：对比官方安装器、`/bug` 类反馈通道；Cai_Agent 以 pip/源码为主，需自建支持渠道。
5. **P2 - 云运行后端**：Modal / Daytona 等按需沙箱 **默认不纳入交付**（**`OOS`**）；备案与替代路径见 [`CLOUD_RUNTIME_OOS.zh-CN.md`](CLOUD_RUNTIME_OOS.zh-CN.md)。

## 发布门禁（相对「完全体」愿景）

每次对外发版（或主版本号递增）前建议满足：

- **Parity 矩阵**：至少更新一处 [PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md)（`Next`→`Done`，或新增 `MCP` 文档链接，或 `OOS` 备案）。
- **P1 缺口**：不得在无说明的情况下长期滞留「既未实现也未 MCP 也未 OOS」；与本表「关键缺口」冲突的须在发版说明或 CHANGELOG 中可见。
- **愿景一致性**：若 README 与 [PRODUCT_VISION_FUSION.zh-CN.md](PRODUCT_VISION_FUSION.zh-CN.md) 表述冲突，以愿景文档为准并回写 README。

## 对应落地原则

- **完全体路径**：在统一栈内按 L1（官方能力环）→ L2（架构完备度）→ L3（治理与跨 harness）分阶段填平，避免无里程碑的「永久缺口」。
- 仍优先 **低耦合、可迭代**：注册表、清单、网关型命令先做稳，再加深自动化。
- 复杂能力坚持 **可执行入口 + 文档规范** 先行，再迭代策略与 UI。
- 开发主路径优先：**计划 → 实现 → 验证 → 交付**，生态与运营面（L3 后半）不阻塞 L1 发版。

## 相关文档

- 三源融合愿景（一页纸）：[PRODUCT_VISION_FUSION.zh-CN.md](PRODUCT_VISION_FUSION.zh-CN.md)
- 新用户路径与 CI 示例：[ONBOARDING.zh-CN.md](ONBOARDING.zh-CN.md)
- 上下文压缩与成本联动说明：[CONTEXT_AND_COMPACT.zh-CN.md](CONTEXT_AND_COMPACT.zh-CN.md)
- 执行清单（唯一）：[PRODUCT_PLAN.zh-CN.md](PRODUCT_PLAN.zh-CN.md)
