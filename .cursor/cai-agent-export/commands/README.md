# Commands 兼容层

`commands/` 用于提供传统斜杠命令语义的兼容文档层，风格参考 Everything Claude Code。

当前阶段采用「命令定义 + 执行建议」形式，后续可逐步接入 `cai-agent` 的 CLI/TUI 入口。

## 设计目标

- 让常见命令（如 `/plan`、`/code-review`、`/verify`）有统一语义。
- 便于不同 Agent Harness（Claude Code/Cursor/Codex）迁移。
- 与 `skills/` 一一关联，命令负责入口，技能负责流程细节。

## 当前已提供命令

- `/plan`
- `/code-review`
- `/verify`
- `/fix-build`
- `/security-scan`
- `/sessions`

