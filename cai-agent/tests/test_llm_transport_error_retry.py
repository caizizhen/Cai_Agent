"""Regression tests for transport-level error retry in LLM adapters.

Covers the "Channel Error" class of failures where llama.cpp / any LLM backend
drops the TCP connection mid-request. These errors surface as
``httpx.TransportError`` subclasses (``RemoteProtocolError``, ``ReadError``,
``ConnectError``, etc.) rather than HTTP error responses.

Before this fix, a single ``httpx.TransportError`` propagated unhandled all
the way up and crashed the agent. After the fix:
- The retry count comes from ``[llm].max_http_retries`` / ``Settings.llm_max_http_retries``
  (default 50), overridable by env ``CAI_LLM_MAX_RETRIES`` (1..100).
- The retry loop uses that cap with exponential backoff.
- If the error clears before the last attempt the call succeeds normally.
- If all attempts fail, a descriptive ``RuntimeError`` is raised (which is
  then caught by ``graph.llm_node`` and turned into a graceful agent error).
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import httpx

from cai_agent import llm as llm_mod
from cai_agent import llm_anthropic
from cai_agent.config import Settings


@dataclass
class _OAISettings:
    base_url: str = "http://127.0.0.1:1234/v1"
    model: str = "google/gemma-4-31b"
    api_key: str = "test-key"
    temperature: float = 0.2
    llm_timeout_sec: float = 30.0
    llm_max_http_retries: int = 50
    http_trust_env: bool = False
    mock: bool = False


def _make_anthropic_settings(**overrides: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "provider": "anthropic",
        "base_url": "https://api.anthropic.com",
        "model": "claude-sonnet-4-5-20250929",
        "api_key": "test-anthropic-key",
        "temperature": 0.2,
        "llm_timeout_sec": 30.0,
        "llm_max_http_retries": 50,
        "http_trust_env": False,
        "mock": False,
        "anthropic_version": "2023-06-01",
        "anthropic_max_tokens": 256,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _good_oai_response() -> dict:
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": '{"type":"finish","message":"ok"}'},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 10, "total_tokens": 15},
    }


def _good_anthropic_response() -> dict:
    return {
        "content": [{"type": "text", "text": '{"type":"finish","message":"ok"}'}],
        "usage": {"input_tokens": 5, "output_tokens": 10},
    }


class OpenAICompatTransportErrorRetryTests(unittest.TestCase):
    """Tests for httpx.TransportError retry in the OpenAI-compat adapter."""

    def setUp(self) -> None:
        llm_mod.reset_usage_counters()
        self._real_client = httpx.Client

    def tearDown(self) -> None:
        httpx.Client = self._real_client  # type: ignore[misc]
        llm_mod.httpx.Client = self._real_client  # type: ignore[attr-defined]

    def _install_transport(self, transport: httpx.BaseTransport) -> None:
        real_cls = self._real_client

        def fake_client(*args, **kwargs):
            kwargs["transport"] = transport
            return real_cls(*args, **kwargs)

        llm_mod.httpx.Client = fake_client  # type: ignore[attr-defined]

    def test_transport_error_then_success_retries_and_succeeds(self) -> None:
        """First attempt raises RemoteProtocolError; second attempt succeeds."""
        calls = {"n": 0}

        class _OneFailTransport(httpx.BaseTransport):
            def handle_request(self, request: httpx.Request) -> httpx.Response:
                calls["n"] += 1
                if calls["n"] == 1:
                    raise httpx.RemoteProtocolError("Channel Error", request=request)
                return httpx.Response(200, json=_good_oai_response())

        self._install_transport(_OneFailTransport())
        with patch.object(llm_mod.time, "sleep", return_value=None):
            out = llm_mod.chat_completion(
                _OAISettings(),
                [{"role": "user", "content": "ping"}],
            )
        self.assertIn("finish", out)
        self.assertEqual(calls["n"], 2)

    def test_all_transport_errors_raises_runtime_error(self) -> None:
        """Repeated RemoteProtocolError raises RuntimeError after all attempts."""
        calls = {"n": 0}

        class _AlwaysFailTransport(httpx.BaseTransport):
            def handle_request(self, request: httpx.Request) -> httpx.Response:
                calls["n"] += 1
                raise httpx.RemoteProtocolError("Channel Error", request=request)

        self._install_transport(_AlwaysFailTransport())
        with patch.object(llm_mod.time, "sleep", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                llm_mod.chat_completion(
                    _OAISettings(),
                    [{"role": "user", "content": "ping"}],
                )
        self.assertEqual(calls["n"], llm_mod.llm_max_retries(_OAISettings()))
        self.assertIn("传输层错误", str(ctx.exception))

    def test_read_error_is_also_retried(self) -> None:
        """httpx.ReadError (a TransportError subclass) is also retried."""
        calls = {"n": 0}

        class _ReadErrorTransport(httpx.BaseTransport):
            def handle_request(self, request: httpx.Request) -> httpx.Response:
                calls["n"] += 1
                if calls["n"] < 3:
                    raise httpx.ReadError("connection reset", request=request)
                return httpx.Response(200, json=_good_oai_response())

        self._install_transport(_ReadErrorTransport())
        with patch.object(llm_mod.time, "sleep", return_value=None):
            out = llm_mod.chat_completion(
                _OAISettings(),
                [{"role": "user", "content": "ping"}],
            )
        self.assertIn("finish", out)
        self.assertEqual(calls["n"], 3)

    def test_invalid_json_response_is_retried_then_succeeds(self) -> None:
        """HTTP 200 with malformed/truncated JSON should also be retried."""
        calls = {"n": 0}

        class _InvalidJsonThenOk(httpx.BaseTransport):
            def handle_request(self, request: httpx.Request) -> httpx.Response:
                calls["n"] += 1
                if calls["n"] == 1:
                    # Simulate server-side channel break / truncated payload:
                    # status is 200 but body is not valid JSON.
                    return httpx.Response(
                        200,
                        content=b'{"choices":[{"message":{"role":"assistant","content":"',
                    )
                return httpx.Response(200, json=_good_oai_response())

        self._install_transport(_InvalidJsonThenOk())
        with patch.object(llm_mod.time, "sleep", return_value=None):
            out = llm_mod.chat_completion(
                _OAISettings(),
                [{"role": "user", "content": "ping"}],
            )
        self.assertIn("finish", out)
        self.assertEqual(calls["n"], 2)


class AnthropicTransportErrorRetryTests(unittest.TestCase):
    """Tests for httpx.TransportError retry in the Anthropic adapter."""

    def setUp(self) -> None:
        llm_mod.reset_usage_counters()
        llm_anthropic._DEFAULT_TRANSPORT = None

    def tearDown(self) -> None:
        llm_anthropic._DEFAULT_TRANSPORT = None

    def test_transport_error_then_success_retries_and_succeeds(self) -> None:
        calls = {"n": 0}

        class _OneFailTransport(httpx.BaseTransport):
            def handle_request(self, request: httpx.Request) -> httpx.Response:
                calls["n"] += 1
                if calls["n"] == 1:
                    raise httpx.RemoteProtocolError("Channel Error", request=request)
                return httpx.Response(200, json=_good_anthropic_response())

        with patch.object(llm_anthropic.time, "sleep", return_value=None):
            out = llm_anthropic.chat_completion(
                _make_anthropic_settings(),
                [{"role": "user", "content": "ping"}],
                transport=_OneFailTransport(),
            )
        self.assertIn("finish", out)
        self.assertEqual(calls["n"], 2)

    def test_all_transport_errors_raises_runtime_error(self) -> None:
        calls = {"n": 0}

        class _AlwaysFailTransport(httpx.BaseTransport):
            def handle_request(self, request: httpx.Request) -> httpx.Response:
                calls["n"] += 1
                raise httpx.RemoteProtocolError("Channel Error", request=request)

        with patch.object(llm_anthropic.time, "sleep", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                llm_anthropic.chat_completion(
                    _make_anthropic_settings(),
                    [{"role": "user", "content": "ping"}],
                    transport=_AlwaysFailTransport(),
                )
        self.assertEqual(calls["n"], llm_mod.llm_max_retries(_make_anthropic_settings()))
        self.assertIn("传输层错误", str(ctx.exception))

    def test_invalid_json_response_is_retried_then_succeeds(self) -> None:
        calls = {"n": 0}

        class _InvalidJsonThenOk(httpx.BaseTransport):
            def handle_request(self, request: httpx.Request) -> httpx.Response:
                calls["n"] += 1
                if calls["n"] == 1:
                    return httpx.Response(200, content=b'{"content":[{"type":"text","text":"')
                return httpx.Response(200, json=_good_anthropic_response())

        with patch.object(llm_anthropic.time, "sleep", return_value=None):
            out = llm_anthropic.chat_completion(
                _make_anthropic_settings(),
                [{"role": "user", "content": "ping"}],
                transport=_InvalidJsonThenOk(),
            )
        self.assertIn("finish", out)
        self.assertEqual(calls["n"], 2)


class LlmMaxRetriesEnvTests(unittest.TestCase):
    """Retry cap: TOML ``[llm].max_http_retries`` / env ``CAI_LLM_MAX_RETRIES``."""

    def tearDown(self) -> None:
        os.environ.pop("CAI_LLM_MAX_RETRIES", None)

    def test_llm_max_retries_default_no_settings(self) -> None:
        os.environ.pop("CAI_LLM_MAX_RETRIES", None)
        self.assertEqual(llm_mod.llm_max_retries(None), 50)

    def test_llm_max_retries_from_settings(self) -> None:
        os.environ.pop("CAI_LLM_MAX_RETRIES", None)
        self.assertEqual(llm_mod.llm_max_retries(_OAISettings(llm_max_http_retries=12)), 12)

    def test_llm_max_retries_from_env_overrides_settings(self) -> None:
        os.environ["CAI_LLM_MAX_RETRIES"] = "8"
        self.assertEqual(llm_mod.llm_max_retries(_OAISettings(llm_max_http_retries=99)), 8)

    def test_llm_max_retries_invalid_env_falls_back_to_settings(self) -> None:
        os.environ["CAI_LLM_MAX_RETRIES"] = "not-a-number"
        self.assertEqual(llm_mod.llm_max_retries(_OAISettings(llm_max_http_retries=7)), 7)

    def test_settings_from_toml_max_http_retries(self) -> None:
        os.environ.pop("CAI_LLM_MAX_RETRIES", None)
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "cai-agent.toml"
            cfg.write_text(
                '[llm]\nprovider = "openai_compatible"\n'
                'base_url = "http://127.0.0.1:9/v1"\nmodel = "m"\n'
                'api_key = "k"\nmax_http_retries = 33\n',
                encoding="utf-8",
            )
            s = Settings.from_env(config_path=str(cfg))
            self.assertEqual(s.llm_max_http_retries, 33)
            self.assertEqual(llm_mod.llm_max_retries(s), 33)

    def test_llm_max_retries_clamped(self) -> None:
        os.environ["CAI_LLM_MAX_RETRIES"] = "0"
        self.assertEqual(llm_mod.llm_max_retries(_OAISettings()), 1)
        os.environ["CAI_LLM_MAX_RETRIES"] = "150"
        self.assertEqual(llm_mod.llm_max_retries(_OAISettings()), 100)

    def test_transport_errors_respect_env_retry_count(self) -> None:
        """3 attempts when CAI_LLM_MAX_RETRIES=3."""
        os.environ["CAI_LLM_MAX_RETRIES"] = "3"
        llm_mod.reset_usage_counters()
        calls = {"n": 0}

        class _AlwaysFailTransport(httpx.BaseTransport):
            def handle_request(self, request: httpx.Request) -> httpx.Response:
                calls["n"] += 1
                raise httpx.RemoteProtocolError("Channel Error", request=request)

        real_cls = httpx.Client

        def fake_client(*args, **kwargs):
            kwargs["transport"] = _AlwaysFailTransport()
            return real_cls(*args, **kwargs)

        llm_mod.httpx.Client = fake_client  # type: ignore[attr-defined]
        try:
            with patch.object(llm_mod.time, "sleep", return_value=None):
                with self.assertRaises(RuntimeError) as ctx:
                    llm_mod.chat_completion(
                        _OAISettings(),
                        [{"role": "user", "content": "ping"}],
                    )
        finally:
            llm_mod.httpx.Client = real_cls  # type: ignore[attr-defined]

        self.assertEqual(calls["n"], 3)
        self.assertIn("已重试 3 次", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
