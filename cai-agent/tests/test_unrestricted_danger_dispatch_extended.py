"""SAFETY-N02: unrestricted_mode + dangerous_confirmation for MCP / fetch_url."""

from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from cai_agent.config import Settings
from cai_agent.sandbox import SandboxError
from cai_agent.tools import (
    dispatch,
    grant_dangerous_approval_once,
    reset_dangerous_approval_budget_for_testing,
)


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
        reset_dangerous_approval_budget_for_testing()
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

    def test_fetch_url_https_private_dns_requires_confirmation(self) -> None:
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
                allow_private_resolved_ips = true
                [safety]
                unrestricted_mode = true
                dangerous_confirmation_required = true
                """,
            ),
        )
        with patch("cai_agent.tools.tool_fetch_url", return_value="fetch_priv_ok") as mock_tool:
            with self.assertRaises(SandboxError):
                dispatch(s, "fetch_url", {"url": "https://example.com/x"})
            mock_tool.assert_not_called()
            grant_dangerous_approval_once()
            out = dispatch(s, "fetch_url", {"url": "https://example.com/x"})
        self.assertEqual(out, "fetch_priv_ok")

    def test_fetch_url_file_scheme_rejected(self) -> None:
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
                dangerous_confirmation_required = false
                """,
            ),
        )
        with self.assertRaises(SandboxError) as ctx:
            dispatch(s, "fetch_url", {"url": "file:///etc/passwd"})
        self.assertIn("file://", str(ctx.exception))

    def test_write_file_critical_basename_requires_confirmation(self) -> None:
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
                write_file = "allow"
                [safety]
                unrestricted_mode = true
                dangerous_confirmation_required = true
                """,
            ),
        )
        with patch("cai_agent.tools.tool_write_file", return_value="w_ok") as mock_tool:
            with self.assertRaises(SandboxError):
                dispatch(s, "write_file", {"path": "pkg/pyproject.toml", "content": "x"})
            mock_tool.assert_not_called()
            grant_dangerous_approval_once()
            out = dispatch(s, "write_file", {"path": "pkg/pyproject.toml", "content": "x"})
        self.assertEqual(out, "w_ok")

    def test_write_file_critical_basename_noop_skips_confirmation(self) -> None:
        pkg = self.root / "pkg"
        pkg.mkdir(parents=True)
        disk_body = '[project]\nname = "demo"\n'
        (pkg / "pyproject.toml").write_text(disk_body, encoding="utf-8")
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
                write_file = "allow"
                [safety]
                unrestricted_mode = true
                dangerous_confirmation_required = true
                """,
            ),
        )
        inject = '[project]\r\nname = "demo"\r\n  \n'
        with patch("cai_agent.tools.tool_write_file", return_value="w_ok") as mock_tool:
            out = dispatch(
                s,
                "write_file",
                {"path": "pkg/pyproject.toml", "content": inject},
            )
        self.assertEqual(out, "w_ok")
        mock_tool.assert_called_once()

    def test_write_file_critical_pyproject_semantic_reorder_skips_confirmation(self) -> None:
        pkg = self.root / "pkg"
        pkg.mkdir(parents=True)
        disk = '[tool.foo]\nx = 1\n\n[project]\nname = "demo"\n'
        incoming = '[project]\nname = "demo"\n\n[tool.foo]\nx = 1\n'
        (pkg / "pyproject.toml").write_text(disk, encoding="utf-8")
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
                write_file = "allow"
                [safety]
                unrestricted_mode = true
                dangerous_confirmation_required = true
                """,
            ),
        )
        with patch("cai_agent.tools.tool_write_file", return_value="w_ok") as mock_tool:
            out = dispatch(
                s,
                "write_file",
                {"path": "pkg/pyproject.toml", "content": incoming},
            )
        self.assertEqual(out, "w_ok")
        mock_tool.assert_called_once()

    def test_write_file_critical_package_json_semantic_reorder_skips_confirmation(self) -> None:
        pkg = self.root / "pkg"
        pkg.mkdir(parents=True)
        disk = '{"name":"x","version":"1.0.0"}'
        incoming = '{\n  "version": "1.0.0",\n  "name": "x"\n}'
        (pkg / "package.json").write_text(disk, encoding="utf-8")
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
                write_file = "allow"
                [safety]
                unrestricted_mode = true
                dangerous_confirmation_required = true
                """,
            ),
        )
        with patch("cai_agent.tools.tool_write_file", return_value="w_ok") as mock_tool:
            out = dispatch(
                s,
                "write_file",
                {"path": "pkg/package.json", "content": incoming},
            )
        self.assertEqual(out, "w_ok")
        mock_tool.assert_called_once()

    def test_write_file_critical_pyproject_semantic_change_still_requires_confirmation(self) -> None:
        pkg = self.root / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "pyproject.toml").write_text('[project]\nname = "a"\n', encoding="utf-8")
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
                write_file = "allow"
                [safety]
                unrestricted_mode = true
                dangerous_confirmation_required = true
                """,
            ),
        )
        with patch("cai_agent.tools.tool_write_file", return_value="w_ok") as mock_tool:
            with self.assertRaises(SandboxError):
                dispatch(
                    s,
                    "write_file",
                    {"path": "pkg/pyproject.toml", "content": '[project]\nname = "b"\n'},
                )
            mock_tool.assert_not_called()

    def test_write_file_critical_semantic_reorder_respects_false_skip_setting(self) -> None:
        pkg = self.root / "pkg"
        pkg.mkdir(parents=True)
        disk = '[tool.foo]\nx = 1\n\n[project]\nname = "demo"\n'
        incoming = '[project]\nname = "demo"\n\n[tool.foo]\nx = 1\n'
        (pkg / "pyproject.toml").write_text(disk, encoding="utf-8")
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
                write_file = "allow"
                [safety]
                unrestricted_mode = true
                dangerous_confirmation_required = true
                dangerous_critical_write_skip_if_unchanged = false
                """,
            ),
        )
        with patch("cai_agent.tools.tool_write_file", return_value="w_ok") as mock_tool:
            with self.assertRaises(SandboxError):
                dispatch(
                    s,
                    "write_file",
                    {"path": "pkg/pyproject.toml", "content": incoming},
                )
            mock_tool.assert_not_called()

    def test_write_file_critical_basename_changed_still_requires_confirmation(self) -> None:
        pkg = self.root / "pkg"
        pkg.mkdir(parents=True)
        (pkg / "pyproject.toml").write_text("keep\n", encoding="utf-8")
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
                write_file = "allow"
                [safety]
                unrestricted_mode = true
                dangerous_confirmation_required = true
                """,
            ),
        )
        with patch("cai_agent.tools.tool_write_file", return_value="w_ok") as mock_tool:
            with self.assertRaises(SandboxError):
                dispatch(s, "write_file", {"path": "pkg/pyproject.toml", "content": "changed\n"})
            mock_tool.assert_not_called()
            grant_dangerous_approval_once()
            out = dispatch(s, "write_file", {"path": "pkg/pyproject.toml", "content": "changed\n"})
        self.assertEqual(out, "w_ok")

    def test_write_file_critical_basename_missing_file_still_requires_confirmation(self) -> None:
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
                write_file = "allow"
                [safety]
                unrestricted_mode = true
                dangerous_confirmation_required = true
                """,
            ),
        )
        with patch("cai_agent.tools.tool_write_file", return_value="w_ok") as mock_tool:
            with self.assertRaises(SandboxError):
                dispatch(
                    s,
                    "write_file",
                    {"path": "pkg/pyproject.toml", "content": "[project]\n"},
                )
            mock_tool.assert_not_called()

    def test_write_file_critical_basename_false_skip_still_requires_confirmation(self) -> None:
        pkg = self.root / "pkg"
        pkg.mkdir(parents=True)
        body = '[project]\nname = "demo"\n'
        (pkg / "pyproject.toml").write_text(body, encoding="utf-8")
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
                write_file = "allow"
                [safety]
                unrestricted_mode = true
                dangerous_confirmation_required = true
                dangerous_critical_write_skip_if_unchanged = false
                """,
            ),
        )
        with patch("cai_agent.tools.tool_write_file", return_value="w_ok") as mock_tool:
            with self.assertRaises(SandboxError):
                dispatch(s, "write_file", {"path": "pkg/pyproject.toml", "content": body})
            mock_tool.assert_not_called()

    def test_run_command_extra_basename_requires_confirmation(self) -> None:
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
                run_command = "allow"
                [safety]
                unrestricted_mode = true
                dangerous_confirmation_required = true
                run_command_extra_danger_basenames = ["git"]
                """,
            ),
        )
        with patch("cai_agent.tools.tool_run_command", return_value="git_ok") as mock_tool:
            with self.assertRaises(SandboxError):
                dispatch(s, "run_command", {"argv": ["git", "status"], "cwd": "."})
            mock_tool.assert_not_called()
            grant_dangerous_approval_once()
            out = dispatch(s, "run_command", {"argv": ["git", "status"], "cwd": "."})
        self.assertEqual(out, "git_ok")


if __name__ == "__main__":
    unittest.main()
