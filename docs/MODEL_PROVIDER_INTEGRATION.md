# Mainstream Model Provider Integration

Last verified: 2026-04-29.

CAI Agent talks to model backends through profiles. The runtime has two direct wire protocols:

- `provider = "openai_compatible"`: `POST {base_url}/chat/completions`, with `Authorization: Bearer ...`.
- `provider = "anthropic"`: Anthropic Messages API, with `x-api-key`, `anthropic-version`, and `max_tokens`.

Most providers below can be connected directly by adding a `[[models.profile]]` entry or by running `cai-agent models add --preset ...` when a preset exists. Providers with different native protocols should be used through an OpenAI-compatible gateway such as LiteLLM, OpenRouter, a self-hosted proxy, or the vendor's own compatibility layer.

## Fast Pattern

```bash
# 1) Keep secrets in environment variables, not TOML.
export OPENAI_API_KEY="..."

# 2) Add a profile.
cai-agent models add --preset openai --id openai-main --model gpt-4.1 --set-active

# 3) Check configuration and then do an optional chat smoke.
cai-agent models ping openai-main --json
cai-agent models ping openai-main --chat-smoke --json

# 4) Use the profile in CLI or TUI.
cai-agent models use openai-main
cai-agent ui -w "$PWD"
```

Minimal TOML shape:

```toml
[models]
active = "openai-main"

[[models.profile]]
id = "openai-main"
provider = "openai_compatible"
base_url = "https://api.openai.com/v1"
model = "gpt-4.1"
api_key_env = "OPENAI_API_KEY"
temperature = 0.2
timeout_sec = 120
```

## Direct Provider Matrix

| Provider | CAI provider | Base URL / protocol | Key env | Notes |
|---|---|---|---|---|
| OpenAI | `openai_compatible` | `https://api.openai.com/v1` | `OPENAI_API_KEY` | Use the built-in `openai` preset. See OpenAI Chat Completions docs. |
| Anthropic Claude | `anthropic` | `https://api.anthropic.com` Messages API | `ANTHROPIC_API_KEY` | Use the built-in `anthropic` preset; keep `anthropic_version = "2023-06-01"` unless Anthropic changes your account requirement. |
| Google Gemini | `openai_compatible` | `https://generativelanguage.googleapis.com/v1beta/openai` | `GEMINI_API_KEY` | Gemini provides an OpenAI compatibility endpoint. |
| xAI Grok | `openai_compatible` | `https://api.x.ai/v1` | `XAI_API_KEY` | Use model ids from the xAI console/docs. |
| DeepSeek | `openai_compatible` | `https://api.deepseek.com` or `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` | DeepSeek documents OpenAI-compatible Chat Completions. |
| Alibaba Qwen / DashScope | `openai_compatible` | DashScope OpenAI-compatible endpoint | `DASHSCOPE_API_KEY` | Use DashScope's compatibility mode; exact regional URL may differ. |
| Zhipu GLM / Z.ai | `openai_compatible` | `https://open.bigmodel.cn/api/paas/v4` | `ZAI_API_KEY` | Built-in presets: `zhipu`, `zai_glm`. Do not append another `/v1`; CAI normalizes paths. |
| Moonshot Kimi | `openai_compatible` | `https://api.moonshot.cn/v1` | `MOONSHOT_API_KEY` | Built-in preset: `kimi_moonshot`. |
| MiniMax | `openai_compatible` | `https://api.minimax.chat/v1` | `MINIMAX_API_KEY` | Built-in preset: `minimax`. |
| Mistral AI | `openai_compatible` | Mistral Chat Completions endpoint | `MISTRAL_API_KEY` | Mistral exposes a chat-completions style API; set the documented base URL and model id. |
| Groq | `openai_compatible` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` | Groq documents OpenAI SDK compatibility. |
| Cohere | Gateway recommended | Cohere v2 Chat API or OpenAI-compatible gateway | `COHERE_API_KEY` | CAI does not yet implement Cohere's native v2 chat wire; use LiteLLM/OpenRouter unless using a compatible endpoint. |
| Perplexity | `openai_compatible` | `https://api.perplexity.ai` | `PPLX_API_KEY` | Perplexity exposes chat completions for online-answer models. |
| NVIDIA NIM | `openai_compatible` | `https://integrate.api.nvidia.com/v1` | `NVIDIA_API_KEY` | Built-in preset: `nvidia_nim`. |
| Hugging Face Inference Providers | `openai_compatible` | `https://api-inference.huggingface.co/v1` | `HF_TOKEN` | Built-in preset: `huggingface`; model availability depends on provider routing. |
| OpenRouter | `openai_compatible` | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` | Built-in preset: `openrouter`; useful for many hosted models behind one profile style. |
| Volcengine Ark / Doubao | `openai_compatible` | `https://ark.cn-beijing.volces.com/api/v3` or regional equivalent | `ARK_API_KEY` | Ark documents OpenAI SDK compatibility; choose the region and endpoint from your console. |
| SiliconFlow | `openai_compatible` | `https://api.siliconflow.cn/v1` | `SILICONFLOW_API_KEY` | Common OpenAI-compatible router for Qwen, DeepSeek, GLM, and open models. |
| Together AI | `openai_compatible` | `https://api.together.xyz/v1` | `TOGETHER_API_KEY` | OpenAI-compatible hosted open-model API. |
| Fireworks AI | `openai_compatible` | `https://api.fireworks.ai/inference/v1` | `FIREWORKS_API_KEY` | OpenAI-compatible inference endpoint for hosted open models. |

## Local And Self-Hosted Runtimes

| Runtime | CAI provider | Base URL | Key env | Notes |
|---|---|---|---|---|
| LM Studio | `openai_compatible` | `http://localhost:1234/v1` | `LM_API_KEY` | Built-in preset: `lmstudio`; local servers often ignore the key but CAI still accepts one. |
| Ollama | `openai_compatible` | `http://localhost:11434/v1` | `OLLAMA_API_KEY` | Built-in preset: `ollama`; model id is the local tag, for example `qwen2.5-coder:7b`. |
| vLLM | `openai_compatible` | `http://localhost:8000/v1` | `VLLM_API_KEY` | Built-in preset: `vllm`; start with `vllm serve <model>`. |
| llama.cpp server | `openai_compatible` | Usually `http://localhost:8080/v1` | any env you choose | Use the `gateway` preset and override base URL/model. |
| LiteLLM / one-api / custom proxy | `openai_compatible` | Your proxy `/v1` endpoint | proxy-specific | Best option for Bedrock, Azure variants, Qianfan/ERNIE, Tencent Hunyuan, or any provider whose native wire is not implemented in CAI. |

## Gateway-Recommended Backends

Use these through LiteLLM, OpenRouter, one-api, an in-house gateway, or the vendor's OpenAI-compatible mode when your account exposes one.

| Backend | Why gateway is recommended |
|---|---|
| Azure OpenAI | Native Azure routes include deployment names and `api-version` query parameters; a gateway can normalize them to `/v1/chat/completions`. |
| AWS Bedrock | Bedrock's Converse / InvokeModel APIs are not OpenAI Chat Completions wire by default. |
| Google Vertex AI | Gemini on Vertex uses Google auth and Vertex-specific routing; direct CAI use is easiest through an OpenAI-compatible gateway unless you use the Gemini API compatibility endpoint. |
| Baidu Qianfan / ERNIE | Accounts and endpoints vary; use a documented OpenAI-compatible mode or a gateway. |
| Tencent Hunyuan | Use a compatibility mode or gateway unless your endpoint already accepts OpenAI-style chat completions. |
| Replicate, Modal, custom inference services | Usually provider-specific auth/routing; expose a `/v1` compatible facade for CAI. |

## Example Profiles

### Anthropic Claude

```toml
[[models.profile]]
id = "claude"
provider = "anthropic"
base_url = "https://api.anthropic.com"
model = "claude-sonnet-4-5"
api_key_env = "ANTHROPIC_API_KEY"
anthropic_version = "2023-06-01"
max_tokens = 4096
```

### Gemini OpenAI Compatibility

```toml
[[models.profile]]
id = "gemini"
provider = "openai_compatible"
base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
model = "gemini-2.5-pro"
api_key_env = "GEMINI_API_KEY"
```

### Generic OpenAI-Compatible Vendor

```toml
[[models.profile]]
id = "vendor"
provider = "openai_compatible"
base_url = "https://vendor.example.com/v1"
model = "vendor-model-id"
api_key_env = "VENDOR_API_KEY"
```

## Operational Checklist

1. Put credentials in environment variables and use `api_key_env` in TOML.
2. Prefer `cai-agent models ping <id> --json` before a real chat smoke.
3. Run `cai-agent models capabilities <id> --json` and fill `context_window` manually when the provider does not expose it.
4. Use separate profiles for routing roles: active, subagent, planner.
5. For providers with non-OpenAI-native semantics, connect through a gateway and document the translation layer in the profile `notes`.

## Official References

- OpenAI Chat Completions: <https://platform.openai.com/docs/api-reference/chat/create>
- Anthropic Messages API: <https://docs.anthropic.com/en/api/messages>
- Gemini OpenAI compatibility: <https://ai.google.dev/gemini-api/docs/openai>
- xAI API: <https://docs.x.ai/docs/api-reference>
- DeepSeek API: <https://api-docs.deepseek.com/>
- DashScope OpenAI compatibility: <https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope>
- Zhipu OpenAI SDK compatibility: <https://docs.bigmodel.cn/cn/guide/develop/openai/introduction>
- Moonshot Kimi API: <https://platform.moonshot.cn/docs/>
- Mistral API: <https://docs.mistral.ai/api/>
- Groq OpenAI compatibility: <https://console.groq.com/docs/openai>
- Cohere Chat API: <https://docs.cohere.com/v2/reference/chat>
- Perplexity Chat Completions: <https://docs.perplexity.ai/api-reference/chat-completions>
- Ollama OpenAI compatibility: <https://github.com/ollama/ollama/blob/main/docs/openai.md>
- vLLM OpenAI-compatible server: <https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html>
- LM Studio local server: <https://lmstudio.ai/docs/app/api>
- Azure OpenAI reference: <https://learn.microsoft.com/azure/ai-services/openai/reference>
- AWS Bedrock Converse API: <https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html>
- Volcengine Ark OpenAI SDK compatibility: <https://www.volcengine.com/docs/82379/1298454>
- SiliconFlow API: <https://docs.siliconflow.cn/>
- Together AI API: <https://docs.together.ai/docs/openai-api-compatibility>
- Fireworks AI OpenAI compatibility: <https://docs.fireworks.ai/api-reference/post-chatcompletions>
