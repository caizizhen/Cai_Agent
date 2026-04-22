"""Regression tests for the reasoning-only / empty-content guard.

Triggered by LM Studio + Qwen3-reasoning style responses where
``choices[0].message.content`` is ``""`` and the entire model output ends up
in ``message.reasoning_content``. Before the fix the agent would crash on
``extract_json_object("")`` and spin ``max_iterations``; now the adapter
synthesises a ``{"type":"finish", ...}`` envelope so the graph stops cleanly
with an actionable diagnostic.
"""
from __future__ import annotations

import json
import unittest
from dataclasses import dataclass

import httpx

from cai_agent import llm as llm_mod
from cai_agent import llm_anthropic


@dataclass
class _OAISettings:
    base_url: str = "http://127.0.0.1:1234/v1"
    model: str = "qwen/qwen3.6-35b-a3b"
    api_key: str = "lm-studio"
    temperature: float = 0.2
    llm_timeout_sec: float = 30.0
    llm_max_http_retries: int = 50
    http_trust_env: bool = False
    mock: bool = False


def _mock_transport(payload: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    return httpx.MockTransport(handler)


class OpenAICompatEmptyContentTests(unittest.TestCase):
    """Reproduces the reported Qwen3-via-LM-Studio payload shape."""

    def setUp(self) -> None:
        llm_mod.reset_usage_counters()

    def _call(self, payload: dict) -> str:
        settings = _OAISettings()
        transport = _mock_transport(payload)
        timeout = httpx.Timeout(5.0, connect=1.0)
        # Patch httpx.Client constructor to inject our MockTransport.
        real_client = httpx.Client

        def fake_client(*args, **kwargs):
            kwargs["transport"] = transport
            kwargs.setdefault("timeout", timeout)
            return real_client(*args, **kwargs)

        llm_mod.httpx.Client = fake_client  # type: ignore[attr-defined]
        try:
            return llm_mod.chat_completion(settings, [{"role": "user", "content": "hi"}])
        finally:
            llm_mod.httpx.Client = real_client  # type: ignore[attr-defined]

    def test_reasoning_only_returns_finish_envelope(self) -> None:
        payload = {
            "id": "chatcmpl-x",
            "object": "chat.completion",
            "model": "qwen/qwen3.6-35b-a3b",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "reasoning_content": "让我想想…" * 500,
                        "tool_calls": [],
                    },
                    "finish_reason": "stop",
                },
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "completion_tokens_details": {"reasoning_tokens": 22858},
            },
        }
        out = self._call(payload)

        obj = json.loads(out)
        self.assertEqual(obj["type"], "finish")
        self.assertIn("empty-completion", obj["message"])
        self.assertIn("reasoning_tokens=22858", obj["message"])
        self.assertIn("finish_reason=stop", obj["message"])
        self.assertIn("reasoning", obj["message"])

    def test_empty_content_no_reasoning_returns_generic_advice(self) -> None:
        payload = {
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": None},
                    "finish_reason": "length",
                },
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 0, "total_tokens": 10},
        }
        out = self._call(payload)
        obj = json.loads(out)
        self.assertEqual(obj["type"], "finish")
        self.assertIn("empty-completion", obj["message"])
        self.assertIn("finish_reason=length", obj["message"])
        self.assertIn("上下文过长", obj["message"])

    def test_content_with_think_prefix_is_stripped(self) -> None:
        """DeepSeek-R1 via OpenAI-compat often embeds reasoning in <think>…</think>.

        The prefix should be stripped so downstream JSON parsing sees the real payload.
        """
        payload = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": (
                            '<think>let me think...\nstill thinking</think>\n'
                            '{"type":"finish","message":"done"}'
                        ),
                    },
                    "finish_reason": "stop",
                },
            ],
        }
        out = self._call(payload)
        self.assertEqual(out, '{"type":"finish","message":"done"}')

    def test_content_only_think_block_treated_as_empty(self) -> None:
        payload = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "<think>loop loop loop</think>   ",
                    },
                    "finish_reason": "stop",
                },
            ],
        }
        out = self._call(payload)
        obj = json.loads(out)
        self.assertEqual(obj["type"], "finish")
        self.assertIn("empty-completion", obj["message"])

    def test_list_shape_content_is_flattened(self) -> None:
        payload = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": '{"type":"finish",'},
                            {"type": "text", "text": '"message":"ok"}'},
                        ],
                    },
                    "finish_reason": "stop",
                },
            ],
        }
        out = self._call(payload)
        self.assertIn('"type":"finish"', out)
        self.assertIn('"message":"ok"', out)

    def test_result_can_be_parsed_by_extract_json_object(self) -> None:
        """End-to-end: the envelope produced by the guard must pass
        ``extract_json_object`` so ``graph.llm_node`` no longer crashes.
        """
        payload = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "reasoning_content": "stuck",
                    },
                    "finish_reason": "stop",
                },
            ],
        }
        out = self._call(payload)
        obj = llm_mod.extract_json_object(out)
        self.assertEqual(obj["type"], "finish")


class AnthropicEmptyContentTests(unittest.TestCase):
    """Anthropic side: empty text block should also degrade to a finish
    envelope instead of raising (which used to crash the graph)."""

    def test_empty_text_blocks_returns_finish_envelope(self) -> None:
        payload = {
            "id": "msg_abc",
            "type": "message",
            "role": "assistant",
            "stop_reason": "end_turn",
            "content": [],
            "usage": {"input_tokens": 5, "output_tokens": 0},
        }

        @dataclass
        class _AnthSettings:
            base_url: str = "https://api.anthropic.com"
            model: str = "claude-sonnet-4-5-20250929"
            api_key: str = "test"
            temperature: float = 0.2
            llm_timeout_sec: float = 30.0
            llm_max_http_retries: int = 50
            http_trust_env: bool = False
            mock: bool = False
            anthropic_version: str = "2023-06-01"
            anthropic_max_tokens: int = 512

        transport = _mock_transport(payload)
        out = llm_anthropic.chat_completion(
            _AnthSettings(),
            [{"role": "user", "content": "hi"}],
            transport=transport,
        )
        obj = json.loads(out)
        self.assertEqual(obj["type"], "finish")
        self.assertIn("empty-completion", obj["message"])
        self.assertIn("provider=Anthropic", obj["message"])
        self.assertIn("finish_reason=end_turn", obj["message"])


if __name__ == "__main__":
    unittest.main()
