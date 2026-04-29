# 当前产品路线（本阶段）

## 当前阶段目标

- 完成 `SYNC-N01` 产品状态清账：`API-N01`、`OPS-N01`、`CC-N05`、`GW-N01`、`ECC-N05`、`ECC-N06` 已按新 ID 归档，当前 TODO 不再重复排已实现能力。
- 下一轮从“补产品化外表面”转入“可插拔/可验证/可编排”三条主线：memory provider、runtime 真机矩阵、workflow/subagent 编排增强。
- Browser automation 保持 MCP first；`BRW-N04` 可作为 P2 插入项，不抢默认 P1。

## 当前优先级（按顺序）

1. `SYNC-N01`：收口 TODO / roadmap / parity / gap 文档一致性。
2. `MEM-N01`：外部 memory provider adapter 契约与首个可测 adapter。
3. `RT-N01`：Docker/SSH runtime 分层真实 smoke 与 mock 测试矩阵。
4. `WF-N01`：workflow/subagent branch / retry / aggregate schema 与失败恢复。
5. `BRW-N04`：Browser MCP executor（条件插入，显式确认 + 审计优先）。

## 当前不做

- `CC-N07` / `HM-N11` 未授权云相关
- `CC-N06` 原生搜索重实现
