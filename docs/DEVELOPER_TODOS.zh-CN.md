# 开发 TODO（当前执行基准）

> 与 `TEST_TODOS.zh-CN.md` 一起作为开发与测试的双基准。  
> 仅维护未完成开发任务；已完成项统一记录到 `CHANGELOG.md` / `CHANGELOG.zh-CN.md`。

## 当前开发队列

| 顺位 | 子任务 ID | 状态 | 开发目标 | 代码入口 | 完成门槛 |
|---|---|---|---|---|---|
| 1 | `ECC-N02-D05` | Ready | pack apply 路径接入 ingest sanitizer 等价门禁，与 `PRODUCT_GAP` P2「import-install 执行链」对齐 | `__main__.py`（`ecc pack-import` / `ecc pack-repair` apply）、可选 `skills.py` / ingest 辅助模块 | pytest + smoke；回写 `CHANGELOG` / `PARITY_MATRIX` / `OPS` 或 schema 说明（若新增契约字段） |

## 未来开发（缩略）

- `ECC-N02-D05`：pack apply × ingest sanitizer（见 `ROADMAP_EXECUTION` §10）
- `CC-N04`：session/recap 收口已合入（`session_recap_v1` + `sessions --recap` + TUI `/recap`）
- `HM-N03`：**`HM-N03-D01`**（API 状态路由）已合入 roadmap；`HM-N04`：**`HM-N04-D01`**（dashboard preview/apply/audit contract）已合入
- `ECC-N03`：doctor/diff 深化（**D03** inventory、**D04** structured home diff 已合入 roadmap）
- `HM-N06` / `CC-N05` / `ECC-N05`：Explore
- `CC-N07` / `HM-N11`：Conditional
