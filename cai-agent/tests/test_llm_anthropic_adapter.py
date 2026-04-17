"""Tests for the Anthropic native adapter (M10 skeleton).

All HTTP traffic is routed through :class:`httpx.MockTransport`.  We
set both the ``transport=`` kwarg and the legacy module-level
``_DEFAULT_TRANSPORT`` fallback so the test double is installed no
matter which path the adapter consults.  No new dependency, no network
egress.  ``SimpleNamespace`` stands in for ``Settings`` because we only
need a handful of attributes and building a real ``Settings`` would
require Dev A's full M1/M2 projection.
"""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from typing import Any

import httpx

from cai_agent import llm as openai_llm
from cai_agent import llm_anthropic


def _make_settings(**overrides: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "provider": "anthropic",
        # Dev A's ``project_base_url`` strips ``/v1`` for anthropic
        # profiles; the adapter must also cope with a trailing ``/v1``
        # for callers that skip the projection step.  Default to the
        # post-projection shape (host root) and cover the other case in
        # its own test.
        "base_url": "https://api.anthropic.com",
        "model": "claude-sonnet-4-5-20250929",
        "api_key": "test-anthropic-key",
        "temperature": 0.2,
        "llm_timeout_sec": 30.0,
        "http_trust_env": False,
        "mock": False,
        "anthropic_version": "2023-06-01",
        "anthropic_max_tokens": 256,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class AnthropicAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        openai_llm.reset_usage_counters()
        self._captured: list[httpx.Request] = []
        llm_anthropic._DEFAULT_TRANSPORT = None

    def tearDown(self) -> None:
        llm_anthropic._DEFAULT_TRANSPORT = None

    def _mock_transport(self, responder: Any) -> httpx.MockTransport:
        def _wrap(request: httpx.Request) -> httpx.Response:
            self._captured.append(request)
            return responder(request)

        return httpx.MockTransport(_wrap)

    def test_happy_path_request_and_parse(self) -> None:
        def responder(_req: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "id": "msg_01",
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {"type": "text", "text": "hello "},
                        {"type": "text", "text": "world"},
                    ],
                    "usage": {"input_tokens": 12, "output_tokens": 5},
                },
            )

        settings = _make_settings()
        out = llm_anthropic.chat_completion(
            settings,
            [
                {"role": "system", "content": "be concise"},
                {"role": "user", "content": "say hi"},
            ],
            transport=self._mock_transport(responder),
        )
        self.assertEqual(out, "hello world")

        self.assertEqual(len(self._captured), 1)
        req = self._captured[0]
        self.assertEqual(req.method, "POST")
        self.assertEqual(str(req.url), "https://api.anthropic.com/v1/messages")
        self.assertEqual(req.headers["x-api-key"], "test-anthropic-key")
        self.assertEqual(req.headers["anthropic-version"], "2023-06-01")
        self.assertIn("application/json", req.headers["content-type"].lower())

        body = json.loads(req.content.decode("utf-8"))
        self.assertEqual(body["model"], settings.model)
        self.assertEqual(body["system"], "be concise")
        self.assertEqual(body["max_tokens"], 256)
        self.assertEqual(body["temperature"], 0.2)
        self.assertEqual(
            body["messages"], [{"role": "user", "content": "say hi"}],
        )
        for turn in body["messages"]:
            self.assertIn(turn["role"], ("user", "assistant"))

        # usage counters live in ``cai_agent.llm`` so all adapters share them.
        usage = openai_llm.get_usage_counters()
        self.assertEqual(usage["prompt_tokens"], 12)
        self.assertEqual(usage["completion_tokens"], 5)
        self.assertEqual(usage["total_tokens"], 17)

    def test_base_url_with_trailing_v1_still_yields_v1_messages(self) -> None:
        def responder(_req: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "ok"}],
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                },
            )

        settings = _make_settings(base_url="https://api.anthropic.com/v1")
        out = llm_anthropic.chat_completion(
            settings,
            [{"role": "user", "content": "hi"}],
            transport=self._mock_transport(responder),
        )
        self.assertEqual(out, "ok")
        self.assertEqual(
            str(self._captured[0].url), "https://api.anthropic.com/v1/messages",
        )

    def test_tool_role_becomes_user_with_prefix(self) -> None:
        """Tool results stay in their own turn (no adjacent merge) and
        gain a ``[tool:<name>]`` prefix so the model can identify the
        boundary without inventing an Anthropic tool_result schema."""

        def responder(_req: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "ok"}],
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                },
            )

        llm_anthropic.chat_completion(
            _make_settings(),
            [
                {"role": "system", "content": "sys1"},
                {"role": "system", "content": "sys2"},
                {"role": "user", "content": "hi"},
                {"role": "tool", "name": "run_shell", "content": "listing"},
                {"role": "assistant", "content": "seen"},
            ],
            transport=self._mock_transport(responder),
        )

        body = json.loads(self._captured[0].content.decode("utf-8"))
        self.assertEqual(body["system"], "sys1\n\nsys2")
        roles = [m["role"] for m in body["messages"]]
        self.assertEqual(roles, ["user", "user", "assistant"])
        self.assertEqual(body["messages"][0]["content"], "hi")
        self.assertIn("[tool:run_shell]", body["messages"][1]["content"])
        self.assertIn("listing", body["messages"][1]["content"])
        self.assertEqual(body["messages"][2]["content"], "seen")

    def test_first_assistant_gets_placeholder_user_prepended(self) -> None:
        def responder(_req: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "ok"}],
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                },
            )

        llm_anthropic.chat_completion(
            _make_settings(),
            [
                {"role": "assistant", "content": "I was mid-sentence"},
                {"role": "user", "content": "continue"},
            ],
            transport=self._mock_transport(responder),
        )
        body = json.loads(self._captured[0].content.decode("utf-8"))
        roles = [m["role"] for m in body["messages"]]
        self.assertEqual(roles[0], "user")
        self.assertEqual(len(roles), 3)

    def test_max_tokens_prefers_anthropic_field_over_legacy(self) -> None:
        def responder(_req: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "x"}],
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                },
            )

        settings = _make_settings(
            anthropic_max_tokens=512,
            max_tokens=9999,
        )
        llm_anthropic.chat_completion(
            settings,
            [{"role": "user", "content": "hi"}],
            transport=self._mock_transport(responder),
        )
        body = json.loads(self._captured[0].content.decode("utf-8"))
        self.assertEqual(body["max_tokens"], 512)

    def test_max_tokens_falls_back_to_legacy_then_default(self) -> None:
        def responder(_req: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "x"}],
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                },
            )

        settings = _make_settings()
        # Simulate pre-M2 Settings: new field absent, legacy field present.
        del settings.anthropic_max_tokens
        settings.max_tokens = 128
        llm_anthropic.chat_completion(
            settings,
            [{"role": "user", "content": "hi"}],
            transport=self._mock_transport(responder),
        )
        body = json.loads(self._captured[0].content.decode("utf-8"))
        self.assertEqual(body["max_tokens"], 128)

    def test_retry_on_429_then_success(self) -> None:
        calls = {"n": 0}

        def responder(_req: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(
                    429, json={"error": {"type": "rate_limit_error"}},
                )
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "retried"}],
                    "usage": {"input_tokens": 2, "output_tokens": 3},
                },
            )

        transport = self._mock_transport(responder)

        original_sleep = llm_anthropic.time.sleep
        llm_anthropic.time.sleep = lambda _s: None
        try:
            out = llm_anthropic.chat_completion(
                _make_settings(),
                [{"role": "user", "content": "ping"}],
                transport=transport,
            )
        finally:
            llm_anthropic.time.sleep = original_sleep

        self.assertEqual(out, "retried")
        self.assertEqual(calls["n"], 2)

    def test_non_retryable_error_raises(self) -> None:
        def responder(_req: httpx.Request) -> httpx.Response:
            return httpx.Response(
                401, json={"error": {"type": "authentication_error"}},
            )

        with self.assertRaises(RuntimeError) as ctx:
            llm_anthropic.chat_completion(
                _make_settings(),
                [{"role": "user", "content": "hi"}],
                transport=self._mock_transport(responder),
            )
        self.assertIn("401", str(ctx.exception))

    def test_no_text_content_returns_finish_envelope(self) -> None:
        """Contract change (2026-04): an Anthropic response containing only
        non-text blocks (e.g. ``tool_use``) no longer raises. Instead we
        synthesise a ``{"type":"finish", ...}`` envelope so the graph can
        surface the problem to the user and stop cleanly — matching the
        behaviour of the OpenAI-compat adapter's empty-content guard.
        """
        def responder(_req: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "tool_use", "name": "x", "input": {}}],
                    "stop_reason": "tool_use",
                    "usage": {"input_tokens": 1, "output_tokens": 0},
                },
            )

        out = llm_anthropic.chat_completion(
            _make_settings(),
            [{"role": "user", "content": "hi"}],
            transport=self._mock_transport(responder),
        )
        obj = json.loads(out)
        self.assertEqual(obj["type"], "finish")
        self.assertIn("empty-completion", obj["message"])
        self.assertIn("provider=Anthropic", obj["message"])

    def test_missing_content_array_returns_finish_envelope(self) -> None:
        def responder(_req: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, json={"usage": {"input_tokens": 1, "output_tokens": 0}},
            )

        out = llm_anthropic.chat_completion(
            _make_settings(),
            [{"role": "user", "content": "hi"}],
            transport=self._mock_transport(responder),
        )
        obj = json.loads(out)
        self.assertEqual(obj["type"], "finish")
        self.assertIn("empty-completion", obj["message"])

    def test_mock_mode_shortcircuits(self) -> None:
        settings = _make_settings(mock=True)
        out = llm_anthropic.chat_completion(
            settings, [{"role": "user", "content": "hi"}],
        )
        self.assertIn("finish", out)

    def test_default_transport_is_used_when_kwarg_absent(self) -> None:
        """Legacy test-double path: callers that can't reach the kwarg
        (e.g. code that still goes through the plain ``chat_completion``
        import) can install a transport via the module variable."""

        def responder(_req: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "text", "text": "via-default"}],
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                },
            )

        llm_anthropic._DEFAULT_TRANSPORT = self._mock_transport(responder)
        try:
            out = llm_anthropic.chat_completion(
                _make_settings(),
                [{"role": "user", "content": "hi"}],
            )
        finally:
            llm_anthropic._DEFAULT_TRANSPORT = None
        self.assertEqual(out, "via-default")


if __name__ == "__main__":
    unittest.main()
