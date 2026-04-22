from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from cai_agent.__main__ import main
from cai_agent.config import Settings

_MIN_TOML = """[llm]
provider = "openai_compatible"
base_url = "http://127.0.0.1:9/v1"
model = "test-model"
api_key = ""

[agent]
mock = {mock}

[models]
active = "p1"

[[models.profile]]
id = "p1"
provider = "openai_compatible"
base_url = "http://127.0.0.1:9/v1"
model = "test-model"
api_key = ""
"""


class DoctorCliTests(unittest.TestCase):
    def test_doctor_json_schema(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "cai-agent.toml").write_text(
                _MIN_TOML.format(mock="true"),
                encoding="utf-8",
            )
            cfg = str(root / "cai-agent.toml")
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["doctor", "--config", cfg, "--json"])
            self.assertEqual(rc, 0)
            pl = json.loads(buf.getvalue().strip())
            self.assertEqual(pl.get("schema_version"), "doctor_v1")
            self.assertIsInstance(pl.get("cai_agent_version"), str)
            self.assertIn("workspace", pl)
            self.assertTrue(pl.get("mock"))

    def test_doctor_fail_on_missing_api_key_skipped_when_mock(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "cai-agent.toml").write_text(
                _MIN_TOML.format(mock="true"),
                encoding="utf-8",
            )
            cfg = str(root / "cai-agent.toml")
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["doctor", "--config", cfg, "--json", "--fail-on-missing-api-key"])
            self.assertEqual(rc, 0)

    def test_doctor_fail_on_missing_api_key_when_not_mock(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "cai-agent.toml").write_text(
                _MIN_TOML.format(mock="false"),
                encoding="utf-8",
            )
            cfg = str(root / "cai-agent.toml")
            base = Settings.from_env(config_path=cfg)
            no_key = replace(base, mock=False, api_key="")
            buf = io.StringIO()
            with patch("cai_agent.__main__.Settings.from_env", return_value=no_key):
                with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                    with redirect_stdout(buf):
                        rc = main(["doctor", "--config", cfg, "--json", "--fail-on-missing-api-key"])
            self.assertEqual(rc, 2)
            pl = json.loads(buf.getvalue().strip())
            self.assertFalse(pl.get("mock"))
            self.assertFalse(pl.get("api_key_present"))


if __name__ == "__main__":
    unittest.main()
