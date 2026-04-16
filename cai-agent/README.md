# CAI Agent

基于 **LangGraph** 的终端 Agent：在指定工作区内通过自然语言调用「目录树、列目录、glob、文本搜索、按行读文件、读/写文件、受限执行命令」，对接任意 **OpenAI 兼容** `POST /v1/chat/completions` 服务（默认面向 [LM Studio](https://lmstudio.ai/)），可选 **Textual** 交互界面。

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

配置方式（`cai-agent.toml`）：

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

### 0.3.6（当前开发）

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

在 `cai-agent` 目录下：

```bash
pip install -e .
```

安装后使用命令：`cai-agent`（`cai-agent --version` 查看版本）。

## 快速生成配置

```bash
cai-agent init
```

会生成 `cai-agent.toml`，按需编辑其中的 `[llm]` / `[agent]` 即可。

## 配置文件

1. 推荐 **`cai-agent init`** 生成 `cai-agent.toml`。
2. 将 `cai-agent.toml` 放在**运行命令时的当前工作目录**，或使用 **`CAI_CONFIG`** / **`--config`**（适用于 `run` / `continue` / `ui` / **`doctor`**）。
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

### 本地（LM Studio）示例

```toml
[llm]
base_url = "http://localhost:1234/v1"
model = "你的模型标识"
api_key = "lm-studio"
temperature = 0.2
timeout_sec = 120
```

### 云端兼容 API 示例

```toml
[llm]
base_url = "https://api.openai.com/v1"
model = "gpt-4o-mini"
api_key = "sk-..."
```

### Copilot 代理模式示例（重点）

```toml
[llm]
provider = "copilot"

[copilot]
base_url = "http://localhost:4141/v1"
model = "gpt-4o-mini"
api_key = "your-copilot-proxy-token"
```

也可以只设环境变量（推荐用于本机临时调试）：

```bash
set LM_PROVIDER=copilot
set COPILOT_BASE_URL=http://localhost:4141/v1
set COPILOT_MODEL=gpt-4o-mini
set COPILOT_API_KEY=your-token
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
| `COPILOT_BASE_URL` | Copilot 模式的代理 URL（OpenAI 兼容） |
| `COPILOT_MODEL` | Copilot 模式模型名 |
| `COPILOT_API_KEY` | Copilot 模式 token |
| `LM_HTTP_TRUST_ENV` | `1` / `true` 时使用系统代理 |
| `LM_TEMPERATURE` | 温度 |
| `LM_TIMEOUT` | Chat Completions HTTP 超时（秒） |
| `CAI_MAX_ITER` | 最大迭代轮数 |
| `CAI_CMD_TIMEOUT` | `run_command` 超时（秒） |
| `CAI_PROJECT_CONTEXT` | `0` / `1` 关闭或开启项目说明文件注入 |
| `CAI_GIT_CONTEXT` | `0` / `1` 关闭或开启 Git 摘要注入 |
| `MCP_ENABLED` | `1` 时启用 MCP Bridge 工具 |
| `MCP_BASE_URL` | MCP Bridge 基础地址（如 `http://localhost:8787`） |
| `MCP_API_KEY` | MCP Bridge 可选鉴权 token |
| `MCP_TIMEOUT` | MCP Bridge 请求超时（秒） |
| `CAI_MOCK` | `1` 时不请求真实模型 |
| `CAI_MOCK_REPLY` | Mock 模式下固定模型返回文本 |

## 用法

**诊断当前配置（推荐连不上 API 时先跑）：**

```bash
cai-agent doctor
cai-agent doctor -w D:\repo\myapp --config D:\repo\myapp\cai-agent.toml

# 临时切模型查看配置结果
cai-agent doctor --model gpt-4o-mini
```

**单次任务：**

```bash
cai-agent run --workspace D:\repo\myapp 用一句话说明 src 目录下有哪些顶层文件
cai-agent run --model gpt-4o-mini 解释当前项目结构

# 保存会话到 JSON（后续可继续）
cai-agent run --save-session .cai-session.json 修复 tests 失败

# 从历史会话继续
cai-agent run --load-session .cai-session.json 继续刚才任务并补充测试
```

**继续历史会话（专用子命令）：**

```bash
cai-agent continue .cai-session.json 请把 README 的更新日志再整理一下
```

**查看代理可用模型并手动选择：**

```bash
# 文本输出
cai-agent models

# JSON 输出（脚本友好）
cai-agent models --json

# 结合 copilot provider + 指定模型运行
cai-agent run --model gpt-4o-mini 请总结当前任务
```

**检查 MCP Bridge 连通性：**

```bash
cai-agent mcp-check
cai-agent mcp-check --json
```

**单次任务且输出 JSON（便于脚本解析）：**

```bash
cai-agent run --json 你的任务描述
```

**交互式终端 UI：**

```bash
cai-agent ui -w D:\repo\myapp
```

**内置斜杠命令（UI）：**

- `/help` 或 `/?` — 帮助  
- `/status` — 当前模型、API、工作区、配置路径、上下文开关  
- `/models` — 拉取当前代理可用模型列表  
- `/mcp` — 拉取 MCP 工具列表（带短时缓存）  
- `/use-model <id>` — 临时切换当前会话模型  
- `/reload` — 仅更新首条 system 提示（重读项目说明与 Git）  
- `/clear` — 清空对话并重建系统提示  
- 其他 `/` 开头会提示未知命令  

## 工具与安全说明

- **read_file** / **list_dir** / **list_tree** / **write_file**：路径相对于工作区，不能越界；`read_file` 可用 `line_start` / `line_end` 控制行范围。
- **glob_search**：`pattern` 与 `root` 不得包含 `..`；结果条数有上限。
- **search_text**：子串搜索；通过 `glob`、`max_files`、`max_matches`、`max_file_bytes` 限制开销。
- **git_status**：只读 `git status`（支持 short 模式）。
- **git_diff**：只读 `git diff`（支持 staged 与 path 参数）。
- **mcp_list_tools**：读取 MCP Bridge 工具清单（需启用）。
- **mcp_call_tool**：调用 MCP Bridge 工具（需启用）。
- **run_command**：仅允许白名单中的可执行文件名，禁止路径形式与常见 shell 元字符；支持 `cwd` 指定工作区内子目录（默认 `.`）。

实现见 `src/cai_agent/tools.py` 与 `src/cai_agent/sandbox.py`。

## 许可证

以仓库根目录为准（若未声明则由使用者自行约定）。
