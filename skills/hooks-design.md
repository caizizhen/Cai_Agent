## 技能：Hook 设计与治理

> 适用场景：需要新增会话钩子、工具前后置检查或自动化治理逻辑。

### 目标

- 让自动化可控、可审计、可关闭，不干扰主流程。

### 典型步骤

1. 定义触发时机与触发条件；
2. 明确输入输出与失败处理；
3. 设计开关与回退机制；
4. 加入日志与监控字段；
5. 验证正常路径与异常路径。

### 项目级 `hooks.json` 与 CLI

- 配置文件路径：优先 `hooks/hooks.json`，否则 `.cai/hooks/hooks.json`（可用 `cai-agent hooks list` 确认实际解析到的文件）。
- 运行配置：`cai-agent.toml` 中 `[hooks]` 的 `profile`、`disabled`、`timeout_sec`，或环境变量 `CAI_HOOKS_PROFILE` / `CAI_HOOKS_DISABLED` / `CAI_HOOKS_TIMEOUT_SEC`。
- 自检命令：
  - `cai-agent hooks list`：列出全部 hook 条目及在当前 profile 下是否会跳过/阻断（输出 `hooks_catalog_v1`）。
  - `cai-agent hooks run-event <event> --dry-run`：仅分类、不执行子进程（`hooks_run_event_result_v1`）。
  - `cai-agent hooks run-event <event> --payload '{...}'`：执行匹配且含 `command` 数组的外部钩子。

