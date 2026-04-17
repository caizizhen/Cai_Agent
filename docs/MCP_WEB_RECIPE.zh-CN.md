# 通过 MCP 提供 Web / 搜索能力（与内置 `fetch_url` 二选一或并存）

当 **不**开启内置 `fetch_url`（见 `cai-agent.toml` 的 `[fetch_url]`）时，可通过自建 **MCP Bridge** 暴露只读工具，例如：

- `web_fetch`：服务端校验 URL、超时、大小上限、允许域名
- `web_search`：接入合规搜索 API

## Bridge 协议（与 CAI Agent 一致）

- `GET {base_url}/tools` → 工具列表 JSON
- `POST {base_url}/tools/{name}`，body `{"args":{...}}` → 工具结果

在 `cai-agent.toml` 中：

```toml
[mcp]
base_url = "http://127.0.0.1:8787"
timeout_sec = 30

[agent]
mcp_enabled = true
```

模型侧使用已有工具：`mcp_list_tools`、`mcp_call_tool`。

## 安全建议

- Bridge 与 Agent 同机或内网部署，对公网接口做鉴权（`MCP_API_KEY`）
- 在 Bridge 内实现与内置 `fetch_url` 同类的主机白名单与 SSRF 防护
- 不要将 Bridge 无鉴权暴露在公网

## 与 parity 矩阵的关系

在 [PARITY_MATRIX.zh-CN.md](PARITY_MATRIX.zh-CN.md) 中，若采用本方案替代内置 Web 工具，请将对应行状态标为 **`MCP`**，并在备注中链接到本文件或你的 Bridge 仓库。
