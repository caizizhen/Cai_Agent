# NEXT_ACTIONS.zh-CN.md

> 会话短入口（精简版）。  
> 详细任务以 `DEVELOPER_TODOS.zh-CN.md` 与 `TEST_TODOS.zh-CN.md` 为基准。
> 已完成功能只记录到 `CHANGELOG.md` / `CHANGELOG.zh-CN.md`。

## 当前目标

- 体验层第六阶段（plan/workflow/release-ga 失败提示收口）已完成并通过全量验证；保持主干稳定并等待下一条非 Explore 优先级。

## 现在做

| 顺位 | 任务 | 状态 | 验收 |
|---|---|---|---|
| 1 | `（待排期）` | Ready | 用户指定下一条非 Explore 主线任务（建议延续体验层第二阶段） |

## 最近完成（缩略）

- `UX-N01-D06`（plan/workflow/release-ga 失败 hints 统一到同一排障语义）
- `UX-N01-D05`（run 家族失败 hints 扩展到 command/agent/fix-build）
- `UX-N01-D04`（run/continue 失败 hints 统一：JSON `hints[]` + 文本 `hint:`）
- `UX-N01-D03`（`sessions/continue` help quickstart + sessions 输出下一步 continue 提示）
- `UX-N01-D02`（`--help` onboarding quickstart + 高入口命令缺配置失败统一 hint）
- `UX-N01-D01`（`cai-agent onboarding` 聚合入口 + onboarding-first 提示统一 + TUI `/recap` 可见性补强）
- `ECC-N02-D08`（`skills hub install` ingest 门禁 smoke + CLI 回归）
- `ECC-N02-D07`（**`skills hub install`** × **`hooks.json`** ingest 门禁，**`ingest_scan_kind=explicit_hooks`**）
- `ECC-N02-D06`（README + **`doctor`/`api` summary** 暴露 **`ecc_pack_ingest_gate`**）
- `ECC-N02-D05`（**`ecc_pack_ingest_gate_v1`**：`ecc pack-import` 计划附带 ingest 门禁，`--apply` 与 **`hook_runtime`** 危险命令规则对齐）
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
