# 主流大模型接入指南

最后核对日期：2026-04-29。

CAI Agent 通过 profile 接入模型后端。目前运行时直接支持两类协议：

- `provider = "openai_compatible"`：调用 `POST {base_url}/chat/completions`，使用 `Authorization: Bearer ...`。
- `provider = "anthropic"`：调用 Anthropic Messages API，使用 `x-api-key`、`anthropic-version` 与 `max_tokens`。

下面的主流厂商大多可以通过 `[[models.profile]]` 直接接入；如果厂商原生协议不是 OpenAI 兼容，也可以通过 LiteLLM、OpenRouter、自建代理、one-api 或厂商自己的兼容层转成 OpenAI-compatible 后再接入 CAI。

## 最短流程

```bash
# 1) 密钥放环境变量，不写入 TOML。
export OPENAI_API_KEY="..."

# 2) 添加 profile。
cai-agent models add --preset openai --id openai-main --model gpt-4.1 --set-active

# 3) 先做配置探活，再按需做真实 chat smoke。
cai-agent models ping openai-main --json
cai-agent models ping openai-main --chat-smoke --json

# 4) CLI / TUI 使用该 profile。
cai-agent models use openai-main
cai-agent ui -w "$PWD"
```

最小 TOML 形态：

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

## 直接接入矩阵

| 厂商 / 平台 | CAI provider | Base URL / 协议 | Key 环境变量 | 说明 |
|---|---|---|---|---|
| OpenAI | `openai_compatible` | `https://api.openai.com/v1` | `OPENAI_API_KEY` | 内置 `openai` preset；使用 Chat Completions。 |
| Anthropic Claude | `anthropic` | `https://api.anthropic.com` Messages API | `ANTHROPIC_API_KEY` | 内置 `anthropic` preset；除非官方要求变更，否则保留 `anthropic_version = "2023-06-01"`。 |
| Google Gemini | `openai_compatible` | `https://generativelanguage.googleapis.com/v1beta/openai` | `GEMINI_API_KEY` | Gemini 提供 OpenAI compatibility endpoint。 |
| xAI Grok | `openai_compatible` | `https://api.x.ai/v1` | `XAI_API_KEY` | 模型 id 以 xAI 控制台 / 文档为准。 |
| DeepSeek | `openai_compatible` | `https://api.deepseek.com` 或 `https://api.deepseek.com/v1` | `DEEPSEEK_API_KEY` | DeepSeek 文档声明兼容 OpenAI Chat Completions。 |
| 阿里 Qwen / DashScope | `openai_compatible` | DashScope OpenAI 兼容模式 endpoint | `DASHSCOPE_API_KEY` | 具体 URL 可能与地域和开通方式有关，以百炼 / DashScope 文档为准。 |
| 智谱 GLM / Z.ai | `openai_compatible` | `https://open.bigmodel.cn/api/paas/v4` | `ZAI_API_KEY` | 内置 `zhipu`、`zai_glm` preset；不要额外拼 `/v1`，CAI 会规范化路径。 |
| Moonshot Kimi | `openai_compatible` | `https://api.moonshot.cn/v1` | `MOONSHOT_API_KEY` | 内置 `kimi_moonshot` preset。 |
| MiniMax | `openai_compatible` | `https://api.minimax.chat/v1` | `MINIMAX_API_KEY` | 内置 `minimax` preset。 |
| Mistral AI | `openai_compatible` | Mistral Chat Completions endpoint | `MISTRAL_API_KEY` | 设置官方文档中的 base URL 与模型 id。 |
| Groq | `openai_compatible` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` | Groq 提供 OpenAI SDK 兼容接口。 |
| Cohere | 建议网关 | Cohere v2 Chat API 或 OpenAI 兼容网关 | `COHERE_API_KEY` | CAI 暂未实现 Cohere v2 原生协议；建议走 LiteLLM / OpenRouter。 |
| Perplexity | `openai_compatible` | `https://api.perplexity.ai` | `PPLX_API_KEY` | 使用 Perplexity Chat Completions 在线回答模型。 |
| NVIDIA NIM | `openai_compatible` | `https://integrate.api.nvidia.com/v1` | `NVIDIA_API_KEY` | 内置 `nvidia_nim` preset。 |
| Hugging Face Inference Providers | `openai_compatible` | `https://api-inference.huggingface.co/v1` | `HF_TOKEN` | 内置 `huggingface` preset；可用模型取决于 HF 的 provider 路由。 |
| OpenRouter | `openai_compatible` | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` | 内置 `openrouter` preset；适合用同一种 profile 形态接多个托管模型。 |
| 火山方舟 / 豆包 | `openai_compatible` | `https://ark.cn-beijing.volces.com/api/v3` 或对应地域 endpoint | `ARK_API_KEY` | 方舟提供 OpenAI SDK 兼容；地域与 endpoint 以控制台为准。 |
| SiliconFlow | `openai_compatible` | `https://api.siliconflow.cn/v1` | `SILICONFLOW_API_KEY` | 常见 OpenAI 兼容聚合入口，可接 Qwen、DeepSeek、GLM 与开源模型。 |
| Together AI | `openai_compatible` | `https://api.together.xyz/v1` | `TOGETHER_API_KEY` | OpenAI 兼容的托管开源模型 API。 |
| Fireworks AI | `openai_compatible` | `https://api.fireworks.ai/inference/v1` | `FIREWORKS_API_KEY` | 面向托管开源模型的 OpenAI 兼容推理 endpoint。 |

## 本地与自托管运行时

| 运行时 | CAI provider | Base URL | Key 环境变量 | 说明 |
|---|---|---|---|---|
| LM Studio | `openai_compatible` | `http://localhost:1234/v1` | `LM_API_KEY` | 内置 `lmstudio` preset；本地服务通常忽略 key，但 CAI 支持配置。 |
| Ollama | `openai_compatible` | `http://localhost:11434/v1` | `OLLAMA_API_KEY` | 内置 `ollama` preset；模型 id 是本地 tag，例如 `qwen2.5-coder:7b`。 |
| vLLM | `openai_compatible` | `http://localhost:8000/v1` | `VLLM_API_KEY` | 内置 `vllm` preset；先运行 `vllm serve <model>`。 |
| llama.cpp server | `openai_compatible` | 常见为 `http://localhost:8080/v1` | 自定义 | 使用 `gateway` preset 后覆盖 base URL 与模型 id。 |
| LiteLLM / one-api / 自建代理 | `openai_compatible` | 你的代理 `/v1` endpoint | 代理自定义 | 适合 Bedrock、Azure OpenAI 特殊部署、百度千帆 / ERNIE、腾讯混元等原生协议尚未在 CAI 直接实现的后端。 |

## 建议通过网关接入的后端

这些后端建议通过 LiteLLM、OpenRouter、one-api、内部网关，或厂商账号已开通的 OpenAI 兼容模式接入。

| 后端 | 建议网关的原因 |
|---|---|
| Azure OpenAI | Azure 原生路由包含 deployment 名称与 `api-version` 查询参数；网关可归一成 `/v1/chat/completions`。 |
| AWS Bedrock | Bedrock Converse / InvokeModel 默认不是 OpenAI Chat Completions 协议。 |
| Google Vertex AI | Vertex 上的 Gemini 使用 Google 鉴权与 Vertex 路由；除非使用 Gemini API 兼容 endpoint，否则走网关更稳。 |
| 百度千帆 / ERNIE | 账号与 endpoint 形态差异较大；优先使用官方兼容模式或网关。 |
| 腾讯混元 | 仅当 endpoint 已支持 OpenAI 风格 chat completions 时可直连，否则建议网关。 |
| Replicate、Modal、自建推理服务 | 通常有平台自定义鉴权和路由；给 CAI 暴露 `/v1` 兼容 facade 最省心。 |

## 示例 Profile

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

### Gemini OpenAI 兼容模式

```toml
[[models.profile]]
id = "gemini"
provider = "openai_compatible"
base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
model = "gemini-2.5-pro"
api_key_env = "GEMINI_API_KEY"
```

### 任意 OpenAI 兼容厂商

```toml
[[models.profile]]
id = "vendor"
provider = "openai_compatible"
base_url = "https://vendor.example.com/v1"
model = "vendor-model-id"
api_key_env = "VENDOR_API_KEY"
```

## 运营检查清单

1. API key 放环境变量，TOML 只写 `api_key_env`。
2. 先运行 `cai-agent models ping <id> --json`，再决定是否做真实 `--chat-smoke`。
3. 运行 `cai-agent models capabilities <id> --json`；如果 provider 不暴露上下文窗口，手动补 `context_window`。
4. active、subagent、planner 可以拆成不同 profile，便于成本和能力分层。
5. 对非 OpenAI 原生协议的厂商，在 profile `notes` 中写清楚经过哪个网关转接。

## 官方参考

- OpenAI Chat Completions：<https://platform.openai.com/docs/api-reference/chat/create>
- Anthropic Messages API：<https://docs.anthropic.com/en/api/messages>
- Gemini OpenAI compatibility：<https://ai.google.dev/gemini-api/docs/openai>
- xAI API：<https://docs.x.ai/docs/api-reference>
- DeepSeek API：<https://api-docs.deepseek.com/>
- DashScope OpenAI 兼容模式：<https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope>
- 智谱 OpenAI SDK 兼容：<https://docs.bigmodel.cn/cn/guide/develop/openai/introduction>
- Moonshot Kimi API：<https://platform.moonshot.cn/docs/>
- Mistral API：<https://docs.mistral.ai/api/>
- Groq OpenAI compatibility：<https://console.groq.com/docs/openai>
- Cohere Chat API：<https://docs.cohere.com/v2/reference/chat>
- Perplexity Chat Completions：<https://docs.perplexity.ai/api-reference/chat-completions>
- Ollama OpenAI compatibility：<https://github.com/ollama/ollama/blob/main/docs/openai.md>
- vLLM OpenAI-compatible server：<https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html>
- LM Studio local server：<https://lmstudio.ai/docs/app/api>
- Azure OpenAI reference：<https://learn.microsoft.com/azure/ai-services/openai/reference>
- AWS Bedrock Converse API：<https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html>
- 火山方舟 OpenAI SDK 兼容：<https://www.volcengine.com/docs/82379/1298454>
- SiliconFlow API：<https://docs.siliconflow.cn/>
- Together AI API：<https://docs.together.ai/docs/openai-api-compatibility>
- Fireworks AI OpenAI compatibility：<https://docs.fireworks.ai/api-reference/post-chatcompletions>
