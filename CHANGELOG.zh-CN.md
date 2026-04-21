## 更新日志

> 默认英文变更记录见 **[CHANGELOG.md](CHANGELOG.md)**。以下为完整中文变更说明（本文件）。

> 根目录 **`README.md`** 为默认英文说明，**`README.zh-CN.md`** 为完整中文说明；**`CHANGELOG.md`** 为默认英文变更记录，**`CHANGELOG.zh-CN.md`** 为完整中文变更记录。

### 0.5.0（当前开发）

- **跨会话检索 `recall`（Hermes `/insights` 衍生能力）**：新增 `cai-agent recall <query>`，支持跨会话内容检索并返回命中片段。支持 `--days`（时间窗口）、`--limit`（返回条数）、`--regex`（正则模式）与 `--json`（结构化输出）；默认按最近会话优先。命中结果包含会话路径、文件时间、`task_id`、命中行号与片段预览，无法解析的会话会统计到 `parse_skipped` 且不中断执行。

- **`recall-index` 增量刷新**：新增 `cai-agent recall-index refresh`，在已有 `.cai-recall-index.json`（schema `1.1`）上合并更新：**mtime 未变则跳过 JSON 解析**；未出现在本轮扫描窗口内的旧条目仍保留；`--prune` 可剔除磁盘已不存在或超出 `--days` 窗口的路径。`recall-index build` 仍为全量重建。`recall --use-index` 与 `recall-index` 统一使用 `--index-path` 指定索引文件。

- **schedule daemon 生产护栏（防重 + 日志）**：`cai-agent schedule daemon` 新增单实例锁（默认 `.cai-schedule-daemon.lock`，可用 `--lock-file` 自定义）防止同工作区重复启动；重复启动会安全返回并给出 `daemon_already_running`。新增 `--log-file` 将每轮 JSON 摘要追加到日志，便于 QA 与线上排障。命令参数统一为 `--max-cycles`（README 同步修正），并新增 `docs/qa/schedule-daemon-testplan.md` 作为手工验收清单。

- **schedule 真执行（MVP）**：`cai-agent schedule run-due --execute` 不再仅写元数据，现会对每个到点任务真实触发一次 Agent 运行（基于任务 `goal` 调用主循环），并把结果回写到 `.cai-schedule.json`（`last_run_at` / `last_status` / `last_error` / `run_count`）。返回 JSON 新增执行结果数组（含 `answer` 预览、`iteration`、`finished`）。同时兼容早期 `schedule` 数据：历史任务若缺 `enabled` 字段默认视为启用。

- **智谱（BigModel）OpenAI 兼容路由**：`profiles.PRESETS` 增加 **`zhipu`** 预设（`cai-agent models add --preset zhipu …`）；`normalize_openai_chat_base_url` / `project_base_url` 对 `https://open.bigmodel.cn/api/paas/v4` **不再追加 `/v1`**，与[智谱 OpenAI 兼容文档](https://docs.bigmodel.cn/cn/guide/develop/openai/introduction)一致。示例模板说明 **`ZAI_API_KEY`** 与 **`glm-5.1`**。
- **系统代理与本机 LLM**：`[llm].http_trust_env=true` 时，对 **环回地址**（`localhost`、`127.*`、`::1`）的 OpenAI 兼容 **chat**、**`GET …/models` / profile ping**、以及 **MCP** 的 httpx 客户端仍使用 **`trust_env=false` 直连**，避免企业代理错误转发本机 LM Studio/Ollama 导致 **HTTP 503**。
- **Sprint 3 — TUI 模型面板（M4）**：`Ctrl+M` / `/models` 打开面板；列表列为 `id | model | provider | base_url | notes | [active]`；`Enter` 切换、`t` 连通测试、`a`/`e`/`d` 新增/编辑/删除（写回 `cai-agent.toml`，与 CLI `models` 语义一致）；空列表时给出引导文案。详见 [MODEL_SWITCHER_DEVPLAN.zh-CN.md](docs/MODEL_SWITCHER_DEVPLAN.zh-CN.md) §4。
- **Sprint 3 — `/use-model` 与 provider 提示（M5）**：在 TUI 内切换 profile 若 **provider** 变化，聊天区追加简短提示，建议必要时执行 `/compact` 或 `/clear`，降低跨供应商上下文错位风险。
- **Sprint 3 — `/status` 与 session（M7）**：`/status` 增加 `profile:` 行（与 `profile(active):` 并存，便于与 QA 矩阵表述对齐）；TUI `/save` 与 `run --save-session` 落盘 JSON 增加 **`profile`**（当前 active profile id）及 **`active_profile_id` / `subagent_profile_id` / `planner_profile_id`**；加载会话时支持仅用 **`profile`** 恢复 active。
- **Sprint 3 — 文档与 Parity（M9）+ P1 定案**：`docs/PARITY_MATRIX.zh-CN.md` 增「多模型 profile + TUI」Done 行并链 devplan；新增 [WEBSEARCH_NOTEBOOK_MCP.zh-CN.md](docs/WEBSEARCH_NOTEBOOK_MCP.zh-CN.md)（WebSearch/Notebook **MCP 优先** 与任务看板 schema 说明）；`board --json` 顶层增加 **`observe_schema_version`**（与内嵌 `observe` 同源）。
- **本地多后端与网关一键配置**：新增 `cai-agent init --preset starter`，从内置 `cai-agent.starter.toml` 生成含 LM Studio / Ollama / vLLM / OpenRouter / **智谱 GLM** / 自建 OpenAI 兼容网关等多条 `[[models.profile]]` 的配置；`cai-agent models add --preset` 增加 **`vllm`**、**`gateway`**、**`zhipu`**（`profiles.PRESETS` 约定默认端口与 `VLLM_API_KEY`、`OPENAI_API_KEY`、`ZAI_API_KEY`）。README / README.zh-CN、`docs/ONBOARDING.zh-CN.md` 已补充说明；`doctor` 提示 `init --preset starter` 与新 preset。
- **移除 Cursor Cloud API 集成**：删除 `cai-agent cursor`、`cai_agent.cursor_cloud`、TOML `[cursor]` / 环境变量 `CURSOR_*` 的解析与 `Settings` 字段、TUI 的 **Ctrl+Shift+M** / **`/cursor-launch`**，以及 `doctor` 中的 Cursor 行。**`cai-agent export --target cursor` 保留不变**（仅向 `.cursor/cai-agent-export` 导出规则/技能等目录，与 Cloud Agents HTTP API 无关）。
- **TUI 支持文本选择与一键复制**：在 App 上显式设置 `ALLOW_SELECT=True`（即便 Textual 未来改默认值也不会回归），鼠标拖选聊天区可直接选中文字；新增键位 **`Ctrl+Shift+C`** 通过 `Screen.get_selected_text()` + `App.copy_to_clipboard()` 写入系统剪贴板（并弹出"已复制 N 个字符"提示；未选中时给出「用鼠标拖选或 `Ctrl+Shift+A` 全选」的引导）。**`Ctrl+Shift+A`** 调用 `RichLog.text_select_all()` 一键全选当前聊天区，便于整段拷走。`Ctrl+C` 依然是「停止任务」（终端惯例）。欢迎页与 `/help` 同步提示新快捷键；Windows Terminal 里按住 `Shift + 鼠标` 仍可走系统原生选择。
- **配置发现：用户级全局配置兜底**：`--config` / `CAI_CONFIG` / cwd 向上查找 / `CAI_WORKSPACE` / `-w` 都找不到时，`_resolve_config_file` 现在会再尝试一组**用户级全局路径**，让「从任何目录 `cai-agent ui` 都能读到你的配置」成立。顺序：`%APPDATA%\cai-agent\cai-agent.toml`（Windows）→ `$XDG_CONFIG_HOME/cai-agent/cai-agent.toml`（缺省 `~/.config/cai-agent/cai-agent.toml`）→ `~/.cai-agent.toml` → `~/cai-agent.toml`。`cai-agent init` 新增 **`--global`** 开关，按平台写入对应位置（自动创建父目录）。项目级 `cai-agent.toml` 仍优先于全局；`CAI_CONTEXT_WINDOW` 与 profile 级 `context_window` 仍优先于 `[llm].context_window`。欢迎页 `source=default` 的提示从原来的「请从含该文件的目录启动」改为 **四条具体可操作路径**：从含 TOML 的目录启动、`init --global`、设置 `CAI_CONFIG`、或启动时用 `--config` / `-w`。
- **配置发现：workspace_hint**：`Settings.from_env` / `from_sources` 新增 `workspace_hint` 形参，`__main__.py` 里所有带 `-w/--workspace` 的子命令都已串起；在 cwd 向上查找失败后，继续沿 `CAI_WORKSPACE` 与 `workspace_hint` 各自的父目录链查找，修正「`cd` 到别处 + `-w` 回项目根 + 仍读到 8192」的历史坑。
- **TUI 上下文进度条**：输入框上方新增一行 `ctx ███░░ prompt_tokens / context_window (pct%)`，< 70% 绿、70–89% 黄、≥ 90% 红。每次模型响应后自动取服务端 `prompt_tokens` 刷新；首次响应前用 **CJK 加权估算器**（中日韩字符按 ~1.5 chars/token，其它按 ~4 chars/token，避免中文场景低估 2–3 倍）并加 `~` 前缀与"估算"字样。可配置项：`[llm].context_window`（兜底）、`[[models.profile]].context_window`（优先）、环境变量 `CAI_CONTEXT_WINDOW`；默认 `8192`。`Settings` 新增 `context_window_source`（`profile|llm|env|default`），TUI 欢迎页 + `/status` 都会打印解析值与来源，一眼看出"为啥分母是 8k"。按 Enter 后即刻用估算器重算（不等服务端 round-trip）。新增 Python API：`cai_agent.llm.get_last_usage()` / `estimate_tokens_from_messages()`；`graph.llm_node` 每次 LLM 调用后发 `phase="usage"` 进度事件。
- **空输出兜底**（Qwen3 / DeepSeek-R1 / LM Studio reasoning 模型）：服务端返回 `content=""` 且把所有 token 塞进 `reasoning_content`（推理预算耗尽）时，OpenAI-compat 与 Anthropic 适配器会合成 `{"type":"finish","message":"[empty-completion] …"}` 带诊断信息的 envelope，而不是在 `extract_json_object("")` 崩溃或空转到 `max_iterations`。`<think>…</think>` 前缀也会被透明剥离。Anthropic 两个"空 content 抛异常"的老契约反转为返回 envelope —— 见 `test_llm_empty_content_guard.py`。
- **`plan --json` + 缺失配置**：`--config` 指向不存在文件时输出 JSON 错误体（`error: config_not_found`），不再仅 stderr。
- **`stats`（非 JSON）**：文本摘要增加 `run_events_total`、`sessions_with_events`、`parse_skipped` 一行。
- **钩子**：`observe_start` / `observe_end` 包裹 `observe`；`cost_budget_start` / `cost_budget_end` 包裹 `cost budget`；人类可读 `observe` 行末附带 `run_events_total`。
- **`stats --json`**：增加 `stats_schema_version`（`1.0`）、`run_events_total`、`sessions_with_events`、`parse_skipped` 与 `session_summaries`（逐文件的 `events_count` / `task_id` / token 与工具统计摘要）。
- **`plan --json` 错误路径**：`goal` 为空或 LLM 抛错时仍输出一行 JSON（`ok: false`，`error` 为 `goal_empty` 或 `llm_error`；失败时 `task.status=failed`）；成功体含 `ok: true`。
- **钩子**：`memory_start` / `memory_end` 包裹 `cai-agent memory`；`export_start` / `export_end` 包裹 `cai-agent export`；`export` 子命令增加 `-w` / `--workspace`。
- **`plan --json`**：稳定信封字段 `plan_schema_version`（`1.0`）、`generated_at`（UTC ISO）、`task`（`plan-*` 任务 id）及 `usage` 等。
- **`sessions --json`**：即使未加 `--details`，也会尝试解析会话文件并附带 `events_count`、`run_schema_version`、`task_id`、`total_tokens`、`error_count`；失败时标记 `parse_error`；`--details` 文本行增加 `events=`。
- **`security-scan` 钩子**：`security_scan_start` / `security_scan_end` 包裹 `cai-agent security-scan`（扫描抛错时仍会在退出前触发 `security_scan_end`）。
- **会话落盘**：`--save-session` 现写入 `run_schema_version`、`events`、工具统计（`tool_calls_count` / `used_tools` / `last_tool` / `error_count`）及适用的 `post_gate`，与 `run --json` 对齐。
- **observe**：每条会话摘要增加 `task_id`、`events_count`、`run_schema_version`；聚合增加 `run_events_total` 与 `sessions_with_events`。
- **workflow 钩子**：`cai-agent workflow` 前后触发 `workflow_start` / `workflow_end`（失败退出前仍会触发 `workflow_end`），行为与 `session_*` 钩子一致（非 JSON 模式下 stderr 列出已启用 hook id）。
- **quality-gate 钩子**：独立子命令 `cai-agent quality-gate` 前后触发 `quality_gate_start` / `quality_gate_end`；`quality-gate` 现与共用解析器一致，支持 `-w` / `--workspace`。
- **fetch_url**：在白名单校验前先拒绝常见 SSRF 主机名（如 `localhost`、GCP metadata 域名）。
- **fetch_url 工具**：可选 HTTPS GET，主机白名单、响应体上限与超时；由 `[fetch_url]` 与 `[permissions].fetch_url` 控制（默认关闭且权限为 `deny`）。示例见 `cai-agent/src/cai_agent/templates/cai-agent.example.toml`；纯 MCP 方案见 `docs/MCP_WEB_RECIPE.zh-CN.md`。
- **Run JSON 事件信封**：`run --json` / `continue --json`（及 `command` / `agent` / `fix-build` 共用路径）增加 `run_schema_version` 与 `events`（`run.started` / `run.finished`），与 `workflow` 的 `events` 风格对齐。
- **记忆条目校验**：写入 `memory/entries.jsonl` 前按 v1 形状校验；JSON Schema 见 `cai-agent/src/cai_agent/schemas/memory_entry_v1.schema.json`。
- **doctor**：启用 `fetch_url` 时打印白名单项数与权限模式。
- **QA 回归留痕**：`scripts/run_regression.py` 每次执行后在 `docs/qa/runs/` 生成带时间戳的 Markdown 报告（见 `docs/QA_REGRESSION_LOGGING.zh-CN.md`）；CI 工作流将该目录下的报告作为 artifact 上传。
- **变更记录拆分**：默认 `CHANGELOG.md` 改为英文；原中文全文迁至 `CHANGELOG.zh-CN.md`。
- **文档拆分**：默认 `README.md` 改为英文；原中文全文迁至 `README.zh-CN.md`，两文件顶部互相链接。
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
- **README 三次同步**：补充 `commands/agents/hooks` 目录说明，并更新「可复用内容库 → 运行层雏形」的项目定位描述。
- **Bug 修复（工具节点）**：修复 `graph` 工具节点对 `pending` 字段的直接索引风险，改为使用已校验的 `name/args`，降低异常路径下的 KeyError 风险。
- **CLI 新增命令模板能力**：新增 `cai-agent commands` 与 `cai-agent command <name> <goal...>`，可读取仓库 `commands/*.md` 作为执行指令模板。
- **Hook 运行时接入**：新增 `hook_runtime`，在 `run/continue/command` 会话开始与结束时读取 `hooks/hooks.json` 并输出已启用 hook 标识（非 JSON 模式）。
- **README 四次同步**：更新用法示例，补充 `commands`/`command` 命令及 hook 运行时行为说明。
- **Bug 修复（command 会话保存）**：修复 `command` 子命令缺少 `save_session` 属性导致的潜在运行时异常，补齐参数并改为安全读取。
- **CLI 新增子代理执行能力**：新增 `cai-agent agents` 与 `cai-agent agent <name> <goal...>`，可读取 `agents/*.md` 作为角色模板执行任务。
- **自动技能注入**：`cai-agent command` / `cai-agent agent` 会自动匹配 `skills/*.md` 的相关内容并注入执行提示（同名或前缀匹配）。
- **README 五次同步**：补充 `agents` / `agent` 用法示例与「命令/角色 + 技能」组合执行说明。

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
