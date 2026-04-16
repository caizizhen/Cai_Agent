# 跨工具兼容映射（Cursor/Codex/OpenCode/Claude）

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

## 验收条件（P2）

- 同一仓库可导出至少两种 harness 配置
- 至少 80% 核心工作流（plan/run/review/verify）在目标 harness 具备可执行替代
- 不支持能力有明确提示和替代路径
