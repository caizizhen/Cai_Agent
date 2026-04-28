from __future__ import annotations

from typing import Any


_DOC_PATH = "docs/WEBSEARCH_NOTEBOOK_MCP.zh-CN.md"
_BROWSER_DOC_PATH = "docs/BROWSER_MCP.zh-CN.md"
_ONBOARDING_PATH = "docs/ONBOARDING.zh-CN.md"

MCP_PRESET_DEFS: dict[str, dict[str, Any]] = {
    "websearch": {
        "title": "WebSearch",
        "recommended_tools": ["search", "web", "serp", "tavily", "duckduckgo", "google", "bing"],
        "summary": "MCP-first Web search / structured search onboarding.",
        "template_comment": "推荐把 Web 检索服务挂到 MCP，再通过 /mcp call 或工具白名单调用。",
    },
    "notebook": {
        "title": "Notebook",
        "recommended_tools": ["notebook", "jupyter", "ipynb", "cell"],
        "summary": "MCP-first Jupyter / notebook controlled cell operations.",
        "template_comment": "推荐把 notebook/Jupyter 服务挂到 MCP，默认保持只读或受控单元执行。",
    },
    "browser": {
        "title": "Browser Automation",
        "recommended_tools": [
            "browser",
            "playwright",
            "navigate",
            "click",
            "type",
            "screenshot",
            "snapshot",
            "evaluate",
        ],
        "summary": "MCP-first Playwright browser automation with isolated sessions.",
        "template_comment": "推荐先接 microsoft/playwright-mcp，并使用 isolated 模式；所有浏览器动作默认走 mcp_call_tool=ask。",
        "doc_path": _BROWSER_DOC_PATH,
        "isolation_hint": "Use Playwright MCP with --isolated; keep credentials and downloads under explicit user control.",
        "mcp_server_command": "npx @playwright/mcp@latest --isolated",
    },
}


def allowed_mcp_preset_choices() -> tuple[str, ...]:
    return ("websearch", "notebook", "websearch/notebook", "browser")


def expand_mcp_preset_choice(preset: str | None) -> list[str]:
    key = str(preset or "").strip().lower()
    if not key:
        return []
    if key == "websearch/notebook":
        return ["websearch", "notebook"]
    if key in MCP_PRESET_DEFS:
        return [key]
    return []


def mcp_preset_doc_path(name: str) -> str:
    meta = MCP_PRESET_DEFS[name]
    return str(meta.get("doc_path") or _DOC_PATH)


def mcp_preset_isolation_hint(name: str) -> str | None:
    meta = MCP_PRESET_DEFS[name]
    hint = str(meta.get("isolation_hint") or "").strip()
    return hint or None


def build_mcp_preset_template(name: str) -> str:
    meta = MCP_PRESET_DEFS[name]
    recommended = ", ".join(meta["recommended_tools"])
    base = (
        "# cai-agent.toml (MCP preset template)\n"
        "[agent]\n"
        "mcp_enabled = true\n\n"
        "[mcp]\n"
        "base_url = \"http://127.0.0.1:8787\"\n\n"
        "[permissions]\n"
        "mcp_list_tools = \"allow\"\n"
        "mcp_call_tool = \"ask\"\n\n"
        f"# preset = {name}\n"
        f"# title = {meta['title']}\n"
        f"# recommended_tools = {recommended}\n"
        f"# note = {meta['template_comment']}\n"
        f"# docs = {mcp_preset_doc_path(name)}\n"
        f"# onboarding = {_ONBOARDING_PATH}\n"
    )
    if name == "browser":
        return base + (
            "\n"
            "# Playwright MCP server example (configure in your MCP launcher):\n"
            "# command = \"npx\"\n"
            "# args = [\"@playwright/mcp@latest\", \"--isolated\"]\n"
        )
    return base


def format_tui_mcp_web_notebook_quickstart() -> str:
    """TUI /help、/mcp-presets、任务看板：WebSearch·Notebook MCP 最短路径（CC-01b）。"""
    return (
        "\n[bold]WebSearch · Notebook（MCP）[/]\n"
        f"[dim]文档[/] [cyan]{_DOC_PATH}[/] [dim]· 入门[/] [cyan]{_ONBOARDING_PATH}[/]\n"
        "[dim]另开终端自检：[/]\n"
        "[cyan]cai-agent mcp-check --preset websearch/notebook --list-only[/]\n"
        "[cyan]cai-agent mcp-check --preset websearch --print-template[/]\n"
        "[dim]本界面：[/][cyan]/mcp[/][dim] 列工具 →[/] [cyan]/mcp call 工具名 {\"query\":\"…\"}[/]\n"
        "[dim]随时重看本段：[/][cyan]/mcp-presets[/]"
    )


def build_mcp_preset_report(*, name: str, tool_list: list[str]) -> dict[str, Any]:
    meta = MCP_PRESET_DEFS[name]
    matched_tools: list[str] = []
    missing_tools: list[str] = []
    for kw in meta["recommended_tools"]:
        hit = next((tool for tool in tool_list if kw in tool.lower()), None)
        if hit is not None:
            matched_tools.append(hit)
        else:
            missing_tools.append(kw)
    suggested_command = f"cai-agent mcp-check --json --preset {name} --list-only"
    print_template_command = f"cai-agent mcp-check --preset {name} --print-template"
    doc_path = mcp_preset_doc_path(name)
    isolation_hint = mcp_preset_isolation_hint(name)
    quickstart_commands = [
        suggested_command,
        print_template_command,
        f"cai-agent mcp-check --json --preset {name}",
    ]
    ok = len(matched_tools) > 0
    next_step = None
    if not ok:
        next_step = {
            "kind": "preset_missing_tools",
            "message": f"未检测到 {name} 相关 MCP 工具；请先按文档和 onboarding 完成服务配置后重试。",
            "doc_path": doc_path,
            "onboarding_path": _ONBOARDING_PATH,
            "recommended_keywords": list(meta["recommended_tools"]),
            "suggested_command": suggested_command,
            "print_template_command": print_template_command,
            "isolation_hint": isolation_hint,
        }
    return {
        "name": name,
        "title": meta["title"],
        "summary": meta["summary"],
        "recommended_tools": list(meta["recommended_tools"]),
        "matched_tools": matched_tools,
        "matches": matched_tools,
        "missing_tools": missing_tools,
        "missing_keywords": missing_tools,
        "ok": ok,
        "doc_path": doc_path,
        "onboarding_path": _ONBOARDING_PATH,
        "isolation_hint": isolation_hint,
        "mcp_server_command": meta.get("mcp_server_command"),
        "suggested_command": suggested_command,
        "print_template_command": print_template_command,
        "quickstart_commands": quickstart_commands,
        "template": build_mcp_preset_template(name),
        "next_step": next_step,
    }
