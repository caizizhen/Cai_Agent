# 跨工具兼容映射（Cursor/Codex/OpenCode/Claude）

> 英文版：[CROSS_HARNESS_COMPATIBILITY.md](CROSS_HARNESS_COMPATIBILITY.md)

本文件定义 Cai_Agent 面向多 Agent 工具链的兼容映射策略。

## 目标

- 同一套规则/技能/代理资产可在不同 harness 复用
- 对不支持能力提供“降级替代”而不是直接失效

## 能力映射表（v1）

| 能力 | Claude 类环境 | Cursor | Codex | OpenCode | Cai_Agent 策略 |
|---|---|---|---|---|---|
| rules | 原生规则目录 | 支持 | 指令文件为主 | instructions | 保持 `rules/` 作为统一源 |
| skills | `skills/` | 可共享 | 部分共享格式 | 可映射 | 统一 markdown 技能文本 |
| agents | `agents/*.md` | 支持 | 支持角色文件 | 支持 | 统一代理模板 + 适配层 |
| hooks | 强支持 | 强支持 | 弱/无 | 强支持 | 在不支持场景降级为命令前后检查 |
| mcp | 强支持 | 支持 | 支持 | 支持 | 保留 `mcp-configs` 作为统一配置源 |
| 命令入口 | slash 命令 | 命令面板 | 指令/配置 | slash | 统一 `commands/` + CLI 子命令 |

## 降级策略

1. **无 hooks 场景**：把 `pre/post` Hook 逻辑映射到 `quality-gate` 与 CLI 包装脚本。
2. **skills 格式差异**：以纯 markdown 作为中间表示，再由适配脚本渲染目标格式。
3. **agent 元数据差异**：保留最小公共字段（name/description/tools），其余字段按目标平台可选注入。

## 最小适配实现建议

- 生成命令：
  - `cai-agent plugins --json` 读取扩展面
  - 后续新增 `cai-agent export --target <cursor|codex|opencode>`
- 输出目录：
  - `.cursor/`
  - `.codex/`
  - `.opencode/`

## Manifest 版本（`cai-export-manifest.json`）

- `schema`：固定为 `export-v2`，表示本仓库导出器的 JSON 外形代际。
- `manifest_version`：语义化版本（当前 **2.1.0**），仅在增加字段、改变 `copied` 语义或目标目录约定时递增；与 ECC 等多 harness 生态对齐时，消费方可按 `manifest_version` 做兼容分支。
- `target`：`cursor` | `codex` | `opencode`。

## 机读兼容矩阵（CLI / doctor）

与上表同一语义的 **JSON** 由 **`plugin_compat_matrix_v1`** 承载：`cai-agent plugins --json --with-compat-matrix`，且 **`doctor --json`** 的 **`plugins.compat_matrix`** 同源。人读与维护约定见 [PLUGIN_COMPAT_MATRIX.zh-CN.md](PLUGIN_COMPAT_MATRIX.zh-CN.md) / [PLUGIN_COMPAT_MATRIX.md](PLUGIN_COMPAT_MATRIX.md)。

## 仓库根资产目录约定（ECC-01a）

以下路径为 **Cai_Agent 默认读取顺序**（与 `cai_agent.ecc_layout` / `doctor` 口径一致）：

| 资产 | 路径 | 说明 |
|------|------|------|
| rules | `rules/common/*.md`、`rules/python/*.md` | `plan` 阶段注入通用规则文本 |
| skills | `skills/*.md`（排除 `README.md`） | 技能绑定、hub、进化 |
| hooks | `hooks/hooks.json` → `.cai/hooks/hooks.json` | 事件钩子；前者优先 |

**脚手架**：`cai-agent ecc -w <工作区> scaffold` 从内置模板创建最小 `README` / 示例 skill / 空 `hooks.json`（**不覆盖**已有文件）。**机读索引**：`cai-agent ecc -w <工作区> layout --json` → **`ecc_asset_layout_v1`**。

**导出**：`cai-agent export --target cursor|codex|opencode` 与 **`export_ecc_dir_diff`** 仍以仓库根 `rules/`、`skills/` 等为源；详见上文 Manifest 与 [PLUGIN_COMPAT_MATRIX.zh-CN.md](PLUGIN_COMPAT_MATRIX.zh-CN.md)。

## 安装 / 导出 / 共享流转（ECC-01b）

统一叙事，避免「能导出但不知道装到哪、和谁共享」：

1. **本地初始化**：`cai-agent init`（或 **`init --preset starter`**）→ 得到根 **`cai-agent.toml`**；首次能力自检 **`cai-agent doctor`**。
2. **ECC 资产就位**：在仓库根执行 **`cai-agent ecc -w . layout --json`** 查看 **`ecc_asset_layout_v1`**；缺省时用 **`ecc scaffold`** 生成最小 **`skills/`** / **`hooks/hooks.json`** 示例（不覆盖已有文件）。
3. **导出到其它 harness**：**`cai-agent export --target cursor|codex|opencode`** → 目标目录 **`.cursor/`**、**`.codex/`**、**`.opencode/`**；发 PR 前可用 **`export --ecc-diff`**（**`export_ecc_dir_diff_v1`**）只做差异报告。
4. **共享给同事**：共享 **Git 仓库** + **`cai-agent.toml` 中不含密钥**（用 **`api_key_env`**）；对方 **`doctor --json`** 核对 **`plugin_compat_matrix`** 与 **`installation_guidance`**。
5. **机读兼容**：**`plugins --json --with-compat-matrix`** 与 **`doctor --json.plugins.compat_matrix`** 同源，消费方按目标 harness 列降级即可。

## 验收条件（P2）

- 同一仓库可导出至少两种 harness 配置
- 至少 80% 核心工作流（plan/run/review/verify）在目标 harness 具备可执行替代
- 不支持能力有明确提示和替代路径
