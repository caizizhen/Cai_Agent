from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from cai_agent.config import Settings
from cai_agent.sandbox import SandboxError
from cai_agent.tools import dispatch, grant_dangerous_approval_once, tool_make_dir


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


class MakeDirToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name).resolve()

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_creates_nested_relative_to_workspace(self) -> None:
        s = _settings_from_toml(
            textwrap.dedent(
                f"""
                [llm]
                base_url = "http://localhost:1/v1"
                model = "m"
                api_key = "k"
                [agent]
                workspace = "{self.root.as_posix()}"
                """,
            ),
        )
        out = tool_make_dir(s.workspace, {"path": "a/b/c"})
        self.assertIn("a/b/c", out)
        self.assertTrue((self.root / "a" / "b" / "c").is_dir())

    def test_rejects_escape_workspace(self) -> None:
        s = _settings_from_toml(
            textwrap.dedent(
                f"""
                [llm]
                base_url = "http://localhost:1/v1"
                model = "m"
                api_key = "k"
                [agent]
                workspace = "{self.root.as_posix()}"
                """,
            ),
        )
        with self.assertRaises(SandboxError):
            tool_make_dir(s.workspace, {"path": "../outside"})

    def test_dispatch_respects_write_permission_deny(self) -> None:
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
                write_file = "deny"
                """,
            ),
        )
        with self.assertRaises(SandboxError) as ctx:
            dispatch(s, "make_dir", {"path": "x"})
        self.assertIn("make_dir", str(ctx.exception))

    def test_fails_if_path_is_file(self) -> None:
        (self.root / "f.txt").write_text("x", encoding="utf-8")
        s = _settings_from_toml(
            textwrap.dedent(
                f"""
                [llm]
                base_url = "http://localhost:1/v1"
                model = "m"
                api_key = "k"
                [agent]
                workspace = "{self.root.as_posix()}"
                """,
            ),
        )
        with self.assertRaises(SandboxError) as ctx:
            tool_make_dir(s.workspace, {"path": "f.txt"})
        self.assertIn("不是目录", str(ctx.exception))

    def test_unrestricted_write_sensitive_file_requires_confirmation(self) -> None:
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
        with self.assertRaises(SandboxError) as ctx:
            dispatch(s, "write_file", {"path": ".env", "content": "A=1"})
        self.assertIn("危险操作需要二次确认", str(ctx.exception))
        grant_dangerous_approval_once()
        out = dispatch(s, "write_file", {"path": ".env", "content": "A=1"})
        self.assertIn("已写入 .env", out)
