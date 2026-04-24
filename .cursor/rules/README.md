# Rules（约束与建议规则）

## Cursor Agent：全计划自动交付

- 本目录 **`full-plan-autonomous-delivery.mdc`**（`alwaysApply: true`）：按 **`docs/DEVELOPER_TODOS.zh-CN.md`** / **`docs/ROADMAP_EXECUTION.zh-CN.md`** 推进开发；每完成一项即 **pytest → smoke →（必要时）regression → 更新文档 → git commit（+ 已授权则 push）**。

`rules/` 目录用于存放针对不同语言与场景的约束与建议规则，思路参考 Everything Claude Code 的 `rules/`：

- `rules/common/`：与具体语言无关的通用规则，例如：
  - 错误处理与日志约定
  - 目录与模块划分建议
  - 安全与隐私边界（敏感文件、密钥、生成代码的审查要求）
- `rules/python/`：Python 专用规则，例如：
  - 类型标注与依赖管理
  - 异步/同步选择与并发模式
  - 测试与验证策略

当前版本已提供通用规则与 Python 规则文件，并可在 `cai_agent` 内部按需加载，用于：

- 在生成实现计划时提醒风险点；
- 在执行前后输出针对当前改动的规则检查提示；
- 为不同仓库提供可定制的风格与安全基线。

