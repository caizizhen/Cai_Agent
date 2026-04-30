from __future__ import annotations

import os
import textwrap
import unittest

from cai_agent.config import Settings


def _settings_from_toml(content: str) -> Settings:
    import tempfile

    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".toml",
        delete=False,
        encoding="utf-8",
    ) as f:
        f.write(content)
        path = f.name
    try:
        return Settings.from_env(config_path=path)
    finally:
        os.unlink(path)


class UnrestrictedModeConfigTests(unittest.TestCase):
    def test_default_false_without_safety_section(self) -> None:
        s = _settings_from_toml(
            textwrap.dedent(
                """
                [llm]
                base_url = "http://localhost/v1"
                model = "m"
                api_key = "k"
                """
            ).strip()
            + "\n",
        )
        self.assertFalse(s.unrestricted_mode)

    def test_toml_true(self) -> None:
        s = _settings_from_toml(
            textwrap.dedent(
                """
                [llm]
                base_url = "http://localhost/v1"
                model = "m"
                api_key = "k"

                [safety]
                unrestricted_mode = true
                """
            ).strip()
            + "\n",
        )
        self.assertTrue(s.unrestricted_mode)

    def test_env_overrides_toml_false(self) -> None:
        body = textwrap.dedent(
            """
            [llm]
            base_url = "http://localhost/v1"
            model = "m"
            api_key = "k"

            [safety]
            unrestricted_mode = false
            """
        ).strip() + "\n"
        old = os.environ.get("CAI_UNRESTRICTED_MODE")
        try:
            os.environ["CAI_UNRESTRICTED_MODE"] = "1"
            s = _settings_from_toml(body)
            self.assertTrue(s.unrestricted_mode)
        finally:
            if old is None:
                os.environ.pop("CAI_UNRESTRICTED_MODE", None)
            else:
                os.environ["CAI_UNRESTRICTED_MODE"] = old


if __name__ == "__main__":
    unittest.main()
