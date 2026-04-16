# Cai Agent — 架构概览（对标 Claude Code）

> 本文档参考 `ComeOnOliver/claude-code-analysis` 对 Claude Code 的结构化分析，整理 `Cai_Agent` 当前的模块划分与子系统，对齐关系与差异。

---

## 1. 项目概览

`Cai_Agent` 是一个基于 **LangGraph** 的终端 Agent，用于在指定工作区内执行代码理解与小规模改动任务：

- 通过自然语言描述目标；
- 在受限工作区内使用只读/写入/搜索/Git/MCP 等工具；
- 在 CLI 与 Textual TUI 中以会话形式运行。

目标是向 `anthropics/claude-code` 和 `affaan-m/everything-claude-code` 学习其架构与安全/性能/规则体系，但保持轻量 Python 实现。

---

## 2. 技术栈

- **语言**：Python 3.11+
- **编排框架**：LangGraph（有向图形式的状态机）
- **HTTP 客户端**：`httpx`
- **终端 UI**：Textual
- **配置**：TOML + 环境变量

---

## 3. 目录结构（简化）

```text
Cai_Agent/
├── README.md
├── rules/                 # 规则目录骨架（common/python 等）
├── skills/                # 技能目录骨架（可复用工作流模版）
├── docs/
│   └── ARCHITECTURE.zh-CN.md
└── cai-agent/
    ├── pyproject.toml
    └── src/cai_agent/
        ├── __init__.py
        ├── __main__.py    # CLI 入口（run/continue/plan/ui/...）
        ├── config.py      # Settings 解析（TOML + env）
        ├── context.py     # 系统提示增强（项目/Git 上下文）
        ├── graph.py       # LangGraph 状态机（LLM ↔ 工具）
        ├── llm.py         # Chat Completions + 重试 + token 统计
        ├── tools.py       # 工具实现与 dispatch
        ├── sandbox.py     # 路径与命令沙箱
        ├── session.py     # 会话 JSON 读写与枚举
        ├── tui.py         # Textual UI（斜杠命令）
        ├── doctor.py      # `cai-agent doctor` 诊断
        ├── models.py      # `/v1/models` 查询封装
        └── templates/
            └── cai-agent.example.toml
```

---

## 4. 入口点

- `cai_agent.__main__.py`：提供 `cai-agent` 脚本入口，子命令包括：
  - `init`：生成示例 `cai-agent.toml`；
  - `run` / `continue`：一次性执行或基于历史会话继续；
  - `sessions`：列出会话 JSON；
  - `models`：列出模型；
  - `mcp-check`：MCP Bridge 探活；
  - `ui`：Textual 交互界面；
  - `plan`：只生成实现计划草案（不执行工具）。

CLI 层负责解析参数和加载 `Settings`，然后调用下层 `graph.build_app` 或直接调用 `llm.chat_completion`。

---

## 5. 核心架构

### 5.1 配置与状态（`config.py`）

- `Settings` 数据类封装：
  - LLM 提供方/模型/API 地址与 Key；
  - 工作区路径与命令超时；
  - 项目/Git 上下文开关；
  - MCP Bridge 配置；
  - 从哪个 TOML 读取配置（`config_loaded_from`）。
- 加载顺序：**默认值 → TOML → 环境变量**，环境变量优先。

### 5.2 LLM 封装与用量统计（`llm.py`）

- `chat_completion(settings, messages)`：
  - 通过 OpenAI 兼容 `POST /chat/completions` 发起请求；
  - 内置对 429/502/503/504 的指数退避重试；
  - 从响应中提取 `usage` 字段，将 prompt/完成/总 token 数累加到进程级计数器。
- `reset_usage_counters()` / `get_usage_counters()`：
  - 供 CLI 在一次调用前清零，结束后读出本次会话的 token 使用。

### 5.3 LangGraph 状态机（`graph.py`）

- `AgentState`：
  - `messages`：对话历史（system/user/assistant）；
  - `iteration`：迭代次数；
  - `pending`：待执行工具请求；
  - `finished` / `answer`：结束标志与最终回答。
- 节点：
  - `llm`：调用 `chat_completion`，要求模型输出 JSON（`finish` 或 `tool`）；
  - `tools`：调用 `tools.dispatch` 执行对应工具并将结果编码为 JSON 附加到 `messages`。
- 状态机路线：
  - `START → llm → (end|tools|llm)`，类似 Claude Code 的 QueryEngine 循环。

---

## 6. 工具系统与沙箱（`tools.py` + `sandbox.py`）

- 工具实现（只列核心）：
  - `read_file` / `list_dir` / `list_tree`；
  - `glob_search` / `search_text`；
  - `write_file`；
  - `run_command`：只允许白名单命令名，禁止路径与 shell 元字符；
  - `git_status` / `git_diff`（只读）；
  - `mcp_list_tools` / `mcp_call_tool`。
- `dispatch(settings, name, args)`：
  - 统一入口，根据工具名路由到具体实现；
  - 统一抛出 `SandboxError` 用于提示 LLM 工具调用错误。
- 沙箱（`sandbox.py`）：
  - `resolve_workspace_path`：保证所有文件操作在工作区内，阻止 `..` 越界。

这一套与 Claude Code 的 Tool + 权限/沙箱模型在概念上对齐，但实现更轻量。

---

## 7. 会话与 TUI（`session.py` + `tui.py`）

- `session.py`：
  - 读写会话 JSON（包含 messages/answer/配置/工作区等信息）；
  - 列出最近会话文件（支持 pattern/limit），供 CLI 与 TUI 复用。
- Textual TUI：
  - 顶栏 + 对话区 + 底部输入；
  - 内置斜杠命令：`/status`、`/models`、`/mcp`、`/save`、`/load`、`/sessions`、`/use-model`、`/reload`、`/clear` 等；
  - 通过后台线程调用 `graph.build_app(...).invoke`，并实时更新进度提示。

---

## 8. 计划模式（`cai-agent plan`）

- `plan` 子命令：
  - 使用独立的系统提示 + 直接调用 `llm.chat_completion`；
  - 只生成实现方案（不调工具），输出结构化自然语言计划；
  - 支持 `--json` 输出，包含 goal、plan 文本、provider/model、elapsed_ms 和本次 LLM 调用的 token 统计。
- 对齐关系：
  - 概念上对应 Claude Code 的 Plan Mode 和 ECC 的 `plan-then-execute` 工作流；
  - 当前版本不自动执行计划，仍由用户手动运行 `run` / `continue`。

---

## 9. 规则与技能（`rules/` + `skills/`）

- `rules/`：
  - 提供 `common/` 与 `python/` 等子目录的骨架；
  - 用于未来放置风格、安全与工程实践规则；
  - 计划在计划/执行阶段读取并注入到系统提示中，形成项目级「护栏」。
- `skills/`：
  - 提供统一存放技能（可复用工作流与提示模版）的目录；
  - 风格对齐 Everything Claude Code 的技能系统；
  - 未来可为常用技能提供 CLI 子命令或 TUI 斜杠入口。

---

## 10. 与外部仓库的对齐与差异

- **对齐点**：
  - 终端内 Agent 工作流（Claude Code）；
  - 工具 + 沙箱 + Git/MCP 集成（Claude Code / ECC）；
  - 计划优先与 token 统计视角（Claude Code / ECC）。
- **刻意保留的差异**：
  - 使用 Python + LangGraph 而非 TypeScript + Bun + Ink；
  - 暂不实现多 Agent、Bridge/Kairos/Coordinator 等高级模式；
  - 规则与技能体系目前仅有目录与文档骨架，后续视需求演进。

---

## 11. Roadmap（参考 Claude Code / Everything Claude Code）

本节是对后续演进方向的更细分规划，按阶段对齐 Claude Code 与 Everything Claude Code 的能力。

### 阶段 5：工作流与多 Agent / 子任务编排

- 当前已实现基础版 workflow：`cai-agent workflow <file> [--json]`，按 JSON 文件中的 `steps` 顺序依次运行多个 `goal`，并汇总每步的耗时与工具调用统计；
- 后续可以在此基础上扩展为更复杂的工作流描述（如带条件、重试或分支），以及多 Agent 协调（在同一进程内维护多个独立的 `AgentState` 并汇总结果）。

### 阶段 6：规则执行与安全扫描深化

- 为 `rules/common`、`rules/python` 设计简单规则格式（YAML/Markdown），描述命名/日志/测试/安全等约束；
- 在 `plan` 阶段加载匹配当前目标的规则，并将其融入 system prompt，让模型生成「规则清单 + 风险提示」；
- 预留 `security-scan` 类技能，通过现有工具（`search_text`、`git_diff`、`run_command`）对常见敏感模式做基础扫描，并在未来可集成专用安全工具。

### 阶段 7：记忆 / 会话持久化与学习

- 基于 `.cai-session*.json` 定义「记忆抽取」流程：对历史会话运行专门技能，将经验提炼成规则或项目说明，落地到 `rules/` 或 `memory/`；
- 在 `context.augment_system_prompt` 中注入这些项目记忆摘要，并对长度做裁剪，形成跨会话的持续学习能力。

### 阶段 8：多入口与生态集成

- 保持 `run --json` / `plan --json` 输出结构稳定，方便脚本和 CI 集成（自动审查、报表等场景）；
- 预留一个极简本地协议（如 HTTP 或 socket），让 IDE/其他 Agent Harness 可以把 `Cai_Agent` 作为后端服务调用；
- 保持 `rules/`、`skills/` 文件格式尽量语言无关，使其可以被 Claude Code、Cursor 等其他工具直接复用。

### 阶段 9：观察性与调试支持

- 在现有 `doctor` 基础上扩展一个面向统计的子命令（如 `stats`），汇总最近若干次调用的耗时、token 使用和工具调用次数；
- 在架构文档中持续记录调试/观察性入口（CLI 参数、JSON 字段、会话文件结构），方便在实际项目中分析 Agent 表现。

