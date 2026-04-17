# 对标参考源的本版功能清单（2026-04-17）

本文档由产品侧根据以下公开仓库的能力与实现取向整理，用于 **开发排期、QA 验收、用户预期管理** 的同一事实源：

- 官方终端 Agent 基线：[anthropics/claude-code](https://github.com/anthropics/claude-code)（安装分发、终端/IDE/GitHub 集成、`/bug` 反馈、插件目录、官方文档站点）
- 治理与 harness 增强基线：[affaan-m/everything-claude-code](https://github.com/affaan-m/everything-claude-code)（skills/agents/hooks/rules、连续学习/本能、质量与安全门禁、跨 Cursor/Codex/OpenCode、Dashboard、hook runtime profile、选择性安装与状态存储等）

与本仓库既有能力地图的关系：

- 总缺口与门禁：[PRODUCT_GAP_ANALYSIS.zh-CN.md](PRODUCT_GAP_ANALYSIS.zh-CN.md)
- 发版勾选矩阵：[PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md)
- 工程落地清单：[ROADMAP_EXECUTION.zh-CN.md](ROADMAP_EXECUTION.zh-CN.md)

---

## 1. 给所有人的摘要（What / Why / Not）

| 主题 | 结论 |
|------|------|
| **本版目标** | 在 **不复制** Claude Code 封闭能力（企业门控、官方 `/bug` 上报管道等）的前提下，把 **官方 L1 体验环** 与 **ECC 式 L2/L3 治理面** 中、与 CAI Agent 架构（Python / LangGraph / OpenAI 兼容）匹配的部分，收敛为可验收的迭代包。 |
| **已较强对齐** | 工作区工具链、受限 Shell、只读 Git、计划→执行、会话延续、工作流 JSON、`fetch_url`、质量门禁与安全扫描、导出到多 harness、记忆/本能 CLI 等（详见 Parity 矩阵）。 |
| **本版优先补齐** | WebSearch/Notebook 的 **MCP 或内置二选一** 决策落地；任务/会话 **运营可视化** 最小版；记忆 **schema + TTL/置信度**；hooks **执行器与配置** 深化；**用户反馈与发行说明** 闭环。 |
| **明确降级** | 与 Anthropic 账号/市场/Discord 强绑定的能力标为 **OOS**，用开源替代方案（Issue 模板、社区渠道、可自建遥测）满足「可反馈」而非「同形态」。 |

---

## 2. 开发（Dev）— 本版需求包与实现要点

以下每项含：**交付物**、**技术要点**、**依赖**。

### Epic A — 官方体验环补齐（claude-code）

| ID | 需求 | 交付物 | 技术要点 |
|----|------|--------|----------|
| A1 | **Web 检索能力**（对标官方 WebSearch 类工作流） | `docs/` 中 **认证 MCP 配方** *或* 内置工具（二选一写进 Parity）；`[permissions]` / 配置样例 | 若走 MCP：固定工具名、超时、密钥环境变量、最小复现步骤；若内置：API Key、配额、结果截断与安全域 |
| A2 | **Notebook 编辑**（对标） | 同上：`MCP` 路径优先或 `OOS` 备注 | Jupyter 协议重；默认建议 MCP + 文档，避免引入重依赖到核心包 |
| A3 | **任务看板 / 富任务 UI**（对标多步任务可观测性） | TUI 或本地 Web **最小看板**：`workflow` / `observe` 消费同一事件模型 | 统一 `task_id`、状态机、`events` schema 版本化；与 `graph.py` 输出对齐 |
| A4 | **插件发现体验**（对标 plugins 目录说明，非市场） | `cai-agent plugins` 输出增强或 `docs` 一页「推荐组合包」 | 与 `plugin_registry.py` 一致；不写死商业市场 |

### Epic B — ECC 式治理与 harness（everything-claude-code）

| ID | 需求 | 交付物 | 技术要点 |
|----|------|--------|----------|
| B1 | **记忆 v1 完备** | `memory` 写入 **schema 校验**、导入导出、检索排序；可选 **TTL / 置信度** 字段 | 与 `schemas/memory_entry_v1.schema.json` 一致；CLI 与文档同步 |
| B2 | **本能（instincts）流水线** | 与记忆联动的 **提炼 / 过期 / 搜索** 策略文档 + 必要自动化钩子 | 对齐现有 `memory/instincts/` 实践；避免静默丢内容（参考 ECC `/instinct-import` 类问题） |
| B3 | **Hooks 运行时** | `hooks.json` **匹配器 + 命令执行** 与主循环集成度提升；**禁用列表 / profile**（minimal/standard/strict） | 安全：默认禁止高危 shell；跨平台 Windows 测通 |
| B4 | **上下文与成本策略** | `[context]` 与 `observe` / usage **联动规则**（何时 compact、何时降模） | 配置化；可观测：日志或 `stats` 可验证 |
| B5 | **跨 harness 导出** | `export` manifest 维度与 [CROSS_HARNESS_COMPATIBILITY.zh-CN.md](CROSS_HARNESS_COMPATIBILITY.zh-CN.md) 对齐项勾选 | 增量对齐，不追求 ECC 全量技能库 |

### Epic C — 产品化与分发（双参考交集）

| ID | 需求 | 交付物 | 技术要点 |
|----|------|--------|----------|
| C1 | **用户反馈通道**（对标 `/bug` 的「可行动」而非「同管道」） | Issue 模板 + TUI/CLI **一键复制环境信息**（版本、OS、配置脱敏） | 不落盘密钥；`doctor` 输出可包含 |
| C2 | **发行说明** | CHANGELOG / README 可见：**本版相对 claude-code & ECC 的对标进度** | 与 Parity 矩阵一行联动 |

**开发优先级建议（本版迭代内）**：A3、B1、B3 → A1（MCP 文档优先）→ B4 → B2 → A2/C1/C2。  
（理由：运营可视与记忆/hooks 是 ECC 差异化核心且利于后续 MCP 与 Web 能力叠加。）

---

## 3. QA — 验收清单与回归范围

### 3.1 每 Epic 最小验收

| Epic | 必须通过 |
|------|----------|
| A | A1：按文档从零复现 MCP（或内置）成功一次检索；A3：看板展示至少一次完整 `workflow`  run 的状态变化 |
| B | B1：非法 memory entry 写入失败且错误可读；B3：关闭某 hook ID 后行为可验证变化 |
| C | C1：导出诊断信息不含 `api_key` 明文；C2：CHANGELOG 与 Parity 至少一行一致 |

### 3.2 回归

- 跑通：`python scripts/run_regression.py`（策略见 [QA_REGRESSION_LOGGING.zh-CN.md](QA_REGRESSION_LOGGING.zh-CN.md)）
- 新增用例建议：`workflow`/`observe` 事件 schema；`memory` schema；hook profile 切换

### 3.3 风险与负面测试

- **密钥泄漏**：配置文件、日志、反馈粘贴框
- **Windows 路径**：hook 命令、`run_command`、会话路径
- **MCP 超时与降级**：桥接不可用时主循环仍可用

---

## 4. 用户（User）— 本版你会看到什么

| 能力 | 用户可见变化 |
|------|----------------|
| 任务可观测 | 除 JSON 外，可用 **更简单的方式** 看到任务进行到哪一步（TUI 或本地页） |
| 记忆更可靠 | 导入导出更一致，**坏数据会被拒绝** 而不是静默失败 |
| 更省 token / 更可控 | 可在配置里看到 **压缩与成本** 的建议策略（与文档一致） |
| 上网搜索 / Notebook | **优先通过 MCP** 接入；请按文档绑定密钥；核心包保持精简 |
| 反馈问题更方便 | 一键收集 **非敏感** 环境信息，便于在 GitHub 提 Issue |

**仍与 Claude Code 官方不一致的说明（预期管理）**：不提供 Anthropic 安装脚本、官方插件市场、Discord 一体化；CAI Agent 面向 **OpenAI 兼容端点** 与 **自托管 MCP**。

---

## 5. 维护动作（发版前 PM / Release Owner）

1. 更新 [PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md)：`Next` → `Done` 或 `MCP`（附文档路径）或 `OOS`（附理由）。  
2. 若本清单与 [ROADMAP_EXECUTION.zh-CN.md](ROADMAP_EXECUTION.zh-CN.md) 冲突，以 **Parity + 本清单** 合并结论为准，并回写路线图对应条。  
3. 在 CHANGELOG 中用 3～5 条 **用户语言** 概括 Epic 交付。

---

## 6. 参考链接（便于评审打开）

- [https://github.com/anthropics/claude-code](https://github.com/anthropics/claude-code)
- [https://github.com/affaan-m/everything-claude-code](https://github.com/affaan-m/everything-claude-code)

---

*文档版本：2026-04-17；维护者：产品（可随迭代重命名文件或追加修订小节）。*
