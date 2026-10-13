# CAI Agent

**Pi-style coding-agent kernel** with a DeepSeek Harness–inspired CLI / Web / Desktop UI.

> Kernel is Pi: `pi_core` + `pi_session` + default tools (`read` / `write` / `edit` / `bash`), wired through an EventBus adapter. UI is Harness-style, not a Cordis/DSH kernel fork.

```text
Electron (desktop/) ──► Web shell + EventBus ──► Pi engine
CLI / Web            ──► ui / surfaces       ──► Pi engine
```

中文说明见 [README.zh-CN.md](README.zh-CN.md)。

## Features

- **Pi engine** — sequential tool loop, JSONL sessions, abort
- **Providers** — OpenAI-compatible Chat Completions **and** Anthropic Messages
- **Harness UI** — workspace tree with nested sessions, settings, file drawer
- **Desktop** — Electron + local Python sidecar (Win / macOS / Linux)
- **Layered** — `ui` → `adapter` → `engine` (no UI hard-wire into the loop)

## Install

```bash
pip install -e ".[dev]"
```

## Quick start

### Desktop

```bash
cd desktop
npm install
npm run desktop
```

Settings → protocol (`openai` / `anthropic`) → Base URL / API Key / Model.  
Sidebar → **工作区** to add folders; chats nest under each workspace.

### CLI / Web

```bash
CAI_MOCK=1 cai-agent run "hello"
cai-agent ui
cai-agent web --port 8765
```

Copy [`config.example.yaml`](config.example.yaml) → `cai.config.yaml`.

Env: `CAI_PROVIDER`, `LM_BASE_URL`, `LM_MODEL`, `LM_API_KEY`, `CAI_WORKSPACE`, `CAI_HOME`, `CAI_MOCK`.

## Layout

| Path | Role |
|------|------|
| `src/cai_agent/pi_core/` | Pi agent loop |
| `src/cai_agent/pi_session/` | Sessions + store |
| `src/cai_agent/adapter/` | EventBus + bridge |
| `src/cai_agent/llm/` | OpenAI + Anthropic clients |
| `src/cai_agent/surfaces/` | Web API + static shell |
| `src/cai_agent/ui/` | CLI / TUI |
| `desktop/` | Electron host |

## Docs

| Doc | |
|-----|--|
| [Architecture](docs/architecture.md) | [中文](docs/architecture.zh-CN.md) |
| [Guide](docs/guide.md) | [中文](docs/guide.zh-CN.md) |
| [Acceptance](docs/acceptance.md) | [中文](docs/acceptance.zh-CN.md) |

## Test

```bash
python -m pytest -q
```

## License

See repository license file if present; otherwise all rights reserved by the project owners.
