# Architecture

CAI is a **Pi-style agent kernel** with a DeepSeek Harness–inspired UI shell.

```text
Desktop (Electron) / CLI / Web
        ↓
   surfaces + ui/          Presentation (Harness-style)
        ↓
   adapter/                EventBus · EngineBridge · AgentEvent
        ↓
   pi_core/ · pi_session/ · tools/ · llm/     Pi engine
```

Runtime id: `layered-pi+harness-ui` (see `/api/info`).

## Layers

| Layer | Package | Role |
|-------|---------|------|
| Presentation | `ui/`, `surfaces/web_static/`, `desktop/` | CLI/TUI, Web shell, Electron host |
| Adapter | `adapter/` | Decouples UI from the engine via `EventBus` |
| Engine | `pi_core/`, `pi_session/`, `engine/`, `tools/`, `llm/` | Agent loop, sessions, tools, model clients |

UI code must not call engine internals for rendering — subscribe to the bus only.

## Pi engine

Aligned with [earendil-works/pi](https://github.com/earendil-works/pi) for the coding-agent core:

| Area | Behavior |
|------|----------|
| Tools | `read`, `write`, `edit`, `bash` |
| Loop | `prompt` → sequential tool turns → final reply |
| Session | JSONL under `$CAI_HOME/sessions` (+ `meta.json` workspace binding) |
| Abort | Supported |
| Extensions / skills / sub-agents | Not in scope yet |

### Event pipeline

```text
StepStart → ThinkingStream → ToolInvoke → ToolResult → MessageStream → Finished
```

Pi internal names (`agent_start`, `tool_execution_*`, …) are mapped in `adapter/bridge.py`.

## LLM providers

| `provider` | Protocol | Default base |
|------------|----------|--------------|
| `openai` (default) | OpenAI Chat Completions `/v1/chat/completions` | `http://localhost:1234/v1` |
| `anthropic` | Anthropic Messages `/v1/messages` | `https://api.anthropic.com` |

Factory: `llm/factory.py`. Anthropic accepts the same OpenAI-shaped tool loop internally.

## Surfaces

- `cai-agent run` — terminal renderer on the bus  
- `cai-agent ui` — interactive REPL  
- `cai-agent web` — Harness-style Web UI (SSE)  
- `desktop/` — Electron + Python sidecar  

## Config precedence

defaults → YAML/JSON (`--config` / `CAI_CONFIG` / `cai.config.yaml`) → env → `$CAI_HOME/runtime.json` → CLI flags

Key env: `CAI_PROVIDER`, `LM_BASE_URL`, `LM_MODEL`, `LM_API_KEY`, `CAI_WORKSPACE`, `CAI_HOME`, `CAI_MOCK`.
