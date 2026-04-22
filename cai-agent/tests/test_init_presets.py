"""Smoke tests for `cai-agent init --preset`."""
from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cai_agent.__main__ import main
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
                    "zhipu-glm51",
                    "compat-gateway",
                },
            )
            raw = tomllib.loads(cfg.read_text(encoding="utf-8"))
            profs = raw["models"]["profile"]
            self.assertEqual(len(profs), 6)

    def test_init_json_success_default_preset(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["init", "--json"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "init_cli_v1")
            self.assertIs(payload.get("ok"), True)
            self.assertEqual(payload.get("preset"), "default")
            self.assertIs(payload.get("global"), False)
            self.assertTrue((root / "cai-agent.toml").is_file())

    def test_init_json_config_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "cai-agent.toml").write_text("[llm]\nmodel = \"x\"\n", encoding="utf-8")
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["init", "--json"])
            self.assertEqual(rc, 2)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "init_cli_v1")
            self.assertIs(payload.get("ok"), False)
            self.assertEqual(payload.get("error"), "config_exists")


if __name__ == "__main__":
    unittest.main()
