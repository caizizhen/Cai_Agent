# Cai_Agent 功能能力地图与缺口分析

本文档基于以下三类参考面进行对比：

- 官方能力基线：`anthropics/claude-code`
- 架构能力雷达：`ComeOnOliver/claude-code-analysis`
- 生态工作流增强：`affaan-m/everything-claude-code`

## 对比维度与当前结论

| 维度 | 参考基线 | Cai_Agent 当前状态 | 缺口等级 |
|---|---|---|---|
| 核心 REPL/CLI | 官方 CLI + 多端 | 已有 CLI + Textual UI | 低 |
| 工具系统 | 文件/搜索/Shell/Web/MCP/任务等 | 已有文件、搜索、命令、Git、MCP 基础 | 中 |
| 插件扩展面 | skills/agents/hooks/mcp/lsp/monitors/bin | 目录与注册骨架已存在，缺统一清单视图 | 中 |
| 计划模式 | Plan Mode + 审批 | 已有 `plan` 命令（只读规划） | 低 |
| 任务与并行 | 子 Agent/任务状态/后台输出 | workflow + 会话统计，缺统一任务看板 | 中 |
| 质量门禁 | review/CI/自动验证 | 有 `doctor`、`stats`，缺一键 gate | 高 |
| 安全治理 | hooks + 权限 + 秘钥检测 | 沙箱/白名单已具备，缺集中式安全扫描入口 | 中 |
| 记忆学习 | auto memory / instincts | 已有 memory 目录与会话沉淀，缺结构化提炼流 | 中 |
| 成本治理 | token/cost 与路由策略 | 已有基础 usage 统计，缺预算策略与面板 | 中 |
| 跨工具适配 | Cursor/Codex/OpenCode 等 | 目前主要聚焦 CLI 单体 | 高 |

## 当前仓库已具备的优势

- 具备可运行的本地 agent 主循环：`cai-agent/src/cai_agent/graph.py`
- 具备清晰的工具安全边界：`cai-agent/src/cai_agent/tools.py` + `cai-agent/src/cai_agent/sandbox.py`
- 具备可扩展内容层：`rules/`、`skills/`、`commands/`、`agents/`、`hooks/`
- 具备最小会话/统计链路：`run/continue/sessions/stats/workflow`

## 关键缺口（按优先级）

1. **P0 - 扩展能力可见性不足**：缺“插件扩展面统一清单”（便于运营和排查）
2. **P0/P1 - 验证闭环不完整**：缺统一的 `quality-gate` 命令（lint/type/test/security）
3. **P1 - 成本/上下文治理流程化不足**：缺可执行的门槛与路由策略文档化入口
4. **P2 - 跨工具映射未产品化**：缺标准化兼容映射与降级策略文档

## 对应落地原则

- 优先做“低耦合、可迭代”的功能：先补注册、清单、网关型命令。
- 把复杂能力先做成“可执行入口 + 文档规范”，再逐步深挖自动化。
- 先覆盖开发主路径（计划 -> 实现 -> 验证 -> 交付），再扩展生态场景。
