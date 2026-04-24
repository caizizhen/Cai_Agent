# Discord 与 Telegram 网关能力对照（Slash / 文本）

本文档对齐 **Telegram Webhook** 中已实现的「斜杠命令 + 普通文本执行」语义，与 **Discord** 侧 **Application Commands（Slash）注册** 及 **Polling 文本消息** 的关系，便于运维与二次开发。

## 命令语义对照（用户可见）

| 用户侧触发 | Telegram（`_telegram_slash_reply_text`） | Discord Slash（`register-commands` 默认集） | Discord Polling（纯文本） |
|------------|--------------------------------------------|---------------------------------------------|----------------------------|
| 连通检查 | `/ping` → 固定回复 | `/ping`（需在客户端选 Slash；**响应路由见下**） | 任意非空文本 → 可走 `execute-on-message` |
| 帮助 | `/help`、`/start` | `/help` | 同左 |
| 状态 | `/status` | `/status` | 同左 |
| 续聊说明 | `/new` | `/new` | 同左 |
| 普通消息 → `run`/`continue` | 非 `/` 开头且开启 `execute-on-update` | 无直接等价（需打字，非 Slash） | `--execute-on-message` 时同源 `graph` |

## CLI 对照

| 能力 | Telegram | Discord |
|------|----------|---------|
| 会话绑定 | `gateway telegram bind …` | `gateway discord bind …` |
| 白名单 | `gateway telegram allow …` | `gateway discord allow …` |
| 常驻收消息 | `gateway telegram serve-webhook` | `gateway discord serve-polling` |
| **注册「命令」菜单** | Telegram 无单独注册（文本 `/` 即命令） | **`gateway discord register-commands`**（PUT Discord API） |
| **列出已注册命令** | — | **`gateway discord list-commands`** |
| **运维自检（映射 + 可选 Token）** | — | **`gateway discord health`** |

注册示例（推荐写入 **Guild**，生效快）：

```bash
set CAI_DISCORD_BOT_TOKEN=...
cai-agent gateway discord register-commands --guild-id <GUILD_SNOWFLAKE> --json
```

仅预览提交体、不调 PUT：

```bash
cai-agent gateway discord register-commands --guild-id <GUILD_SNOWFLAKE> --dry-run --json
```

全局命令（省略 `--guild-id`）传播可能较慢，见 [Discord 文档](https://discord.com/developers/docs/interactions/application-commands)。

## 排障与值班路径（HM-03a）

1. **确认 Bot Token 与网络**
   - `cai-agent gateway discord health --json`（不设 Token 时仅输出本地 `discord-session-map` 摘要；设 `CAI_DISCORD_BOT_TOKEN` 或 `--bot-token` 时会调用 `GET /users/@me`）。
   - Token 无效或缺失权限时：`health` 的 JSON 里 `token_check.ok=false`，CLI 退出码为 `2`。
2. **确认频道已绑定且未被白名单挡掉**
   - `cai-agent gateway discord list --json` → 检查 `bindings`、`allowed_channel_ids`；若 `allowlist_enabled=true`，未列入的频道不会轮询。
3. **主路径收消息（Polling）**
   - `cai-agent gateway discord serve-polling --bot-token …`（或环境变量）；需要 **Message Content Intent**（Developer Portal → Bot → Privileged Gateway Intents）以便读取普通用户消息内容，否则 `content` 可能为空被跳过。
4. **Slash 命令「点了没反应」**
   - 见下文「实现边界」：当前仓库**未**实现 Discord Interactions HTTP 回调；已注册的 Slash 需自建 Interaction 服务才有与 Telegram 相同的短回复语义；**文本对话**请走 Polling + `--execute-on-message`。
5. **与 `doctor` 对齐**
   - `cai-agent doctor` / `doctor --json` 的 `cai_dir_health.discord_map_summary` 会给出绑定条数与白名单开关（仅本地文件，默认不触网）。

## 实现边界（B1 交付范围）

- **已实现**：通过 Bot Token 调用 REST，**列出 / 覆盖注册** 默认 Slash（`ping` / `help` / `status` / `new`），与 Telegram 侧文案职责对齐。
- **未实现（后续 Sprint）**：Discord **Interaction** 回调（需在 Developer Portal 配置 **Interactions Endpoint URL**）、**Ed25519** 请求体验签、以及将 Slash 选择路由到与 Telegram 相同的执行分支。当前若仅注册 Slash 而无 Interaction 服务，用户在客户端点选命令可能得到 Discord 默认错误或一直加载，属预期缺口。
- **Polling 路径**：与 Telegram 的「普通文本 → `run`/`continue`」最接近；Slash 的「固定短回复」在 Discord 上需上述 Interaction 服务才能与 Telegram 完全等价。

## 相关代码

- Telegram 斜杠与执行：`cai_agent.__main__` 中 `_telegram_slash_reply_text`、`_run_gateway_telegram_webhook_server`。
- Discord REST 与默认命令表：`cai_agent.gateway_discord`（`discord_default_slash_command_specs`、`discord_register_application_commands`、`discord_list_application_commands`）。
