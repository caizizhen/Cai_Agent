# Guide

## Install

```bash
pip install -e ".[dev]"
```

## Desktop (Windows / macOS / Linux)

```bash
cd desktop
npm install
npm run desktop
```

Open the app directly, then add/switch workspaces in the sidebar (Harness-style tree).  
Settings → choose **OpenAI Compatible** or **Anthropic Messages**, set Base URL / API Key / Model.  
Persist to `$CAI_HOME/runtime.json` (default `~/.cai`).

Optional installers:

```bash
npm run dist:win
npm run dist:mac
npm run dist:linux
```

## CLI / Web

```bash
CAI_MOCK=1 cai-agent run "hello"
CAI_MOCK=1 cai-agent run --json "hello"
cai-agent ui
cai-agent web --port 8765
cai-agent --model my-model --max-steps 8 --dump-config
```

Copy `config.example.yaml` → `cai.config.yaml`, or configure in the App.

## Environment

| Variable | Meaning |
|----------|---------|
| `CAI_PROVIDER` | `openai` or `anthropic` |
| `LM_BASE_URL` / `LM_MODEL` / `LM_API_KEY` | Model endpoint |
| `CAI_WORKSPACE` / `CAI_HOME` | Workspace + data home |
| `CAI_CONFIG` | Config file path |
| `CAI_MOCK` / `CAI_MOCK_REPLY` | Mock LLM |
| `CAI_MAX_ITER` / `CAI_STREAM` / `CAI_DEBUG` | Engine / UI knobs |

## Tests

```bash
python -m pytest -q
```
