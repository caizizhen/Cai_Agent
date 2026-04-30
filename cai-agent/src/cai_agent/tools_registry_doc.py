"""内置工具注册表文档元数据（中文）。

`docs/TOOLS_REGISTRY.zh-CN.md` 中的工具表由 ``scripts/gen_tools_registry_zh.py`` 根据
本模块的 :data:`BUILTIN_TOOLS_DOC_ROWS` 生成；新增/重命名 ``tools.dispatch`` 工具时请
同步更新 :data:`BUILTIN_TOOLS_DOC_ROWS` 与 ``tools.DISPATCH_TOOL_NAMES``，并运行生成脚本。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BuiltinToolDocRow:
    name: str
    category: str
    permission_key: str
    summary: str


BUILTIN_TOOLS_DOC_ROWS: tuple[BuiltinToolDocRow, ...] = (
    BuiltinToolDocRow(
        "read_file",
        "文件系统（只读）",
        "read_file",
        "读取文件（默认相对工作区）；解限时可绝对路径（工作区外须二次确认）；支持 `line_start`/`line_end`",
    ),
    BuiltinToolDocRow(
        "list_dir",
        "文件系统（只读）",
        "read_file",
        "列出目录内容（解限时可绝对路径，工作区外须二次确认）",
    ),
    BuiltinToolDocRow(
        "list_tree",
        "文件系统（只读）",
        "read_file",
        "目录树（深度与条数受限；解限时可绝对路径，工作区外须二次确认）",
    ),
    BuiltinToolDocRow(
        "glob_search",
        "文件系统（只读）",
        "read_file",
        "按 glob 搜索路径（解限时 ``root`` 可绝对路径，工作区外须二次确认）",
    ),
    BuiltinToolDocRow(
        "search_text",
        "文件系统（只读）",
        "read_file",
        "文本子串搜索（解限时 ``root`` 可绝对路径，工作区外须二次确认）",
    ),
    BuiltinToolDocRow(
        "git_status",
        "Git（只读）",
        "git_status",
        "只读 `git status`",
    ),
    BuiltinToolDocRow(
        "git_diff",
        "Git（只读）",
        "git_diff",
        "只读 `git diff`，支持 `staged` 标志",
    ),
    BuiltinToolDocRow(
        "write_file",
        "文件系统（写入）",
        "write_file",
        "写入/覆盖文件（解限时可绝对路径，工作区外须二次确认）",
    ),
    BuiltinToolDocRow(
        "make_dir",
        "文件系统（写入）",
        "write_file",
        "递归创建目录（等同 `mkdir -p`；解限时可绝对路径，工作区外须二次确认）",
    ),
    BuiltinToolDocRow(
        "run_command",
        "Shell 执行",
        "run_command",
        "按白名单 `argv[0]` 执行命令；解限时 `cwd` 可绝对路径（工作区外须二次确认）；受 `[permissions]` 约束",
    ),
    BuiltinToolDocRow(
        "fetch_url",
        "网络（只读）",
        "fetch_url",
        "HTTPS GET；受主机白名单与 `[permissions].fetch_url` 约束；**`[fetch_url].max_redirects`**（**1–50**，默认 **20**）或 **`CAI_FETCH_URL_MAX_REDIRECTS`** 控制跟随重定向次数；请求前 **`getaddrinfo`** 解析 IP 校验（反 DNS rebinding），内网解析需 **`allow_private_resolved_ips`** / **`CAI_FETCH_URL_ALLOW_PRIVATE_RESOLVED_IPS`**",
    ),
    BuiltinToolDocRow(
        "mcp_list_tools",
        "MCP Bridge",
        "mcp_list_tools",
        "从 MCP Bridge 拉取工具清单（短时缓存）",
    ),
    BuiltinToolDocRow(
        "mcp_call_tool",
        "MCP Bridge",
        "mcp_call_tool",
        "调用 MCP Bridge 工具（需 `mcp_enabled=true`）",
    ),
)


_MARKDOWN_DOC_FOOTER = """## 权限模型

工具执行前须通过 `enforce_tool_permission(settings, name)`：

- `allow`：直接允许
- `ask`：需要用户确认（`CAI_AUTO_APPROVE=1` 可绕过）
- `deny`：拒绝并抛出 `PermissionDeniedError`

权限在 `[permissions]` 配置段或 `CAI_PERMISSION_<TOOL>` 环境变量中指定。

## 高危命令审批

`run_command` 额外受 `[permissions].run_command_approval_mode` 控制：

- `block_high_risk`（默认）：匹配 `run_command_high_risk_patterns` 的命令被阻断
- `allow_all`：跳过高危检查（不推荐生产）

## Hooks 支持

以下事件会自动触发 `hooks.json` 中匹配的钩子脚本（`command` 或 `script` 字段）：

`session_start` / `session_end`、`workflow_start` / `workflow_end`、
`quality_gate_start` / `quality_gate_end`、`security_scan_start` / `security_scan_end`、
`memory_start` / `memory_end`、`export_start` / `export_end`、
`observe_start` / `observe_end`、`cost_budget_start` / `cost_budget_end`

## 相关文档

- 权限设计：[`CONTEXT_AND_COMPACT.zh-CN.md`](CONTEXT_AND_COMPACT.zh-CN.md)
- 解限模式与危险二次确认（含关键 `write_file` noop）：[`SAFETY_UNRESTRICTED_BACKLOG.zh-CN.md`](SAFETY_UNRESTRICTED_BACKLOG.zh-CN.md)
- MCP 配方：[`MCP_WEB_RECIPE.zh-CN.md`](MCP_WEB_RECIPE.zh-CN.md)
- Hooks 说明：`hooks/README.md`
- 安全扫描：`cai-agent security-scan --json`
"""


def render_tools_registry_markdown_zh_cn() -> str:
    """生成完整 `TOOLS_REGISTRY.zh-CN.md` 正文（Unix LF）。"""
    header = "\n".join(
        [
            "# CAI Agent 工具注册表",
            "",
            "本文档由仓库根目录 **`scripts/gen_tools_registry_zh.py`** 根据 "
            "**`cai-agent/src/cai_agent/tools_registry_doc.py`** 中的 "
            "**`BUILTIN_TOOLS_DOC_ROWS`** 自动生成。"
            "修改工具表请编辑该 Python 元数据后运行生成脚本，**勿手写表格行**。",
            "静态章节（权限模型、Hooks 等）亦由同一模板输出；若需改写请编辑 "
            "**`tools_registry_doc.py`** 中的 `_MARKDOWN_DOC_FOOTER`。",
            "",
            "## 工具分类",
            "",
            "| 工具名 | 分类 | 权限键 | 说明 |",
            "|--------|------|--------|------|",
        ]
    )
    rows: list[str] = []
    for r in BUILTIN_TOOLS_DOC_ROWS:
        summ = r.summary.replace("|", "\\|")
        rows.append(
            f"| `{r.name}` | {r.category} | `{r.permission_key}` | {summ} |",
        )
    body = header + "\n" + "\n".join(rows) + "\n\n" + _MARKDOWN_DOC_FOOTER.rstrip() + "\n"
    return body.replace("\r\n", "\n")
