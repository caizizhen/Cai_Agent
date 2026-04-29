# Cai_Agent 功能能力地图与缺口分析

本文档以三个上游仓库为对照基线：

- [`anthropics/claude-code`](https://github.com/anthropics/claude-code)
- [`NousResearch/hermes-agent`](https://github.com/NousResearch/hermes-agent)
- [`affaan-m/everything-claude-code`](https://github.com/affaan-m/everything-claude-code)

产品定位见：[PRODUCT_VISION_FUSION.zh-CN.md](PRODUCT_VISION_FUSION.zh-CN.md)。发版勾选见：[PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md)。

## 1. 当前判断

截至 2026-04-26，当前仓库可以作出两个同时成立的判断：

1. **上一轮 roadmap / backlog 内定义的功能开发，已经基本完成。**
   - 证据见：[ROADMAP_EXECUTION.zh-CN.md](ROADMAP_EXECUTION.zh-CN.md) §10、[COMPLETED_TASKS_ARCHIVE.zh-CN.md](COMPLETED_TASKS_ARCHIVE.zh-CN.md)、[DEVELOPER_TODOS.zh-CN.md](DEVELOPER_TODOS.zh-CN.md)。
   - 自动化基线也已复核通过：`826 passed, 3 subtests passed`，smoke / regression 全绿。
2. **相对三个上游仓库的当前公开能力面，本仓还没有“全部同步完成”。**
   - 当前更接近“**核心主链路已成型，产品化外表面仍需补齐**”。
   - 后续工作的重点，不再是补第一轮内部缺口，而是补“三上游最新能力面”的剩余对齐项。

## 2. 三条能力线现状

| 对齐源 | 当前判断 | 已经对齐的主面 | 仍缺的关键面 |
|---|---|---|---|
| `anthropics/claude-code` | **核心能力高，对外表面中等** | CLI / TUI、plan / run / continue、workflow、MCP、任务板、模型切换、hooks、skills | 官方安装/升级体验、插件/marketplace 入口、Desktop/图形入口、更加收敛的自助反馈与修复链路 |
| `NousResearch/hermes-agent` | **Agent 核心中高，平台化外壳中等** | recall、scheduler、gateway 基础、MODEL-P0 模型接入地基（capabilities / health / onboarding / routing fallback / response envelope）、`api serve` v0 + OpenAI-compatible `/v1/models` / 非流式与 SSE `/v1/chat/completions`、OpenAPI 发现契约、受控 dashboard apply/audit、memory/user-model、docker/ssh runtime、Teams/Discord/Slack/Telegram readiness、marketplace-lite 与 trust gate；**另**：第一批扩展 gateway（Signal/Email/Matrix）、联邦/路由预览、voice contract 与 Telegram voice-reply、memory/tool registry 与 MCP bridge 等主路径已对齐 | 外部 memory provider adapter、runtime 真机矩阵、workflow/subagent 编排深化、Browser MCP executor、RBAC / 多 workspace operator 控制面 |
| `affaan-m/everything-claude-code` | **方法论与治理面中高，资产/分发面中等** | rules / skills / hooks、导出、compat matrix、cost / routing、跨 harness 约定 | 安装/修复/同步面、插件/marketplace 风格分发、规模化资产目录与 home 同步、桌面化管理入口 |

## 3. 当前最值得开发的方向

下一轮不建议继续平均铺开，而应该优先开发这三类：

0. **模型接入地基（已完成 MODEL-P0，本项转为持续维护）**
   - 让不同供应商、不同模型、本地模型、OpenAI-compatible 网关都走统一契约。
   - 对齐重点：Model Gateway、capabilities、health、chat smoke、routing explain、response envelope。
1. **外部接入面**
   - 让外部客户端、外部入口、外部平台能稳定接进来。
   - 对齐重点：Profiles、API Server、更多 Gateway、Dashboard 写路径。
2. **安装/分发/修复面**
   - 让新用户能安装、老用户能修复、跨 harness 用户能同步。
   - 对齐重点：Init / Doctor / Repair / Plugin / Export / Sync。
3. **长期产品差异化面**
   - 这些不是最先挡路，但会决定产品后续高度。
   - 对齐重点：**Asset pack 生命周期**、ingest **信任与 provenance（`ECC-N04-D03`）**、第二批 gateway、桌面化/operator 控制面；Voice / external memory / tool gateway / Browser automation **主路径已落地**，后续为边界内增量与维护。

## 4. 下一轮推荐优先级

状态说明：

- `Ready`：可以直接拆成开发单。
- `Design`：方向明确，但先补契约或交互边界。
- `Explore`：只做技术预研，不进入默认开发线。
- `OOS`：本轮明确不做。

| 分组 | 最高优先项 | 说明 |
|---|---|---|
| `MODEL-P0` 模型接入地基 | `MODEL-P0-01` 到 `MODEL-P0-07` 已完成 | provider contract、capabilities、health、response、routing explain / fallback 与 onboarding runbook 已形成共同底座 |
| `P0` 外部入口补齐 | `CC-N01`、`HM-N01` | 在模型地基稳定后，补安装/修复、profile home 这些最影响“别人怎么接入我们”的能力；**`CC-N02` 反馈线已 Done**；`HM-N02` 已由 OpenAI-compatible API server 收口 |
| `P0` 状态清账 | `SYNC-N01` | 把已实现的 API/OPS/CC/GW/ECC 新 ID 归档，恢复 TODO / roadmap / parity 一致性 |
| `P1` 可插拔/可验证/可编排 | `MEM-N01`、`RT-N01`、`WF-N01` | memory provider adapter、Docker/SSH 真机矩阵、workflow/subagent branch/retry/aggregate 是下一轮真实开发主线 |
| `P2` 受控自动化与 operator 面 | `BRW-N04`、Ops RBAC / 多 workspace、Gateway 深化 | Browser MCP executor 可插入；运营与 gateway 深化不抢默认 P1 |
| `P3` 条件/预研项 | `CC-N07`、`HM-N11` | 云 runtime 等仍按授权、安全、计费、隔离门槛处理 |

**Browser automation 补充**：本轮已把浏览器能力定为 `MCP first`。默认路径见 [`BROWSER_MCP.zh-CN.md`](BROWSER_MCP.zh-CN.md)，治理边界见 [`BROWSER_PROVIDER_RFC.zh-CN.md`](BROWSER_PROVIDER_RFC.zh-CN.md)；当前不把 browser-use 或 Skyvern 作为默认依赖，后续执行器必须先满足凭据、下载、上传、allowlist、审计与许可证边界。

详细执行拆解见：[DEVELOPER_TODOS.zh-CN.md](DEVELOPER_TODOS.zh-CN.md)（开发待办）与 [TEST_TODOS.zh-CN.md](TEST_TODOS.zh-CN.md)（测试待办）。已从 TODO 拆出的 **Done** 表格行见 [TODOS_DONE_ARCHIVE.zh-CN.md](TODOS_DONE_ARCHIVE.zh-CN.md)。能力级仍按 `CC-N* / HM-N* / ECC-N*`，原子级用 `*-Dxx`。

## 5. 本轮明确不默认追求的能力

这些能力即使上游存在，本轮也不建议默认进入开发线：

- **原生 WebSearch / Notebook 重实现**
  - 继续保持 `MCP 优先`，不和现有 MCP 生态重复造轮子。
- **重型 Browser runtime 默认内置**
  - Browser automation 继续保持 `MCP first`；`browser-use` / `Skyvern` 只作参考或可选适配，默认不把浏览器运行时、AGPL 工作流引擎或用户浏览器 profile 绑进核心分发。
- **默认云运行后端**
  - 继续默认 local / docker / ssh；云后端继续按条件立项处理。
- **一次性追平 Hermes 全平台 Gateway**
  - 先做一批代表性平台，不一次性铺满 15+ 平台。
- **闭源企业专属桥接 / 官方企业特性**
  - 维持 `OOS`，避免把路线图绑到不可验证的封闭能力上。
- **付费插件市场 / 公证签名 / 商业化分成**
  - 本轮不作为产品核心交付目标。

## 6. 发布门禁

每次进入下一轮对齐开发后，发版前至少满足：

- **分析页一致**：本页、[PRODUCT_PLAN.zh-CN.md](PRODUCT_PLAN.zh-CN.md)、[PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md) 不互相打架。
- **TODO 一致**：[DEVELOPER_TODOS.zh-CN.md](DEVELOPER_TODOS.zh-CN.md) 与 [TEST_TODOS.zh-CN.md](TEST_TODOS.zh-CN.md) 对同一任务的状态、范围、验收保持一致。
- **实现路径明确**：每个 `Ready` 项至少有一处代码入口、一处自动化验证入口、一处文档回写入口。
- **边界明确**：如果某项降级为 `Explore` 或 `OOS`，必须同步写回 `PARITY_MATRIX` 或相关 RFC。

## 7. 落地原则

- 先补“**别人怎么接入我们**”，再补“**我们自己内部还能更强什么**”。
- 先补“**默认路径可用**”，再补“**高级能力更完整**”。
- 不再扩散新的独立 backlog 文档；统一从本页、[DEVELOPER_TODOS.zh-CN.md](DEVELOPER_TODOS.zh-CN.md)、[NEXT_ACTIONS.zh-CN.md](NEXT_ACTIONS.zh-CN.md) 三份推进。

## 8. 相关文档

- 愿景与定位：[PRODUCT_VISION_FUSION.zh-CN.md](PRODUCT_VISION_FUSION.zh-CN.md)
- 当前执行清单：[PRODUCT_PLAN.zh-CN.md](PRODUCT_PLAN.zh-CN.md)
- 当前路线图：[ROADMAP_EXECUTION.zh-CN.md](ROADMAP_EXECUTION.zh-CN.md)
- 开发待办：[DEVELOPER_TODOS.zh-CN.md](DEVELOPER_TODOS.zh-CN.md)
- 测试迁移说明与自动验证记录：[TEST_TODOS.zh-CN.md](TEST_TODOS.zh-CN.md)
- 发版勾选矩阵：[PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md)
