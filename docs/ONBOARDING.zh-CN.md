# Cai_Agent 新用户路径与 CI 场景

目标：在约 10 分钟内完成 **安装 → 配置探活 → 一次最小对话**。

## 推荐路径

1. **安装**（在仓库 `cai-agent/` 目录）  
   `pip install -e .`

2. **生成配置**（在项目根或工作区目录）  
   - 最小单端点：`cai-agent init`（默认 `[llm]`，本机 LM Studio）。  
   - 多后端 + OpenRouter + **智谱 GLM** + 自建网关模板：`cai-agent init --preset starter`（预置多条 `[[models.profile]]`，再用 `cai-agent models use <id>` 切换）。  
   若已存在 `cai-agent.toml`，使用 `cai-agent init --force`（可加 `--preset starter`）覆盖。

3. **编辑 `cai-agent.toml`**  
   至少设置 `[llm]` 或当前激活 profile 的 `base_url`、`model`、`api_key` / `api_key_env`，使其指向你的 OpenAI 兼容端点（如 LM Studio、Ollama、vLLM、OpenRouter、**智谱** `https://open.bigmodel.cn/api/paas/v4` + `ZAI_API_KEY`，或自建代理）。智谱说明见官方 [OpenAI 兼容](https://docs.bigmodel.cn/cn/guide/develop/openai/introduction)。

4. **健康检查**  
   `cai-agent doctor`  
   确认配置来源、工作区、API 地址与模型无误；工作区内可有 `CAI.md` / `AGENTS.md` / `CLAUDE.md` 作为项目说明。

5. **最小任务**  
   `cai-agent run "用一句话说明当前目录用途"`  
   若 API 不可用，可先设 `CAI_MOCK=1` 验证 CLI 与图流程（仅用于联调）。

## 常见失败与处理

| 现象 | 处理 |
|------|------|
| `配置文件不存在` | 指定 `--config` 或设置 `CAI_CONFIG`，或在当前目录执行 `init` |
| 本机 LM Studio **HTTP 503**（`http_trust_env=true` 且系统有代理） | 升级至含「环回直连」的版本；或设 `NO_PROXY=localhost,127.0.0.1`；或将 `http_trust_env` 设为 `false` |
| 连接超时 / 429 | 检查 `llm.timeout_sec`、端点负载与 `LM_BASE_URL` |
| 工具写入/命令被拒绝 | 检查 `[permissions]` 中 `write_file` / `run_command` 是否为 `deny` |
| 非交互环境卡在权限询问 | 见下文 CI |

## CI / 自动化场景（权限与审批）

在流水线或无人值守环境中，若配置为 `ask`，需要自动批准工具调用：

- 环境变量：`CAI_AUTO_APPROVE=1`  
- 或 CLI：`--auto-approve`（适用于 `run` / `continue` / `command` / `agent` / `fix-build` 等支持该参数的子命令）

**建议**：CI 使用独立配置文件，将 `write_file` / `run_command` 设为 `allow` 或 `deny` 而非 `ask`，缩小攻击面；仅在受信沙箱中开启 `allow`。

## 质量门禁（可选）

合并前在同一工作区执行：

`cai-agent quality-gate --json`

可在 TOML `[quality_gate]` 中开启 `lint`、`security_scan`、`typecheck` 及 `[[quality_gate.extra]]` 自定义步骤（见示例配置 `cai-agent/src/cai_agent/templates/cai-agent.example.toml`）。
