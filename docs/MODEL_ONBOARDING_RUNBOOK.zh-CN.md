# 模型接入 Runbook

本页是 `MODEL-P0` 的模型接入闭环说明，覆盖 OpenAI、Anthropic、OpenRouter、本地 OpenAI-compatible 服务以及 provider preset。

## 最短命令链

先生成接入命令链：

```powershell
cai-agent models onboarding --id my-model --preset openai --model gpt-4o-mini --json
```

输出为 `model_onboarding_flow_v1`，会先校验 preset 是否存在，并附带所选 profile 的非敏感 `capabilities_hint`。按顺序包含：

1. `models list --providers --json`：查看内置 provider preset、所需环境变量与同源 `capabilities_hint`。
2. `models add --id ... --preset ... --model ... --set-active`：新增 profile。
3. `models capabilities <id> --json`：查看非敏感能力元数据。
4. `models ping <id> --json`：默认不消耗 token 的健康检查。
5. `models ping <id> --chat-smoke --json`：显式最小真实 chat smoke。
6. `models use <id>`：切换 active profile。
7. `models routing-test --role active --goal "smoke test" --json`：查看 routing explain 与 fallback candidates。

## Provider 示例

OpenAI：

```powershell
$env:OPENAI_API_KEY="..."
cai-agent models onboarding --id openai-fast --preset openai --model gpt-4o-mini
```

Anthropic：

```powershell
$env:ANTHROPIC_API_KEY="..."
cai-agent models onboarding --id claude-main --preset anthropic --model claude-sonnet-4-5-20250929
```

OpenRouter：

```powershell
$env:OPENROUTER_API_KEY="..."
cai-agent models onboarding --id openrouter --preset openrouter --model anthropic/claude-3.5-sonnet
```

本地 OpenAI-compatible（LM Studio / Ollama / vLLM 等）：

```powershell
cai-agent models onboarding --id local --preset lmstudio --model qwen3-coder
```

## 诊断与回退

- `models capabilities --json`、`GET /v1/models/capabilities`、TUI/API 使用同一套非敏感能力视图。
- `models ping` 会区分 `ENV_MISSING`、`AUTH_FAIL`、`RATE_LIMIT`、`MODEL_NOT_FOUND`、`CONTEXT_TOO_LARGE`、`UNSUPPORTED_FEATURE`、`NET_FAIL`、`CHAT_FAIL` 等状态。
- `models routing-test --json` 输出 `routing_explain_v1`、`base_capabilities`、`effective_capabilities` 与 `model_fallback_candidates_v1`。
- fallback candidates 只解释候选和原因，`auto_switch=false`，不会静默切换模型。

## 边界

- 不提交 API key；优先使用环境变量。
- 默认 ping 不消耗 token；chat smoke 必须显式启用。
- 本 runbook 不承诺实时维护所有 provider 价格，只给 `cost_hint` 和本地/远端提示。
