# 架构

CAI 是 **Pi 风格 Agent 内核**，外层为 DeepSeek Harness 风格 UI。

```text
Desktop (Electron) / CLI / Web
        ↓
   surfaces + ui/          展示层（Harness 风格）
        ↓
   adapter/                EventBus · EngineBridge · AgentEvent
        ↓
   pi_core/ · pi_session/ · tools/ · llm/     Pi 引擎
```

运行时标识：`layered-pi+harness-ui`（见 `/api/info`）。

## 分层

| 层 | 包 | 职责 |
|----|-----|------|
| 展示 | `ui/`、`surfaces/web_static/`、`desktop/` | CLI/TUI、Web 壳、Electron |
| 适配 | `adapter/` | 用 `EventBus` 解耦 UI 与引擎 |
| 引擎 | `pi_core/`、`pi_session/`、`engine/`、`tools/`、`llm/` | Agent 循环、会话、工具、模型客户端 |

UI 不得为渲染直接调用引擎内部，只订阅事件总线。

## Pi 引擎

与 [earendil-works/pi](https://github.com/earendil-works/pi) 在编码 Agent 核心能力对齐：

| 能力 | 行为 |
|------|------|
| 工具 | `read`、`write`、`edit`、`bash` |
| 循环 | `prompt` → 顺序工具回合 → 最终回复 |
| 会话 | `$CAI_HOME/sessions` 下 JSONL（含 `meta.json` 工作区绑定） |
| 中止 | 支持 |
| 扩展 / Skills / 子 Agent | 暂未纳入 |

### 事件管线

```text
StepStart → ThinkingStream → ToolInvoke → ToolResult → MessageStream → Finished
```

Pi 内部事件名在 `adapter/bridge.py` 中映射。

## 模型协议

| `provider` | 协议 | 默认 Base |
|------------|------|-----------|
| `openai`（默认） | OpenAI Chat Completions `/v1/chat/completions` | `http://localhost:1234/v1` |
| `anthropic` | Anthropic Messages `/v1/messages` | `https://api.anthropic.com` |

入口：`llm/factory.py`。Anthropic 路径在内部仍复用同一套工具循环形状。

## 界面入口

- `cai-agent run` — 终端渲染  
- `cai-agent ui` — 交互 REPL  
- `cai-agent web` — Harness 风格 Web（SSE）  
- `desktop/` — Electron + Python sidecar  

## 配置优先级

默认值 → YAML/JSON → 环境变量 → `$CAI_HOME/runtime.json` → CLI 参数

常用环境变量：`CAI_PROVIDER`、`LM_BASE_URL`、`LM_MODEL`、`LM_API_KEY`、`CAI_WORKSPACE`、`CAI_HOME`、`CAI_MOCK`。
