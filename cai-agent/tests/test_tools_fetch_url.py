from __future__ import annotations

import os
import tempfile
import textwrap
import unittest
from unittest.mock import MagicMock, patch

from cai_agent.config import Settings
from cai_agent.sandbox import SandboxError
from cai_agent.tools import dispatch, tool_fetch_url


def _settings_from_toml(content: str) -> Settings:
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


class FetchUrlToolTests(unittest.TestCase):
    def test_dispatch_permission_deny_by_default(self) -> None:
        s = _settings_from_toml(
            textwrap.dedent(
                """
                [llm]
                base_url = "http://localhost:1/v1"
                model = "m"
                api_key = "k"
                """,
            ),
        )
        with self.assertRaises(SandboxError) as ctx:
            dispatch(s, "fetch_url", {"url": "https://example.com/"})
        self.assertIn("fetch_url", str(ctx.exception))

    def test_disabled_even_when_permission_allow(self) -> None:
        s = _settings_from_toml(
            textwrap.dedent(
                """
                [llm]
                base_url = "http://localhost:1/v1"
                model = "m"
                api_key = "k"
                [permissions]
                fetch_url = "allow"
                """,
            ),
        )
        with self.assertRaises(SandboxError) as ctx:
            dispatch(s, "fetch_url", {"url": "https://example.com/"})
        self.assertIn("未启用", str(ctx.exception))

    def test_host_not_in_allowlist(self) -> None:
        s = _settings_from_toml(
            textwrap.dedent(
                """
                [llm]
                base_url = "http://localhost:1/v1"
                model = "m"
                api_key = "k"
                [fetch_url]
                enabled = true
                allow_hosts = ["github.com"]
                [permissions]
                fetch_url = "allow"
                """,
            ),
        )
        with self.assertRaises(SandboxError) as ctx:
            dispatch(s, "fetch_url", {"url": "https://example.com/x"})
        self.assertIn("白名单", str(ctx.exception))

    def test_rejects_http_scheme(self) -> None:
        s = _settings_from_toml(
            textwrap.dedent(
                """
                [llm]
                base_url = "http://localhost:1/v1"
                model = "m"
                api_key = "k"
                [fetch_url]
                enabled = true
                allow_hosts = ["example.com"]
                [permissions]
                fetch_url = "allow"
                """,
            ),
        )
        with self.assertRaises(SandboxError) as ctx:
            dispatch(s, "fetch_url", {"url": "http://example.com/x"})
        self.assertIn("https", str(ctx.exception))

    def test_rejects_localhost_hostname(self) -> None:
        s = _settings_from_toml(
            textwrap.dedent(
                """
                [llm]
                base_url = "http://localhost:1/v1"
                model = "m"
                api_key = "k"
                [fetch_url]
                enabled = true
                allow_hosts = ["localhost"]
                [permissions]
                fetch_url = "allow"
                """,
            ),
        )
        with self.assertRaises(SandboxError) as ctx:
            dispatch(s, "fetch_url", {"url": "https://localhost/path"})
        self.assertIn("拒绝", str(ctx.exception))

    def test_rejects_private_ip_literal(self) -> None:
        s = _settings_from_toml(
            textwrap.dedent(
                """
                [llm]
                base_url = "http://localhost:1/v1"
                model = "m"
                api_key = "k"
                [fetch_url]
                enabled = true
                allow_hosts = ["127.0.0.1"]
                [permissions]
                fetch_url = "allow"
                """,
            ),
        )
        with self.assertRaises(SandboxError) as ctx:
            dispatch(s, "fetch_url", {"url": "https://127.0.0.1/"})
        self.assertIn("私网", str(ctx.exception))

    @patch("cai_agent.tools.httpx.Client")
    def test_success_path(self, client_cls: MagicMock) -> None:
        s = _settings_from_toml(
            textwrap.dedent(
                """
                [llm]
                base_url = "http://localhost:1/v1"
                model = "m"
                api_key = "k"
                [fetch_url]
                enabled = true
                allow_hosts = ["example.com"]
                max_bytes = 10000
                [permissions]
                fetch_url = "allow"
                """,
            ),
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://api.example.com/v"
        mock_resp.headers = {"content-type": "text/plain; charset=utf-8"}
        mock_resp.content = b"hello"
        inst = MagicMock()
        inst.get.return_value = mock_resp
        inst.__enter__.return_value = inst
        inst.__exit__.return_value = None
        client_cls.return_value = inst

        out = tool_fetch_url(s, {"url": "https://api.example.com/v"})
        self.assertIn("HTTP 200", out)
        self.assertIn("hello", out)
        inst.get.assert_called_once()
