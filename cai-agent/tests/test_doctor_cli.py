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
            plug = pl.get("plugins")
            self.assertIsInstance(plug, dict)
            self.assertEqual(plug.get("schema_version"), "doctor_plugins_bundle_v1")
            cm = plug.get("compat_matrix") or {}
            self.assertEqual(cm.get("schema_version"), "plugin_compat_matrix_v1")
            self.assertEqual(cm.get("detail_doc_en"), "docs/PLUGIN_COMPAT_MATRIX.md")
            self.assertIn("model_routing_rules_count", pl)
            self.assertIsInstance(pl.get("model_routing_rules_count"), int)
            contract = pl.get("profile_contract")
            self.assertIsInstance(contract, dict)
            self.assertEqual(contract.get("schema_version"), "profile_contract_v1")
            self.assertEqual(contract.get("active_profile_id"), "p1")
            release = pl.get("release_runbook")
            self.assertIsInstance(release, dict)
            self.assertEqual(release.get("schema_version"), "release_runbook_v1")
            self.assertIsInstance(release.get("runbook_steps"), list)
            install = pl.get("installation_guidance")
            self.assertIsInstance(install, dict)
            self.assertEqual(install.get("schema_version"), "doctor_installation_guidance_v1")
            self.assertEqual(install.get("onboarding_doc"), "docs/ONBOARDING.zh-CN.md")
            self.assertEqual(
                (plug.get("surface") or {}).get("schema_version"),
                "plugins_surface_v1",
            )
            ch = pl.get("cai_dir_health") or {}
            self.assertIsInstance(ch, dict)
            dsum = ch.get("discord_map_summary")
            self.assertIsInstance(dsum, dict)
            self.assertIn("bindings_count", dsum)
            self.assertIn("allowlist_enabled", dsum)

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
