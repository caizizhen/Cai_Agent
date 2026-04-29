# 当前产品路线（本阶段）

## 当前阶段目标

- 已完成 `SYNC-N01` 产品状态清账：`API-N01`、`OPS-N01`、`CC-N05`、`GW-N01`、`ECC-N05`、`ECC-N06` 已按新 ID 归档，当前 TODO 不再重复排已实现能力。
- 已完成“可插拔/可验证/可编排”第一批：`MEM-N01` memory provider mock HTTP contract、`RT-N01` runtime 分层验证矩阵、`WF-N01` workflow branch / retry / aggregate 执行语义。
- Browser automation 保持 MCP first；`BRW-N04` 已落地显式确认的 Playwright MCP executor 映射，`BRW-N05` 已补审计 JSONL 与 artifact manifest。

## 当前优先级（按顺序）

1. Gateway 深化（候选）：slash command 真实注册/部署检查、多 workspace federation 真实部署检查（频道监控独立入口已由 `GW-CHAN-N01` 收口，slash catalog 已由 `GW-SLASH-N01` 收口）。
2. Ops operator 路由深化（候选）：在 `OPS-RBAC-N01` / `OPS-MW-N01` 基础上补更完整的跨 workspace 操作路由与租户边界。
3. Browser step allowlist 深化（候选）：下载、上传、点击、表单输入等更细粒度动作继续保持显式确认。

## 当前不做

- `CC-N07` / `HM-N11` 未授权云相关
- `CC-N06` 原生搜索重实现
