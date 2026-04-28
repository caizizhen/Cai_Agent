from __future__ import annotations

import io
import json
import shutil
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cai_agent.__main__ import main
from cai_agent.mcp_presets import build_mcp_preset_report, build_mcp_preset_template


class BrowserMcpCliTests(unittest.TestCase):
    def _workspace(self) -> Path:
        root = Path.cwd() / ".tmp" / f"browser-mcp-{uuid.uuid4().hex}"
        root.mkdir(parents=True, exist_ok=False)
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        return root

    def _config(self, root: Path) -> Path:
        cfg = root / "cai-agent.toml"
        cfg.write_text(
            '[llm]\nprovider = "openai_compatible"\nbase_url = "http://127.0.0.1:9/v1"\n'
            'model = "m"\napi_key = "k"\n\n[agent]\nmock = true\n'
            'mcp_enabled = true\n\n[mcp]\nbase_url = "http://127.0.0.1:8787"\n',
            encoding="utf-8",
        )
        return cfg.resolve()

    def test_browser_preset_template_mentions_playwright_isolated(self) -> None:
        tmpl = build_mcp_preset_template("browser")

        self.assertIn("preset = browser", tmpl)
        self.assertIn("docs/BROWSER_MCP.zh-CN.md", tmpl)
        self.assertIn("@playwright/mcp@latest", tmpl)
        self.assertIn("--isolated", tmpl)
        self.assertIn('mcp_call_tool = "ask"', tmpl)

    def test_browser_preset_report_matches_playwright_tools(self) -> None:
        report = build_mcp_preset_report(
            name="browser",
            tool_list=["browser_navigate", "browser_click", "browser_take_screenshot"],
        )

        self.assertIs(report.get("ok"), True)
        self.assertEqual(report.get("doc_path"), "docs/BROWSER_MCP.zh-CN.md")
        self.assertIn("browser_navigate", report.get("matched_tools") or [])
        self.assertIn("isolated", str(report.get("isolation_hint") or "").lower())

    def test_tools_bridge_browser_json_reports_docs_and_isolation(self) -> None:
        root = self._workspace()
        cfg = self._config(root)
        buf = io.StringIO()
        tools = "browser_navigate\tNavigate\nbrowser_click\tClick\nbrowser_snapshot\tSnapshot\n"
        with patch("cai_agent.tool_provider.dispatch", return_value=tools):
            with redirect_stdout(buf):
                rc = main(["tools", "--config", str(cfg), "bridge", "--preset", "browser", "--json"])

        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue().strip())
        self.assertEqual(payload.get("schema_version"), "tool_mcp_bridge_v1")
        self.assertEqual(payload.get("preset"), "browser")
        self.assertEqual(payload.get("selected_presets"), ["browser"])
        self.assertIn("docs/BROWSER_MCP.zh-CN.md", payload.get("doc_paths") or [])
        self.assertTrue(payload.get("isolation_hints"))
        hint = payload.get("hint") or {}
        self.assertEqual(hint.get("doc_path"), "docs/BROWSER_MCP.zh-CN.md")
        self.assertIn("browser_navigate", payload.get("matched_tools") or [])

    def test_mcp_check_browser_json_print_template(self) -> None:
        root = self._workspace()
        cfg = self._config(root)
        buf = io.StringIO()
        tools = "- browser_navigate\n- browser_click\n- browser_screenshot\n"
        with patch("cai_agent.__main__.dispatch", return_value=tools):
            with redirect_stdout(buf):
                rc = main(
                    [
                        "mcp-check",
                        "--config",
                        str(cfg),
                        "--json",
                        "--preset",
                        "browser",
                        "--list-only",
                        "--print-template",
                    ],
                )

        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue().strip())
        preset = payload.get("preset") or {}
        self.assertEqual(preset.get("name"), "browser")
        self.assertEqual(preset.get("doc_path"), "docs/BROWSER_MCP.zh-CN.md")
        self.assertIn("docs/BROWSER_MCP.zh-CN.md", preset.get("doc_paths") or [])
        self.assertTrue(preset.get("isolation_hints"))
        self.assertIn("@playwright/mcp@latest", str(payload.get("template") or ""))


if __name__ == "__main__":
    unittest.main()
