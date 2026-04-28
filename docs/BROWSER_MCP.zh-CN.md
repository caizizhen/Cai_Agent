# Browser MCP 接入说明

> 当前定案：Browser automation 先走 MCP。`BRW-N01` 已接入 Playwright MCP preset、检查入口和文档模板；`BRW-N02` 已补最小原生 provider / browser-use 风格 session contract；执行器进入默认 agent 前按 `BRW-N03` RFC 治理。

## 推荐实现

- 首选参考：`microsoft/playwright-mcp`
- 架构参考：`browser-use/browser-use`
- 高级工作流参考：`skyvern-ai/skyvern`（注意 AGPL-3.0 许可证风险，当前只参考治理与审计思路）

## 最小配置

在你的 MCP launcher 中添加 Playwright MCP server，建议使用隔离模式：

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest", "--isolated"]
    }
  }
}
```

Cai Agent 配置继续保持 MCP 权限最小化：

```toml
[agent]
mcp_enabled = true

[mcp]
base_url = "http://127.0.0.1:8787"

[permissions]
mcp_list_tools = "allow"
mcp_call_tool = "ask"
```

## 自检命令

```powershell
cai-agent mcp-check --json --preset browser --list-only
cai-agent mcp-check --preset browser --print-template
cai-agent tools bridge --preset browser --json
cai-agent tools browser-check --json
cai-agent browser check --json
cai-agent browser task "open dashboard and summarize" --url https://example.com --json
cai-agent tools contract --json
cai-agent tools list --json
```

`browser` preset 会查找 `browser`、`playwright`、`navigate`、`click`、`type`、`screenshot`、`snapshot`、`evaluate` 等关键词。命中任一类浏览器工具即可证明 MCP 工具列表已接通；缺失关键词会进入 `missing_tools` / `fallback_hint`，方便 onboarding 和 CI 输出下一步。

## 安全边界

- 浏览器动作默认走 `mcp_call_tool = "ask"`，不要默认自动点击、输入或提交。
- 推荐使用 `--isolated`，避免污染用户常用浏览器 profile。
- 登录、验证码、支付、删除、提交表单、下载、上传文件等动作必须保留显式人工确认。
- 不要把密码、cookie、token 直接交给模型；需要登录态时优先让用户在隔离会话里手动完成。
- 下载目录、截图、trace 等产物后续由 `BRW-N02` 的 provider contract 明确落盘范围和审计字段。

## 当前验收

- `tools contract/list` 中 `browser` provider 可见，权限为 `mcp_call_tool: ask`。
- `tools bridge --preset browser --json` 能输出 `tool_mcp_bridge_v1`、`doc_paths`、`isolation_hints`、matched/missing tools。
- `mcp-check --preset browser --print-template` 能输出 Playwright MCP 的 `npx @playwright/mcp@latest --isolated` 示例。
- `tools browser-check --json` 与 `browser check/task --json` 能输出稳定 provider/session/artifacts/steps/error 契约；`BRW-N02` 暂不启动真实浏览器。
