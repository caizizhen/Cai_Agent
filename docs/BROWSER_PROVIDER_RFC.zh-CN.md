# Browser Provider RFC

> 状态：`BRW-N03` 设计基线。  
> 目标：在 `BRW-N01` 的 Playwright MCP preset 与 `BRW-N02` 的 JSON 契约之上，明确浏览器执行器进入默认 agent 前的安全、审计、产物和许可证边界。

## 1. 结论

- 默认路径继续是 **MCP first**：首选 `microsoft/playwright-mcp`，Cai Agent 不在核心依赖里绑定浏览器运行时。
- `browser-use/browser-use` 作为架构参考：重点借鉴 action registry、browser session state、step limit、failure recovery，不直接把它变成默认依赖。
- `skyvern-ai/skyvern` 只作高级工作流参考：表单工作流、审计、失败恢复值得借鉴；其 AGPL-3.0 许可证不适合未经评估直接嵌入默认分发。
- 当前默认入口只输出契约与计划：`tools browser-check --json`、`browser check --json`、`browser task --json`。真正点击、输入、上传、下载必须进入后续执行器任务，并绑定人工确认。

## 2. 已有基础

- `BRW-N01`：`mcp-check --preset browser`、`tools bridge --preset browser`、`docs/BROWSER_MCP.zh-CN.md`。
- `BRW-N02`：`browser_provider_check_v1` 与 `browser_task_v1`，包含 `provider`、`session`、`artifacts`、`steps`、`error/errors`。
- Tool Provider registry 已有 `browser` 类别，默认权限键为 `mcp_call_tool`，默认模式为 `ask`。

## 3. 安全边界

| 场景 | 默认策略 | 后续执行器要求 |
|---|---|---|
| 普通导航 / 截图 / snapshot | 可计划，执行前确认 | 记录 URL、tool、step index、结果摘要 |
| 点击 / 输入 | 默认 ask | 显示目标 selector / 可访问名称 / 页面 URL |
| 登录 / 验证码 / MFA | 用户手动完成 | 模型不得请求明文密码、cookie、token |
| 支付 / 删除 / 提交表单 | 默认阻断或二次确认 | 必须标记 destructive / irreversible |
| 下载 | 默认 ask | 限制到 `.cai/browser/downloads`，记录文件名、大小、MIME |
| 上传文件 | 默认 ask | 文件必须在 workspace 内，路径过沙箱校验 |
| `evaluate` / JS 执行 | 默认 ask，高风险 | 限制长度，禁止读取敏感存储的自动化脚本 |
| 跨域跳转 | 默认允许但记录 | 若配置 `allow_hosts`，不在列表内直接阻断 |

## 4. Session 与产物

默认 session 字段：

- `max_steps`: 1-50，默认 10。
- `allow_hosts`: 空数组表示未限制；设置后只允许匹配 host。
- `headless`: 默认 `true`。
- `isolated`: 默认 `true`，推荐 Playwright MCP `--isolated`。

默认产物目录：

- `.cai/browser/screenshots`
- `.cai/browser/downloads`
- `.cai/browser/traces`

后续执行器必须把产物路径写入 JSON 输出，不把图片/下载内容直接塞进模型上下文；模型只拿摘要、路径和必要的 OCR / snapshot 文本。

## 5. 审计字段

后续执行器的每一步至少记录：

- `step_id`
- `action`
- `url_before` / `url_after`
- `host`
- `selector` 或 `target_summary`
- `requires_confirmation`
- `confirmed`
- `result`
- `artifact_paths`
- `elapsed_ms`
- `error`

建议新增 JSONL：`.cai/browser/audit.jsonl`，schema 可命名为 `browser_audit_event_v1`。

## 6. 后续任务拆分

| 任务 | 状态建议 | 范围 |
|---|---|---|
| `BRW-N04` | Ready after RFC | Browser MCP executor：把 `browser_task_v1.steps[]` 映射到显式确认的 `mcp_call_tool` |
| `BRW-N05` | Design | Browser audit JSONL 与 artifact manifest |
| `BRW-N06` | Design | 登录态与人工接管 UX：只记录状态，不收集凭据 |
| `BRW-N07` | Explore | `browser-use` optional extra adapter |
| `BRW-N08` | Explore / Legal review | Skyvern 风格表单工作流参考，不直接引入 AGPL 代码 |

## 7. 验收门槛

- 默认无真实浏览器也能跑通 `browser check/task --json`。
- 启用 Playwright MCP 后，executor 至少支持 navigate / snapshot / screenshot 三类只读动作。
- click / type / upload / download / evaluate 必须有显式确认与审计。
- 所有新增 JSON schema 回写 `docs/schema/README.zh-CN.md`。
- 所有下载、截图、trace 都落在 workspace `.cai/browser/` 下。
