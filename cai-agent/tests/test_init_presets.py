"""Smoke tests for `cai-agent init --preset`."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from cai_agent.config import Settings


class InitPresetTests(unittest.TestCase):
    def test_init_starter_parses_as_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            r = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "cai_agent",
                    "init",
                    "--preset",
                    "starter",
                ],
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(r.returncode, 0, msg=r.stderr + r.stdout)
            cfg = tmp_path / "cai-agent.toml"
            self.assertTrue(cfg.is_file())
            s = Settings.from_env(config_path=str(cfg))
            self.assertTrue(s.profiles_explicit)
            ids = {p.id for p in s.profiles}
            self.assertEqual(
                ids,
                {
                    "local-lmstudio",
                    "local-ollama",
                    "local-vllm",
                    "openrouter",
                    "compat-gateway",
                },
            )
            raw = tomllib.loads(cfg.read_text(encoding="utf-8"))
            profs = raw["models"]["profile"]
            self.assertEqual(len(profs), 5)


if __name__ == "__main__":
    unittest.main()
