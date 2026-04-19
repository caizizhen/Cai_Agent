# 对标 Claude Code / ECC 的优化清单与开发计划同步

> 参考仓库（能力与生态取向）：
>
> - [anthropics/claude-code](https://github.com/anthropics/claude-code)：终端 Agent、官方安装脚本、IDE/GitHub 集成、插件目录、`/bug`、官方文档站点、数据使用说明。
> - [affaan-m/everything-claude-code](https://github.com/affaan-m/everything-claude-code)：Skills/Agents/Hooks/Rules、连续学习与本能、质量与安全门禁、跨 Cursor/Codex/OpenCode、Dashboard GUI、`/model-route`、hook profile、选择性安装与状态存储等。
>
> 本仓库权威状态仍以 **[PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md)**、**[PRODUCT_GAP_ANALYSIS.zh-CN.md](PRODUCT_GAP_ANALYSIS.zh-CN.md)**、**[ROADMAP_EXECUTION.zh-CN.md](ROADMAP_EXECUTION.zh-CN.md)** 为准；本文是 **PM 向开发 / QA 的同步视图**。

---

## 1. 两参考源 → 本仓库「仍可优化」映射表

| 参考能力（概括） | 主要来自 | 本仓库现状 | 优化方向 |
|------------------|----------|------------|----------|
| 官方一键安装 / WinGet / Homebrew | claude-code | pip / 源码为主 | **P2**：可选安装脚本或 winget 清单；不阻塞核心 |
| IDE / GitHub 深度集成、`@claude` | claude-code | 无同等官方集成 | **OOS** 或 **MCP/文档** 等价路径，在 Parity 备注备案 |
| `/bug` 内建反馈 | claude-code | 无 | **P2**：Issue 模板 + `doctor` 脱敏导出（见缺口分析 §4） |
| WebSearch / 结构化搜索 | claude-code | Parity：`Next`/`MCP` | **P1**：认证 MCP 配方 + 文档 **或** 内置薄封装，须在矩阵勾选 |
| Notebook 编辑 | claude-code | Parity：`Next`/`MCP` | **P1**：同上 |
| 任务看板 / 富任务 UI | claude-code / ECC | Parity：`Next`；已有 `board --json` 等 | **P1**：TUI 或本地 Web 最小看板，消费 `workflow`/`observe` 事件 |
| 会话历史 / Dashboard 运营 | ECC | Parity L2：`Next` | **P1–P2**：与 `observe`、成本、事件 schema 联动 |
| 上下文压缩 / `/compact` 策略 | ECC + 官方习惯 | `[context]` + 文档 | **P1**：策略可配置 + 与 `observe`/cost 联动（见 CONTEXT_AND_COMPACT） |
| Token / 成本路由（`/model-route`） | ECC | `cost budget` + 模型 profile 路由（进行中） | **P1**：规则化路由（复杂度阈值）；当前以人工 profile 为主 |
| Hooks 全生命周期 + profile | ECC | `hook_runtime` + `[hooks]` profile | **P1**：与 `hooks.json` 事件矩阵对齐、文档化 |
| 记忆 / 本能 / TTL / 置信度 | ECC | Parity L3：`Next` | **P1**：schema 校验已部分具备；补 TTL、自动提炼策略 |
| 跨 harness 导出 | ECC | `export` + 文档 | **P2**：manifest 维度持续对齐 [CROSS_HARNESS_COMPATIBILITY.zh-CN.md](CROSS_HARNESS_COMPATIBILITY.zh-CN.md) |
| Desktop Dashboard（Tkinter 等） | ECC | 无 | **P2+**：与「任务看板」可合并规划，避免双轨 |
| 社区技能库体量 | ECC | 本地 `skills/` + 插件清单 | **MCP/Next**：渐进吸收，不阻塞发版 |
| **多模型选择与多供应商** | 两者交集 | **Sprint 1–2 已交付 CLI + 适配器 + 路由**（见下文） | **Sprint 3**：TUI 面板、`/use-model` 升级、`/status`/session、CHANGELOG/Parity |

---

## 2. 按 Parity 分层汇总（当前仍为 `Next` 的优化点）

以下与 [PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md) 一致，便于发版评审勾选：

| 分层 | 能力项 | 状态 | 优化动作（开发认领） |
|------|--------|------|----------------------|
| **L1** | WebSearch / 结构化搜索 | `Next`/`MCP` | 定案：MCP 配方文档 **或** 内置工具；更新矩阵一行 |
| **L1** | Notebook | `Next`/`MCP` | 同上 |
| **L1** | 任务看板 / 富任务 UI | `Next` | 与 `board`/`workflow` 统一事件模型；先做 TUI 或最小 Web |
| **L2** | 会话与历史（Dashboard 级） | `Next` | 扩展 `observe`/session 导出；可选只读 Dashboard |
| **L2** | 上下文压缩策略 | `Next` | 实现可配置策略 + 可观测指标 |
| **L2** | 成本 / token 策略 | `Next` | 由统计升级为策略（与 profile 路由衔接） |
| **L2** | 钩子扩展深度 | `Next` | 文档 + 执行器与 harness 事件对齐 |
| **L3** | 记忆 / 本能（TTL 等） | `Next` | TTL、置信度、自动提炼流水线 |
| **L3** | 跨工具导出 | `Next` | 按 CROSS_HARNESS 清单逐项 Done |
| **L3** | 可视化运营面板 | `Next` | P2+，与 L1 任务看板合并评估 |

---

## 3. 近期专项：模型切换 / 多供应商（与两参考源对齐）

| 阶段 | 状态（以仓库 QA 报告为准） | 文档 |
|------|----------------------------|------|
| Sprint 1–2 | **已完成**：profile、`cai-agent models`、Anthropic 原生、工厂路由、security-scan 扩展；QA Go beta | [MODEL_SWITCHER_BACKLOG.zh-CN.md](MODEL_SWITCHER_BACKLOG.zh-CN.md)、[docs/qa/runs/sprint2-qa-20260418-035002.md](qa/runs/sprint2-qa-20260418-035002.md) |
| Sprint 3 | **进行中 / 待收尾**：TUI 模型面板、M5/M7/M9、打 GA tag、合 `main` | [MODEL_SWITCHER_DEVPLAN.zh-CN.md](MODEL_SWITCHER_DEVPLAN.zh-CN.md) §4 |

---

## 4. 开发计划同步（给开发）

### 4.1 本周优先级（Sprint 3）

1. **M4**：TUI `/models` 打开模型面板（列表、切换、新增/编辑/删除/测试）；空态引导。
2. **M5**：`/use-model` 优先按 **profile id** 整组切换；远端 `/models` refresh 若 backlog 已列则一并收口。
3. **M7**：`/status` 展示 `active` / `subagent` / `planner`；`--save-session` 落盘含 profile 元数据。
4. **M9**：CHANGELOG 用户语言 4 条；[PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md) 增一行「多模型 profile + 多供应商」→ `Done`；README 示例对齐。

### 4.2 本月次优先级（Parity P1）

- **WebSearch / Notebook**：二选一写进矩阵（`MCP` 链接 **或** `Next` 实现窗口）。
- **任务看板**：与现有 `board --json` 共用 schema，避免重复造事件模型。

### 4.3 工程纪律（合并前）

- 清理不应入仓产物（`__pycache__`、临时 `memory/instincts` 测试文件等），更新 `.gitignore` 若需要。
- Sprint 冻结日：`python scripts/run_regression.py` 全绿后再打 tag。

**详细排期与 RACI**：仍以 [MODEL_SWITCHER_DEVPLAN.zh-CN.md](MODEL_SWITCHER_DEVPLAN.zh-CN.md) 与 [ROADMAP_EXECUTION.zh-CN.md](ROADMAP_EXECUTION.zh-CN.md) 为准。

---

## 5. 开发计划同步（给 QA）

### 5.1 Sprint 3 新增/变更测点

| # | 场景 | 预期 |
|---|------|------|
| 1 | TUI 打开模型面板 | 列表与当前 `active` 一致；Enter 切换后下一条 `run` 走新 profile |
| 2 | 面板子动作 | add / edit / rm / ping 各至少一条正向 + 一条错误路径（env 缺失） |
| 3 | `/use-model` | profile id 与纯 model id 回退行为符合 backlog |
| 4 | `/status` + session | 含 profile 字段；不含明文 api_key |
| 5 | 全量回归 | `python scripts/run_regression.py` + `pytest cai-agent/tests` |

### 5.2 发版前（GA）

- 产出 `docs/qa/runs/regression-*.md` 与 Sprint3 手工矩阵 Markdown（格式同 [sprint2-qa-20260418-035002.md](qa/runs/sprint2-qa-20260418-035002.md)）。
- 真实 key 冒烟（可选）：内测用户各跑一次 `models ping` + `run "hello"`，结果记入 Issue 或 QA 附录。

---

## 6. 维护约定（PM）

- 每对外发版至少更新 [PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md) 一行（`Next`→`Done` 或 `MCP` 或 `OOS`）。
- 本文与 [PRODUCT_GAP_ANALYSIS.zh-CN.md](PRODUCT_GAP_ANALYSIS.zh-CN.md) 冲突时，以 **缺口分析 + Parity 矩阵** 为准，并回写本文「§2」表格。

---

*文档版本：2026-04-18；维护者：产品。*
