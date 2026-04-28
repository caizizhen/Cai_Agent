# NEXT_ACTIONS.zh-CN.md

> 会话短入口（精简版）。  
> 详细任务以 `DEVELOPER_TODOS.zh-CN.md` 与 `TEST_TODOS.zh-CN.md` 为基准。
> 已完成功能只记录到 `CHANGELOG.md` / `CHANGELOG.zh-CN.md`。

## 当前目标

- 交付 **`ECC-N02-D05`**：asset pack 的 **`--apply`** 与 **`ecc_ingest_sanitizer_policy_v1`** 合流，补齐 P2「import-install 执行链」中的写前门禁。

## 现在做

| 顺位 | 任务 | 状态 | 验收 |
|---|---|---|---|
| 1 | `ECC-N02-D05` | Ready | apply 前 sanitizer 等价检查；阻断时机读原因；pytest + smoke |

## 最近完成（缩略）

- `CC-N04`（`session_recap_v1`、`sessions --recap`、TUI `/recap` 收口）
- `HM-N04-D01`（ops interactions 收口：GET 仅 preview/audit，POST 承载 apply，审计链路保留）
- `HM-N03-D01`（`/v1/health`、`/v1/ready`、`api_liveness_v1` 与 RFC 更新）
- `ECC-N03-D04`（`ecc home-diff` / structured add·update·skip·conflict + doctor + repair hints）
- `ECC-N03-D03`（`ecc inventory` / `doctor` → `ecc_harness_target_inventory`）
- `ECC-N02-D03`（`ecc pack-import`）
- `ECC-N02-D04`（`ecc pack-repair` + doctor/repair 挂钩）
- `CC-N03-D04`（plugins sync-home apply）
- `HM-N01-D01`（profile home schema）

## 条件与边界

- `CC-N07` / `HM-N11`：授权后才实现
- `CC-N06`：保持 MCP 优先，不做原生重写
