# WebSearch / Notebook 能力定案（P1）

> 与 [PRODUCT_GAP_ANALYSIS.zh-CN.md](PRODUCT_GAP_ANALYSIS.zh-CN.md) L1 工具深度、[PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md) 中 WebSearch / Notebook 两行、以及 [OPTIMIZATION_ROADMAP_CLAUDE_ECC.zh-CN.md](OPTIMIZATION_ROADMAP_CLAUDE_ECC.zh-CN.md) 的 P1 条目对齐。

## 结论（本仓库当前策略）

| 能力 | 定案 | 说明 |
|------|------|------|
| **WebSearch / 结构化搜索** | **MCP 优先** | 核心包不内置联网搜索 API；由用户在 `cai-agent.toml` 的 MCP 段接入带 **Web 检索** 或 **搜索 API** 的工具服务器，在 TUI 用 `/mcp call` 或 Agent 工具白名单调用。 |
| **Notebook 编辑** | **MCP 优先** | Jupyter 协议与内核管理较重，默认不进入 `cai-agent` 依赖树；推荐经 MCP（如社区 Jupyter / notebook 类 server）暴露只读或受控单元格操作。 |

若某发行版改为**内置薄封装**（专用子命令或工具名），须在发版 PR 中同步：

1. 更新 [PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md) 对应行状态为 `Done` 并写清入口；
2. 在 [CHANGELOG.zh-CN.md](../CHANGELOG.zh-CN.md) / [CHANGELOG.md](../CHANGELOG.md) 增加用户可见说明；
3. 在 `cai-agent.toml` 示例与 `doctor` 提示中给出密钥与权限约定。

## 与现有能力的关系

- **只读 HTTPS GET**：已内置 `fetch_url`（主机白名单 + 权限），见 [MCP_WEB_RECIPE.zh-CN.md](MCP_WEB_RECIPE.zh-CN.md) 的 MCP 并行方案。
- **MCP 调用面**：已具备 `mcp_list_tools` / `mcp_call_tool` 与 TUI `/mcp` 系列命令；WebSearch/Notebook 走同一机制即可复用审计与权限模型。

## 任务看板与事件 schema

- CLI `cai-agent board --json` 输出 **`schema_version: board_v1`**，内嵌 `observe` 子对象（`build_observe_payload`，含 `schema_version` 当前为 **1.1**）与可选 `.cai/last-workflow.json` 摘要。
- 顶层另含 **`observe_schema_version`**，便于看板消费方在不深入 `observe` 对象时做版本门控；与 [ROADMAP_EXECUTION.zh-CN.md](ROADMAP_EXECUTION.zh-CN.md) P1「与 board 共用 schema」方向一致：**会话聚合以 observe 为权威，board 为组合视图**。

## 后续可选工作

- 在 `docs/` 增加**经维护者验证**的示例 MCP 配置片段（固定工具名、超时、环境变量占位），并链到 Parity 矩阵 `MCP` 备注列。
- 若产品决定某能力为 **OOS**，须在 Parity 备注写明理由并在缺口分析备案。

*版本：2026-04-19；与 Sprint 3 文档链一致。*
