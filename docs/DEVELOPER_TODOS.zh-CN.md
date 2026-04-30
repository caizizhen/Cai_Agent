# 开发 TODO（当前执行基准）

> 与 `TEST_TODOS.zh-CN.md` 一起作为开发与测试的双基准。  
> 本文件只维护未完成开发任务；已完成项统一记录到 `CHANGELOG.md` / `CHANGELOG.zh-CN.md` 与 `COMPLETED_TASKS_ARCHIVE.zh-CN.md`。  
> 当前产品愿景见 `PRODUCT_VISION_FUSION.zh-CN.md`：融合 Claude Code 的终端体验、Hermes 的产品化入口、Everything Claude Code 的治理生态。

## 当前开发队列

| 顺位 | 子任务 ID | 状态 | 开发目标 | 代码入口 | 完成门槛 |
|---|---|---|---|---|---|
| - | - | Clear | `CTX-COMPACT-N07` 已完成并归档；N04-N07 集成 QA 见 `docs/qa/runs/context-compaction-n04-n07-integration-qa-20260430.md`；上下文压缩后续计划见 `docs/CONTEXT_COMPACTION_FUTURE_PLAN.zh-CN.md` | `docs/COMPLETED_TASKS_ARCHIVE.zh-CN.md`、`docs/qa/runs/` | 下一轮从 `CTX-COMPACT-N08` TUI 压缩可视化、`CTX-COMPACT-N09` 安全/隐私过滤、Gateway slash 真实注册/部署检查或 Ops operator 路由深化中选择 |

## 执行顺序

1. 本轮已完成 `CTX-COMPACT-N07`，工具输出类型感知摘要字段已收口。
2. 下一轮若继续上下文面，优先做 `CTX-COMPACT-N08` TUI 压缩可视化或 `CTX-COMPACT-N09` 安全/隐私过滤。
3. 若暂停上下文面，再回到 Gateway slash command 真实注册/部署检查或 Ops operator 路由深化中选择。

## 每个任务的统一要求

- 必须有代码入口、自动化验证入口、文档回写入口。
- 新增 JSON 输出必须登记到 `docs/schema/README.zh-CN.md` 或对应 schema 文档。
- 修改产品状态时同步 `PRODUCT_PLAN.zh-CN.md`、`PRODUCT_GAP_ANALYSIS.zh-CN.md`、`PARITY_MATRIX.zh-CN.md` 中相关行。
- 每完成一项任务，必须先运行对应验证，再使用 `scripts/finalize_task.py --task-id <ID> --summary "<变更摘要>" --verification "<命令: PASS>"` 归档完成证据。
- 完成归档必须更新已完成记录：`COMPLETED_TASKS_ARCHIVE.zh-CN.md`、`docs/qa/runs/` QA run 记录，以及需要对外说明时的 `CHANGELOG.md` / `CHANGELOG.zh-CN.md`。
- 任务完成后从本文件当前队列移除或改为后续维护项；不要把已完成任务重新塞回 TODO，历史完成记录只看 changelog 与 completed archive。

## 边界

| 能力 | 状态 | 说明 |
|---|---|---|
| Browser automation | MCP first / Ready | 优先接 `microsoft/playwright-mcp`；原生 provider 只定义稳定契约与受控入口；`browser-use`、`Skyvern` 先作架构参考 |
| 原生 WebSearch / Notebook | MCP | 保持 MCP 优先，不做内置重写 |
| 默认云 runtime | Conditional | 仅在授权、安全、计费、隔离门槛明确后立项 |
| Voice 默认交付 | OOS / MCP | 继续走 STT/TTS MCP 或外部桥接 |
| 商业插件市场、签名分成、公证体系 | OOS | 当前只做 marketplace-lite 与 trust 摘要，不做商业化闭环 |
