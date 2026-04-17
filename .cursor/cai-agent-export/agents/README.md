# Agents 子代理定义

`agents/` 存放可委派角色的定义模板，参考 Everything Claude Code 的多角色协作方式。

当前提供核心角色：

- `planner.md`：规划与任务拆解
- `code-reviewer.md`：风险导向代码审查
- `security-reviewer.md`：安全风险审查
- `debug-resolver.md`：故障排查与修复建议
- `doc-updater.md`：文档与变更记录同步

后续可继续扩展语言专属或场景专属角色（Python reviewer、DB reviewer、build resolver 等）。

