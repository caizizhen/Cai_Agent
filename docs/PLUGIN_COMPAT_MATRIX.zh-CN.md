# 插件扩展面机读兼容矩阵（`plugin_compat_matrix_v1`）

> 英文版：[PLUGIN_COMPAT_MATRIX.md](PLUGIN_COMPAT_MATRIX.md)

本页是 **Cursor / Codex CLI / OpenCode** 与 CAI 仓库内六类扩展目录（`skills`、`commands`、`agents`、`hooks`、`rules`、`mcp-configs`）的对照说明，与 [CROSS_HARNESS_COMPATIBILITY.zh-CN.md](CROSS_HARNESS_COMPATIBILITY.zh-CN.md) 的「能力映射表」一致，并固化为 **`build_plugin_compat_matrix()`** 返回的 JSON（`schema_version`: **`plugin_compat_matrix_v1`**）。

## 消费路径

| 场景 | 命令 / 字段 |
|------|-------------|
| 独立机读 | `cai-agent plugins --json --with-compat-matrix`（在 `plugins_surface_v1` 顶层附加 **`compat_matrix`**） |
| 诊断捆绑 | `cai-agent doctor --json` → **`plugins`**（`doctor_plugins_bundle_v1`）：含 **`surface`** 与 **`compat_matrix`** |
| JSON Schema | `cai-agent/src/cai_agent/schemas/plugin_compat_matrix_v1.schema.json` |

## 状态取值

- **`supported`**：目标 harness 对该类资产有一级或等价入口。  
- **`partial`**：需导出 / 适配或格式子集。  
- **`absent`**：目标侧无等价机制，需流程降级（如用 `quality-gate` 替代 hooks）。

## 矩阵摘要（与实现对齐）

详见 `doctor --json` 内 `plugins.compat_matrix.components_vs_targets[]` 与 `targets[]`；变更时请同步：

1. `cai_agent.plugin_registry.build_plugin_compat_matrix`  
2. 本页与 **CROSS_HARNESS** 表（[CROSS_HARNESS_COMPATIBILITY.zh-CN.md](CROSS_HARNESS_COMPATIBILITY.zh-CN.md) / [CROSS_HARNESS_COMPATIBILITY.md](CROSS_HARNESS_COMPATIBILITY.md)）  
3. `schemas/plugin_compat_matrix_v1.schema.json`

## 技能库 roadmap（G3 分拆说明）

- **当前主线**：仓库内 `skills/` + **`skills hub`**（`manifest` / `suggest` / `install` / `serve`）+ **`export --target`**；见 [PRODUCT_PLAN.zh-CN.md](PRODUCT_PLAN.zh-CN.md) §二 / [WEBSEARCH_NOTEBOOK_MCP.zh-CN.md](WEBSEARCH_NOTEBOOK_MCP.zh-CN.md) 定案。  
- **大规模社区技能库本体**：以 **MCP / 外部包** 渐进吸收，不阻塞核心发版（与 [PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md) L3 表述一致）。
