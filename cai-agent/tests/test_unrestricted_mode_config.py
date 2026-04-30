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
        self.assertTrue(s.dangerous_confirmation_required)
        self.assertTrue(s.dangerous_critical_write_skip_if_unchanged)
        self.assertFalse(s.dangerous_audit_log_enabled)
        self.assertEqual(s.dangerous_write_file_critical_basenames, ())
        self.assertEqual(s.run_command_extra_danger_basenames, ())

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
        self.assertTrue(s.dangerous_confirmation_required)

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

    def test_toml_can_disable_dangerous_confirmation(self) -> None:
        s = _settings_from_toml(
            textwrap.dedent(
                """
                [llm]
                base_url = "http://localhost/v1"
                model = "m"
                api_key = "k"

                [safety]
                unrestricted_mode = true
                dangerous_confirmation_required = false
                """
            ).strip()
            + "\n",
        )
        self.assertTrue(s.unrestricted_mode)
        self.assertFalse(s.dangerous_confirmation_required)

    def test_dangerous_audit_toml_true(self) -> None:
        s = _settings_from_toml(
            textwrap.dedent(
                """
                [llm]
                base_url = "http://localhost/v1"
                model = "m"
                api_key = "k"

                [safety]
                dangerous_audit_log_enabled = true
                """
            ).strip()
            + "\n",
        )
        self.assertTrue(s.dangerous_audit_log_enabled)

    def test_dangerous_audit_env_overrides_toml(self) -> None:
        body = (
            textwrap.dedent(
                """
                [llm]
                base_url = "http://localhost/v1"
                model = "m"
                api_key = "k"

                [safety]
                dangerous_audit_log_enabled = true
                """
            ).strip()
            + "\n"
        )
        old = os.environ.get("CAI_DANGEROUS_AUDIT_LOG")
        try:
            os.environ["CAI_DANGEROUS_AUDIT_LOG"] = "0"
            s = _settings_from_toml(body)
            self.assertFalse(s.dangerous_audit_log_enabled)
        finally:
            if old is None:
                os.environ.pop("CAI_DANGEROUS_AUDIT_LOG", None)
            else:
                os.environ["CAI_DANGEROUS_AUDIT_LOG"] = old

    def test_dangerous_critical_write_skip_env_overrides_toml(self) -> None:
        body = (
            textwrap.dedent(
                """
                [llm]
                base_url = "http://localhost/v1"
                model = "m"
                api_key = "k"

                [safety]
                dangerous_critical_write_skip_if_unchanged = true
                """
            ).strip()
            + "\n"
        )
        old = os.environ.get("CAI_DANGEROUS_CRITICAL_WRITE_SKIP_IF_UNCHANGED")
        try:
            os.environ["CAI_DANGEROUS_CRITICAL_WRITE_SKIP_IF_UNCHANGED"] = "0"
            s = _settings_from_toml(body)
            self.assertFalse(s.dangerous_critical_write_skip_if_unchanged)
        finally:
            if old is None:
                os.environ.pop("CAI_DANGEROUS_CRITICAL_WRITE_SKIP_IF_UNCHANGED", None)
            else:
                os.environ["CAI_DANGEROUS_CRITICAL_WRITE_SKIP_IF_UNCHANGED"] = old


if __name__ == "__main__":
    unittest.main()
