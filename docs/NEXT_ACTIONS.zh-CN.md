# NEXT_ACTIONS.zh-CN.md

> 会话短入口（精简版）。  
> 详细任务以 `DEVELOPER_TODOS.zh-CN.md` 与 `TEST_TODOS.zh-CN.md` 为基准。
> 已完成功能只记录到 `CHANGELOG.md` / `CHANGELOG.zh-CN.md`。

## 当前目标

- 推进 `ECC-N03`：**D03**（harness target inventory，`ecc_harness_target_inventory_v1` + `ecc inventory`）已合入；下一项 **D02**（结构化 home diff）。
- 保持全量 pytest + smoke 稳定通过。

## 现在做

| 顺位 | 任务 | 状态 | 验收 |
|---|---|---|---|
| 1 | `ECC-N03-D02` | Ready | home diff 语义稳定 + 新增/扩展测试 |

## 最近完成（缩略）

- `ECC-N03-D03`（`ecc inventory` / `doctor` → `ecc_harness_target_inventory`）
- `ECC-N02-D03`（`ecc pack-import`）
- `ECC-N02-D04`（`ecc pack-repair` + doctor/repair 挂钩）
- `CC-N03-D04`（plugins sync-home apply）
- `HM-N01-D01`（profile home schema）

## 条件与边界

- `CC-N07` / `HM-N11`：授权后才实现
- `CC-N06`：保持 MCP 优先，不做原生重写
