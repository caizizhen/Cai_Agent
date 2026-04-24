# ECC-03a：插件矩阵与版本治理（设计结论文档）

> 目标：把 **「谁兼容谁、何时 bump、如何分发」** 写成单源叙事，避免 **`plugin_compat_matrix_v1`** 与 **`export` manifest** 各自漂移。

## 1. 版本语义（建议冻结）

| 载体 | 字段 | 语义 |
|------|------|------|
| **`cai-export-manifest.json`** | **`manifest_version`** | **SemVer**；**MAJOR**：目标目录布局或 `copied` 语义不兼容变更；**MINOR**：新增可选字段或新 target；**PATCH**：文档性字段或排序 |
| **CLI / `cai_agent.__version__`** | **包版本** | PyPI /  tarball；与 manifest **无强制同版本**，但在 **CHANGELOG** 中声明「推荐消费的 manifest 下限」 |
| **`plugin_compat_matrix_v1`** | **无独立 semver** | 与 **`cai_agent`** 版本一起发布；矩阵行增删走 **MINOR** 包版本起记 |

## 2. 兼容矩阵维护规则

1. **单一写入路径**：矩阵 JSON 仅通过 **`build_plugin_compat_matrix()`** 生成；**`doctor --json`** 与 **`plugins --json --with-compat-matrix`** 必须同源（已实现则保持）。
2. **变更 checklist**：改 `TOOLS_REGISTRY` / 内置工具名 / harness 目标目录时，必须同步 **矩阵行** + **`docs/PLUGIN_COMPAT_MATRIX*.md`** + **`PARITY_MATRIX`** 相关行。
3. **CI**：保留 **`gen_tools_registry_zh.py --check`** 类检查；可选后续加「矩阵 JSON snapshot」测试（非本 RFC 强制）。

## 3. 分发叙事（与 ECC-01b 对齐）

- **源码 Git**：主交付；**`ecc layout` / `export`** 以仓库根为源。
- **PyPI 包**：`cai-agent` 版本 = 运行时能力版本；不单独发「矩阵包」。
- **Cursor / 技能导出**：见 **`CROSS_HARNESS_COMPATIBILITY*.md`**；manifest **`target`** 扩列前需 **MINOR** manifest bump。

## 4. 明确不做（本阶段）

- 第三方插件市场托管、签名公证、付费分成 **默认 OOS**。
- **VS Code Marketplace** 式的一键安装 **不走本仓库默认交付**（可走 MCP / 外部文档）。

## 5. 验收

- 维护者更新矩阵时有 **可执行 checklist**（本节 §2）；与 **`ECC-01b`** 安装/导出叙事无矛盾。
