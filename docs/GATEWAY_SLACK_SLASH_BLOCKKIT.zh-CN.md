# Slack Slash Commands、Interactivity 与 Block Kit（网关）

`cai-agent gateway slack serve-webhook` 在单端口上同时处理：

| `Content-Type` | 用途 | 响应 |
|----------------|------|------|
| `application/json` | [Events API](https://api.slack.com/events-api)（`url_verification`、`event_callback`） | 与既有 MVP 一致 |
| `application/x-www-form-urlencoded` | [Slash Commands](https://api.slack.com/interactivity/slash-commands) 或 [Interactivity](https://api.slack.com/interactivity/handling)（`payload=` JSON） | JSON 体（`text` 或 `blocks`） |

## 签名校验

与 Events 相同：原始 POST body 字节 + `X-Slack-Request-Timestamp` + `Signing Secret` 计算 `v0` HMAC-SHA256，与 `X-Slack-Signature` 做常量时间比较。实现见 `cai_agent.gateway_slack.verify_slack_request_signature`（与 handler 内逻辑同源）。

生产环境**必须**配置 `CAI_SLACK_SIGNING_SECRET`（或 `--signing-secret`）；未配置时 handler 不验签（仅便于本机联调）。

## Slash：推荐在 Slack App 中的配置

1. **Create New Command**：例如 Command=`/cai`，Request URL=`https://<公网可达主机>:7892/slack/events`（路径可任意，只要与反向代理一致并转发到本服务）。
2. 另可注册独立命令 `/ping`、`/help`、`/status` 等，指向**同一** Request URL；网关根据 `command` 字段分支。
3. 在 **Interactivity** 中把 **Request URL** 指到同一 origin（可与 Slash 同 URL）；收到 `payload=` 时返回 Block Kit ACK。

## `/cai` 子命令与执行开关

| 用户输入 | 行为 |
|----------|------|
| `/cai` 或 `/cai help` | Block Kit 帮助（含 `bind` / `execute-on-slash` 说明） |
| `/cai ping` | 固定 `pong` 文案 |
| `/cai status` | 打印 `slack-session-map.json` 路径提示 |
| `/cai new` | 续聊与 `continue` 提示 |
| `/cai <其它文本>` | 仅当启动服务时带有 **`--execute-on-slash`** 时，将整段文本作为 **goal** 调用与 Events 消息同源的 `graph`（需频道已 `gateway slack bind` 且通过 allowlist） |

## Block Kit

帮助类回复使用 `blocks`（`header` + `section` + `mrkdwn`）。执行结果当前以 **`response_type: ephemeral`** 的纯 `text` 返回（避免 Slash 3s 窗口内块拼装过复杂）；需要频道广播时可配合 **`--reply-on-execution`** 由 bot 再发 `chat.postMessage`。

## Interactivity

`block_actions` 等事件目前仅返回 **ephemeral** 确认块，便于验证 URL 与签名；与业务执行链的对接可作为后续迭代（hooks / 异步 `response_url`）。

## 相关代码

- `cai_agent.gateway_slack`：`build_slack_slash_command_http_response`、`slack_interactivity_http_response`、`slack_try_execute_channel_text`、`_SlackWebhookHandler`。
