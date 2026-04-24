# Gateway 多工作区与映射 Schema（B3）

## 工作区模型

每个 **工作区根目录** 下独立维护：

- `.cai/gateway/telegram-session-map.json`（`gateway_telegram_map_v1`）
- `.cai/gateway/discord-session-map.json`（`gateway_discord_map_v1`）
- `.cai/gateway/slack-session-map.json`（`gateway_slack_map_v1`）

CLI 通过各子命令的 **`-w` / `--workspace`** 选择根目录；跨仓巡检时使用 **`gateway maps summarize`**。

## `gateway maps summarize`

机读输出 schema：**`gateway_maps_summarize_v1`**（见 `cai_agent.gateway_maps.summarize_gateway_maps`）。

常用调用：

```bash
# 当前目录单工作区
cai-agent gateway maps summarize --json

# 多个根（可重复 --root）
cai-agent gateway maps summarize --root D:\repo\A --root D:\repo\B --json

# 从文件读取根列表（每行一个路径，# 开头为注释）
cai-agent gateway maps summarize --workspaces-file ./my-workspaces.txt --json

# 单根简写（与 --root 等价语义）
cai-agent gateway maps summarize -w D:\repo\A --json
```

**注意**：若同时传入 **多个 `--root`** 与 **`-w`**，当前实现以 **`--root` 列表为准**（忽略 `-w`）；文档化以避免歧义。

## 绑定条目可选字段（向前兼容）

在保持原有 `session_file` / `bound_at`（及 Telegram 的 `chat_id` / `user_id`）的前提下，可写入运维用元数据（旧版本读取器可忽略未知键）：

| 平台 | 可选字段 | CLI |
|------|-----------|-----|
| Telegram | `label` | `gateway telegram bind … --label <text>` |
| Discord | `guild_id`, `label` | `gateway discord bind … --guild-id … --label …` |
| Slack | `team_id`, `label` | `gateway slack bind … --team-id … --label …` |

`guild_id` / `team_id` 用于在 **多团队 / 多 Guild** 运维时区分来源；不改变网关执行逻辑（仍以 `channel_id` 为主键）。

补充：Slack 侧现在还提供 `gateway slack health --json`，可把 `slack-session-map.json` 的绑定数量、allowlist 开关、Signing Secret 配置状态和可选 `auth.test` 结果统一导出为 `gateway_slack_health_v1`。

## 与 `gateway status` 的关系

- **`gateway status`**：Telegram 生命周期（`telegram-config.json`、PID、白名单计数等，Hermes S6-01）。
- **`gateway maps summarize`**：三平台 **映射文件** 的绑定列表与计数，便于跨工作区对账。

## 相关源码

- `cai_agent.gateway_maps`：汇总与路径解析。
- `cai_agent.gateway_discord` / `gateway_slack`：`bind` 写入可选元数据。
- `cai_agent.__main__`：`gateway telegram bind` 的 `--label`。
