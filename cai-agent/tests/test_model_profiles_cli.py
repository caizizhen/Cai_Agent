"""M3 契约：`cai-agent models add/use/list/edit/rm/ping` CLI 闭环。

使用 ``httpx.MockTransport`` 跑 ping；其它子命令不触网。
"""
from __future__ import annotations

import io
import json
import os
import tempfile
import tomllib
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import httpx

from cai_agent import models as cai_models
from cai_agent.__main__ import main

_ONBOARDING_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "cai_agent"
    / "schemas"
    / "model_onboarding_flow_v1.schema.json"
)


class ModelsCliEndToEnd(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg = Path(self.tmp.name) / "cai-agent.toml"
        self.cfg.write_text(
            '[llm]\nbase_url = "http://localhost:1234/v1"\nmodel = "legacy"\napi_key = "lm-studio"\n',
            encoding="utf-8",
        )
        self._prev_env: dict[str, str | None] = {}
        for var in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LM_API_KEY", "CAI_ACTIVE_MODEL"):
            self._prev_env[var] = os.environ.get(var)
            os.environ.pop(var, None)

    def tearDown(self) -> None:
        for k, v in self._prev_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _run(self, argv: list[str]) -> tuple[int, str]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(argv + ["--config", str(self.cfg)] if "--config" not in argv else argv)
        return rc, buf.getvalue()

    def _cli(self, *args: str) -> tuple[int, str]:
        """封装：自动注入 --config 到对应子命令上。"""
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(list(args))
        return rc, buf.getvalue()

    def test_add_then_list_then_use_then_rm(self) -> None:
        # add
        rc, _ = self._cli(
            "models", "--config", str(self.cfg), "add",
            "--id", "p1", "--preset", "openai",
            "--model", "gpt-4o-mini", "--set-active",
        )
        self.assertEqual(rc, 0, "add p1 应成功")

        # add second
        rc, _ = self._cli(
            "models", "--config", str(self.cfg), "add",
            "--id", "p2", "--preset", "lmstudio",
            "--model", "qwen2.5-coder:7b",
        )
        self.assertEqual(rc, 0)

        # list --json
        rc, out = self._cli("models", "--config", str(self.cfg), "list", "--json")
        self.assertEqual(rc, 0)
        payload = json.loads(out.strip())
        self.assertEqual(payload.get("schema_version"), "models_list_v1")
        self.assertEqual(payload["active"], "p1")
        contract = payload.get("profile_contract") or {}
        self.assertEqual(contract.get("schema_version"), "profile_contract_v1")
        self.assertEqual(contract.get("migration_state"), "ready")
        self.assertEqual(contract.get("active_profile_id"), "p1")
        ids = [p["id"] for p in payload["profiles"]]
        self.assertEqual(sorted(ids), ["p1", "p2"])

        # use p2
        rc, out_use = self._cli("models", "--config", str(self.cfg), "use", "p2")
        self.assertEqual(rc, 0)
        self.assertIn("profile_switched: p2", out_use)

        # list again: active should be p2
        rc, out = self._cli("models", "--config", str(self.cfg), "list", "--json")
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out.strip())["active"], "p2")

        # rm p2; active should fall back to p1
        rc, _ = self._cli("models", "--config", str(self.cfg), "rm", "p2")
        self.assertEqual(rc, 0)
        rc, out = self._cli("models", "--config", str(self.cfg), "list", "--json")
        payload = json.loads(out.strip())
        self.assertEqual(payload["active"], "p1")
        self.assertEqual(len(payload["profiles"]), 1)

    def test_list_json_includes_legacy_profile_contract_for_llm_only_config(self) -> None:
        rc, out = self._cli("models", "--config", str(self.cfg), "list", "--json")
        self.assertEqual(rc, 0)
        payload = json.loads(out.strip())
        contract = payload.get("profile_contract") or {}
        self.assertEqual(contract.get("schema_version"), "profile_contract_v1")
        self.assertEqual(contract.get("source_kind"), "legacy_llm_default_profile")
        self.assertEqual(contract.get("migration_state"), "needs_explicit_profiles")
        self.assertEqual(contract.get("active_profile_id"), "default")

    def test_add_duplicate_id_fails_cleanly(self) -> None:
        rc, _ = self._cli(
            "models", "--config", str(self.cfg), "add",
            "--id", "p1", "--preset", "lmstudio", "--model", "m1",
        )
        self.assertEqual(rc, 0)
        rc2, _ = self._cli(
            "models", "--config", str(self.cfg), "add",
            "--id", "p1", "--preset", "lmstudio", "--model", "m1",
        )
        self.assertEqual(rc2, 2)

    def test_add_api_key_and_env_conflict_rejected(self) -> None:
        rc, _ = self._cli(
            "models", "--config", str(self.cfg), "add",
            "--id", "bad", "--provider", "openai_compatible",
            "--base-url", "http://x/v1", "--model", "m",
            "--api-key", "literal", "--api-key-env", "SOME_VAR",
        )
        self.assertEqual(rc, 2)

    def test_atomic_write_creates_backup(self) -> None:
        rc, _ = self._cli(
            "models", "--config", str(self.cfg), "add",
            "--id", "p1", "--preset", "lmstudio", "--model", "m", "--set-active",
        )
        self.assertEqual(rc, 0)
        rc, _ = self._cli(
            "models", "--config", str(self.cfg), "add",
            "--id", "p2", "--preset", "lmstudio", "--model", "m2",
        )
        self.assertEqual(rc, 0)
        bak = self.cfg.with_name(self.cfg.name + ".bak")
        self.assertTrue(bak.is_file(), "第二次写入应产生 .bak 备份")

    def test_toml_roundtrip_keeps_other_sections(self) -> None:
        self.cfg.write_text(
            '[llm]\nbase_url = "http://old/v1"\nmodel = "legacy"\napi_key = "k"\n\n'
            '[agent]\nmax_iterations = 7\n',
            encoding="utf-8",
        )
        rc, _ = self._cli(
            "models", "--config", str(self.cfg), "add",
            "--id", "p1", "--preset", "lmstudio", "--model", "m", "--set-active",
        )
        self.assertEqual(rc, 0)
        text = self.cfg.read_text(encoding="utf-8")
        self.assertIn("[agent]", text)
        self.assertIn("max_iterations = 7", text)
        data = tomllib.loads(text)
        self.assertEqual(data["models"]["active"], "p1")
        self.assertEqual(data["models"]["profile"][0]["id"], "p1")

    def test_route_requires_explicit_profiles(self) -> None:
        rc, _ = self._cli("models", "--config", str(self.cfg), "route", "--unset-subagent")
        self.assertEqual(rc, 2)

    def test_route_sets_and_unsets_subagent_planner(self) -> None:
        rc, _ = self._cli(
            "models", "--config", str(self.cfg), "add",
            "--id", "pa", "--preset", "lmstudio", "--model", "m1", "--set-active",
        )
        self.assertEqual(rc, 0)
        rc, _ = self._cli(
            "models", "--config", str(self.cfg), "add",
            "--id", "pb", "--preset", "lmstudio", "--model", "m2",
        )
        self.assertEqual(rc, 0)
        rc, _ = self._cli(
            "models",
            "--config",
            str(self.cfg),
            "route",
            "--subagent",
            "pb",
            "--planner",
            "pa",
        )
        self.assertEqual(rc, 0)
        data = tomllib.loads(self.cfg.read_text(encoding="utf-8"))
        self.assertEqual(data["models"]["subagent"], "pb")
        self.assertEqual(data["models"]["planner"], "pa")

        rc, _ = self._cli(
            "models",
            "--config",
            str(self.cfg),
            "route",
            "--unset-subagent",
            "--unset-planner",
        )
        self.assertEqual(rc, 0)
        data = tomllib.loads(self.cfg.read_text(encoding="utf-8"))
        self.assertNotIn("subagent", data["models"])
        self.assertNotIn("planner", data["models"])

    def test_edit_updates_model_and_notes_and_list_reflects_changes(self) -> None:
        rc, _ = self._cli(
            "models", "--config", str(self.cfg), "add",
            "--id", "p1", "--preset", "lmstudio", "--model", "m1", "--set-active",
        )
        self.assertEqual(rc, 0)
        rc, _ = self._cli(
            "models",
            "--config",
            str(self.cfg),
            "edit",
            "p1",
            "--model",
            "m2",
            "--notes",
            "primary local profile",
        )
        self.assertEqual(rc, 0)

        rc, out = self._cli("models", "--config", str(self.cfg), "list", "--json")
        self.assertEqual(rc, 0)
        payload = json.loads(out.strip())
        prof = next(p for p in payload["profiles"] if p["id"] == "p1")
        self.assertEqual(prof["model"], "m2")
        self.assertEqual(prof["notes"], "primary local profile")

    def test_route_rejects_unknown_profile_id(self) -> None:
        rc, _ = self._cli(
            "models", "--config", str(self.cfg), "add",
            "--id", "only", "--preset", "lmstudio", "--model", "m", "--set-active",
        )
        self.assertEqual(rc, 0)
        rc2, _ = self._cli(
            "models", "--config", str(self.cfg), "route", "--subagent", "nope",
        )
        self.assertEqual(rc2, 2)

    def test_rm_clears_subagent_and_planner_when_target_is_removed(self) -> None:
        rc, _ = self._cli(
            "models", "--config", str(self.cfg), "add",
            "--id", "pa", "--preset", "lmstudio", "--model", "m1", "--set-active",
        )
        self.assertEqual(rc, 0)
        rc, _ = self._cli(
            "models", "--config", str(self.cfg), "add",
            "--id", "pb", "--preset", "lmstudio", "--model", "m2",
        )
        self.assertEqual(rc, 0)
        rc, _ = self._cli(
            "models",
            "--config",
            str(self.cfg),
            "route",
            "--subagent",
            "pb",
            "--planner",
            "pb",
        )
        self.assertEqual(rc, 0)

        rc, _ = self._cli("models", "--config", str(self.cfg), "rm", "pb")
        self.assertEqual(rc, 0)

        rc, out = self._cli("models", "--config", str(self.cfg), "list", "--json")
        self.assertEqual(rc, 0)
        payload = json.loads(out.strip())
        self.assertEqual(payload["active"], "pa")
        self.assertIsNone(payload.get("subagent"))
        self.assertIsNone(payload.get("planner"))

    def test_route_subagent_unset_mutually_exclusive(self) -> None:
        rc, _ = self._cli(
            "models", "--config", str(self.cfg), "add",
            "--id", "pa", "--preset", "lmstudio", "--model", "m1", "--set-active",
        )
        self.assertEqual(rc, 0)
        rc, _ = self._cli(
            "models", "--config", str(self.cfg), "add",
            "--id", "pb", "--preset", "lmstudio", "--model", "m2",
        )
        self.assertEqual(rc, 0)
        rc2, _ = self._cli(
            "models",
            "--config",
            str(self.cfg),
            "route",
            "--subagent",
            "pb",
            "--unset-subagent",
        )
        self.assertEqual(rc2, 2)

    def test_models_ping_fail_on_any_error_uses_exit_2(self) -> None:
        rc, _ = self._cli(
            "models", "--config", str(self.cfg), "add",
            "--id", "px", "--preset", "lmstudio", "--model", "m", "--set-active",
        )
        self.assertEqual(rc, 0)
        with patch(
            "cai_agent.__main__.ping_profile",
            return_value={"profile_id": "px", "status": "AUTH_FAIL", "message": "nope"},
        ):
            rc2, out = self._cli(
                "models",
                "--config",
                str(self.cfg),
                "ping",
                "px",
                "--json",
                "--fail-on-any-error",
            )
        self.assertEqual(rc2, 2)
        payload = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(payload.get("schema_version"), "models_ping_v1")
        self.assertEqual(len(payload.get("results") or []), 1)

    def test_models_ping_default_exit_2_when_not_all_ok(self) -> None:
        rc, _ = self._cli(
            "models", "--config", str(self.cfg), "add",
            "--id", "py", "--preset", "lmstudio", "--model", "m", "--set-active",
        )
        self.assertEqual(rc, 0)
        with patch(
            "cai_agent.__main__.ping_profile",
            return_value={"profile_id": "py", "status": "NET_FAIL", "message": "down"},
        ):
            rc2, out = self._cli(
                "models",
                "--config",
                str(self.cfg),
                "ping",
                "py",
                "--json",
            )
        self.assertEqual(rc2, 2)
        payload = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(payload.get("schema_version"), "models_ping_v1")

    def test_models_fetch_json_has_schema_version(self) -> None:
        rc, _ = self._cli(
            "models", "--config", str(self.cfg), "add",
            "--id", "fx", "--preset", "lmstudio", "--model", "m", "--set-active",
        )
        self.assertEqual(rc, 0)
        with patch(
            "cai_agent.__main__.fetch_models",
            return_value=["alpha", "beta"],
        ):
            rc2, out = self._cli(
                "models", "--config", str(self.cfg), "fetch", "--json",
            )
        self.assertEqual(rc2, 0)
        payload = json.loads(out.strip())
        self.assertEqual(payload.get("schema_version"), "models_fetch_v1")
        self.assertEqual(payload.get("models"), ["alpha", "beta"])

    def test_models_capabilities_json_has_non_secret_metadata(self) -> None:
        rc, _ = self._cli(
            "models", "--config", str(self.cfg), "add",
            "--id", "cap", "--preset", "lmstudio", "--model", "qwen3-coder",
            "--set-active",
        )
        self.assertEqual(rc, 0)
        rc2, out = self._cli(
            "models", "--config", str(self.cfg), "capabilities", "--json",
        )
        self.assertEqual(rc2, 0)
        payload = json.loads(out.strip())
        self.assertEqual(payload.get("schema_version"), "model_capabilities_list_v1")
        self.assertEqual(payload.get("active_profile_id"), "cap")
        row = payload["profiles"][0]
        self.assertEqual(row["profile_id"], "cap")
        self.assertEqual(row["provider"], "openai_compatible")
        self.assertIn("capabilities", row)
        self.assertNotIn("api_key", row)
        self.assertNotIn("base_url", row)

    def test_models_ping_chat_smoke_adds_chat_status(self) -> None:
        rc, _ = self._cli(
            "models", "--config", str(self.cfg), "add",
            "--id", "smoke", "--preset", "lmstudio", "--model", "m", "--set-active",
        )
        self.assertEqual(rc, 0)
        with patch(
            "cai_agent.__main__.ping_profile",
            return_value={"profile_id": "smoke", "status": "OK", "http_status": 200},
        ), patch(
            "cai_agent.__main__.smoke_chat_profile",
            return_value={
                "profile_id": "smoke",
                "status": "OK",
                "latency_ms": 1,
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            },
        ):
            rc2, out = self._cli(
                "models",
                "--config",
                str(self.cfg),
                "ping",
                "smoke",
                "--chat-smoke",
                "--json",
            )
        self.assertEqual(rc2, 0)
        payload = json.loads(out.strip().splitlines()[-1])
        row = payload["results"][0]
        self.assertEqual(row.get("status"), "OK")
        self.assertEqual(row.get("chat_status"), "OK")
        self.assertEqual(row.get("chat_smoke", {}).get("status"), "OK")

    def test_models_onboarding_json_outputs_command_chain(self) -> None:
        rc, out = self._cli(
            "models",
            "--config",
            str(self.cfg),
            "onboarding",
            "--id",
            "new-local",
            "--preset",
            "lmstudio",
            "--model",
            "qwen3-coder",
            "--json",
        )
        self.assertEqual(rc, 0)
        payload = json.loads(out.strip())
        self.assertEqual(payload.get("schema_version"), "model_onboarding_flow_v1")
        self.assertEqual(payload.get("profile_id"), "new-local")
        hint = payload.get("capabilities_hint")
        self.assertIsInstance(hint, dict)
        self.assertEqual(hint.get("schema_version"), "model_capabilities_v1")
        self.assertEqual(hint.get("profile_id"), "new-local")
        self.assertEqual(hint.get("cost_hint"), "local")
        self.assertNotIn("api_key", hint)
        self.assertNotIn("base_url", hint)
        steps = [row.get("step") for row in payload.get("commands") or []]
        self.assertEqual(
            steps,
            [
                "inspect_providers",
                "add_profile",
                "capabilities",
                "ping",
                "chat_smoke",
                "use",
                "routing_test",
            ],
        )
        commands = [row.get("command") for row in payload.get("commands") or []]
        self.assertTrue(any("models add --id new-local --preset lmstudio" in str(c) for c in commands))
        self.assertTrue(any("--chat-smoke" in str(c) for c in commands))
        self.assertTrue(any("routing-test" in str(c) for c in commands))

    def test_model_onboarding_flow_v1_schema_file(self) -> None:
        schema = json.loads(_ONBOARDING_SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            schema["properties"]["schema_version"]["const"],
            "model_onboarding_flow_v1",
        )
        self.assertIn("capabilities_hint", schema.get("required", []))
        self.assertIn("commands", schema.get("required", []))
        hint = schema["properties"]["capabilities_hint"]
        self.assertEqual(hint["properties"]["schema_version"]["const"], "model_capabilities_v1")

    def test_models_onboarding_rejects_unknown_preset_early(self) -> None:
        rc, out = self._cli(
            "models",
            "--config",
            str(self.cfg),
            "onboarding",
            "--id",
            "bad",
            "--preset",
            "missing-preset",
            "--model",
            "m",
            "--json",
        )
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")


class PingProfileTests(unittest.TestCase):
    def test_env_missing_short_circuits(self) -> None:
        os.environ.pop("CAI_NONEXISTENT_KEY", None)
        from cai_agent.profiles import Profile

        p = Profile(
            id="c",
            provider="openai",
            base_url="https://api.openai.com/v1",
            model="gpt-4o",
            api_key_env="CAI_NONEXISTENT_KEY",
            temperature=0.2,
            timeout_sec=120.0,
        )
        out = cai_models.ping_profile(p, timeout_sec=5.0)
        self.assertEqual(out["status"], "ENV_MISSING")
        self.assertIn("CAI_NONEXISTENT_KEY", out.get("message", ""))

    def test_openai_ok_via_mock_transport(self) -> None:
        from cai_agent.profiles import Profile

        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(
                200, json={"data": [{"id": "gpt-4o"}, {"id": "gpt-3.5"}]},
            )

        p = Profile(
            id="c",
            provider="openai_compatible",
            base_url="http://localhost:1234/v1",
            model="x",
            api_key=None,
            api_key_env=None,
            temperature=0.2,
            timeout_sec=120.0,
        )
        out = cai_models.ping_profile(
            p, timeout_sec=5.0, transport=httpx.MockTransport(handler),
        )
        self.assertEqual(out["status"], "OK")
        self.assertEqual(str(captured[0].url), "http://localhost:1234/v1/models")

    def test_anthropic_uses_x_api_key_header(self) -> None:
        from cai_agent.profiles import Profile

        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(200, json={"data": []})

        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        try:
            p = Profile(
                id="c",
                provider="anthropic",
                base_url="https://api.anthropic.com",
                model="claude",
                api_key_env="ANTHROPIC_API_KEY",
                temperature=0.2,
                timeout_sec=120.0,
                anthropic_version="2023-06-01",
                max_tokens=4096,
            )
            out = cai_models.ping_profile(
                p, timeout_sec=5.0, transport=httpx.MockTransport(handler),
            )
        finally:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        self.assertEqual(out["status"], "OK")
        self.assertEqual(captured[0].headers.get("x-api-key"), "sk-ant-test")
        self.assertEqual(captured[0].headers.get("anthropic-version"), "2023-06-01")
        self.assertEqual(str(captured[0].url), "https://api.anthropic.com/v1/models")

    def test_http_401_maps_to_auth_fail(self) -> None:
        from cai_agent.profiles import Profile

        def handler(_req: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "nope"})

        p = Profile(
            id="c",
            provider="openai",
            base_url="https://api.openai.com/v1",
            model="m",
            api_key="k",
            temperature=0.2,
            timeout_sec=120.0,
        )
        out = cai_models.ping_profile(
            p, timeout_sec=5.0, transport=httpx.MockTransport(handler),
        )
        self.assertEqual(out["status"], "AUTH_FAIL")
        self.assertEqual(out["http_status"], 401)


class FetchModelsTests(unittest.TestCase):
    """`cai-agent models fetch` contract: must pick the endpoint/headers
    based on the *active profile*'s provider, not a hardcoded OpenAI shape.
    """

    def _make_settings(
        self,
        profile: "Profile",  # noqa: F821
        *,
        anth_version: str | None = None,
    ) -> "Settings":  # noqa: F821
        from dataclasses import replace
        from cai_agent.config import Settings
        from cai_agent.profiles import project_base_url

        base = Settings.from_env()
        return replace(
            base,
            provider=profile.provider,
            base_url=project_base_url(profile),
            model=profile.model,
            api_key=profile.resolve_api_key() or "k",
            profiles=(profile,),
            profiles_explicit=True,
            active_profile_id=profile.id,
            active_api_key_env=profile.api_key_env,
            anthropic_version=anth_version or profile.anthropic_version or "2023-06-01",
        )

    def test_openai_compat_path(self) -> None:
        from cai_agent.profiles import Profile

        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(
                200, json={"data": [{"id": "a"}, {"id": "b"}]},
            )

        p = Profile(
            id="oai",
            provider="openai_compatible",
            base_url="http://localhost:1234/v1",
            model="x",
            api_key="tok",
            temperature=0.2,
            timeout_sec=60.0,
        )
        settings = self._make_settings(p)
        out = cai_models.fetch_models(
            settings, transport=httpx.MockTransport(handler),
        )
        self.assertEqual(out, ["a", "b"])
        self.assertEqual(str(captured[0].url), "http://localhost:1234/v1/models")
        self.assertEqual(captured[0].headers.get("Authorization"), "Bearer tok")

    def test_anthropic_path_uses_v1_models_and_x_api_key(self) -> None:
        from cai_agent.profiles import Profile

        captured: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            captured.append(request)
            return httpx.Response(
                200,
                json={"data": [{"id": "claude-sonnet-4"}, {"id": "claude-haiku-4"}]},
            )

        p = Profile(
            id="anth",
            provider="anthropic",
            base_url="https://api.anthropic.com",
            model="claude-sonnet-4",
            api_key="sk-anth-xxxxxxxxxxxxxxxx",
            temperature=0.2,
            timeout_sec=60.0,
            anthropic_version="2023-06-01",
        )
        settings = self._make_settings(p, anth_version="2023-06-01")
        out = cai_models.fetch_models(
            settings, transport=httpx.MockTransport(handler),
        )
        self.assertEqual(out, ["claude-haiku-4", "claude-sonnet-4"])
        self.assertEqual(
            str(captured[0].url), "https://api.anthropic.com/v1/models",
        )
        self.assertIsNone(captured[0].headers.get("Authorization"))
        self.assertEqual(
            captured[0].headers.get("x-api-key"), "sk-anth-xxxxxxxxxxxxxxxx",
        )
        self.assertEqual(
            captured[0].headers.get("anthropic-version"), "2023-06-01",
        )


if __name__ == "__main__":
    unittest.main()
