from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from cai_agent.config import Settings
from cai_agent.sandbox import SandboxError
from cai_agent.tools import tool_run_command


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


class RunCommandSecurityPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name).resolve()

    def tearDown(self) -> None:
        self._td.cleanup()

    def test_blocks_high_risk_pattern_by_default(self) -> None:
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
                """,
            ),
        )
        with self.assertRaises(SandboxError) as ctx:
            tool_run_command(
                s,
                {"argv": ["python", "-c", "rm -rf /tmp/x"], "cwd": "."},
            )
        # shell 元字符先于高风险审批策略校验。
        self.assertIn("高危模式", str(ctx.exception))

    def test_allow_all_mode_disables_pattern_blocking(self) -> None:
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
                run_command_approval_mode = "allow_all"
                """,
            ),
        )
        # 使用基名 `python`（符合 run_command 白名单），避免 Windows 上 `pip` 被策略拦截。
        out = tool_run_command(
            s,
            {"argv": ["python", "-c", "print('ok')"], "cwd": "."},
        )
        self.assertIn("exit=0", out)
        self.assertIn("ok", out)

