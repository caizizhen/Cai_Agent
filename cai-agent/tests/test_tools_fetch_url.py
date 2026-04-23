from __future__ import annotations

import os
import socket
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


def _gai_inet_public(port: int) -> list[tuple[int, int, int, str, tuple[str, int]]]:
    return [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            "",
            ("1.1.1.1", port),
        ),
    ]


class FetchUrlToolTests(unittest.TestCase):
    @patch("cai_agent.tools.socket.getaddrinfo", return_value=_gai_inet_public(443))
    @patch("cai_agent.tools.httpx.Client")
    def test_builtin_defaults_enable_unrestricted_fetch(
        self, client_cls: MagicMock, _gai: MagicMock
    ) -> None:
        """无 [fetch_url] 段时：内置默认开启且无主机白名单。"""
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
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://api.weather.example/1"
        mock_resp.headers = {"content-type": "text/plain"}
        mock_resp.content = b"sunny"
        inst = MagicMock()
        inst.get.return_value = mock_resp
        inst.__enter__.return_value = inst
        inst.__exit__.return_value = None
        client_cls.return_value = inst

        out = tool_fetch_url(s, {"url": "https://api.weather.example/1"})
        self.assertIn("HTTP 200", out)
        self.assertIn("sunny", out)
        client_cls.assert_called_once()
        self.assertEqual(client_cls.call_args.kwargs.get("max_redirects"), 20)

    def test_dispatch_permission_deny(self) -> None:
        s = _settings_from_toml(
            textwrap.dedent(
                """
                [llm]
                base_url = "http://localhost:1/v1"
                model = "m"
                api_key = "k"
                [permissions]
                fetch_url = "deny"
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
                [fetch_url]
                enabled = false
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
                unrestricted = false
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
                unrestricted = false
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
                unrestricted = false
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
                unrestricted = false
                allow_hosts = ["127.0.0.1"]
                [permissions]
                fetch_url = "allow"
                """,
            ),
        )
        with self.assertRaises(SandboxError) as ctx:
            dispatch(s, "fetch_url", {"url": "https://127.0.0.1/"})
        self.assertIn("私网", str(ctx.exception))

    @patch("cai_agent.tools.socket.getaddrinfo", return_value=_gai_inet_public(443))
    @patch("cai_agent.tools.httpx.Client")
    def test_success_path(self, client_cls: MagicMock, _gai: MagicMock) -> None:
        s = _settings_from_toml(
            textwrap.dedent(
                """
                [llm]
                base_url = "http://localhost:1/v1"
                model = "m"
                api_key = "k"
                [fetch_url]
                enabled = true
                unrestricted = false
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
        self.assertEqual(client_cls.call_args.kwargs.get("max_redirects"), 20)

    @patch("cai_agent.tools.socket.getaddrinfo", return_value=_gai_inet_public(443))
    @patch("cai_agent.tools.httpx.Client")
    def test_max_redirects_from_toml(self, client_cls: MagicMock, _gai: MagicMock) -> None:
        s = _settings_from_toml(
            textwrap.dedent(
                """
                [llm]
                base_url = "http://localhost:1/v1"
                model = "m"
                api_key = "k"
                [fetch_url]
                enabled = true
                unrestricted = false
                allow_hosts = ["example.com"]
                max_redirects = 7
                [permissions]
                fetch_url = "allow"
                """,
            ),
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://api.example.com/"
        mock_resp.headers = {"content-type": "text/plain"}
        mock_resp.content = b"x"
        inst = MagicMock()
        inst.get.return_value = mock_resp
        inst.__enter__.return_value = inst
        inst.__exit__.return_value = None
        client_cls.return_value = inst
        tool_fetch_url(s, {"url": "https://api.example.com/"})
        self.assertEqual(client_cls.call_args.kwargs.get("max_redirects"), 7)

    @patch("cai_agent.tools.socket.getaddrinfo", return_value=_gai_inet_public(443))
    @patch("cai_agent.tools.httpx.Client")
    def test_max_redirects_env_clamps_and_overrides_toml(
        self, client_cls: MagicMock, _gai: MagicMock
    ) -> None:
        toml = textwrap.dedent(
            """
            [llm]
            base_url = "http://localhost:1/v1"
            model = "m"
            api_key = "k"
            [fetch_url]
            enabled = true
            unrestricted = false
            allow_hosts = ["example.com"]
            max_redirects = 3
            [permissions]
            fetch_url = "allow"
            """,
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://api.example.com/"
        mock_resp.headers = {"content-type": "text/plain"}
        mock_resp.content = b"x"
        inst = MagicMock()
        inst.get.return_value = mock_resp
        inst.__enter__.return_value = inst
        inst.__exit__.return_value = None
        client_cls.return_value = inst
        with patch.dict(os.environ, {"CAI_FETCH_URL_MAX_REDIRECTS": "99"}):
            s = _settings_from_toml(toml)
            tool_fetch_url(s, {"url": "https://api.example.com/"})
        self.assertEqual(client_cls.call_args.kwargs.get("max_redirects"), 50)

    @patch("cai_agent.tools.socket.getaddrinfo", return_value=_gai_inet_public(443))
    @patch("cai_agent.tools.httpx.Client")
    def test_unrestricted_skips_allow_hosts(self, client_cls: MagicMock, _gai: MagicMock) -> None:
        s = _settings_from_toml(
            textwrap.dedent(
                """
                [llm]
                base_url = "http://localhost:1/v1"
                model = "m"
                api_key = "k"
                [fetch_url]
                enabled = true
                unrestricted = true
                [permissions]
                fetch_url = "allow"
                """,
            ),
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://news.example.org/"
        mock_resp.headers = {"content-type": "text/plain"}
        mock_resp.content = b"ok"
        inst = MagicMock()
        inst.get.return_value = mock_resp
        inst.__enter__.return_value = inst
        inst.__exit__.return_value = None
        client_cls.return_value = inst

        out = tool_fetch_url(s, {"url": "https://news.example.org/p"})
        self.assertIn("HTTP 200", out)
        self.assertIn("ok", out)

    @patch("cai_agent.tools.socket.getaddrinfo", return_value=_gai_inet_public(80))
    @patch("cai_agent.tools.httpx.Client")
    def test_unrestricted_allows_http(self, client_cls: MagicMock, _gai: MagicMock) -> None:
        s = _settings_from_toml(
            textwrap.dedent(
                """
                [llm]
                base_url = "http://localhost:1/v1"
                model = "m"
                api_key = "k"
                [fetch_url]
                enabled = true
                unrestricted = true
                [permissions]
                fetch_url = "allow"
                """,
            ),
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "http://example.com/x"
        mock_resp.headers = {"content-type": "text/plain"}
        mock_resp.content = b"h"
        inst = MagicMock()
        inst.get.return_value = mock_resp
        inst.__enter__.return_value = inst
        inst.__exit__.return_value = None
        client_cls.return_value = inst

        out = tool_fetch_url(s, {"url": "http://example.com/x"})
        self.assertIn("HTTP 200", out)

    def test_unrestricted_still_rejects_localhost(self) -> None:
        s = _settings_from_toml(
            textwrap.dedent(
                """
                [llm]
                base_url = "http://localhost:1/v1"
                model = "m"
                api_key = "k"
                [fetch_url]
                enabled = true
                unrestricted = true
                [permissions]
                fetch_url = "allow"
                """,
            ),
        )
        with self.assertRaises(SandboxError) as ctx:
            tool_fetch_url(s, {"url": "https://localhost/"})
        self.assertIn("拒绝", str(ctx.exception))

    @patch("cai_agent.tools.socket.getaddrinfo")
    def test_rejects_when_any_resolved_addr_is_loopback(self, gai: MagicMock) -> None:
        s = _settings_from_toml(
            textwrap.dedent(
                """
                [llm]
                base_url = "http://localhost:1/v1"
                model = "m"
                api_key = "k"
                [fetch_url]
                enabled = true
                unrestricted = false
                allow_hosts = ["example.com"]
                [permissions]
                fetch_url = "allow"
                """,
            ),
        )
        gai.return_value = _gai_inet_public(443) + [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("127.0.0.1", 443),
            ),
        ]
        with self.assertRaises(SandboxError) as ctx:
            tool_fetch_url(s, {"url": "https://example.com/x"})
        self.assertIn("DNS", str(ctx.exception))

    @patch("cai_agent.tools.httpx.Client")
    @patch("cai_agent.tools.socket.getaddrinfo")
    def test_allow_private_resolved_ips_skips_dns_check(
        self, gai: MagicMock, client_cls: MagicMock
    ) -> None:
        s = _settings_from_toml(
            textwrap.dedent(
                """
                [llm]
                base_url = "http://localhost:1/v1"
                model = "m"
                api_key = "k"
                [fetch_url]
                enabled = true
                unrestricted = false
                allow_hosts = ["corp.internal"]
                allow_private_resolved_ips = true
                [permissions]
                fetch_url = "allow"
                """,
            ),
        )
        gai.return_value = [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("10.0.0.5", 443),
            ),
        ]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://corp.internal/"
        mock_resp.headers = {"content-type": "text/plain"}
        mock_resp.content = b"intranet"
        inst = MagicMock()
        inst.get.return_value = mock_resp
        inst.__enter__.return_value = inst
        inst.__exit__.return_value = None
        client_cls.return_value = inst

        out = tool_fetch_url(s, {"url": "https://corp.internal/"})
        self.assertIn("HTTP 200", out)
        self.assertIn("intranet", out)
