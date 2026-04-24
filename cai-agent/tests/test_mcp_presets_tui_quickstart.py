from __future__ import annotations

from cai_agent.mcp_presets import format_tui_mcp_web_notebook_quickstart


def test_format_tui_mcp_web_notebook_quickstart_contains_paths_and_commands() -> None:
    s = format_tui_mcp_web_notebook_quickstart()
    assert "WEBSEARCH_NOTEBOOK_MCP" in s
    assert "ONBOARDING" in s
    assert "mcp-check --preset websearch/notebook --list-only" in s
    assert "/mcp-presets" in s
