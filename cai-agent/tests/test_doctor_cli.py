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

_DOCTOR_MODEL_GATEWAY_SCHEMA = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "cai_agent"
    / "schemas"
    / "doctor_model_gateway_v1.schema.json"
)

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
    def test_doctor_model_gateway_v1_schema_file(self) -> None:
        sch = json.loads(_DOCTOR_MODEL_GATEWAY_SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(sch["properties"]["schema_version"]["const"], "doctor_model_gateway_v1")
        self.assertEqual(sch["properties"]["chat_smoke_default"]["const"], "explicit_only")
        self.assertIn("capabilities", sch.get("required", []))
        self.assertIn("recommended_flow", sch.get("required", []))

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
            mg = pl.get("model_gateway")
            self.assertIsInstance(mg, dict)
            self.assertEqual(mg.get("schema_version"), "doctor_model_gateway_v1")
            self.assertEqual(mg.get("onboarding_runbook"), "docs/MODEL_ONBOARDING_RUNBOOK.zh-CN.md")
            self.assertIn("AUTH_FAIL", mg.get("known_health_statuses") or [])
            caps = mg.get("capabilities") or {}
            self.assertEqual(caps.get("schema_version"), "model_capabilities_list_v1")
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
            install_diag = pl.get("install")
            self.assertIsInstance(install_diag, dict)
            self.assertEqual(install_diag.get("schema_version"), "doctor_install_v1")
            self.assertIsInstance(install_diag.get("checks"), list)
            sync_diag = pl.get("sync")
            self.assertIsInstance(sync_diag, dict)
            self.assertEqual(sync_diag.get("schema_version"), "doctor_sync_v1")
            self.assertIsInstance(sync_diag.get("items"), list)
            command_center = pl.get("command_center")
            self.assertIsInstance(command_center, dict)
            self.assertEqual(command_center.get("schema_version"), "command_discovery_v1")
            self.assertIsInstance(command_center.get("commands_count"), int)
            self.assertEqual(
                (plug.get("surface") or {}).get("schema_version"),
                "plugins_surface_v1",
            )
            hsd = plug.get("home_sync_drift") or {}
            self.assertIsInstance(hsd, dict)
            self.assertEqual(hsd.get("schema_version"), "plugins_home_sync_drift_v1")
            self.assertIn("targets_with_drift", hsd)
            ch = pl.get("cai_dir_health") or {}
            self.assertIsInstance(ch, dict)
            dsum = ch.get("discord_map_summary")
            self.assertIsInstance(dsum, dict)
            self.assertIn("bindings_count", dsum)
            self.assertIn("allowlist_enabled", dsum)
            fb = pl.get("feedback")
            self.assertIsInstance(fb, dict)
            self.assertEqual(fb.get("schema_version"), "feedback_stats_v1")
            rr_fb = (pl.get("release_runbook") or {}).get("feedback")
            self.assertIsInstance(rr_fb, dict)
            self.assertEqual(fb, rr_fb)
            mp = pl.get("memory_policy")
            self.assertIsInstance(mp, dict)
            self.assertIn("max_entries_per_day", mp)
            self.assertIn("default_ttl_days", mp)
            self.assertIn("recall_negative_audit", mp)
            mprov = pl.get("memory_provider")
            self.assertIsInstance(mprov, dict)
            self.assertEqual(mprov.get("schema_version"), "memory_active_provider_v1")
            self.assertEqual(mprov.get("active_provider"), "local_entries_jsonl")
            vc = pl.get("voice")
            self.assertIsInstance(vc, dict)
            self.assertEqual(vc.get("schema_version"), "voice_provider_contract_v1")
            self.assertIn("stt", vc)
            self.assertIn("tts", vc)
            self.assertIn("health", vc)
            tp = pl.get("tool_provider")
            self.assertIsInstance(tp, dict)
            self.assertEqual(tp.get("schema_version"), "tool_provider_contract_v1")
            self.assertIn("providers", tp)
            ecc_d = pl.get("ecc_home_sync_drift")
            self.assertIsInstance(ecc_d, dict)
            self.assertEqual(ecc_d.get("schema_version"), "ecc_home_sync_drift_v1")
            epr = pl.get("ecc_asset_pack_repair")
            self.assertIsInstance(epr, dict)
            self.assertEqual(epr.get("schema_version"), "ecc_asset_pack_repair_report_v1")
            ehi = pl.get("ecc_harness_target_inventory")
            self.assertIsInstance(ehi, dict)
            self.assertEqual(ehi.get("schema_version"), "ecc_harness_target_inventory_v1")
            esd = pl.get("ecc_structured_home_diff")
            self.assertIsInstance(esd, dict)
            self.assertEqual(esd.get("schema_version"), "ecc_structured_home_diff_bundle_v1")
            self.assertIn("targets_with_pending_actions", esd)
            uh = pl.get("upgrade_hints")
            self.assertIsInstance(uh, dict)
            self.assertEqual(uh.get("schema_version"), "doctor_upgrade_hints_v1")

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
