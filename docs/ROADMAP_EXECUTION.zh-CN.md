# Cai_Agent P0-P2 开发落地清单

本清单对应「功能对比后的工程执行与验收」，并与产品北极星对齐：**在单一运行时（Python / LangGraph / OpenAI 兼容）内实现三源融合「完全体」**——详见 [PRODUCT_VISION_FUSION.zh-CN.md](PRODUCT_VISION_FUSION.zh-CN.md)；发版前 parity 勾选约定见 [PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md)；维度级缺口与发布门禁见 [PRODUCT_GAP_ANALYSIS.zh-CN.md](PRODUCT_GAP_ANALYSIS.zh-CN.md)。

## P0（2-4 周）可用性底座

### 1) 插件化扩展骨架
- 已落地：
  - 扩展面注册模块：`cai-agent/src/cai_agent/plugin_registry.py`
  - CLI 清单命令：`cai-agent plugins`（支持 `--json`）
- 验收标准：
  - 能输出 `skills/commands/agents/hooks/rules/mcp-configs` 存在性与文件数
  - 在无配置文件和有配置文件场景都能正常识别项目根

### 2) 统一命令入口
- 现状：`plan/run/continue/commands/command/agents/agent/workflow` 已形成主链路
- **已落地（主线）**：`fix-build` / `security-scan` 命令与 `commands/` 模板；TUI **`/fix-build`**、**`/security-scan`**（见 **NEXT_IMPLEMENTATION_BUNDLE** 补记）。
- **仍属演进 / 非阻塞**：更多斜杠模板与「一键组合」可按 Sprint 再增。

### 3) 权限与安全最小体系
- 现状：`sandbox.py` 路径越界防护 + `tools.py` 命令白名单
- **已落地（主线）**：**`pii-scan`**（**`pii_scan_result_v1`**）；**`run_command_approval_mode`** + **`run_command_high_risk_patterns`**（高危命令二次确认）。
- **仍属演进**：针对 **prompt 内联** 的专项扫描策略、更多规则集可按需迭代。

### 4) 任务状态与可观测
- 现状：`sessions`、`stats`、`workflow` 已有最小统计
- **已落地（主线）**：**`task_id`** 贯通 run/continue/workflow/sessions/observe；**`run`/`continue` JSON** 含 **`run_events_envelope_v1`**；**`board`/`observe`/`insights`** 等同源事件聚合。
- **仍属演进**：面向 **Dashboard 消费** 的独立事件总线 / 动态运营 Web 见 **§P2** 与 [`OPS_DYNAMIC_WEB_API.zh-CN.md`](OPS_DYNAMIC_WEB_API.zh-CN.md)。

## P1（4-8 周）效率引擎

> **本月增量（与 Parity L1 对齐）**：WebSearch / Notebook 的 **MCP 优先**定案与 `board`/`observe` 共用事件模型说明见 [WEBSEARCH_NOTEBOOK_MCP.zh-CN.md](WEBSEARCH_NOTEBOOK_MCP.zh-CN.md)；Sprint 3 执行细节仍以 [MODEL_SWITCHER_DEVPLAN.zh-CN.md](MODEL_SWITCHER_DEVPLAN.zh-CN.md) §4 与 [OPTIMIZATION_ROADMAP_CLAUDE_ECC.zh-CN.md](OPTIMIZATION_ROADMAP_CLAUDE_ECC.zh-CN.md) 为准。

### 1) 记忆与学习系统 v1
- 目标：将会话经验沉淀为可检索“项目记忆”
- **已落地（主线）**：`memory` 全家桶、**`memory health`/`state`/`nudge`**、**`validate-entries`/`extract --structured`**、**`[models.routing]`** 之外的 **TTL/置信度** 策略见 [`MEMORY_TTL_CONFIDENCE_POLICY.zh-CN.md`](MEMORY_TTL_CONFIDENCE_POLICY.zh-CN.md)。
- **仍属演进**：更重的 **Honcho 级用户建模** 见 RFC [`docs/rfc/HONCHO_USER_MODEL_EPIC.zh-CN.md`](rfc/HONCHO_USER_MODEL_EPIC.zh-CN.md)。

### 2) 上下文与成本治理
- 目标：把 token/cost 从“统计”升级为“策略”
- **已落地（主线）**：**`models suggest`**；**`[models.routing]`** + **`models routing-test`**（含成本条件）；**`compact_hint` 与 `cost_budget_max_tokens` 约 85% 联动**（见 **PRODUCT_PLAN** / **CHANGELOG 0.7.0**）。
- **仍属演进**：更细的「按会话阶段自动切 profile」与 **Dashboard 成本视图**。

### 3) 多 Agent 编排 v1
- 目标：提供“探索-实现-评审”模板化协作
- **已落地（主线）**：**`workflow --templates`**、**`subagent_io_schema_version`=`1.1`**、**`parallel_group`**、**`on_error`/`budget_*`**、**`quality_gate` 后置** 等（见 **PRODUCT_PLAN §二 23**）。
- **仍属演进**：更丰富的 **冲突融合策略 UI** 与可视化编排。

### 4) 质量门禁
- 已落地：
  - `cai-agent quality-gate`（compileall、pytest、可选 ruff、可选 mypy、可选 `[[quality_gate.extra]]`、可选内嵌 security-scan）
  - 模块：`cai-agent/src/cai_agent/quality_gate.py`
- **已落地（增量）**：**`CAI_QG_FRONTEND_MONOREPO=1`** 时自动追加 **`npm run -ws --if-present lint`**；**`security-scan --badge`**（**`security_badge_v1`**）。
- **仍属演进**：更多语言栈默认模板；**CI 徽章**消费示例与文档外链。

## P2（8-12 周）生态与平台化

### 1) 跨工具兼容层
- 目标：对齐 Cursor/Codex/OpenCode 主要配置维度
- **已落地（主线）**：**`cai-agent export --target`**；人读/机读映射 **[`CROSS_HARNESS_COMPATIBILITY.zh-CN.md`](CROSS_HARNESS_COMPATIBILITY.zh-CN.md)** / **[`CROSS_HARNESS_COMPATIBILITY.md`](CROSS_HARNESS_COMPATIBILITY.md)**；**`plugin_compat_matrix_v1`**（**`plugins --json --with-compat-matrix`** / **`doctor`**）。
- **仍属演进**：更多目标格式的 **一键转换脚本** 与 ECC 深度对齐。

### 2) 可视化运营面板
- 目标：从“命令行可用”升级到“团队可运营”
- **已落地（MVP + Phase A/B）**：**`ops dashboard`**（JSON / HTML 单文件；**`--html-refresh-seconds`**）；**`ops serve`** 只读 HTTP（与 **`ops_dashboard_v1`** 同源）；契约见 **PRODUCT_PLAN §二 26** 与 [`OPS_DYNAMIC_WEB_API.zh-CN.md`](OPS_DYNAMIC_WEB_API.zh-CN.md)。
- **仍属演进**：Phase C（SSE / 实时队列 / RBAC 等）同上文档。

### 3) 插件市场与版本治理
- 目标：形成可发布、可回滚、可评估的生态机制
- 里程碑：
  - **插件版本兼容矩阵**（**已落地**：`plugin_compat_matrix_v1` + `doctor`/`plugins` 消费路径；见 [PLUGIN_COMPAT_MATRIX.zh-CN.md](PLUGIN_COMPAT_MATRIX.zh-CN.md) / [PLUGIN_COMPAT_MATRIX.md](PLUGIN_COMPAT_MATRIX.md)）
  - 插件健康评分与风险提示（**已有** `plugins_surface_v1.health_score`；后续可做阈值告警与 CHANGELOG 联动）

## 推荐 KPI

- 首次可用时间（安装到首次成功任务）
- 端到端任务成功率（计划到可合并改动）
- 人工干预率
- 单任务 token 成本
- 安全拦截有效率
- 技能/命令复用率
