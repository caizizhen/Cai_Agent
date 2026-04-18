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

import httpx

from cai_agent import models as cai_models
from cai_agent.__main__ import main


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
        self.assertEqual(payload["active"], "p1")
        ids = [p["id"] for p in payload["profiles"]]
        self.assertEqual(sorted(ids), ["p1", "p2"])

        # use p2
        rc, _ = self._cli("models", "--config", str(self.cfg), "use", "p2")
        self.assertEqual(rc, 0)

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
