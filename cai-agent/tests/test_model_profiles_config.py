"""M1/M2 契约：[[models.profile]] 解析 + Settings 投影 + [llm] 兼容。"""
from __future__ import annotations

import os
import tempfile
import textwrap
import unittest
from pathlib import Path

from cai_agent.config import Settings
from cai_agent.profiles import (
    Profile,
    ProfilesError,
    apply_preset,
    build_profile_contract_payload,
    build_profile,
    get_profile_by_id,
    normalize_openai_chat_base_url,
    parse_models_section,
    pick_active,
    project_base_url,
    resolve_role_profile_id,
    strip_models_blocks,
)


def _write(tmp: Path, body: str) -> Path:
    p = tmp / "cai-agent.toml"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


class ProfilesParsingTests(unittest.TestCase):
    def test_legacy_llm_synthesises_default_profile(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            cfg = _write(
                Path(d),
                """
                [llm]
                base_url = "http://localhost:1234/v1"
                model = "demo-model"
                api_key = "lm-studio"
                temperature = 0.3
                timeout_sec = 42
                """,
            )
            s = Settings.from_env(config_path=str(cfg))
        self.assertEqual(len(s.profiles), 1)
        self.assertEqual(s.active_profile_id, "default")
        self.assertEqual(s.profiles[0].provider, "openai_compatible")
        self.assertEqual(s.base_url, "http://localhost:1234/v1")
        self.assertEqual(s.model, "demo-model")
        self.assertAlmostEqual(s.temperature, 0.3, places=5)

    def test_profiles_projection_overrides_llm_section(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            cfg = _write(
                Path(d),
                """
                [llm]
                base_url = "http://localhost:1234/v1"
                model = "legacy"
                api_key = "legacy-key"

                [models]
                active = "anthropic"

                [[models.profile]]
                id = "anthropic"
                provider = "anthropic"
                base_url = "https://api.anthropic.com"
                model = "claude-sonnet-4-5-20250929"
                api_key_env = "ANTHROPIC_API_KEY"
                temperature = 0.1
                timeout_sec = 30

                [[models.profile]]
                id = "local"
                provider = "openai_compatible"
                base_url = "http://localhost:1234/v1"
                model = "gemma"
                api_key_env = "LM_API_KEY"
                """,
            )
            os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
            try:
                s = Settings.from_env(config_path=str(cfg))
            finally:
                os.environ.pop("ANTHROPIC_API_KEY", None)
        self.assertEqual(s.active_profile_id, "anthropic")
        self.assertEqual(s.provider, "anthropic")
        self.assertEqual(s.model, "claude-sonnet-4-5-20250929")
        # anthropic 的 base_url 需要剥离 /v1
        self.assertEqual(s.base_url, "https://api.anthropic.com")
        self.assertEqual(s.api_key, "sk-ant-test")
        self.assertEqual(s.anthropic_version, "2023-06-01")
        self.assertGreaterEqual(s.anthropic_max_tokens, 1)

    def test_env_override_active_model(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            cfg = _write(
                Path(d),
                """
                [models]
                active = "p1"

                [[models.profile]]
                id = "p1"
                provider = "openai_compatible"
                base_url = "http://a/v1"
                model = "m1"

                [[models.profile]]
                id = "p2"
                provider = "openai_compatible"
                base_url = "http://b/v1"
                model = "m2"
                """,
            )
            os.environ["CAI_ACTIVE_MODEL"] = "p2"
            try:
                s = Settings.from_env(config_path=str(cfg))
            finally:
                os.environ.pop("CAI_ACTIVE_MODEL", None)
        self.assertEqual(s.active_profile_id, "p2")
        self.assertEqual(s.model, "m2")

    def test_conflicting_api_key_and_env_raises(self) -> None:
        with self.assertRaises(ProfilesError):
            build_profile(
                {
                    "id": "bad",
                    "provider": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "model": "gpt-4o",
                    "api_key": "sk-literal",
                    "api_key_env": "OPENAI_API_KEY",
                },
            )

    def test_duplicate_profile_ids_raises(self) -> None:
        raw = {
            "models": {
                "profile": [
                    {
                        "id": "dup",
                        "provider": "openai_compatible",
                        "base_url": "http://a/v1",
                        "model": "m",
                    },
                    {
                        "id": "dup",
                        "provider": "openai_compatible",
                        "base_url": "http://b/v1",
                        "model": "m",
                    },
                ],
            },
        }
        with self.assertRaises(ProfilesError):
            parse_models_section(raw)

    def test_api_key_env_missing_is_not_a_crash(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            cfg = _write(
                Path(d),
                """
                [models]
                active = "p1"

                [[models.profile]]
                id = "p1"
                provider = "openai_compatible"
                base_url = "http://x/v1"
                model = "m"
                api_key_env = "CAI_TEST_MISSING_KEY_VAR"
                """,
            )
            os.environ.pop("CAI_TEST_MISSING_KEY_VAR", None)
            s = Settings.from_env(config_path=str(cfg))
        self.assertEqual(s.active_api_key_env, "CAI_TEST_MISSING_KEY_VAR")
        self.assertEqual(s.api_key, "")

    def test_apply_preset_merges_user_fields(self) -> None:
        merged = apply_preset(
            {"id": "c1", "model": "claude-sonnet-4-5"}, "anthropic",
        )
        self.assertEqual(merged["provider"], "anthropic")
        self.assertEqual(merged["base_url"], "https://api.anthropic.com")
        self.assertEqual(merged["api_key_env"], "ANTHROPIC_API_KEY")
        self.assertEqual(merged["model"], "claude-sonnet-4-5")

    def test_apply_preset_vllm_and_gateway(self) -> None:
        v = apply_preset({"id": "v1"}, "vllm")
        self.assertEqual(v["provider"], "openai_compatible")
        self.assertIn("8000", v["base_url"])
        self.assertEqual(v["api_key_env"], "VLLM_API_KEY")
        self.assertIn("model", v)
        g = apply_preset({"id": "g1", "base_url": "http://proxy.internal:9000/v1"}, "gateway")
        self.assertEqual(g["base_url"], "http://proxy.internal:9000/v1")
        self.assertEqual(g["api_key_env"], "OPENAI_API_KEY")
        self.assertEqual(g["model"], "gpt-4o-mini")

    def test_apply_preset_zhipu(self) -> None:
        z = apply_preset({"id": "z1"}, "zhipu")
        self.assertEqual(z["provider"], "openai_compatible")
        self.assertEqual(z["model"], "glm-5.1")
        self.assertEqual(z["api_key_env"], "ZAI_API_KEY")
        self.assertIn("open.bigmodel.cn", z["base_url"])
        self.assertEqual(z.get("context_window"), 200_000)

    def test_normalize_openai_chat_base_url_zhipu_no_v1_suffix(self) -> None:
        self.assertEqual(
            normalize_openai_chat_base_url("https://open.bigmodel.cn/api/paas/v4/"),
            "https://open.bigmodel.cn/api/paas/v4",
        )

    def test_project_base_url_anthropic_strips_v1(self) -> None:
        p = Profile(
            id="c",
            provider="anthropic",
            base_url="https://api.anthropic.com/v1",
            model="x",
            temperature=0.2,
            timeout_sec=120.0,
            anthropic_version="2023-06-01",
            max_tokens=4096,
        )
        self.assertEqual(project_base_url(p), "https://api.anthropic.com")

    def test_project_base_url_openai_compat_appends_v1(self) -> None:
        p = Profile(
            id="c",
            provider="openai_compatible",
            base_url="http://localhost:1234",
            model="x",
            temperature=0.2,
            timeout_sec=120.0,
        )
        self.assertEqual(project_base_url(p), "http://localhost:1234/v1")

    def test_project_base_url_zhipu_openai_compat(self) -> None:
        p = Profile(
            id="z",
            provider="openai_compatible",
            base_url="https://open.bigmodel.cn/api/paas/v4",
            model="glm-5.1",
            api_key_env="ZAI_API_KEY",
            temperature=0.6,
            timeout_sec=120.0,
        )
        self.assertEqual(project_base_url(p), "https://open.bigmodel.cn/api/paas/v4")

    def test_settings_zhipu_legacy_llm_base_url(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            cfg = _write(
                Path(d),
                """
                [llm]
                provider = "openai_compatible"
                base_url = "https://open.bigmodel.cn/api/paas/v4/"
                model = "glm-5.1"
                api_key = "dummy"
                temperature = 0.6
                """,
            )
            s = Settings.from_env(config_path=str(cfg))
        self.assertEqual(s.base_url, "https://open.bigmodel.cn/api/paas/v4")
        self.assertEqual(s.model, "glm-5.1")

    def test_strip_models_blocks_preserves_other_sections(self) -> None:
        src = textwrap.dedent(
            """
            [llm]
            model = "x"

            [models]
            active = "p1"

            [[models.profile]]
            id = "p1"
            provider = "openai"
            base_url = "u"
            model = "m"

            [agent]
            max_iterations = 10
            """,
        )
        stripped = strip_models_blocks(src)
        self.assertIn("[llm]", stripped)
        self.assertIn("[agent]", stripped)
        self.assertNotIn("[models]", stripped)
        self.assertNotIn("[[models.profile]]", stripped)


class PickActiveTests(unittest.TestCase):
    def _make(self, pid: str) -> Profile:
        return Profile(
            id=pid,
            provider="openai_compatible",
            base_url="http://x/v1",
            model="m",
            temperature=0.2,
            timeout_sec=120.0,
        )

    def test_env_override_wins_when_defined(self) -> None:
        p1, p2 = self._make("a"), self._make("b")
        got = pick_active((p1, p2), "a", env_override="b")
        self.assertEqual(got.id, "b")

    def test_env_override_ignored_when_id_unknown(self) -> None:
        p1, p2 = self._make("a"), self._make("b")
        got = pick_active((p1, p2), "b", env_override="ghost")
        self.assertEqual(got.id, "b")

    def test_falls_back_to_first_when_active_missing(self) -> None:
        p1, p2 = self._make("a"), self._make("b")
        got = pick_active((p1, p2), None)
        self.assertEqual(got.id, "a")

    def test_profile_contract_contains_profile_home_layout_when_workspace_given(self) -> None:
        p1, p2 = self._make("alpha"), self._make("beta")
        contract = build_profile_contract_payload(
            (p1, p2),
            profiles_explicit=True,
            active_profile_id="beta",
            workspace_root="d:/ws/demo",
        )
        self.assertEqual(contract.get("profile_home_schema_version"), "profile_home_layout_v1")
        homes = contract.get("profile_homes")
        self.assertIsInstance(homes, dict)
        beta_home = (homes or {}).get("beta")
        self.assertIsInstance(beta_home, dict)
        root_norm = str((beta_home or {}).get("root", "")).replace("/", "\\")
        self.assertTrue(root_norm.endswith(".cai\\profiles\\beta"))
        cfg_norm = str((beta_home or {}).get("config_dir", "")).replace("/", "\\")
        self.assertTrue(cfg_norm.endswith(".cai\\profiles\\beta\\config"))
        self.assertEqual(contract.get("active_profile_home"), beta_home)

    def test_get_profile_by_id_returns_none_on_unknown(self) -> None:
        p1, p2 = self._make("alpha"), self._make("beta")
        self.assertIsNone(get_profile_by_id((p1, p2), "ghost"))

    def test_resolve_role_profile_id_prefers_role_specific_ids(self) -> None:
        self.assertEqual(
            resolve_role_profile_id(
                role="subagent",
                active_profile_id="a",
                subagent_profile_id="s",
                planner_profile_id="p",
            ),
            "s",
        )
        self.assertEqual(
            resolve_role_profile_id(
                role="planner",
                active_profile_id="a",
                subagent_profile_id="s",
                planner_profile_id="p",
            ),
            "p",
        )
        self.assertEqual(
            resolve_role_profile_id(
                role="active",
                active_profile_id="a",
                subagent_profile_id="s",
                planner_profile_id="p",
            ),
            "a",
        )


class ConfigDiscoveryTests(unittest.TestCase):
    def test_finds_toml_in_parent_directory(self) -> None:
        prev_cfg = os.environ.pop("CAI_CONFIG", None)
        prev_cwd = os.getcwd()
        cfg_path: Path | None = None
        try:
            with tempfile.TemporaryDirectory() as d:
                root = Path(d)
                sub = root / "pkg" / "nested"
                sub.mkdir(parents=True)
                cfg_path = root / "cai-agent.toml"
                cfg_path.write_text(
                    "[llm]\n"
                    'base_url = "http://x/v1"\n'
                    'model = "m"\n'
                    'api_key = "k"\n'
                    "context_window = 40000\n",
                    encoding="utf-8",
                )
                os.chdir(sub)
                s = Settings.from_env()
                os.chdir(prev_cwd)
        finally:
            if prev_cfg is not None:
                os.environ["CAI_CONFIG"] = prev_cfg
        self.assertIsNotNone(cfg_path)
        self.assertEqual(s.context_window, 40000)
        self.assertEqual(s.context_window_source, "llm")
        self.assertEqual(s.config_loaded_from, str(cfg_path.resolve()))

    def test_finds_toml_via_cai_workspace_when_cwd_unrelated(self) -> None:
        """cwd 与项目不在同一目录树（例如跨盘）时，用 CAI_WORKSPACE 仍能加载 [llm].context_window。"""
        prev_cfg = os.environ.pop("CAI_CONFIG", None)
        prev_ws = os.environ.pop("CAI_WORKSPACE", None)
        prev_cwd = os.getcwd()
        cfg_path: Path | None = None
        try:
            with tempfile.TemporaryDirectory() as base:
                root = Path(base) / "project"
                elsewhere = Path(base) / "elsewhere"
                root.mkdir()
                elsewhere.mkdir()
                cfg_path = root / "cai-agent.toml"
                cfg_path.write_text(
                    "[llm]\n"
                    'base_url = "http://x/v1"\n'
                    'model = "m"\n'
                    'api_key = "k"\n'
                    "context_window = 50000\n",
                    encoding="utf-8",
                )
                os.chdir(elsewhere)
                os.environ["CAI_WORKSPACE"] = str(root)
                try:
                    s = Settings.from_env()
                finally:
                    os.chdir(prev_cwd)
        finally:
            if prev_cfg is not None:
                os.environ["CAI_CONFIG"] = prev_cfg
            if prev_ws is not None:
                os.environ["CAI_WORKSPACE"] = prev_ws
            else:
                os.environ.pop("CAI_WORKSPACE", None)
        self.assertIsNotNone(cfg_path)
        self.assertEqual(s.context_window, 50000)
        self.assertEqual(s.context_window_source, "llm")
        self.assertEqual(s.config_loaded_from, str(cfg_path.resolve()))

    def test_finds_toml_via_workspace_hint_when_cwd_unrelated(self) -> None:
        prev_cfg = os.environ.pop("CAI_CONFIG", None)
        prev_ws = os.environ.pop("CAI_WORKSPACE", None)
        prev_cwd = os.getcwd()
        cfg_path: Path | None = None
        try:
            with tempfile.TemporaryDirectory() as base:
                root = Path(base) / "project"
                elsewhere = Path(base) / "elsewhere"
                root.mkdir()
                elsewhere.mkdir()
                cfg_path = root / "cai-agent.toml"
                cfg_path.write_text(
                    "[llm]\n"
                    'base_url = "http://x/v1"\n'
                    'model = "m"\n'
                    'api_key = "k"\n'
                    "context_window = 44000\n",
                    encoding="utf-8",
                )
                os.chdir(elsewhere)
                try:
                    s = Settings.from_env(workspace_hint=str(root))
                finally:
                    os.chdir(prev_cwd)
        finally:
            if prev_cfg is not None:
                os.environ["CAI_CONFIG"] = prev_cfg
            if prev_ws is not None:
                os.environ["CAI_WORKSPACE"] = prev_ws
        self.assertIsNotNone(cfg_path)
        self.assertEqual(s.context_window, 44000)
        self.assertEqual(s.context_window_source, "llm")
        self.assertEqual(s.config_loaded_from, str(cfg_path.resolve()))

    def test_user_home_global_config_is_loaded_when_no_project_toml(self) -> None:
        """cwd / CAI_WORKSPACE / workspace_hint 都找不到项目级 TOML 时，
        应当回退到用户级全局配置（模拟 Windows 下 %APPDATA% 的位置）。"""
        prev_cfg = os.environ.pop("CAI_CONFIG", None)
        prev_ws = os.environ.pop("CAI_WORKSPACE", None)
        prev_appdata = os.environ.get("APPDATA")
        prev_xdg = os.environ.get("XDG_CONFIG_HOME")
        prev_home = os.environ.get("HOME")
        prev_userprofile = os.environ.get("USERPROFILE")
        prev_cwd = os.getcwd()
        cfg_path: Path | None = None
        try:
            with tempfile.TemporaryDirectory() as base:
                appdata = Path(base) / "AppData"
                fake_home = Path(base) / "home"
                elsewhere = Path(base) / "elsewhere"
                appdata.mkdir()
                fake_home.mkdir()
                elsewhere.mkdir()
                cfg_dir = appdata / "cai-agent"
                cfg_dir.mkdir()
                cfg_path = cfg_dir / "cai-agent.toml"
                cfg_path.write_text(
                    "[llm]\n"
                    'base_url = "http://x/v1"\n'
                    'model = "m"\n'
                    'api_key = "k"\n'
                    "context_window = 60000\n",
                    encoding="utf-8",
                )
                os.environ["APPDATA"] = str(appdata)
                os.environ["HOME"] = str(fake_home)
                os.environ["USERPROFILE"] = str(fake_home)
                os.environ.pop("XDG_CONFIG_HOME", None)
                os.chdir(elsewhere)
                try:
                    s = Settings.from_env()
                finally:
                    os.chdir(prev_cwd)
        finally:
            if prev_cfg is not None:
                os.environ["CAI_CONFIG"] = prev_cfg
            if prev_ws is not None:
                os.environ["CAI_WORKSPACE"] = prev_ws
            if prev_appdata is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = prev_appdata
            if prev_xdg is None:
                os.environ.pop("XDG_CONFIG_HOME", None)
            else:
                os.environ["XDG_CONFIG_HOME"] = prev_xdg
            if prev_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = prev_home
            if prev_userprofile is None:
                os.environ.pop("USERPROFILE", None)
            else:
                os.environ["USERPROFILE"] = prev_userprofile
        self.assertIsNotNone(cfg_path)
        self.assertEqual(s.context_window, 60000)
        self.assertEqual(s.context_window_source, "llm")
        self.assertEqual(s.config_loaded_from, str(cfg_path.resolve()))

    def test_project_toml_wins_over_user_home_global(self) -> None:
        """项目级 cai-agent.toml 优先于用户级全局配置，不能被覆盖。"""
        prev_cfg = os.environ.pop("CAI_CONFIG", None)
        prev_ws = os.environ.pop("CAI_WORKSPACE", None)
        prev_appdata = os.environ.get("APPDATA")
        prev_xdg = os.environ.get("XDG_CONFIG_HOME")
        prev_home = os.environ.get("HOME")
        prev_userprofile = os.environ.get("USERPROFILE")
        prev_cwd = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as base:
                appdata = Path(base) / "AppData"
                fake_home = Path(base) / "home"
                project = Path(base) / "project"
                for d in (appdata, fake_home, project, appdata / "cai-agent"):
                    d.mkdir()
                global_cfg = appdata / "cai-agent" / "cai-agent.toml"
                global_cfg.write_text(
                    "[llm]\nbase_url=\"http://x/v1\"\nmodel=\"m\"\napi_key=\"k\"\ncontext_window=60000\n",
                    encoding="utf-8",
                )
                proj_cfg = project / "cai-agent.toml"
                proj_cfg.write_text(
                    "[llm]\nbase_url=\"http://x/v1\"\nmodel=\"m\"\napi_key=\"k\"\ncontext_window=12345\n",
                    encoding="utf-8",
                )
                os.environ["APPDATA"] = str(appdata)
                os.environ["HOME"] = str(fake_home)
                os.environ["USERPROFILE"] = str(fake_home)
                os.environ.pop("XDG_CONFIG_HOME", None)
                os.chdir(project)
                try:
                    s = Settings.from_env()
                finally:
                    os.chdir(prev_cwd)
        finally:
            if prev_cfg is not None:
                os.environ["CAI_CONFIG"] = prev_cfg
            if prev_ws is not None:
                os.environ["CAI_WORKSPACE"] = prev_ws
            if prev_appdata is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = prev_appdata
            if prev_xdg is None:
                os.environ.pop("XDG_CONFIG_HOME", None)
            else:
                os.environ["XDG_CONFIG_HOME"] = prev_xdg
            if prev_home is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = prev_home
            if prev_userprofile is None:
                os.environ.pop("USERPROFILE", None)
            else:
                os.environ["USERPROFILE"] = prev_userprofile
        self.assertEqual(s.context_window, 12345)

    def test_context_window_string_in_llm(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / "cai-agent.toml"
            cfg.write_text(
                "[llm]\n"
                'base_url = "http://x/v1"\n'
                'model = "m"\n'
                'api_key = "k"\n'
                'context_window = "32000"\n',
                encoding="utf-8",
            )
            s = Settings.from_env(config_path=str(cfg))
        self.assertEqual(s.context_window, 32000)
        self.assertEqual(s.context_window_source, "llm")


if __name__ == "__main__":
    unittest.main()
