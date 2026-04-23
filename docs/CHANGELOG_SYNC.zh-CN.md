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

## 4. 机器人 / 单语补丁策略

- 若 PR 仅英文机器人提交：合并前由维护者补中文节，或在同一 PR 追加 commit。
- 若紧急 hotfix 仅中文：须补英文一行 **parity** 说明，避免海外用户只看到中文文件。

---

*维护：本约定变更时同步 [`NEXT_IMPLEMENTATION_BUNDLE.zh-CN.md`](NEXT_IMPLEMENTATION_BUNDLE.zh-CN.md) §0 与 [`PRODUCT_PLAN.zh-CN.md`](PRODUCT_PLAN.zh-CN.md) T7 相关表述。*
