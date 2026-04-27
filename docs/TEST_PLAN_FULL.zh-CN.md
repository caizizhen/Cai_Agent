# 测试完整计划（过去 + 当前 + 未来）

## 1. 已完成测试（缩略）

- 全量基线长期保持可运行（pytest/smoke/regression）。
- 已完成能力对应测试以 CHANGELOG + QA 运行记录为准。
- 详细记录：`CHANGELOG.md` / `CHANGELOG.zh-CN.md` 与 `docs/qa/runs/`。

## 2. 当前测试

- `ECC-N02-D03`：`ecc pack-import` dry-run/apply/force/no-backup
- `ECC-N02-D04`：repair 场景待补
- 当前执行清单：`TEST_TODOS.zh-CN.md`

## 3. 未来测试

- `ECC-N03`：inventory/home diff/compat drift 快照测试
- `HM-N03/HM-N04`：API 路由与 dashboard 写动作契约测试
- 高风险改动保持“聚焦 + 全量 + smoke”三级验证

