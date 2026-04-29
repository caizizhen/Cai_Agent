# 开发 TODO（当前执行基准）

> 与 `TEST_TODOS.zh-CN.md` 一起作为开发与测试的双基准。  
> 本文件只维护未完成开发任务；已完成项统一记录到 `CHANGELOG.md` / `CHANGELOG.zh-CN.md` 与 `COMPLETED_TASKS_ARCHIVE.zh-CN.md`。  
> 当前产品愿景见 `PRODUCT_VISION_FUSION.zh-CN.md`：融合 Claude Code 的终端体验、Hermes 的产品化入口、Everything Claude Code 的治理生态。

## 当前开发队列

| 顺位 | 子任务 ID | 状态 | 开发目标 | 代码入口 | 完成门槛 |
|---|---|---|---|---|---|
| 1 | `SYNC-N01` | In Progress | 产品状态清账：把已实现但仍挂在 Ready 队列的 API/OPS/CC/GW/ECC 项归档，并恢复 TODO/roadmap/parity 一致性 | `docs/NEXT_ACTIONS.zh-CN.md`、`docs/DEVELOPER_TODOS.zh-CN.md`、`docs/TEST_TODOS.zh-CN.md`、`docs/PRODUCT_ROADMAP_CURRENT.zh-CN.md`、`docs/PRODUCT_GAP_ANALYSIS.zh-CN.md`、`docs/PARITY_MATRIX.zh-CN.md` | `API-N01`/`OPS-N01`/`CC-N05`/`GW-N01`/`ECC-N05`/`ECC-N06` 已归档；当前开发队列只保留真实未完成项；文档一致性 rg + 窄 pytest |
| 2 | `MEM-N01` | Design | 外部 memory provider adapter：从 local/user-model 扩展到可插拔 provider | `cai-agent/src/cai_agent/memory.py`、`cai-agent/src/cai_agent/user_model.py`、`docs/schema/README.zh-CN.md` | 先定义 provider contract、mock/filesystem 或 sqlite adapter、`memory provider test --json`；实现前补 RFC 或 schema |
| 3 | `RT-N01` | Design | runtime 真机矩阵：Docker/SSH 从产品化接口走向可验证环境矩阵 | `cai-agent/src/cai_agent/runtime/`、`docs/RUNTIME_BACKENDS.zh-CN.md`、`docs/qa/` | 分层真实 smoke 与 mock 测试；CI 不被外部环境硬绑定；实现前补测试矩阵 |
| 4 | `WF-N01` | Design | workflow / subagent 编排增强：条件分支、结果汇总、失败恢复 | `cai-agent/src/cai_agent/workflow*.py`、`docs/schema/README.zh-CN.md` | schema 示例覆盖 branch/retry/aggregate；pytest 覆盖 happy path 与失败恢复 |
| 5 | `BRW-N04` | Ready after SYNC | Browser MCP executor：把 `browser_task_v1.steps[]` 映射到显式确认的 Playwright MCP 调用 | `cai-agent/src/cai_agent/browser_provider.py`、`cai-agent/src/cai_agent/tool_provider.py`、`docs/BROWSER_PROVIDER_RFC.zh-CN.md` | 只在显式确认下执行 MCP steps；输出可审计结果；pytest 覆盖 dry-run、拒绝、成功映射 |

## 执行顺序

1. 先完成 `SYNC-N01`，把已验证完成的产品化队列从 TODO 中移出并同步 roadmap / parity。
2. 再推进 `MEM-N01`、`RT-N01`、`WF-N01` 的契约或测试矩阵设计，把可实现部分升为 Ready。
3. 若下一版主卖点转向浏览器自动化，则排 `BRW-N04`；否则它保持 P2。

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
