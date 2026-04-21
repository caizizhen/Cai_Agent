from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cai_agent.__main__ import _print_hook_status
from cai_agent.config import Settings


def _settings_for_tmp_root(root: Path) -> Settings:
    cfg = root / "cai-agent.toml"
    cfg.write_text(
        "[llm]\nbase_url = \"http://x/v1\"\nmodel = \"m\"\napi_key = \"k\"\n",
        encoding="utf-8",
    )
    s = Settings.from_env(config_path=str(cfg))
    return replace(s)


class HookStatusOutputTests(unittest.TestCase):
    def test_prints_summary_with_non_ok_statuses(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            settings = _settings_for_tmp_root(root)
            fake_results = [
                {"id": "a", "status": "ok"},
                {"id": "b", "status": "blocked", "reason": "dangerous_command_pattern"},
                {"id": "c", "status": "error", "reason": "timeout"},
            ]
            with (
                patch("cai_agent.__main__.run_project_hooks", return_value=fake_results),
                patch("cai_agent.__main__.enabled_hook_ids", return_value=["a", "b", "c"]),
            ):
                err = io.StringIO()
                with redirect_stderr(err):
                    _print_hook_status(
                        settings,
                        event="observe_start",
                        json_output=False,
                        hook_payload={"x": 1},
                    )
            out = err.getvalue()
            self.assertIn("[hook:observe_start]", out)
            self.assertIn("a", out)
            self.assertIn("b", out)
            self.assertIn("c", out)
        self.assertIn("results=a:ok; b:blocked(dangerous_command_pattern); c:error(timeout)", out)

    def test_json_output_suppresses_print(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            settings = _settings_for_tmp_root(root)
            with (
                patch("cai_agent.__main__.run_project_hooks", return_value=[{"id": "a", "status": "ok"}]),
                patch("cai_agent.__main__.enabled_hook_ids", return_value=["a"]),
            ):
                err = io.StringIO()
                with redirect_stderr(err):
                    _print_hook_status(
                        settings,
                        event="observe_start",
                        json_output=True,
                        hook_payload=None,
                    )
            self.assertEqual(err.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
