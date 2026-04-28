# 开发 TODO（当前执行基准）

> 与 `TEST_TODOS.zh-CN.md` 一起作为开发与测试的双基准。  
> 本文件只维护未完成开发任务；已完成项统一记录到 `CHANGELOG.md` / `CHANGELOG.zh-CN.md` 与 `COMPLETED_TASKS_ARCHIVE.zh-CN.md`。  
> 当前产品愿景见 `PRODUCT_VISION_FUSION.zh-CN.md`：融合 Claude Code 的终端体验、Hermes 的产品化入口、Everything Claude Code 的治理生态。

## 当前开发队列

| 顺位 | 子任务 ID | 状态 | 开发目标 | 代码入口 | 完成门槛 |
|---|---|---|---|---|---|
| 1 | `API-N01` | Ready | OpenAPI + API/ops 统一网关：让外部系统能稳定发现、调用、审计当前能力 | `cai-agent/src/cai_agent/api_http_server.py`、`cai-agent/src/cai_agent/__main__.py`、`docs/schema/README.zh-CN.md` | 新增 `api openapi --json` 或 `/openapi.json`；覆盖 status/doctor/models/chat/ops 的非敏感契约；pytest + smoke |
| 2 | `OPS-N01` | Ready | Dashboard 从可读/preview 升级为受控可写闭环 | `cai-agent/src/cai_agent/ops_http_server.py`、`cai-agent/src/cai_agent/ops_dashboard.py` | 至少支持 schedule reorder 与 gateway bind-edit 的 preview/apply/audit；审计链路可验证；pytest |
| 3 | `CC-N05` | Ready | 安装、升级、恢复体验收口：降低新用户和老用户修复成本 | `cai-agent/src/cai_agent/doctor.py`、`cai-agent/src/cai_agent/repair.py`、`README*.md` | `doctor`/`repair`/onboarding 给出一致升级和恢复路径；常见缺配置/旧配置/资产漂移有下一步命令；pytest + smoke |
| 4 | `GW-N01` | Ready | Gateway 生产化第二阶段：Discord/Slack/Teams 从 MVP 推到可运维 | `cai-agent/src/cai_agent/gateway*.py`、`docs/GATEWAY_*.zh-CN.md` | `gateway prod-status --json` 增加 readiness/checklist；每个平台至少一条故障诊断路径；pytest |
| 5 | `ECC-N05` | Ready | asset marketplace-lite：本地/仓库级资产目录、安装、更新建议与 trust 摘要 | `cai-agent/src/cai_agent/skills.py`、`cai-agent/src/cai_agent/ecc.py`、`docs/PLUGIN_COMPAT_MATRIX*.md` | 新增资产 catalog/list/upgrade-plan 类入口；展示 source/version/license/trust/install 状态；pytest + smoke |
| 6 | `ECC-N06` | Ready | provenance/trust 策略进入执行链：把现有草案用于 pack/import/install 决策 | `cai-agent/src/cai_agent/ecc.py`、`cai-agent/src/cai_agent/hook_runtime.py`、`docs/ECC_04*.md` | 未知或低信任来源默认 dry-run/阻断；危险 hooks 继续阻断；输出可解释 trust decision；pytest |
| 7 | `MEM-N01` | Design | 外部 memory provider adapter：从 local/user-model 扩展到可插拔 provider | `cai-agent/src/cai_agent/memory.py`、`cai-agent/src/cai_agent/user_model.py` | 先定义 provider contract、mock/filesystem 或 sqlite adapter、`memory provider test --json`；实现前补 RFC 或 schema |
| 8 | `RT-N01` | Design | runtime 真机矩阵：Docker/SSH 从产品化接口走向可验证环境矩阵 | `cai-agent/src/cai_agent/runtime/`、`docs/RUNTIME_BACKENDS.zh-CN.md` | 分层真实 smoke 与 mock 测试；CI 不被外部环境硬绑定；实现前补测试矩阵 |
| 9 | `WF-N01` | Design | workflow / subagent 编排增强：条件分支、结果汇总、失败恢复 | `cai-agent/src/cai_agent/workflow*.py`、`docs/schema/README.zh-CN.md` | schema 示例覆盖 branch/retry/aggregate；pytest 覆盖 happy path 与失败恢复 |

## 执行顺序

1. 先做 `API-N01`，因为它把现有能力变成外部可发现、可调用的稳定契约。
2. 再做 `OPS-N01`，把已有 dashboard interactions 从契约推进到受控闭环。
3. 随后做 `CC-N05`，补齐安装、升级、恢复这条 Claude Code 风格体验线。
4. 然后推进 `GW-N01`、`ECC-N05`、`ECC-N06`，把 Hermes gateway 与 ECC 资产治理从 MVP 推到可运营。
5. `MEM-N01`、`RT-N01`、`WF-N01` 先保持 Design，完成契约或测试矩阵后再进入 Ready。

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
| 原生 WebSearch / Notebook | MCP | 保持 MCP 优先，不做内置重写 |
| 默认云 runtime | Conditional | 仅在授权、安全、计费、隔离门槛明确后立项 |
| Voice 默认交付 | OOS / MCP | 继续走 STT/TTS MCP 或外部桥接 |
| 商业插件市场、签名分成、公证体系 | OOS | 当前只做 marketplace-lite 与 trust 摘要，不做商业化闭环 |
