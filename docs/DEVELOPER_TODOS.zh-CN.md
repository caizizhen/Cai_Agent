# 开发 TODO（当前执行基准）

> 与 `TEST_TODOS.zh-CN.md` 一起作为开发与测试的双基准。  
> 仅维护未完成开发任务；已完成项统一记录到 `CHANGELOG.md` / `CHANGELOG.zh-CN.md`。

## 当前开发队列

| 顺位 | 子任务 ID | 状态 | 开发目标 | 代码入口 | 完成门槛 |
|---|---|---|---|---|---|
| 1 | `ECC-N03-D02` | Ready | home diff（add/update/skip/conflict） | `exporter.py`、`doctor.py` | 差分语义稳定 |
| 2 | `HM-N03-D01` | Design | API 状态路由扩展 | `api_http_server.py` | 契约先定后实现 |
| 3 | `HM-N04-D01` | Design | dashboard preview/apply/audit contract | `ops_http_server.py`、`ops_dashboard.py` | 写动作安全可审计 |

## 未来开发（缩略）

- `CC-N04`：session/recap
- `HM-N03/HM-N04`：API + dashboard 收口
- `ECC-N03`：doctor/diff 深化（**D03** inventory 已合入 roadmap **`ECC-N03-D03`**；开发队列下一项为 **D02** home diff）
- `HM-N06` / `CC-N05` / `ECC-N05`：Explore
- `CC-N07` / `HM-N11`：Conditional
