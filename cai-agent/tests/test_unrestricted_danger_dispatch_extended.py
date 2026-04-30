"""SAFETY-N02: unrestricted_mode + dangerous_confirmation for MCP / fetch_url."""

from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from cai_agent.config import Settings
from cai_agent.sandbox import SandboxError
from cai_agent.tools import dispatch, grant_dangerous_approval_once


def _settings_from_toml(content: str) -> Settings:
    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".toml",
        delete=False,
        encoding="utf-8",
    ) as f:
        f.write(content)
        path = f.name
    try:
        return Settings.from_env(config_path=path)
    finally:
        import os

        os.unlink(path)


class UnrestrictedDangerDispatchExtendedTests(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name).resolve()

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_mcp_call_requires_confirmation(self) -> None:
        s = _settings_from_toml(
            textwrap.dedent(
                f"""
                [llm]
                base_url = "http://localhost:1/v1"
                model = "m"
                api_key = "k"
                [agent]
                workspace = "{self.root.as_posix()}"
                mcp_enabled = true
                [mcp]
                base_url = "http://127.0.0.1:9"
                [permissions]
                fetch_url = "allow"
                [fetch_url]
                enabled = true
                unrestricted = true
                [safety]
                unrestricted_mode = true
                dangerous_confirmation_required = true
                """,
            ),
        )
        with patch("cai_agent.tools.tool_mcp_call_tool", return_value="mcp_ok") as mock_tool:
            with self.assertRaises(SandboxError) as ctx:
                dispatch(s, "mcp_call_tool", {"name": "ping", "args": {}})
            self.assertIn("危险操作需要二次确认", str(ctx.exception))
            mock_tool.assert_not_called()
            grant_dangerous_approval_once()
            out = dispatch(s, "mcp_call_tool", {"name": "ping", "args": {}})
        self.assertEqual(out, "mcp_ok")
        mock_tool.assert_called_once()

    def test_fetch_url_http_requires_confirmation(self) -> None:
        s = _settings_from_toml(
            textwrap.dedent(
                f"""
                [llm]
                base_url = "http://localhost:1/v1"
                model = "m"
                api_key = "k"
                [agent]
                workspace = "{self.root.as_posix()}"
                [permissions]
                fetch_url = "allow"
                [fetch_url]
                enabled = true
                unrestricted = true
                [safety]
                unrestricted_mode = true
                dangerous_confirmation_required = true
                """,
            ),
        )
        with patch("cai_agent.tools.tool_fetch_url", return_value="fetch_ok") as mock_tool:
            with self.assertRaises(SandboxError):
                dispatch(s, "fetch_url", {"url": "http://example.com/x"})
            mock_tool.assert_not_called()
            grant_dangerous_approval_once()
            out = dispatch(s, "fetch_url", {"url": "http://example.com/x"})
        self.assertEqual(out, "fetch_ok")

    def test_fetch_url_https_skips_extra_confirmation(self) -> None:
        s = _settings_from_toml(
            textwrap.dedent(
                f"""
                [llm]
                base_url = "http://localhost:1/v1"
                model = "m"
                api_key = "k"
                [agent]
                workspace = "{self.root.as_posix()}"
                [permissions]
                fetch_url = "allow"
                [fetch_url]
                enabled = true
                unrestricted = true
                [safety]
                unrestricted_mode = true
                dangerous_confirmation_required = true
                """,
            ),
        )
        with patch("cai_agent.tools.tool_fetch_url", return_value="fetch_https_ok") as mock_tool:
            out = dispatch(s, "fetch_url", {"url": "https://example.com/x"})
        self.assertEqual(out, "fetch_https_ok")
        mock_tool.assert_called_once()


if __name__ == "__main__":
    unittest.main()
