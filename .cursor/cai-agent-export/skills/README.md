# Skills（可复用工作流与提示模版）

`skills/` 目录用于存放可复用的 Agent 工作流与高级提示模版，思路参考 Everything Claude Code 的 `skills/`：

- 每个技能对应一个文件（例如 `plan-then-execute.md`、`security-scan.md`），描述：
  - 技能名称与适用场景
  - 推荐的对话提示模版
  - 典型步骤与注意事项
- 后续可以在 `cai-agent` 中为这些技能提供快捷入口（如专门的 CLI 子命令或 TUI 斜杠命令）。

当前版本仅提供目录和说明文档，后续可以逐步补充具体技能内容，并在：

- CLI 中通过子命令调用（例如 `cai-agent plan ...` 结合某个技能模版）；
- TUI 中通过斜杠命令引用（例如 `/ecc:plan` 风格别名），

以便在 Claude Code / Everything Claude Code / Cursor 等不同 Agent Harness 之间迁移复用这些技能。

