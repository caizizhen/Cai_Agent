# Acceptance

Version **1.2.0** · Architecture `layered-pi+harness-ui`

## Pi kernel

| # | Requirement | Status |
|---|-------------|--------|
| 1 | Default tools: read, write, edit, bash | PASS |
| 2 | Sequential agent loop + events | PASS |
| 3 | Session JSONL persist / resume + workspace meta | PASS |
| 4 | OpenAI-compat + Anthropic Messages (+ mock) | PASS |
| 5 | Layered ui / adapter / engine | PASS |
| 6 | Unified EventBus events | PASS |

## UI / Desktop

| # | Requirement | Status |
|---|-------------|--------|
| 1 | Harness-style Web shell (sessions under workspaces) | PASS |
| 2 | Electron host + Python sidecar | PASS |
| 3 | In-app workspace add/switch (no forced boot dialog) | PASS |
| 4 | Settings: provider + fetch models + runtime.json | PASS |
| 5 | CLI `run` / `ui` / `web` / `--dump-config` | PASS |
| 6 | Tests green (`python -m pytest -q`) | PASS |

See [architecture.md](architecture.md) and [guide.md](guide.md).
