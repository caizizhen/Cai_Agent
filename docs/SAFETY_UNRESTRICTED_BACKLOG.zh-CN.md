# 解限模式与安全确认：完整开发清单

> 产品语义：**默认不按「任务类型」拦工具**；仅在命中**危险行为**时要求二次确认（TUI：`/danger-approve`；非交互：`CAI_DANGEROUS_APPROVE=1`）。  
> 配置：`[safety].unrestricted_mode`、`[safety].dangerous_confirmation_required`（见 `cai-agent.toml` 模板）。

## 状态图例

- **Done**：已实现并有测试/冒烟覆盖  
- **Doing**：当前迭代正在做  
- **Todo**：已立项，待排期  
- **Explore**：需产品/安全评审后再做  

---

## P0 · 配置与可观测（Done）

| ID | 项 | 说明 |
|---|---|---|
| P0-1 | `[safety].unrestricted_mode` | 默认 `false`；`CAI_UNRESTRICTED_MODE` 覆盖 |
| P0-2 | `[safety].dangerous_confirmation_required` | 默认 `true`；`CAI_DANGEROUS_CONFIRMATION_REQUIRED` 覆盖 |
| P0-3 | `doctor --json` / 文本 doctor | `unrestricted_mode`、`dangerous_confirmation_required` |
| P0-4 | `tools guard --json` | `policy` 同上字段 |
| P0-5 | 示例模板 | `cai-agent.example.toml`、`cai-agent.starter.toml` |

---

## P1 · TUI 与执行闭环（Done）

| ID | 项 | 说明 |
|---|---|---|
| P1-1 | `/unrestricted` / `/unrestricted on|off` | 查看与切换；有 `config_loaded_from` 时写回 TOML |
| P1-2 | `/danger-approve` | 进程内放行**下一次**危险 `dispatch` |
| P1-3 | `/status` | 展示解限与确认开关 |
| P1-4 | `dispatch` 前置确认 | `unrestricted_mode` + `dangerous_confirmation_required` 时拦截 |
| P1-5 | `run_command` | 高危子串命中 → 确认（解限下跳过「硬阻断」，改为确认后执行） |
| P1-6 | `write_file` | 敏感路径后缀（`.env`、密钥类等）→ 确认 |
| P1-7 | 非交互逃逸 | `CAI_DANGEROUS_APPROVE=1` |

---

## P2 · 扩大危险面（Done）

| ID | 项 | 说明 |
|---|---|---|
| P2-1 | `mcp_call_tool` | 解限 + 要求确认时：**任意** MCP 调用需先确认（外部工具不可信） |
| P2-2 | `fetch_url`（http） | 明文 `http://` → 确认（降级传输风险） |
| P2-3 | 文档 | `README.zh-CN.md` 权限与安全小节用户说明 |
| P2-4 | 自动化测试 | `test_unrestricted_danger_dispatch_extended.py` |

---

## P3 · 体验与结构化确认

| ID | 状态 | 项 | 说明 |
|---|---|---|---|
| P3-1 | **Done** | Graph 执行链 **progress** 载荷 | `tools_node` 在将进入交互确认前下发 `progress.phase=danger_confirm_prompt`（含工具名、原因、摘要），并与 `prepare_interactive_dangerous_dispatch` 串联；非 TUI 入口仍不传 `dangerous_confirm`，行为与原先一致 |
| P3-2 | **Done** | TUI **Modal** 自动弹出 | `DangerConfirmScreen`：无进程内预授权且无 `CAI_DANGEROUS_APPROVE` 时弹窗「允许执行 / 取消」；拒绝则不入 `dispatch`，返回合成失败说明（仍可 `/danger-approve` 或环境变量放行） |
| P3-3 | **Done** | 批量/会话级策略 | TUI：`/danger-session-mcp <name>`、`/danger-session-fetch <host|url>`、`/danger-session-clear`；确认框对 MCP / 明文 http fetch 增加「本会话放行」按钮；`tools.session_danger_preapproved` + `dispatch` 不消耗一次性 budget |
| P3-4 | **Done** | 审计日志 | `[safety].dangerous_audit_log_enabled`（默认 `false`）与 `CAI_DANGEROUS_AUDIT_LOG`；工作区 ``.cai/dangerous-approve.jsonl`` 追加 `dangerous_audit_event_v1`（grant / executed / session_*） |

---

## P4 · 规则细化（Todo / Explore）

| ID | 项 | 说明 |
|---|---|---|
| P4-1 | `fetch_url` SSRF 扩展 | `allow_private_resolved_ips=true` 时强制确认、`file://`（若引入）等 |
| P4-2 | `write_file` 语义规则 | 覆盖关键配置文件名（`pyproject.toml` 仅在有破坏性 diff 时确认——需启发式） |
| P4-3 | `run_command` 扩展 | 可选放宽白名单时的命令级确认列表 |
| P4-4 | Gateway / API Server | 非 TUI 入口的统一确认契约 |

---

## 验证命令（回归）

```powershell
$env:PYTHONPATH="d:\path\cai-agent\src"
python -m pytest -q cai-agent/tests/test_run_command_security_policy.py `
  cai-agent/tests/test_tools_make_dir.py `
  cai-agent/tests/test_unrestricted_mode_config.py `
  cai-agent/tests/test_tui_slash_suggester.py `
  cai-agent/tests/test_tool_provider_contract_cli.py `
  cai-agent/tests/test_doctor_cli.py `
  cai-agent/tests/test_unrestricted_danger_dispatch_extended.py `
  cai-agent/tests/test_tools_prepare_interactive_dangerous_dispatch.py `
  cai-agent/tests/test_danger_session_and_audit.py
python scripts/smoke_new_features.py
```

（路径按本机仓库调整。）

---

## 关联变更记录

- `CHANGELOG.md` / `CHANGELOG.zh-CN.md`：`SAFETY-N01-D01`、`SAFETY-N01-D02`、`SAFETY-N02-*`、`SAFETY-N03-D01`、`SAFETY-N04-D01`
