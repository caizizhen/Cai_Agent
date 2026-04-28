# NEXT_ACTIONS.zh-CN.md

> 会话短入口（精简版）。  
> 详细任务以 `DEVELOPER_TODOS.zh-CN.md` 与 `TEST_TODOS.zh-CN.md` 为基准。  
> 已完成功能只记录到 `CHANGELOG.md` / `CHANGELOG.zh-CN.md` 与 `COMPLETED_TASKS_ARCHIVE.zh-CN.md`。
> 完成任一任务后，必须运行验证并用 `scripts/finalize_task.py` 把完成证据写入已完成记录，再更新本短入口的下一步。

## 当前目标

- 进入“三 repo 融合”下一轮产品化开发：优先补齐外部接入面、受控运营面、安装/升级/恢复体验，再推进 gateway 生产化与 ECC 资产治理。

## 现在做

| 顺位 | 任务 | 状态 | 验收 |
|---|---|---|---|
| 1 | `API-N01` | Ready | OpenAPI + API/ops 统一网关；新增可验证的非敏感外部契约；pytest + smoke |
| 2 | `OPS-N01` | Ready | dashboard interactions 从 preview 推进到受控 apply/audit；pytest |
| 3 | `CC-N05` | Ready | 安装、升级、恢复体验收口；doctor/repair/onboarding 给出一致下一步 |

## 后续队列

- `GW-N01`：Gateway 生产化第二阶段（Discord/Slack/Teams readiness、故障诊断、workspace 路由预览）
- `ECC-N05`：asset marketplace-lite（资产目录、安装、更新建议、trust 摘要）
- `ECC-N06`：provenance/trust 策略进入 pack/import/install 执行链
- `MEM-N01` / `RT-N01` / `WF-N01`：先 Design，补契约或测试矩阵后再进入 Ready

## 条件与边界

- 原生 WebSearch / Notebook：保持 MCP 优先，不做内置重写
- 默认云 runtime：授权、安全、计费、隔离门槛明确后才实现
- Voice 默认交付：继续 OOS / MCP
- 商业插件市场、签名分成、公证体系：当前不做
