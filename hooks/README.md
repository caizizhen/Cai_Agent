# Hooks 自动化骨架

`hooks/` 用于定义会话与工具生命周期自动化规则，当前以文档与配置骨架为主。

## 文件说明

- `hooks.json`：hook 规则配置（示例）。
- `session-start.md`：会话开始时建议动作。
- `session-end.md`：会话结束时建议动作。

## CLI 识别的 `event` 取值（`hooks.json` 中 `event` 字段）

- `session_start` / `session_end`：`cai-agent run` / `continue` / `command` / `agent` / `fix-build` 包裹一次模型调用。
- `workflow_start` / `workflow_end`：`cai-agent workflow` 整次多步执行前后（失败时仍会在返回前触发 `workflow_end`）。
- `quality_gate_start` / `quality_gate_end`：包裹独立子命令 `cai-agent quality-gate` 的一次执行（`fix-build` 内嵌调用的门禁不触发这两项，以免重复刷屏）。
- `security_scan_start` / `security_scan_end`：包裹 `cai-agent security-scan`；扫描抛错时仍会在 `return` 前触发 `security_scan_end`。
- `memory_start` / `memory_end`：包裹 `cai-agent memory` 各子命令整段执行（子命令 `return` 前会先跑 `memory_end`）。
- `export_start` / `export_end`：包裹 `cai-agent export`（该命令 stdout 恒为 JSON，钩子 stderr 在非交互脚本中通常关闭）。
- `observe_start` / `observe_end`：包裹 `cai-agent observe`；人类可读一行摘要末尾会带 `run_events_total=…`（与 JSON 中 `aggregates` 对齐）。
- `cost_budget_start` / `cost_budget_end`：包裹 `cai-agent cost budget`（stdout 恒为一行 JSON）。

## `hooks.json` 条目字段

- `command`：字符串数组，非空时作为子进程 argv 执行（与历史行为一致）。
- `script`：可选，相对 `hooks.json` 所在目录的路径；须落在项目根内。支持 `.py`（用当前解释器）、`.sh`（POSIX 或 Windows 上 `bash`/`sh`）、Windows 下 `.ps1` / `.cmd` / `.bat`。与 `command` 二选一即可触发执行。

## 设计原则

- 可控：所有 hook 支持开关或按环境禁用。
- 可观测：记录触发、耗时、状态。
- 安全：不泄露敏感数据，不执行破坏性默认动作。

