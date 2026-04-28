# 开发 TODO（当前执行基准）

> 与 `TEST_TODOS.zh-CN.md` 一起作为开发与测试的双基准。  
> 仅维护未完成开发任务；已完成项统一记录到 `CHANGELOG.md` / `CHANGELOG.zh-CN.md`。

## 当前开发队列

| 顺位 | 子任务 ID | 状态 | 开发目标 | 代码入口 | 完成门槛 |
|---|---|---|---|---|---|
| 1 | `（待排期）` | Ready | 等待用户指定下一优先级（非 Explore） | — | 立项后执行 |

## 未来开发（缩略）

- `UX-N01-D06`：体验层第六阶段已合入（plan/workflow/release-ga 失败 hints 收口）
- `UX-N01-D05`：体验层第五阶段已合入（run 家族失败 hints 扩展到 command/agent/fix-build）
- `UX-N01-D04`：体验层第四阶段已合入（run/continue 失败 hints 统一：JSON + 文本）
- `UX-N01-D03`：体验层第三阶段已合入（`sessions/continue` help quickstart + sessions 下一步 continue 提示）
- `UX-N01-D02`：体验层第二阶段已合入（root help quickstart + 缺配置失败统一 onboarding hint）
- `UX-N01-D01`：体验层第一阶段（Onboarding 优先）已合入（`onboarding` 聚合入口、help/doctor/README 对齐、TUI `/recap` discoverability）
- `ECC-N02-D08`：`skills hub install` ingest 门禁 smoke + CLI 回归已合入
- `ECC-N02-D07`：**`skills hub install`** 与 **`ecc_pack_ingest_gate`**（显式 **`hooks.json`** 路径）已合入
- `ECC-N02-D06`：README + doctor/API **`ecc_pack_ingest_gate`** 暴露已合入
- `ECC-N02-D05`：pack **`--apply`** × **`ecc_pack_ingest_gate_v1`**（hooks.json + hook_runtime 危险命令规则）已合入
- `CC-N04`：session/recap 收口已合入（`session_recap_v1` + `sessions --recap` + TUI `/recap`）
- `HM-N03`：**`HM-N03-D01`**（API 状态路由）已合入 roadmap；`HM-N04`：**`HM-N04-D01`**（dashboard preview/apply/audit contract）已合入
- `ECC-N03`：doctor/diff 深化（**D03** inventory、**D04** structured home diff 已合入 roadmap）
- `HM-N06` / `CC-N05` / `ECC-N05`：Explore
- `CC-N07` / `HM-N11`：Conditional
