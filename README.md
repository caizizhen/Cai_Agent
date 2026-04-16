# CAI Agent

基于 **LangGraph** 的终端 Agent：在指定工作区内通过自然语言调用「目录树、列目录、glob、文本搜索、按行读文件、读/写文件、受限执行命令」，对接任意 **OpenAI 兼容** `POST /v1/chat/completions` 服务（默认面向 [LM Studio](https://lmstudio.ai/)），可选 **Textual** 交互界面。

## 与 Claude Code / Everything Claude Code 的功能对齐

- **整体定位**：`cai-agent` 对标官方 `anthropics/claude-code` 的「终端内智能代码 Agent」，并参考 `affaan-m/everything-claude-code` 的「性能优化 + 安全护栏 + 规则/技能」设计思路。
- **当前已对齐的子系统**（概念层级）：
  - **工具系统（Tools）**：`cai_agent.tools` 提供只读/写入/搜索/Git/MCP 等工具，并通过沙箱 `cai_agent.sandbox` 实现工作区越界防护和命令白名单，类似 Claude Code 的 Tool + 权限模型。
  - **会话与编排（Query/Tasks）**：`cai_agent.graph` 使用 LangGraph 状态机驱动「LLM ↔ 工具」循环，与 Claude Code 的 QueryEngine 思路一致；CLI 的 `run` / `continue` + `sessions` 子命令承担最小会话/任务管理角色。
  - **终端 UI（TUI）**：`cai_agent.tui` 使用 Textual 提供类似 Claude Code REPL 的对话界面和内置斜杠命令（`/status`、`/models`、`/mcp`、`/save`、`/load` 等）。
  - **安全模型（Sandbox & MCP）**：`cai_agent.sandbox` + `run_command` 白名单 + Git 只读工具 + MCP Bridge 的超时/鉴权，与 Everything Claude Code 中的 Agent 安全与沙箱策略保持同类防护思路。
- **规划中的增强能力**（逐步对齐中）：
  - **计划模式（Plan Mode）**：在执行前生成只读实现方案，风格对齐 Claude Code 的 Plan 模式与 Everything Claude Code 的 “research-first / plan-then-execute”。
  - **规则与技能（Rules / Skills）**：在仓库中提供 `rules/`、`skills/` 目录，结合 CLI/TUI 命令为常见语言和场景提供约束与可复用工作流（参考 ECC 的 `rules/`、`skills/` 结构）。
  - **统计与诊断（Stats）**：在现有 `run --json` / `continue --json` 输出基础上，逐步加入模型调用耗时、token 使用等诊断信息，对齐 Claude Code / ECC 的成本与性能视角。

完整架构说明与后续 Roadmap 见 `docs/ARCHITECTURE.zh-CN.md`。

## ⭐ Copilot 集成（重点）

`cai-agent` 现已内置 **Copilot provider 模式**（`llm.provider = "copilot"`），用于快速切到 Copilot 生态代理。

- **推荐方式**：通过 OpenAI 兼容代理接入 Copilot，再配置 `base_url/model/api_key`
- **优先级（copilot 模式）**：`COPILOT_*` 环境变量 > `[copilot]` > `[llm]`
- **关键变量**：`COPILOT_BASE_URL`、`COPILOT_MODEL`、`COPILOT_API_KEY`
- **手动选模型**：支持 `--model` 临时覆盖，以及 `cai-agent models` 列出代理当前可用模型

> 注意：GitHub Copilot 官方并未提供稳定公开的通用 `chat/completions` 编程接口；工程上通常通过兼容代理接入。

## MCP Bridge（下一步能力，已接入）

已内置最小 MCP Bridge 集成（可选开启）：

- `mcp_list_tools`：读取外部工具清单
- `mcp_call_tool`：调用外部工具

配置方式（`cai-agent/cai-agent.toml`）：

```toml
[mcp]
base_url = "http://localhost:8787"
api_key = "optional-token"
timeout_sec = 20

[agent]
mcp_enabled = true
```

协议约定（当前版本）：

- `GET {base_url}/tools` -> `{"tools":[{"name":"...","description":"..."}]}` 或 `["tool1", ...]`
- `POST {base_url}/tools/{name}`，Body: `{"args":{...}}`

## 更新日志

### 0.5.0（当前开发）

- **JSON 诊断补强**：`run --json` / `continue --json` 新增 `last_tool` 与 `error_count` 字段。
- **会话管理增强**：新增 `cai-agent sessions` 子命令；TUI 新增 `/sessions`，`/load latest` 可快速恢复最近会话。
- **会话详情增强**：`cai-agent sessions --details` 可查看每个会话的消息数、工具调用数、错误计数与回答预览。
- **会话匹配修复**：`sessions` 与 `/load latest` 默认匹配 `.cai-session*.json`，兼容 `.cai-session.json` 与自动命名文件。

### 0.4.1

- **TUI 保存优化**：`/save` 支持省略路径，默认生成 `.cai-session-YYYYMMDD-HHMMSS.json`。

### 0.4.0

- **JSON 结果再增强**：`run --json` / `continue --json` 新增 `tool_calls_count` 与 `used_tools` 字段。
- **TUI 加载摘要**：`/load <path>` 成功后自动显示会话摘要（assistant 轮次、工具调用数、最后回答预览）。

### 0.3.9

- **JSON 结果增强**：`run --json` / `continue --json` 新增 `provider`、`model`、`mcp_enabled`、`elapsed_ms` 字段，便于脚本和 CI 诊断。
- **TUI 会话管理**：新增 `/save <path>` 与 `/load <path>`，可在交互界面直接保存/恢复会话。

### 0.3.8

- **README 移至仓库根目录**：统一从根目录查看项目说明，避免 `cai-agent/README.md` 与外层文档双份维护。
- **MCP 探活增强**：`mcp-check` 新增 `--tool` / `--args`，可在列工具后直接做一次真实工具调用测试。

### 0.3.7

- **跨平台文档增强**：新增 macOS/Linux 使用说明（安装、复制配置、环境变量设置、常用命令）。
- **MCP 运维增强**：`mcp-check` 新增 `--force` / `--verbose`；TUI 新增 `/mcp refresh` 与 `/mcp call <name> <json_args>`。

### 0.3.6

- **MCP 可用性增强**：新增 `cai-agent mcp-check` 子命令；`mcp_list_tools` 增加短时缓存（15s，可 `force=true` 强刷）；TUI 增加 `/mcp` 快速查看。

### 0.3.5

- **MCP Bridge 最小集成**：新增 `mcp_list_tools` / `mcp_call_tool`，支持通过配置接入外部工具服务；`doctor` 与 TUI `/status` 展示 MCP 状态。

### 0.3.4

- **Git 只读工具增强**：新增 `git_status` 与 `git_diff` 工具，便于在推理链路中先判断改动范围再读文件，减少无效扫描。

### 0.3.3

- **TUI 模型管理**：新增 `/models` 与 `/use-model <id>`，可在交互界面直接拉取代理模型列表并切换会话模型（无需退出重启）。

### 0.3.2

- **Copilot 手动选模型**：新增 `cai-agent models`（读取 `/v1/models`）与全局 `--model` 参数（`run`/`continue`/`ui`/`doctor`/`models` 均可临时覆盖模型）。

### 0.3.1

- **Copilot 集成（提升优先级）**：新增 `llm.provider`（`openai_compatible` / `copilot`），`doctor` 与 TUI `/status` 会显示当前 provider；新增 `[copilot]` 配置段与 `COPILOT_*` 环境变量支持。

### 0.3.0

- **会话导入导出**：`run` 支持 `--save-session PATH` 与 `--load-session PATH`，可把 `messages` 持久化到 JSON 并恢复继续跑。
- **`cai-agent continue`**：基于历史会话 JSON 继续提问（语义等价于 `run --load-session`），适合做多轮脚本化自动化。
- **`run_command` 增强**：支持 `cwd`（相对工作区），可在子目录执行命令且仍保持沙箱边界。

### 0.2.x

- **`cai-agent doctor`**：打印解析后的配置、工作区、说明文件是否存在、是否在 Git 仓库内；**API Key 打码**；支持 `--config`、`-w` / `--workspace`。
- **`Settings.config_loaded_from`**：记录实际加载的 TOML 绝对路径（无文件则为 `None`）；`cai-agent run --json` 会附带该字段便于脚本排查。
- **`run --json`**：向 stdout 输出一行 JSON（`answer`、`iteration`、`finished`、`config`、`workspace`），并**不再**打印 stderr 上的对话过程片段。
- **LLM 重试**：对 HTTP **429 / 502 / 503 / 504** 自动退避重试（最多 5 次请求）。
- **工具**：`read_file` 支持 **`line_start` / `line_end`**（按行切片，省略 `line_end` 则读到文件尾）；新增 **`list_tree`**（受限深度与条数）。
- **TUI**：**`/status`** 查看当前模型与工作区；**`/reload`** 仅重建首条 system 提示（重读项目说明与 Git 摘要）。

### 0.1.x 及更早能力摘要

- **`cai-agent init`**：生成 `cai-agent.toml`（`--force` 覆盖）。
- **配置**：`temperature`、`timeout_sec`、`project_context`、`git_context` 等；环境变量覆盖。
- **系统提示**：可选 `CAI.md` / `AGENTS.md` / `CLAUDE.md` 与只读 Git 摘要。
- **工具**：`glob_search`、`search_text`；`run` / `ui`；内置示例 TOML 模板。

---

## 环境要求

- Python **3.11+**
- 提供 OpenAI 兼容 Chat Completions 的推理或 API 服务

## 安装

在仓库根目录下进入 `cai-agent`：

```bash
cd cai-agent
pip install -e .
```

安装后使用命令：`cai-agent`（`cai-agent --version` 查看版本）。

## macOS / Linux 使用

### 安装与初始化

```bash
cd /path/to/Cai_Agent/cai-agent
python3 -m pip install -e .
cai-agent init
cp cai-agent.toml .cai-agent.toml
```

### 环境变量（bash/zsh）

```bash
export LM_PROVIDER=copilot
export COPILOT_BASE_URL=http://localhost:4141/v1
export COPILOT_MODEL=gpt-4o-mini
export COPILOT_API_KEY=your-token
```

### 常用命令（macOS/Linux）

```bash
cai-agent doctor
cai-agent models
cai-agent run --workspace "$PWD" "请总结当前仓库结构"
cai-agent ui -w "$PWD"
cai-agent mcp-check --verbose
```

## Windows 使用

```powershell
cd .\cai-agent
py -m pip install -e .
cai-agent init
set LM_PROVIDER=copilot
set COPILOT_BASE_URL=http://localhost:4141/v1
set COPILOT_MODEL=gpt-4o-mini
set COPILOT_API_KEY=your-token
```

## 快速生成配置

```bash
cd cai-agent
cai-agent init
```

会生成 `cai-agent.toml`，按需编辑其中的 `[llm]` / `[agent]` 即可。

## 配置文件

1. 推荐在 `cai-agent/` 目录内运行 **`cai-agent init`** 生成 `cai-agent.toml`。
2. 将 `cai-agent.toml` 放在运行命令时的当前工作目录，或使用 **`CAI_CONFIG`** / **`--config`**。
3. **优先级**：环境变量 **高于** TOML **高于** 内置默认值。勿将含真实 API Key 的配置提交到版本库。

### `[llm]` 常用项

| 键 | 说明 |
|----|------|
| `base_url` | API 根地址；未以 `/v1` 结尾时会自动补全 |
| `model` | 模型 ID |
| `api_key` | Bearer Token |
| `provider` | `openai_compatible`（默认）或 `copilot` |
| `http_trust_env` | 是否使用系统代理 |
| `temperature` | 采样温度，默认 `0.2`，范围会裁剪到 `0~2` |
| `timeout_sec` | 单次 Chat Completions 请求超时（秒），默认 `120`，范围约 `5~3600` |

### `[agent]` 常用项

| 键 | 说明 |
|----|------|
| `workspace` | 可选，工作区根；不设则用当前目录或 `CAI_WORKSPACE` |
| `max_iterations` | LLM↔工具最大轮数 |
| `command_timeout_sec` | `run_command` 进程超时 |
| `mock` | 为 `true` 时不请求真实模型 |
| `project_context` | 为 `true` 时在系统提示中附加根目录说明文件（有长度上限） |
| `git_context` | 为 `true` 时附加只读 `git` 摘要 |
| `mcp_enabled` | 为 `true` 时启用 MCP Bridge 工具 |

### Copilot 代理模式示例（重点）

```toml
[llm]
provider = "copilot"

[copilot]
base_url = "http://localhost:4141/v1"
model = "gpt-4o-mini"
api_key = "your-copilot-proxy-token"
```

## 环境变量（覆盖配置文件）

| 变量 | 含义 |
|------|------|
| `CAI_CONFIG` | TOML 配置文件路径 |
| `CAI_WORKSPACE` | 工作区根目录 |
| `LM_BASE_URL` | API 根 URL |
| `LM_MODEL` | 模型名 |
| `LM_API_KEY` | Bearer Token |
| `LM_PROVIDER` | `openai_compatible` 或 `copilot` |
| `COPILOT_BASE_URL` | Copilot 模式代理 URL |
| `COPILOT_MODEL` | Copilot 模式模型名 |
| `COPILOT_API_KEY` | Copilot 模式 token |
| `MCP_ENABLED` | `1` 时启用 MCP Bridge 工具 |
| `MCP_BASE_URL` | MCP Bridge 基础地址 |
| `MCP_API_KEY` | MCP Bridge 可选鉴权 token |
| `MCP_TIMEOUT` | MCP Bridge 请求超时（秒） |

## 用法

```bash
cai-agent doctor
cai-agent models
cai-agent sessions
cai-agent sessions --details
cai-agent run --model gpt-4o-mini "解释当前项目结构"
cai-agent continue .cai-session.json "继续上次任务"
cai-agent run --json "输出机器可解析结果"
cai-agent mcp-check --force --verbose
cai-agent mcp-check --tool ping --args "{}"
cai-agent ui -w "$PWD"
# 基于 workflow JSON 依次运行多步任务
cai-agent workflow path/to/workflow.json --json
```

`run --json` / `continue --json` 当前会返回：

- `answer` / `iteration` / `finished`
- `workspace` / `config` / `provider` / `model`
- `mcp_enabled` / `elapsed_ms`
- `tool_calls_count` / `used_tools` / `last_tool` / `error_count`

**内置斜杠命令（UI）：**

- `/help` 或 `/?`
- `/status`
- `/models`
- `/mcp`
- `/mcp refresh`
- `/mcp call <name> <json_args>`
- `/save [path]`（不传则自动命名）
- `/load <path|latest>`
- `/sessions`
- `/use-model <id>`
- `/reload`
- `/clear`

## 工具与安全说明

- **read_file** / **list_dir** / **list_tree** / **write_file**：路径相对于工作区，不能越界；`read_file` 可用 `line_start` / `line_end` 控制行范围。
- **glob_search**：`pattern` 与 `root` 不得包含 `..`；结果条数有上限。
- **search_text**：子串搜索；通过 `glob`、`max_files`、`max_matches`、`max_file_bytes` 限制开销。
- **git_status**：只读 `git status`（支持 short 模式）。
- **git_diff**：只读 `git diff`（支持 staged 与 path 参数）。
- **mcp_list_tools**：读取 MCP Bridge 工具清单（需启用）。
- **mcp_call_tool**：调用 MCP Bridge 工具（需启用）。
- **run_command**：仅允许白名单中的可执行文件名，禁止路径形式与常见 shell 元字符；支持 `cwd` 指定工作区内子目录（默认 `.`）。

实现见 `cai-agent/src/cai_agent/tools.py` 与 `cai-agent/src/cai_agent/sandbox.py`。

## 许可证

以仓库根目录为准（若未声明则由使用者自行约定）。
