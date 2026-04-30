"""Tests for prepare_interactive_dangerous_dispatch (SAFETY-N03)."""

from __future__ import annotations

import os
import tempfile
import textwrap
import unittest
from pathlib import Path

from cai_agent.config import Settings
from cai_agent.tools import (
    peek_dangerous_approval_budget,
    prepare_interactive_dangerous_dispatch,
    reset_dangerous_approval_budget_for_testing,
)


def _settings_unrestricted(root: Path) -> Settings:
    content = textwrap.dedent(
        f"""
        [llm]
        base_url = "http://localhost:1/v1"
        model = "m"
        api_key = "k"
        [agent]
        workspace = "{root.as_posix()}"
        [permissions]
        run_command = "allow"
        [safety]
        unrestricted_mode = true
        dangerous_confirmation_required = true
        """,
    )
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
        os.unlink(path)


class PrepareInteractiveDangerousDispatchTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_dangerous_approval_budget_for_testing()
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name).resolve()

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_interactive_denies_skips_grant(self) -> None:
        s = _settings_unrestricted(self.root)
        self.assertEqual(peek_dangerous_approval_budget(), 0)
        ok, msg = prepare_interactive_dangerous_dispatch(
            s,
            "run_command",
            {"argv": ["python", "-c", "print('rm -rf /tmp/x')"], "cwd": "."},
            interactive_confirm=lambda _p: False,
        )
        self.assertFalse(ok)
        self.assertIsNotNone(msg)
        self.assertIn("取消", msg or "")
        self.assertEqual(peek_dangerous_approval_budget(), 0)

    def test_interactive_approves_grants_budget(self) -> None:
        s = _settings_unrestricted(self.root)
        self.assertEqual(peek_dangerous_approval_budget(), 0)
        ok, msg = prepare_interactive_dangerous_dispatch(
            s,
            "run_command",
            {"argv": ["python", "-c", "print('rm -rf /tmp/x')"], "cwd": "."},
            interactive_confirm=lambda _p: True,
        )
        self.assertTrue(ok)
        self.assertIsNone(msg)
        self.assertEqual(peek_dangerous_approval_budget(), 1)

    def test_non_interactive_still_defers_to_dispatch(self) -> None:
        s = _settings_unrestricted(self.root)
        ok, msg = prepare_interactive_dangerous_dispatch(
            s,
            "run_command",
            {"argv": ["python", "-c", "print('rm -rf /tmp/x')"], "cwd": "."},
            interactive_confirm=None,
        )
        self.assertTrue(ok)
        self.assertIsNone(msg)


if __name__ == "__main__":
    unittest.main()
