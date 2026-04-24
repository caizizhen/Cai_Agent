# WebSearch / Notebook 能力定案（P1）

> 与 [PRODUCT_GAP_ANALYSIS.zh-CN.md](PRODUCT_GAP_ANALYSIS.zh-CN.md) 中 Claude Code 体验缺口、[PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md) 中 WebSearch / Notebook 两行，以及 [ROADMAP_EXECUTION.zh-CN.md](ROADMAP_EXECUTION.zh-CN.md) 的 `CC-01` 对齐。

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

## CLI 自检入口（Sprint 3 增量）

为降低接入排障成本，`mcp-check` 增强了面向 WebSearch/Notebook 的预设自检：

- `cai-agent mcp-check --json --preset websearch`
- `cai-agent mcp-check --json --preset notebook`
- `cai-agent mcp-check --json --preset websearch/notebook --list-only`
- `cai-agent mcp-check --json --preset websearch --list-only`
- `cai-agent mcp-check --preset notebook --print-template`

说明：

- `--preset` 会对 MCP 工具列表做名称启发式匹配，并输出 `preset` 结构（`name` / `recommended_tools` / `matched_tools` / `missing_tools` / `ok`）。
- `--preset websearch/notebook` 会一次返回 `preset` 聚合对象与 `presets[]` 明细数组，适合在 onboarding 或 CI 里快速检查两类能力是否都接好了。
- `--list-only` 仅做工具清单检查，不执行 `--tool` 探活（适合先排配置再排调用）。
- `--print-template` 会输出对应 preset 的最小 MCP 配置模板（文本模式直接打印，JSON 模式在 `template` 字段返回），用于快速拷贝到配置；`websearch` 与 `notebook` 模板会包含差异化注释、文档入口、onboarding 入口与示例工具命名建议。
- 若未命中推荐工具，会在 JSON 与文本输出中返回 `next_step` / `fallback_hint`（含文档路径、onboarding 路径、建议命令、模板命令、缺失关键词），用于快速降级排障。

### 失败降级提示（推荐流程）

当 `preset.ok=false` 或 `ok=false` 时，建议按以下顺序处理：

1. 先运行 `cai-agent mcp-check --json --preset <websearch|notebook> --list-only`，确认是否至少命中一类推荐工具；
   若你要一次排两类能力，直接用 `cai-agent mcp-check --json --preset websearch/notebook --list-only`。
2. 打开 `docs/WEBSEARCH_NOTEBOOK_MCP.zh-CN.md` 与 `docs/MCP_WEB_RECIPE.zh-CN.md`，对齐 MCP 服务声明、超时与鉴权配置；
   新用户可同时打开 `docs/ONBOARDING.zh-CN.md`，按最短路径补 `init -> doctor -> mcp-check`。
3. 若工具列表正常，再用 `--tool <name> --args '<json>'` 做单工具探活；
4. 若仍失败，按 `next_step` 中 `missing_tools` 和 `recommended_tools` 与服务端维护者核对能力注册。

### 最小复现命令序列（建议复制执行）

```bash
# 1) 先做 list-only 预检
cai-agent mcp-check --json --preset websearch --list-only

# 1.5) 一次检查 WebSearch + Notebook 两类能力
cai-agent mcp-check --json --preset websearch/notebook --list-only

# 2) 打印 websearch 模板（复制到 cai-agent.toml）
cai-agent mcp-check --preset websearch --print-template

# 3) 复检 notebook 能力
cai-agent mcp-check --json --preset notebook --list-only

# 4) 打印 notebook 模板（复制到 cai-agent.toml）
cai-agent mcp-check --preset notebook --print-template
```

*版本：2026-04-19；与 Sprint 3 文档链一致。*
