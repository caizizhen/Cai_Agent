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
    build_profile,
    parse_models_section,
    pick_active,
    project_base_url,
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


if __name__ == "__main__":
    unittest.main()
