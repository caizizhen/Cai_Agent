# CAI Agent 上手路径（推荐阅读顺序）

本路径图对应 backlog 中的 **ONBOARDING**：从愿景到可运行闭环的最短链路。

1. **读愿景与范围**  
   打开 [`PRODUCT_VISION_FUSION.zh-CN.md`](PRODUCT_VISION_FUSION.zh-CN.md)，了解「官方能力环 / 治理 / 跨 harness」分层与不做事项（OOS）。

2. **（可选）网络与 MCP**  
   若需要只读网页：在仓库根 `cai-agent.toml` 中配置 `[fetch_url]` 与 `[permissions].fetch_url`；或按 [`MCP_WEB_RECIPE.zh-CN.md`](MCP_WEB_RECIPE.zh-CN.md) 接入 MCP。
   若目标是 WebSearch / Notebook：先看 [`WEBSEARCH_NOTEBOOK_MCP.zh-CN.md`](WEBSEARCH_NOTEBOOK_MCP.zh-CN.md)，然后执行 `cai-agent mcp-check --json --preset websearch/notebook --list-only`；需要模板时再用 `cai-agent mcp-check --preset websearch --print-template` 或 `--preset notebook --print-template`。

3. **初始化与自检**  
   - `cai-agent init`（或 `init --global`）生成配置骨架。  
   - `cai-agent doctor`：确认工作区、API Key（脱敏）、工具链可发现性。
   - 若已启用 MCP：`cai-agent mcp-check --json --preset websearch/notebook --list-only`，先确认工具列表是否具备目标能力，再做单工具探活。

4. **第一次运行**  
   - `cai-agent run "你的目标"`，或使用 `cai-agent ui` 进入 TUI。  
   - 需要规划而不执行工具时：`cai-agent plan "目标" --json`。

5. **深入清单**  
   已完成能力以 [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md) 为准；当前阶段开发顺序看 [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md)；缺口与 OOS 看 [`PRODUCT_GAP_ANALYSIS.zh-CN.md`](PRODUCT_GAP_ANALYSIS.zh-CN.md)。
