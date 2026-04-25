from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path

from cai_agent.config import Settings
from cai_agent.gateway_platforms import build_gateway_platforms_payload
from cai_agent.skills import build_skill_evolution_suggest
from cai_agent.user_model import build_memory_user_model_overview


class GatewayUserModelSkillsEvolutionTests(unittest.TestCase):
    def test_gateway_platforms_runtime_signals(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = build_gateway_platforms_payload(workspace=td)
        self.assertEqual(p.get("schema_version"), "gateway_platforms_v1")
        self.assertEqual(p.get("adapter_contract_schema_version"), "gateway_platform_adapter_contract_v1")
        self.assertIn("telegram_webhook_pid_exists", p)
        self.assertIn("telegram_bot_token_env_present", p)
        self.assertIsInstance(p.get("telegram_webhook_pid_exists"), bool)
        pl = p.get("platforms")
        self.assertIsInstance(pl, list)
        discord = next((x for x in pl if isinstance(x, dict) and x.get("id") == "discord"), None)
        self.assertIsNotNone(discord)
        ep = discord.get("env_present")
        self.assertIsInstance(ep, dict)
        self.assertIn("CAI_GATEWAY_DISCORD_BOT_TOKEN", ep)
        adapter = discord.get("adapter_contract")
        self.assertIsInstance(adapter, dict)
        self.assertEqual(adapter.get("schema_version"), "gateway_platform_adapter_contract_v1")
        self.assertTrue((adapter.get("map") or {}).get("supported"))

    def test_user_model_overview_schema(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "cai-agent.toml").write_text(
                '[llm]\nbase_url = "http://127.0.0.1:9/v1"\nmodel = "m"\napi_key = "k"\n',
                encoding="utf-8",
            )
            (root / ".cai").mkdir(parents=True)
            (root / ".cai" / "user-model.json").write_text(
                json.dumps({"display_name": "smoke-user", "traits": ["careful"]}, ensure_ascii=False),
                encoding="utf-8",
            )
            sess = root / ".cai-session-smoke.json"
            sess.write_text('{"version":2,"goal":"g"}\n', encoding="utf-8")
            now = time.time()
            os.utime(sess, (now, now))
            s0 = Settings.from_env(config_path=str(root / "cai-agent.toml"))
            s = replace(s0, workspace=str(root.resolve()))
            payload = build_memory_user_model_overview(s, days=14)
        self.assertEqual(payload.get("schema_version"), "memory_user_model_v1")
        self.assertIn(payload.get("honcho_parity"), ("stub", "behavior_extract"))
        self.assertGreaterEqual(int(payload.get("sessions_total") or 0), 1)
        ud = payload.get("user_declared")
        self.assertIsInstance(ud, dict)
        self.assertEqual(ud.get("display_name"), "smoke-user")

    def test_skill_evolution_suggest_write_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = build_skill_evolution_suggest(
                root=str(root),
                goal="fix login bug",
                write=True,
            )
            self.assertEqual(out.get("schema_version"), "skills_evolution_suggest_v1")
            self.assertTrue(out.get("written"))
            p = root / str(out.get("suggested_path")).replace("/", os.sep)
            self.assertTrue(p.is_file())
            raw = build_skill_evolution_suggest(
                root=str(root),
                goal="fix login bug",
                write=True,
            )
            self.assertFalse(raw.get("written"))
            self.assertTrue(raw.get("file_existed_before"))

    def test_cli_skills_hub_suggest_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            env = dict(os.environ)
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
            p = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "cai_agent",
                    "skills",
                    "hub",
                    "suggest",
                    "cli smoke goal",
                    "--json",
                ],
                cwd=td,
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(p.returncode, 0, p.stderr)
            o = json.loads((p.stdout or "").strip())
            self.assertEqual(o.get("schema_version"), "skills_evolution_suggest_v1")
            self.assertIn("_evolution_", str(o.get("suggested_path")))

    def test_cli_memory_user_model_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "cai-agent.toml").write_text(
                '[llm]\nbase_url = "http://127.0.0.1:9/v1"\nmodel = "m"\napi_key = "k"\n',
                encoding="utf-8",
            )
            env = dict(os.environ)
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
            p = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "cai_agent",
                    "memory",
                    "user-model",
                    "--json",
                    "--days",
                    "7",
                ],
                cwd=str(root),
                capture_output=True,
                text=True,
                env=env,
                check=False,
            )
            self.assertEqual(p.returncode, 0, p.stderr)
            o = json.loads((p.stdout or "").strip())
            self.assertEqual(o.get("schema_version"), "memory_user_model_v1")
            self.assertIn(o.get("honcho_parity"), ("stub", "behavior_extract"))


if __name__ == "__main__":
    unittest.main()
