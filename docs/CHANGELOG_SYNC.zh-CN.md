# CHANGELOG 中英同步约定（I2）

根目录 **`CHANGELOG.md`** 为**默认英文**变更记录；**`CHANGELOG.zh-CN.md`** 为**完整中文**说明（见各文件头部说明）。发版与 PR 须保持两者**同一版本号下语义对齐**。

## 1. 何时必须双写

- **主版本 / minor**（例如 **0.7.x → 0.8.0**）：两文件同增一节，条目一一对应（允许中文更细，但不得与英文冲突）。
- **仅文档 / 无用户可见行为**：可在英文节用一行 *Docs* 概括，中文节可稍扩，但须指向同一 PR。
- **破坏性变更**：英文节必须含 **Breaking changes** 小节；中文节同结构，并交叉链接 [`docs/MIGRATION_GUIDE.md`](MIGRATION_GUIDE.md)（若适用）。

## 2. PR 自检（复制到 PR 描述勾选）

- [ ] 已更新 **`CHANGELOG.md`**（英文）
- [ ] 已更新 **`CHANGELOG.zh-CN.md`**（中文）
- [ ] 两文件 **版本标题日期/版本号** 一致
- [ ] 若改 JSON schema / CLI 契约：已更新 [`docs/schema/README.zh-CN.md`](schema/README.zh-CN.md) 或子文档
- [ ] 若改 Parity 状态：已更新 [`docs/PARITY_MATRIX.zh-CN.md`](PARITY_MATRIX.zh-CN.md) 至少一行

## 3. 与 T7 发版 Gate 的关系

手工发版前除 [`docs/qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md`](qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md) 表格外，**CHANGELOG 双写**为其中「产品与契约文档」子项；未完成则 **T7 不勾选完成**。

## 4. 建议命令顺序（固定 runbook）

建议维护者按下面顺序执行，而不是靠记忆补流程：

1. `cai-agent doctor --json`
2. `cai-agent release-changelog --json --semantic`
3. `python scripts/smoke_new_features.py`
4. 必要时执行 `QA_SKIP_LOG=1 python scripts/run_regression.py`
5. `cai-agent feedback export --dest dist/feedback-export.jsonl --json`
6. 回写 `PRODUCT_PLAN`、`PRODUCT_GAP_ANALYSIS`、`PARITY_MATRIX`、`CHANGELOG.md`、`CHANGELOG.zh-CN.md`

如果只做局部修复，步骤 4 可以留到合入前；但 **步骤 1 / 2 / 3 / 6 不建议跳过**。

补充说明：

- `cai-agent release-changelog --json --semantic` 现在会输出统一的 **`release_changelog_report_v1`**，内含 `bilingual`、`semantic` 与 `runbook` 摘要，适合直接接入 smoke / CI。
- 文本模式 `cai-agent release-changelog --semantic` 也会打印固定 runbook 提示，方便维护者在终端里按顺序继续执行。

## 5. 机器人 / 单语补丁策略

- 若 PR 仅英文机器人提交：合并前由维护者补中文节，或在同一 PR 追加 commit。
- 若紧急 hotfix 仅中文：须补英文一行 **parity** 说明，避免海外用户只看到中文文件。

## 6. 滚动摘要（非替代 CHANGELOG）

发版叙事仍以 **`CHANGELOG.md` / `CHANGELOG.zh-CN.md`** 为准；若只需一页「最近合了什么 / 还有什么没做」，维护者可同步更新：

- [`IMPLEMENTATION_STATUS.md`](IMPLEMENTATION_STATUS.md)（英文）
- [`IMPLEMENTATION_STATUS.zh-CN.md`](IMPLEMENTATION_STATUS.zh-CN.md)（中文）

---

*维护：本约定变更时同步 [`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md) 的 `REL-01` 与 [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md) T7 相关表述。*
