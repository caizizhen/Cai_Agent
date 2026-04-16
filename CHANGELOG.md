## 更新日志

> 本文件记录 `cai-agent` 的版本变更历史；README 只保留概览与链接。

### 0.5.0（当前开发）

- **JSON 诊断补强**：`run --json` / `continue --json` 新增 `last_tool` 与 `error_count` 字段。
- **会话管理增强**：新增 `cai-agent sessions` 子命令；TUI 新增 `/sessions`，`/load latest` 可快速恢复最近会话。
- **会话详情增强**：`cai-agent sessions --details` 可查看每个会话的消息数、工具调用数、错误计数与回答预览。
- **会话匹配修复**：`sessions` 与 `/load latest` 默认匹配 `.cai-session*.json`，兼容 `.cai-session.json` 与自动命名文件。
- **Rules 扩充**：新增通用与 Python 规则文档，覆盖命名/结构、日志/错误、安全/敏感信息、Git/提交、文档/注释、性能/资源、上下文/记忆、MCP/外部工具、类型风格、测试/CI、依赖/打包、CLI/TUI、配置演进等主题。
- **Skills 扩充**：新增计划执行、单模块/多模块重构、新功能+测试、调试诊断、轻量安全扫描、性能评估、依赖升级、API 集成、规则维护、代码评审、发布前检查、workflow 编写、迁移规划等技能文档。
- **README 同步增强**：补充 `rules/` 与 `skills/` 目录现状说明，明确其已从目录骨架演进为可实际复用的内容库。
- **Rules 第二轮扩充**：新增 Hook 自动化、子代理协作、验证评估、research-first、prompt hygiene、Python 并发模型、HTTP 客户端与重试等规则主题。
- **Skills 第二轮扩充**：新增 search-first、TDD、verification loop、Hook 设计、子代理编排、记忆提炼、测试覆盖审计、安全加固、故障复盘、文档同步等技能文档。
- **README 再同步**：更新规则与技能覆盖范围描述，标注新增治理层主题与执行工作流能力。
- **运行层骨架新增**：新增 `commands/`（斜杠命令兼容层）、`agents/`（核心子代理定义）与 `hooks/`（自动化配置骨架与 session 生命周期建议）。
- **README 三次同步**：补充 `commands/agents/hooks` 目录说明，并更新“可复用内容库 -> 运行层雏形”的项目定位描述。
- **Bug 修复（工具节点）**：修复 `graph` 工具节点对 `pending` 字段的直接索引风险，改为使用已校验的 `name/args`，降低异常路径下的 KeyError 风险。
- **CLI 新增命令模板能力**：新增 `cai-agent commands` 与 `cai-agent command <name> <goal...>`，可读取仓库 `commands/*.md` 作为执行指令模板。
- **Hook 运行时接入**：新增 `hook_runtime`，在 `run/continue/command` 会话开始与结束时读取 `hooks/hooks.json` 并输出已启用 hook 标识（非 JSON 模式）。
- **README 四次同步**：更新用法示例，补充 `commands`/`command` 命令及 hook 运行时行为说明。
- **Bug 修复（command 会话保存）**：修复 `command` 子命令缺少 `save_session` 属性导致的潜在运行时异常，补齐参数并改为安全读取。
- **CLI 新增子代理执行能力**：新增 `cai-agent agents` 与 `cai-agent agent <name> <goal...>`，可读取 `agents/*.md` 作为角色模板执行任务。
- **自动技能注入**：`cai-agent command` / `cai-agent agent` 会自动匹配 `skills/*.md` 的相关内容并注入执行提示（同名或前缀匹配）。
- **README 五次同步**：补充 `agents` / `agent` 用法示例与“命令/角色 + 技能”组合执行说明。

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
- **\`cai-agent continue\`**：基于历史会话 JSON 继续提问（语义等价于 `run --load-session`），适合做多轮脚本化自动化。
- **\`run_command\` 增强**：支持 `cwd`（相对工作区），可在子目录执行命令且仍保持沙箱边界。

### 0.2.x

- **\`cai-agent doctor\`**：打印解析后的配置、工作区、说明文件是否存在、是否在 Git 仓库内；**API Key 打码**；支持 `--config`、`-w` / `--workspace`。
- **\`Settings.config_loaded_from\`**：记录实际加载的 TOML 绝对路径（无文件则为 `None`）；`cai-agent run --json` 会附带该字段便于脚本排查。
- **\`run --json\`**：向 stdout 输出一行 JSON（`answer`、`iteration`、`finished`、`config`、`workspace`），并**不再**打印 stderr 上的对话过程片段。
- **LLM 重试**：对 HTTP **429 / 502 / 503 / 504** 自动退避重试（最多 5 次请求）。
- **工具**：`read_file` 支持 **\`line_start\` / \`line_end\`**（按行切片，省略 `line_end` 则读到文件尾）；新增 **\`list_tree\`**（受限深度与条数）。
- **TUI**：**\`/status\`** 查看当前模型与工作区；**\`/reload\`** 仅重建首条 system 提示（重读项目说明与 Git 摘要）。

### 0.1.x 及更早能力摘要

- **\`cai-agent init\`**：生成 `cai-agent.toml`（`--force` 覆盖）。
- **配置**：`temperature`、`timeout_sec`、`project_context`、`git_context` 等；环境变量覆盖。
- **系统提示**：可选 `CAI.md` / `AGENTS.md` / `CLAUDE.md` 与只读 Git 摘要。
- **工具**：`glob_search`、`search_text`；`run` / `ui`；内置示例 TOML 模板。

