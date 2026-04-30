"""SAFETY: unrestricted_mode allows absolute paths outside workspace + dangerous confirmation."""

from __future__ import annotations

import os
import shutil
import tempfile
import textwrap
import unittest
from pathlib import Path

from cai_agent.config import Settings
from cai_agent.sandbox import SandboxError, resolve_tool_path
from cai_agent.tools import (
    dispatch,
    grant_dangerous_approval_once,
    reset_dangerous_approval_budget_for_testing,
)


def _settings_from_toml(content: str) -> Settings:
    import tempfile as tf

    with tf.NamedTemporaryFile("w", suffix=".toml", delete=False, encoding="utf-8") as f:
        f.write(content)
        path = f.name
    try:
        return Settings.from_env(config_path=path)
    finally:
        os.unlink(path)


class ResolveToolPathTests(unittest.TestCase):
    def test_absolute_rejected_when_not_unrestricted(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td).resolve()
            outside = (ws.parent / f"x_abs_{os.getpid()}").resolve()
            outside.mkdir(exist_ok=True)
            try:
                target = outside / "f.txt"
                target.write_text("z", encoding="utf-8")
                with self.assertRaises(SandboxError) as ctx:
                    resolve_tool_path(str(ws), str(target), unrestricted=False)
                self.assertIn("绝对路径", str(ctx.exception))
            finally:
                shutil.rmtree(outside, ignore_errors=True)

    def test_absolute_allowed_when_unrestricted(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td).resolve()
            outside = (ws.parent / f"y_abs_{os.getpid()}").resolve()
            outside.mkdir(exist_ok=True)
            try:
                target = outside / "g.txt"
                target.write_text("z", encoding="utf-8")
                p = resolve_tool_path(str(ws), str(target), unrestricted=True)
                self.assertEqual(p.resolve(), target.resolve())
            finally:
                shutil.rmtree(outside, ignore_errors=True)


class UnrestrictedFilesystemDispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_dangerous_approval_budget_for_testing()
        self._td = tempfile.TemporaryDirectory()
        self.ws = Path(self._td.name).resolve()
        self.out_dir = (self.ws.parent / f"cai_fs_out_{os.getpid()}").resolve()
        self.out_dir.mkdir(exist_ok=True)
        self.out_file = self.out_dir / "outside-read.txt"
        self.out_file.write_text("outside-data\n", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.out_dir, ignore_errors=True)
        self._td.cleanup()

    def _restricted_settings(self) -> Settings:
        return _settings_from_toml(
            textwrap.dedent(
                f"""
                [llm]
                base_url = "http://localhost/v1"
                model = "m"
                api_key = "k"
                [agent]
                workspace = "{self.ws.as_posix()}"
                [permissions]
                read_file = "allow"
                [safety]
                unrestricted_mode = false
                dangerous_confirmation_required = true
                """,
            ),
        )

    def _unrestricted_settings(self) -> Settings:
        return _settings_from_toml(
            textwrap.dedent(
                f"""
                [llm]
                base_url = "http://localhost/v1"
                model = "m"
                api_key = "k"
                [agent]
                workspace = "{self.ws.as_posix()}"
                [permissions]
                read_file = "allow"
                [safety]
                unrestricted_mode = true
                dangerous_confirmation_required = true
                """,
            ),
        )

    def test_absolute_outside_rejected_when_restricted(self) -> None:
        s = self._restricted_settings()
        with self.assertRaises(SandboxError) as ctx:
            dispatch(s, "read_file", {"path": str(self.out_file)})
        self.assertIn("绝对路径", str(ctx.exception))

    def test_absolute_outside_requires_confirmation_when_unrestricted(self) -> None:
        s = self._unrestricted_settings()
        with self.assertRaises(SandboxError) as ctx:
            dispatch(s, "read_file", {"path": str(self.out_file)})
        self.assertIn("二次确认", str(ctx.exception))

    def test_absolute_outside_ok_after_grant(self) -> None:
        s = self._unrestricted_settings()
        grant_dangerous_approval_once()
        out = dispatch(s, "read_file", {"path": str(self.out_file)})
        self.assertIn("outside-data", out)


if __name__ == "__main__":
    unittest.main()
