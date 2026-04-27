# NEXT_ACTIONS.zh-CN.md

> 会话短入口（精简版）。  
> 详细任务以 `DEVELOPER_TODOS.zh-CN.md` 与 `TEST_TODOS.zh-CN.md` 为基准。
> 已完成功能只记录到 `CHANGELOG.md` / `CHANGELOG.zh-CN.md`。

## 当前目标

- 收口 `ECC-N02`：完成 `D03`（pack-import）并进入 `D04`（pack-repair）。
- 保持全量测试与 smoke 稳定通过。

## 现在做

| 顺位 | 任务 | 状态 | 验收 |
|---|---|---|---|
| 1 | `ECC-N02-D03` | In progress | `test_ecc_layout_cli.py` + smoke |
| 2 | `ECC-N02-D04` | Ready | repair 用例 + smoke |

## 最近完成（缩略）

- `CC-N03-D04`（plugins sync-home apply 收口）
- `HM-N01-D01`（profile home schema 深化）

## 条件与边界

- `CC-N07` / `HM-N11`：授权后才实现
- `CC-N06`：保持 MCP 优先，不做原生重写
