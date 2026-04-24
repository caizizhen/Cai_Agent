from __future__ import annotations

from typing import Any


_DOC_PATH = "docs/WEBSEARCH_NOTEBOOK_MCP.zh-CN.md"
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
}


def allowed_mcp_preset_choices() -> tuple[str, ...]:
    return ("websearch", "notebook", "websearch/notebook")


def expand_mcp_preset_choice(preset: str | None) -> list[str]:
    key = str(preset or "").strip().lower()
    if not key:
        return []
    if key == "websearch/notebook":
        return ["websearch", "notebook"]
    if key in MCP_PRESET_DEFS:
        return [key]
    return []


def build_mcp_preset_template(name: str) -> str:
    meta = MCP_PRESET_DEFS[name]
    recommended = ", ".join(meta["recommended_tools"])
    return (
        "# cai-agent.toml (MCP preset template)\n"
        "[agent]\n"
        "mcp_enabled = true\n"
        "mcp_base_url = \"http://127.0.0.1:8787\"\n\n"
        "[permissions]\n"
        "mcp_list_tools = \"allow\"\n"
        "mcp_call_tool = \"ask\"\n\n"
        f"# preset = {name}\n"
        f"# title = {meta['title']}\n"
        f"# recommended_tools = {recommended}\n"
        f"# note = {meta['template_comment']}\n"
        f"# docs = {_DOC_PATH}\n"
        f"# onboarding = {_ONBOARDING_PATH}\n"
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
            "doc_path": _DOC_PATH,
            "onboarding_path": _ONBOARDING_PATH,
            "recommended_keywords": list(meta["recommended_tools"]),
            "suggested_command": suggested_command,
            "print_template_command": print_template_command,
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
        "doc_path": _DOC_PATH,
        "onboarding_path": _ONBOARDING_PATH,
        "suggested_command": suggested_command,
        "print_template_command": print_template_command,
        "quickstart_commands": quickstart_commands,
        "template": build_mcp_preset_template(name),
        "next_step": next_step,
    }
