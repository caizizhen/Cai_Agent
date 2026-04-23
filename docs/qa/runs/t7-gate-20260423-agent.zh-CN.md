# T7 发版 Gate 执行记录（2026-04-23 · agent 回填）

对应 [`T7_RELEASE_GATE_CHECKLIST.zh-CN.md`](../T7_RELEASE_GATE_CHECKLIST.zh-CN.md) 与本轮代码/文档变更（插件兼容矩阵、RFC、schema 索引等）。

## 1. 自动化门禁

| 项 | 命令 | 结果 |
|----|------|------|
| T1 全量单测 | `cd cai-agent && python -m pytest tests -q` | **exit 0**，**546 passed**，3 subtests passed（约 22s） |
| T2 回归脚本 | 仓库根：`python scripts/run_regression.py` | **exit 0**，报告 [regression-20260423-234315.md](regression-20260423-234315.md)（unittest discover + smoke 等全步骤 **PASS**） |
| 冒烟子集 | 仓库根：`PYTHONPATH=cai-agent/src python scripts/smoke_new_features.py` | **exit 0**，输出含 **`NEW_FEATURE_CHECKS_OK`**（约 19s）；**`plugins --json --with-compat-matrix`** + **`doctor.plugins.compat_matrix`** 已纳入 smoke |

## 2. 产品与契约文档（本轮已更新）

| 项 | 说明 |
|----|------|
| Parity | [`PARITY_MATRIX.zh-CN.md`](../../PARITY_MATRIX.zh-CN.md) 新增插件机读矩阵行 |
| 执行清单 / 缺口 | [`ROADMAP_EXECUTION.zh-CN.md`](../../ROADMAP_EXECUTION.zh-CN.md) P2 §3；[`PRODUCT_GAP_ANALYSIS.zh-CN.md`](../../PRODUCT_GAP_ANALYSIS.zh-CN.md)；[`PRODUCT_PLAN.zh-CN.md`](../../PRODUCT_PLAN.zh-CN.md) §3.2 一行 |
| Schema 索引 | [`docs/schema/README.zh-CN.md`](../../schema/README.zh-CN.md) `plugins` / `doctor` |
| 插件矩阵专页 | [`PLUGIN_COMPAT_MATRIX.zh-CN.md`](../../PLUGIN_COMPAT_MATRIX.zh-CN.md) / [`PLUGIN_COMPAT_MATRIX.md`](../../PLUGIN_COMPAT_MATRIX.md) |
| Honcho RFC（A1） | [`docs/rfc/HONCHO_USER_MODEL_EPIC.zh-CN.md`](../../rfc/HONCHO_USER_MODEL_EPIC.zh-CN.md) |

## 3. 未在本机执行项 / 可选

| 项 | 说明 |
|----|------|
| CHANGELOG 条目核对 | **0.7.0** 已双写插件矩阵等（见根目录 **`CHANGELOG.md`** / **`CHANGELOG.zh-CN.md`**）；发版前仍按 [`CHANGELOG_SYNC.zh-CN.md`](../../CHANGELOG_SYNC.zh-CN.md) 自检 |
| Gateway S8-02 AC3 压测 | 非本版必选项；模板见 [`TEMPLATE_GATEWAY_S8_AC3.zh-CN.md`](TEMPLATE_GATEWAY_S8_AC3.zh-CN.md) |

---

*生成：开发代理回填；责任人请以发版 PR 为准。*
