# CAI Agent 上手路径（推荐阅读顺序）

本路径图对应 backlog 中的 **ONBOARDING**：从愿景到可运行闭环的最短链路。

1. **读愿景与范围**  
   打开 [`PRODUCT_VISION_FUSION.zh-CN.md`](PRODUCT_VISION_FUSION.zh-CN.md)，了解「官方能力环 / 治理 / 跨 harness」分层与不做事项（OOS）。

2. **（可选）网络与 MCP**  
   若需要只读网页：在仓库根 `cai-agent.toml` 中配置 `[fetch_url]` 与 `[permissions].fetch_url`；或按 [`MCP_WEB_RECIPE.zh-CN.md`](MCP_WEB_RECIPE.zh-CN.md) 接入 MCP。

3. **初始化与自检**  
   - `cai-agent init`（或 `init --global`）生成配置骨架。  
   - `cai-agent doctor`：确认工作区、API Key（脱敏）、工具链可发现性。

4. **第一次运行**  
   - `cai-agent run "你的目标"`，或使用 `cai-agent ui` 进入 TUI。  
   - 需要规划而不执行工具时：`cai-agent plan "目标" --json`。

5. **深入清单**  
   执行项与缺口以 [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md) 与 [`NEXT_IMPLEMENTATION_BUNDLE.zh-CN.md`](NEXT_IMPLEMENTATION_BUNDLE.zh-CN.md) 为准；与 Hermes 对齐见 `HERMES_PARITY_*` 文档。
