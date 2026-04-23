# 功能包：界面化模型切换 / 新模型配置（2026-04-17）

> 对标参考：
>
> - [anthropics/claude-code](https://github.com/anthropics/claude-code)：`/model`、`/model opus|sonnet|haiku`、`CLAUDE_CODE_SUBAGENT_MODEL`、`ANTHROPIC_BASE_URL` 等。
> - [affaan-m/everything-claude-code](https://github.com/affaan-m/everything-claude-code)：`/model-route`（按复杂度/预算路由）、Dashboard GUI（desktop）、`ECC_HOOK_PROFILE` 风格的 profile 切换。
>
> 关联仓库文档：[`PARITY_MATRIX.zh-CN.md`](PARITY_MATRIX.zh-CN.md)、[`ROADMAP_EXECUTION.zh-CN.md`](ROADMAP_EXECUTION.zh-CN.md)、[`REFERENCE_PARITY_BACKLOG_2026-04-17.zh-CN.md`](REFERENCE_PARITY_BACKLOG_2026-04-17.zh-CN.md)。**声明式路由 TOML 草案（未实现）**：[`MODEL_ROUTING_RULES.zh-CN.md`](MODEL_ROUTING_RULES.zh-CN.md)。

---

## 0. 背景与动机（一段话）

当前 Cai_Agent 仅支持 **单一 `[llm]` 段 + 运行时 `/use-model <id>`**，切换模型必须手敲 ID、且配置不能并列多个账号/端点。参考源两者都已经把模型当作**可选择的一等对象**：Claude Code 让你 `/model sonnet` 即切、ECC 进一步做到**按任务路由**与**子代理单独配置**。本功能包的目标是把 **「选模型 / 加模型 / 路由模型」** 提升到 **TUI 可视化 + CLI 原子命令 + 可持久化配置** 三位一体。

---

## 1. 概览：范围与非目标

| 项 | 内容 |
|----|------|
| **范围（In）** | ① TUI 下拉/面板选择模型；② 新增/编辑/删除模型 profile；③ `/model use / add / edit / rm / list` CLI；④ `active` 与可选 **主/子代理** 路由；⑤ 密钥**仅引用环境变量**；⑥ `doctor` 对 profile 做可选健康 ping；⑦ `/status` 展示当前 profile 名；⑧ **多供应商适配**：OpenAI / Anthropic（Claude）/ OpenAI 兼容网关 / 本地（LM Studio / Ollama / vLLM）。 |
| **非目标（Out）** | 官方 Anthropic 登录链路（登录 → 账号绑定）；云端模型市场；图形化 Dashboard（ECC 的 Tkinter 风格暂不引入，P2+ 再评估）；按「复杂度」自动路由的**决策器**（本期只做人工标签路由）；流式 SSE（本期保持非流式请求，P2+ 评估）。 |
| **关联模块** | `cai-agent/src/cai_agent/config.py`、`tui.py`、`models.py`、`doctor.py`、`session.py`、`templates/cai-agent.example.toml`。 |

---

## 2. 数据模型（开发侧契约）

### 2.1 TOML：新增 `[[models]]` 数组 + `[models] active`

示例（**不落盘密钥**，仅保留 env 名称）：

```toml
# cai-agent.toml
[models]
active = "lmstudio-default"
# 可选：主/子代理路由；未设置时沿用 active
subagent = "local-fast"
planner = "remote-reason"

[[models.profile]]
id = "lmstudio-default"
provider = "openai_compatible"
base_url = "http://localhost:1234/v1"
model = "google/gemma-4-31b"
api_key_env = "LM_API_KEY"   # 只写环境变量名，运行时解析
temperature = 0.2
timeout_sec = 120
notes = "本机 LM Studio 默认"

[[models.profile]]
id = "local-fast"
provider = "openai_compatible"
base_url = "http://localhost:1234/v1"
model = "qwen2.5-coder-7b"
api_key_env = "LM_API_KEY"
temperature = 0.1
notes = "子代理/轻量任务"

[[models.profile]]
id = "remote-reason"
provider = "openai_compatible"
base_url = "https://api.example.com/v1"
model = "gpt-4o"
api_key_env = "REMOTE_OPENAI_KEY"
temperature = 0.3
context_window = 128000   # 可选：仅用于 TUI 上下文进度条分母，不随请求发送
notes = "高推理/规划"
```

> **字段补充（0.5.0）**：`context_window` 为可选字段，单位 token，**仅用于 TUI 显示**（决定上下文进度条分母）。缺省时回落到 `[llm].context_window` / `CAI_CONTEXT_WINDOW` / 默认 `8192`。该字段 **不会** 以任何形式包含在发往服务端的请求体里。

### 2.2 兼容性

- 仍保留 `[llm]` 段：启动时若 `[[models.profile]]` 为空，则**合成一个 profile** `id = "default"` 来自 `[llm]`（零迁移）。
- 环境变量 `CAI_ACTIVE_MODEL` 可临时覆盖 `active`。
- `Settings.model/base_url/api_key/temperature/llm_timeout_sec` **仍作为「当前激活 profile 的投影字段」** 保持向后兼容，不改 `llm.py` 的调用面。

### 2.3 持久化位置

- 优先写入当前仓库的 `cai-agent.toml`（与 `init` 生成位置一致）。
- 可选：用户级 `~/.cai-agent/models.toml`（**仅作回退来源**），避免多项目互污；写入优先走项目级。

---

## 3. 界面与命令（用户可见）

### 3.1 TUI

- **新增快捷键 `Ctrl+M`** 或命令 `/models` **不带参数** → 打开「模型面板」：
  - 列表显示所有 profile：`id | model | provider | base_url | notes | [active]`
  - 选中条目：Enter 切换 active；`e` 编辑；`a` 新增；`d` 删除（带确认）；`t` 测试连通性（调用 `/models` 或空聊天）
  - 顶部一行提示：**当前 active** + **subagent/planner 路由**
- `/models refresh` 仍保留（拉远端 `/v1/models` 列表，用于 **新增对话框里的 model 下拉**）
- 扩展 `/status` 增加：`profile: lmstudio-default`、`subagent: local-fast`（若设置）

### 3.2 CLI（无 TUI 时）

- `cai-agent models list [--json]`
- `cai-agent models use <id>`（改写 `active`）
- `cai-agent models add --id X --provider openai_compatible --base-url ... --model ... [--api-key-env ...] [--temperature 0.2] [--notes ...]`
- `cai-agent models edit <id> [--field value ...]`
- `cai-agent models rm <id>`
- `cai-agent models ping <id>`（发起 `GET /v1/models` 或最小 chat ping）
- `cai-agent models route --subagent <id> --planner <id>`（可选）

### 3.3 `doctor` 扩展

- 新增：逐个 profile 执行一次 **非敏感健康检查**（仅 HEAD/GET `/models`，不消耗 chat token）
- 输出：`OK / TIMEOUT / AUTH_FAIL / NET_FAIL`；对 `api_key_env` 未设置的 profile 明确标记

---

## 4. 开发（Dev）— 分任务与技术要点

| ID | 任务 | 技术要点 | 涉及文件 |
|----|------|----------|----------|
| M1 | 配置层：新增 `[[models.profile]]` 解析 + `active/subagent/planner` | 保持旧 `[llm]` 兼容；`api_key_env` 解析优先于字面 `api_key`；不可同时给出两者（报错） | `config.py`、`templates/cai-agent.example.toml` |
| M2 | 选中 profile 投影到 `Settings` | 用 `active`（或 `CAI_ACTIVE_MODEL`）投影到既有字段；保留 `config_loaded_from` 与新增 `active_profile_id` | `config.py` |
| M3 | CLI `models` 子命令 | 读写 TOML（`tomllib` 读 + 最小 TOML 写工具或手写序列化）；**写前备份**（`.cai-agent.toml.bak`）；atomic replace | `__main__.py`、新文件 `profiles.py` |
| M4 | TUI 模型面板 | Textual `Screen`/`ModalScreen` + `OptionList`；新增「测试」按钮走 M6 | `tui.py` |
| M5 | `/use-model` 行为升级 | 若参数为 **profile id** 则整组切换；若是 **model id** 且当前 active 不存在该模型，保留旧行为（只换 model 字段） | `tui.py` |
| M6 | 健康检查 | 新函数 `ping_profile()`：只做 `/models`；超时/错误结构化返回 | `models.py` 或 `doctor.py` |
| M7 | `/status` 与 `/save` 落盘补字段 | `profile`、`subagent`、`planner` 写入 session JSON | `tui.py`、`session.py` |
| M8 | 路由：主/子代理实际生效点 | 调用子代理处（如 `workflow.py` 里已有「agents」运行位）允许取 `subagent` profile；主循环仍用 `active`；未设置时退回 `active` | `workflow.py`、`graph.py`（最小改动） |
| M9 | 文档同步 | 更新 `README.zh-CN.md` 导航 + 本文件入口 | README / docs |
| M10 | **Anthropic 原生适配器** | 新增 `llm_anthropic.py`，`chat_completion` 同签名；按 §8.4 转换 messages/system/max_tokens；`usage` 统计与 OpenAI 路径对齐 | `llm_anthropic.py`（新） |
| M11 | **调度器**：按 profile.provider 分发 | 新增轻量工厂：`provider=anthropic` → `llm_anthropic`；其余 → `llm`；主循环与子代理调用处统一走工厂 | `graph.py`、`workflow.py` |
| M12 | **供应商预设**：`models add --preset openai|anthropic|openrouter|ollama|lmstudio` | 预设内容见 §8.2，减少用户手敲 base_url 与 env 名 | `profiles.py`、`__main__.py` |
| M13 | **密钥检测** 扩展 `security-scan` | 新规则：`models.profile.api_key` 明文 → 高危；`ANTHROPIC_API_KEY` / `OPENROUTER_API_KEY` 等前缀模式 | `security_scan.py` |

**实现顺序建议**：M1 → M2 → M3 → M12 → M10 → M11 → M6 → M4 → M5 → M7 → M8 → M13 → M9。  
**落地原则**：先 CLI（脚本化友好）→ 再 TUI（体验）→ 路由最后（需求弱耦合，能单独跳）；**Claude 原生（M10/M11）与供应商预设（M12）与基础配置（M1–M3）并行互不阻塞**，可拆到两个开发手里同时推进。

---

## 5. QA — 验收清单

### 5.1 功能用例

- [ ] 无 `[[models.profile]]` 的老 `cai-agent.toml` 启动正常，`active_profile_id` 为合成的 `default`。
- [ ] `cai-agent models add` 后文件中出现新 profile；再次启动能选中。
- [ ] `cai-agent models use <id>` 后 `cai-agent run` 使用新 base_url/model。
- [ ] TUI 打开模型面板 → 选中 → Enter → 下一条消息走新 profile（`/status` 同步）。
- [ ] `api_key_env` 引用未导出 → 启动 **不抛堆栈**，`doctor` 明确标 `AUTH_FAIL (env not set: LM_API_KEY)`。
- [ ] 同一 profile 同时写了 `api_key` 与 `api_key_env` → 配置加载阶段**报错并指向行**（或明确提示）。
- [ ] `subagent` profile 设置后，`workflow` 内子代理确实走 subagent 端点（通过 HTTP 抓包/mock 断言）。

### 5.1.1 供应商矩阵（新增）

- [ ] `provider=openai` + `gpt-4o` 能完成一次 `cai-agent run` 并返回（用 `OPENAI_API_KEY` mock 服务断言 `Authorization: Bearer` 与 `POST /v1/chat/completions`）。
- [ ] `provider=anthropic` + Claude 模型能完成一次 `run`（mock Anthropic server 断言 `x-api-key`、`anthropic-version`、`POST /v1/messages`、body 里 `system` 为独立字段、`max_tokens` 存在）。
- [ ] `provider=openai_compatible` 指向 OpenRouter 的 `anthropic/claude-*` 模型可完成一次 `run`（mock 同 OpenAI 协议）。
- [ ] 本地 LM Studio / Ollama 仍能正常 `run`（回归）。
- [ ] 同一会话 `/use-model <id>` 在 openai ↔ anthropic 之间切换不崩溃；切换后首条消息正确路由到对应适配器。
- [ ] `cai-agent models add --preset anthropic --id c1 --model claude-sonnet-4-5` 生成的条目可直接 `use`。

### 5.2 非功能 & 安全

- [ ] `models add/edit/rm` 写 TOML **原子替换**；崩溃不会产生半写文件（有 `.bak`）。
- [ ] `api_key` 明文**不会**出现在 `session.json`、日志、`doctor` 输出中。
- [ ] Windows 下 `~/.cai-agent/models.toml` 路径用 `%USERPROFILE%` 正确解析。
- [ ] 删除 `active` profile → 自动回退到列表第一个并提示，不崩溃。

### 5.3 回归

- `python scripts/run_regression.py`（见 [`QA_REGRESSION_LOGGING.zh-CN.md`](QA_REGRESSION_LOGGING.zh-CN.md)）。
- 新增最小 pytest：
  - `tests/test_model_profiles_config.py`：TOML 解析兼容性 + 覆盖规则
  - `tests/test_model_profiles_cli.py`：`models add/use/list` 基本闭环
  - `tests/test_model_panel_routing.py`（可选）：workflow 子代理使用 subagent profile

---

## 6. 用户（User）— 你会看到什么

### 6.1 新体验要点

- **TUI 里**：`/models` 会打开一个 **模型列表面板**，上下键选中，Enter 切换；`a` 新增、`e` 编辑、`d` 删除、`t` 测试连通。
- **命令行里**（任选 ChatGPT / Claude / 本地）：
  ```bash
  # 官方 ChatGPT
  export OPENAI_API_KEY=sk-...
  cai-agent models add --preset openai --id gpt --model gpt-4o
  cai-agent models use gpt

  # 官方 Claude
  export ANTHROPIC_API_KEY=sk-ant-...
  cai-agent models add --preset anthropic --id c --model claude-sonnet-4-5-20250929
  cai-agent models use c

  # 经 OpenRouter 访问 Claude（无需信用卡绑 Anthropic）
  export OPENROUTER_API_KEY=sk-or-...
  cai-agent models add --preset openrouter --id c-or --model anthropic/claude-sonnet-4.5
  cai-agent models use c-or

  # 本地 LM Studio / Ollama（保留）
  cai-agent models add --preset lmstudio --id local --model google/gemma-4-31b
  cai-agent models add --preset ollama   --id ol    --model qwen2.5-coder:7b
  cai-agent models use local
  ```
- **密钥更安全**：不再把 API Key 写在 `cai-agent.toml`，改写 **环境变量名**，真正的值在你的 shell/CI secret 里。
- **路由（可选）**：可指定「子代理用便宜模型、规划用强模型」：
  ```toml
  [models]
  active = "gpt"
  subagent = "local"
  planner = "c"
  ```

### 6.2 升级指引

- 旧配置不用改：启动仍用你原来的 `[llm]` 段作为一个隐式 profile。
- 想使用新功能：跑一次 `cai-agent models add ...` 把现有配置显式化，或手工编辑 `cai-agent.toml`。
- 升级后若行为异常：`cai-agent doctor` 会列出每个 profile 的健康状态。

---

## 7. 风险与对策

| 风险 | 对策 |
|------|------|
| 用户把 API Key 直接写进 TOML 并提交到仓库 | 文档强调 `api_key_env`；`security-scan` 规则覆盖 `models.profile.api_key` 字段 |
| 多 profile 导致初学者困惑 | `init` 生成的模板只含 1 个 profile；TUI 面板空态给出「添加第一个模型」引导 |
| 切换后当前对话 token 上下文冲突（模型上下文窗口不同） | `/models` 面板在切换时弹确认：「建议 `/compact` 或 `/clear`」 |
| TOML 原子写入失败 / 并发修改 | `write-then-rename`；锁文件可选（P2）|

---

## 8. 供应商适配矩阵（ChatGPT / Claude / 本地 / 其它）

> 目标：**同一个 profile 结构** 能覆盖主流供应商；尽量复用现有 `llm.py` 的 OpenAI 兼容调用面；Claude 原生 API 用独立适配器，不污染主循环。

### 8.1 `provider` 取值与适配层

| `provider` | 协议 | 适配器 | 说明 |
|------------|------|--------|------|
| `openai` | OpenAI `/v1/chat/completions` | 复用 `llm.py` | 官方 ChatGPT API；`base_url = "https://api.openai.com/v1"` |
| `anthropic` | Anthropic `/v1/messages` | **新增** `llm_anthropic.py` | Claude 原生；鉴权 `x-api-key` + `anthropic-version`；system 独立字段 |
| `openai_compatible` | OpenAI 兼容 | 复用 `llm.py` | OpenRouter / DeepSeek / Moonshot / 智谱 / 自建网关 / LiteLLM / **Claude 经兼容网关** |
| `azure_openai` | Azure OpenAI | 复用 `llm.py` + URL 拼接 | 可选；P1 末尾或 P2 |
| `copilot` | 经代理 | 复用 `llm.py` | 既有路径，保留 |
| `ollama` / `lmstudio` / `vllm` | OpenAI 兼容（本地） | 复用 `llm.py` | 文档预设 base_url；不引入新依赖 |

**适配器选择原则**：

1. **Claude 官方 API** 推荐两条路径都支持：
   - **A（推荐，零新依赖）**：通过 **OpenAI 兼容网关**（OpenRouter / LiteLLM / 自建代理）以 `provider=openai_compatible` 接入，零适配器工作量；
   - **B（原生）**：`provider=anthropic`，新增 `llm_anthropic.py`（httpx，~80 行），**核心差异**：`/v1/messages` + `system` 独立字段 + `messages` 中无 `system` 角色 + `max_tokens` 必填 + 响应 `content` 为数组。
2. **ChatGPT 官方** 直接 `provider=openai` 即可，零新代码。
3. **本地模型** 永远保留：仅改 `base_url`，不碰适配器。

### 8.2 Profile 示例（可直接抄到 `cai-agent.toml`）

```toml
[models]
active = "openai-gpt4o"
# 可选：子代理/规划器路由
subagent = "local-lmstudio"
planner = "anthropic-sonnet"

# --- 官方 ChatGPT ---
[[models.profile]]
id = "openai-gpt4o"
provider = "openai"
base_url = "https://api.openai.com/v1"
model = "gpt-4o"
api_key_env = "OPENAI_API_KEY"
temperature = 0.2
timeout_sec = 120

# --- 官方 Claude（原生 /v1/messages） ---
[[models.profile]]
id = "anthropic-sonnet"
provider = "anthropic"
base_url = "https://api.anthropic.com"
model = "claude-sonnet-4-5-20250929"   # 示例，按官方最新命名填
api_key_env = "ANTHROPIC_API_KEY"
# Anthropic 必需
anthropic_version = "2023-06-01"
max_tokens = 4096
temperature = 0.2
timeout_sec = 120

# --- Claude 经 OpenAI 兼容网关（OpenRouter / LiteLLM） ---
[[models.profile]]
id = "claude-via-openrouter"
provider = "openai_compatible"
base_url = "https://openrouter.ai/api/v1"
model = "anthropic/claude-sonnet-4.5"
api_key_env = "OPENROUTER_API_KEY"
temperature = 0.2

# --- 本地 LM Studio ---
[[models.profile]]
id = "local-lmstudio"
provider = "openai_compatible"
base_url = "http://localhost:1234/v1"
model = "google/gemma-4-31b"
api_key_env = "LM_API_KEY"   # LM Studio 可填任意值，留环境变量统一语义
temperature = 0.2

# --- 本地 Ollama ---
[[models.profile]]
id = "local-ollama"
provider = "openai_compatible"
base_url = "http://localhost:11434/v1"
model = "qwen2.5-coder:7b"
api_key_env = "OLLAMA_API_KEY"   # 未启用鉴权时值可任意
temperature = 0.2
```

### 8.3 环境变量约定（不入仓）

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | ChatGPT 官方 |
| `ANTHROPIC_API_KEY` | Claude 官方 |
| `OPENROUTER_API_KEY` | OpenRouter 等聚合 |
| `DEEPSEEK_API_KEY` / `MOONSHOT_API_KEY` / ... | 其它 OpenAI 兼容供应商 |
| `LM_API_KEY` / `OLLAMA_API_KEY` | 本地（值可任意） |
| `CAI_ACTIVE_MODEL` | 临时覆盖 `[models] active`，不落盘 |

### 8.4 Anthropic 原生适配器（开发实现要点）

开发 `llm_anthropic.py` 时对齐 `chat_completion(settings, messages) -> str` 同签名：

- URL：`{base_url}/v1/messages`
- Headers：`x-api-key: <key>`、`anthropic-version: <settings.anthropic_version>`、`content-type: application/json`
- Body 转换：
  - 从 `messages` 里抽出 `role=="system"` 的内容拼成 `system` 字段（多条合并用 `\n\n`）
  - 其余按原顺序保留为 `messages`，role 仅允许 `user` / `assistant`；`tool` 结果按 `user` 角色合并文本（与当前工具协议一致）
  - `max_tokens` 必填（默认 4096）
- 响应解析：`data["content"]` 是数组，取 `type=="text"` 的 `text` 拼接返回
- 用量：`usage.input_tokens` → `prompt_tokens`，`usage.output_tokens` → `completion_tokens`，`total = input + output`
- 错误重试：与 OpenAI 路径一致（429/502/503/504）

### 8.5 路由决策（graph.py / workflow.py）

- 主循环读 `settings.active_profile_id` 对应 profile → 决定调用 `llm.py` 还是 `llm_anthropic.py`
- 子代理运行位：优先 `settings.subagent_profile_id`，缺省回退 `active`
- Plan 节点（若存在）：优先 `settings.planner_profile_id`，缺省回退 `active`

---

## 9. 发版前勾选（PM 自检）

- [ ] [`PARITY_MATRIX.zh-CN.md`](PARITY_MATRIX.zh-CN.md) 新增一行：`模型 profile 与界面切换 + 多供应商` → `Done`
- [ ] README / README.zh-CN 导航加入本文件
- [ ] `CHANGELOG` 用用户语言描述 4 条（TUI 面板 / CLI 子命令 / **多供应商（ChatGPT / Claude / 本地）** / 路由）
- [ ] 示例配置 `templates/cai-agent.example.toml` 加入一块被注释的 `[[models.profile]]`，**至少包含 openai / anthropic / openai_compatible(本地) 三个示例**
- [ ] `security-scan` 新规则（M13）合并，对 `models.profile.api_key` 明文与常见 API Key 前缀给出告警

---

## 10. CHANGELOG 草稿（交付后择机并入）

> 写成用户语言，可直接挪到 `CHANGELOG.zh-CN.md`。

- **新增** `cai-agent models` 子命令与 TUI 模型面板：可在界面直接 **选择 / 新增 / 编辑 / 删除 / 测试** 模型 profile。
- **新增** 多供应商支持：**OpenAI（ChatGPT）** 与 **Anthropic（Claude）** 官方 API 原生接入，保留 **本地模型**（LM Studio / Ollama / vLLM）与任意 **OpenAI 兼容网关**（OpenRouter / LiteLLM 等）。
- **新增** 主/子代理路由：`[models] active / subagent / planner` 可分别指向不同 profile，便于「子代理用便宜模型、规划用强模型」。
- **安全** API Key 改为 **环境变量引用**（`api_key_env = "..."`），`security-scan` 新增对 `models.profile.api_key` 明文的告警。
- **兼容** 旧 `[llm]` 段仍可用，将被自动视作隐式 `default` profile，无需迁移即可启动。

---

*文档版本：2026-04-17（v2，增加多供应商适配）；维护者：产品。*
