"""Tests for the context-length progress bar feature.

The UI needs three data points to render a fill bar:
1. ``Settings.context_window`` — model's context window, resolved from
   (a) the active profile's ``context_window`` field, or
   (b) the ``[llm].context_window`` TOML fallback, or
   (c) a conservative default of 8192.
2. ``get_last_usage()["prompt_tokens"]`` — authoritative context size after
   each real API response (updated by both OpenAI-compat and Anthropic adapters).
3. ``estimate_tokens_from_messages()`` — CJK-aware fallback (CJK ~1.5 chars/token,
   ASCII ~4) used before the first real response and after Enter until usage arrives.

On top of that, ``graph.llm_node`` must emit a ``phase="usage"`` progress
event after every LLM call so the TUI can update in real time (not only
when the whole turn finishes).
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import httpx

from cai_agent import llm as llm_mod
from cai_agent import llm_anthropic
from cai_agent.config import Settings
from cai_agent.profiles import (
    PRESETS,
    Profile,
    apply_preset,
    build_profile,
    profile_to_public_dict,
    serialize_models_block,
)


class ContextWindowResolutionTests(unittest.TestCase):
    """Settings.context_window resolves from profile → [llm] → default."""

    def _write_toml(self, text: str) -> Path:
        tmp = Path(tempfile.mkdtemp(prefix="cai-ctxwin-")) / "cai-agent.toml"
        tmp.write_text(text, encoding="utf-8")
        return tmp

    def test_default_when_nothing_configured(self) -> None:
        path = self._write_toml(
            """
[llm]
provider = "openai_compatible"
base_url = "http://localhost:1234/v1"
model = "local/model"
api_key = "x"
            """,
        )
        s = Settings.from_sources(config_path=str(path))
        self.assertEqual(s.context_window, 8192)
        self.assertEqual(s.context_window_source, "default")

    def test_llm_section_overrides_default(self) -> None:
        path = self._write_toml(
            """
[llm]
provider = "openai_compatible"
base_url = "http://localhost:1234/v1"
model = "local/model"
api_key = "x"
context_window = 32768
            """,
        )
        s = Settings.from_sources(config_path=str(path))
        self.assertEqual(s.context_window, 32768)
        self.assertEqual(s.context_window_source, "llm")

    def test_env_overrides_llm_section(self) -> None:
        """CAI_CONTEXT_WINDOW 必须覆盖 [llm]，并被标记为 env 来源。"""
        import os
        path = self._write_toml(
            """
[llm]
provider = "openai_compatible"
base_url = "http://localhost:1234/v1"
model = "m"
api_key = "x"
context_window = 32768
            """,
        )
        old = os.environ.get("CAI_CONTEXT_WINDOW")
        os.environ["CAI_CONTEXT_WINDOW"] = "16384"
        try:
            s = Settings.from_sources(config_path=str(path))
            self.assertEqual(s.context_window, 16384)
            self.assertEqual(s.context_window_source, "env")
        finally:
            if old is None:
                os.environ.pop("CAI_CONTEXT_WINDOW", None)
            else:
                os.environ["CAI_CONTEXT_WINDOW"] = old

    def test_profile_overrides_llm_section(self) -> None:
        path = self._write_toml(
            """
[llm]
provider = "openai_compatible"
base_url = "http://localhost:1234/v1"
model = "fallback"
api_key = "x"
context_window = 8192

[models]
active = "p1"

[[models.profile]]
id = "p1"
provider = "openai_compatible"
base_url = "http://localhost:1234/v1"
model = "local/model"
api_key = "x"
context_window = 128000
            """,
        )
        s = Settings.from_sources(config_path=str(path))
        self.assertEqual(s.context_window, 128000)
        self.assertEqual(s.context_window_source, "profile")

    def test_bounds_are_clamped(self) -> None:
        """Absurd values must not propagate; clamp into [256, 10_000_000]."""
        path = self._write_toml(
            """
[llm]
provider = "openai_compatible"
base_url = "http://localhost:1234/v1"
model = "m"
api_key = "x"
context_window = 1
            """,
        )
        s = Settings.from_sources(config_path=str(path))
        self.assertEqual(s.context_window, 256)
        self.assertEqual(s.context_window_source, "llm")

    def test_profile_toml_roundtrip_preserves_context_window(self) -> None:
        raw = {
            "id": "p1",
            "provider": "openai_compatible",
            "base_url": "http://localhost:1234/v1",
            "model": "m",
            "api_key": "x",
            "context_window": 65536,
        }
        p = build_profile(raw)
        self.assertEqual(p.context_window, 65536)
        block = serialize_models_block([p], active="p1")
        self.assertIn("context_window = 65536", block)
        pub = profile_to_public_dict(p)
        self.assertEqual(pub["context_window"], 65536)


class LastUsageSnapshotTests(unittest.TestCase):
    """``get_last_usage()`` must be overwritten (not accumulated) per call."""

    def setUp(self) -> None:
        llm_mod.reset_usage_counters()

    def _call_openai(self, payload: dict) -> str:
        class _S:
            base_url = "http://127.0.0.1:1234/v1"
            model = "m"
            api_key = "k"
            temperature = 0.2
            llm_timeout_sec = 30.0
            llm_max_http_retries = 50
            http_trust_env = False
            mock = False

        def handler(_req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=payload)

        transport = httpx.MockTransport(handler)
        real_client = httpx.Client

        def fake_client(*args, **kwargs):
            kwargs["transport"] = transport
            return real_client(*args, **kwargs)

        llm_mod.httpx.Client = fake_client  # type: ignore[attr-defined]
        try:
            return llm_mod.chat_completion(_S(), [{"role": "user", "content": "hi"}])
        finally:
            llm_mod.httpx.Client = real_client  # type: ignore[attr-defined]

    def test_openai_records_last_usage(self) -> None:
        self._call_openai({
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"prompt_tokens": 123, "completion_tokens": 45, "total_tokens": 168},
        })
        snap = llm_mod.get_last_usage()
        self.assertEqual(snap["prompt_tokens"], 123)
        self.assertEqual(snap["completion_tokens"], 45)
        self.assertEqual(snap["total_tokens"], 168)

    def test_second_call_overwrites_not_accumulates(self) -> None:
        self._call_openai({
            "choices": [{"message": {"role": "assistant", "content": "a"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110},
        })
        self._call_openai({
            "choices": [{"message": {"role": "assistant", "content": "b"}}],
            "usage": {"prompt_tokens": 500, "completion_tokens": 20, "total_tokens": 520},
        })
        snap = llm_mod.get_last_usage()
        # Last snapshot is overwritten — reflects "what's in the model's context NOW".
        self.assertEqual(snap["prompt_tokens"], 500)
        self.assertEqual(snap["completion_tokens"], 20)
        # Cumulative counters still accumulate — they are a separate API.
        cum = llm_mod.get_usage_counters()
        self.assertEqual(cum["prompt_tokens"], 600)

    def test_anthropic_records_last_usage(self) -> None:
        payload = {
            "content": [{"type": "text", "text": "ok"}],
            "usage": {"input_tokens": 77, "output_tokens": 33},
        }

        def handler(_req: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=payload)

        class _S:
            base_url = "https://api.anthropic.com"
            model = "claude"
            api_key = "k"
            temperature = 0.2
            llm_timeout_sec = 30.0
            llm_max_http_retries = 50
            http_trust_env = False
            mock = False
            anthropic_version = "2023-06-01"
            anthropic_max_tokens = 512

        llm_anthropic.chat_completion(
            _S(), [{"role": "user", "content": "hi"}],
            transport=httpx.MockTransport(handler),
        )
        snap = llm_mod.get_last_usage()
        self.assertEqual(snap["prompt_tokens"], 77)
        self.assertEqual(snap["completion_tokens"], 33)
        self.assertEqual(snap["total_tokens"], 110)

    def test_reset_clears_last_snapshot(self) -> None:
        self._call_openai({
            "choices": [{"message": {"role": "assistant", "content": "x"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11},
        })
        self.assertGreater(llm_mod.get_last_usage()["prompt_tokens"], 0)
        llm_mod.reset_usage_counters()
        self.assertEqual(llm_mod.get_last_usage()["prompt_tokens"], 0)


class EstimateTokensTests(unittest.TestCase):
    def test_empty_list(self) -> None:
        self.assertEqual(llm_mod.estimate_tokens_from_messages([]), 0)

    def test_non_list_returns_zero(self) -> None:
        self.assertEqual(llm_mod.estimate_tokens_from_messages("not a list"), 0)  # type: ignore[arg-type]

    def test_rough_ratio_one_token_per_four_chars(self) -> None:
        msgs = [{"role": "user", "content": "a" * 400}]
        est = llm_mod.estimate_tokens_from_messages(msgs)
        # 400 ASCII chars / 4 = 100, plus a small per-message overhead (~1 token)
        self.assertGreaterEqual(est, 100)
        self.assertLess(est, 110)

    def test_handles_list_content_shape(self) -> None:
        msgs = [
            {"role": "assistant", "content": [
                {"type": "text", "text": "x" * 20},
                {"type": "text", "text": "y" * 20},
            ]},
        ]
        est = llm_mod.estimate_tokens_from_messages(msgs)
        self.assertGreater(est, 0)

    def test_cjk_is_denser_than_ascii(self) -> None:
        """400 个中文字应该比 400 个 ASCII 字符估出更多 tokens —
        老的 chars/4 会严重低估中文场景（实际 tokenizer ≈ 1.5 chars/token）。"""
        zh = [{"role": "user", "content": "你" * 400}]
        en = [{"role": "user", "content": "a" * 400}]
        est_zh = llm_mod.estimate_tokens_from_messages(zh)
        est_en = llm_mod.estimate_tokens_from_messages(en)
        # CJK 分支：400 / 1.5 ≈ 267；ASCII 分支：400 / 4 = 100。差距 > 2x。
        self.assertGreater(est_zh, est_en * 2)
        self.assertGreaterEqual(est_zh, 260)
        self.assertLess(est_zh, 280)

    def test_mixed_cjk_and_ascii(self) -> None:
        """混合场景按字符分类分别算，不会整段一刀切。"""
        msgs = [{"role": "user", "content": "你好 hello " * 40}]
        # 每段 10 字符：2 CJK + 1 space + 5 ASCII + 1 space + 1 halfwidth space = 10 chars
        # 具体分布无所谓，只断言不抛异常、给出正数、且落在合理区间。
        est = llm_mod.estimate_tokens_from_messages(msgs)
        self.assertGreater(est, 100)
        self.assertLess(est, 300)

    def test_japanese_hiragana_counts_as_cjk(self) -> None:
        msgs = [{"role": "user", "content": "こんにちは" * 100}]  # 500 hiragana
        est = llm_mod.estimate_tokens_from_messages(msgs)
        # 500 / 1.5 ≈ 333
        self.assertGreater(est, 300)
        self.assertLess(est, 360)

    def test_korean_hangul_counts_as_cjk(self) -> None:
        msgs = [{"role": "user", "content": "안녕하세요" * 100}]  # 500 hangul
        est = llm_mod.estimate_tokens_from_messages(msgs)
        self.assertGreater(est, 300)
        self.assertLess(est, 360)


class GraphEmitsUsageTests(unittest.TestCase):
    """graph.llm_node must emit a phase='usage' payload after every LLM call."""

    def test_usage_phase_is_emitted_with_context_window(self) -> None:
        from types import SimpleNamespace
        from cai_agent import graph as graph_mod

        # Stub the role-based LLM call — no HTTP, just pretend we got a finish
        # reply and prime ``get_last_usage`` ourselves.
        llm_mod.reset_usage_counters()

        def _fake_chat(settings, messages, *, role="active", route_conversation_phase=None):
            llm_mod._record_last_usage(
                prompt_tokens=1234, completion_tokens=56, total_tokens=1290,
            )
            return '{"type":"finish","message":"done"}'

        captured: list[dict] = []

        def sink(payload):
            captured.append(dict(payload))

        original = graph_mod.chat_completion_by_role
        graph_mod.chat_completion_by_role = _fake_chat
        try:
            settings = SimpleNamespace(
                max_iterations=8,
                context_compact_after_iterations=0,
                context_compact_min_messages=8,
                workspace=".",
                provider="openai_compatible",
                context_window=32768,
            )
            app = graph_mod.build_app(settings, progress=sink)
            state = {
                "messages": [
                    {"role": "system", "content": "s"},
                    {"role": "user", "content": "hi"},
                ],
                "iteration": 0,
                "pending": None,
                "finished": False,
            }
            app.invoke(state)
        finally:
            graph_mod.chat_completion_by_role = original

        usages = [p for p in captured if p.get("phase") == "usage"]
        self.assertGreaterEqual(len(usages), 1)
        u = usages[0]
        self.assertEqual(u["prompt_tokens"], 1234)
        self.assertEqual(u["completion_tokens"], 56)
        self.assertEqual(u["context_window"], 32768)


class PresetAndSynthesizeDefaultsTests(unittest.TestCase):
    def test_synthesize_default_infers_hosted_provider_context_window(self) -> None:
        from cai_agent.profiles import synthesize_default_profile

        p = synthesize_default_profile(
            provider="openai_compatible",
            base_url="https://api.openai.com/v1",
            model="gpt-4o",
            api_key="x",
            temperature=0.2,
            timeout_sec=120.0,
        )
        self.assertEqual(p.context_window, 128000)

    def test_synthesize_default_keeps_local_provider_context_window_unknown(self) -> None:
        from cai_agent.profiles import synthesize_default_profile

        p = synthesize_default_profile(
            provider="openai_compatible",
            base_url="http://localhost:1234/v1",
            model="m",
            api_key="x",
            temperature=0.2,
            timeout_sec=120.0,
        )
        self.assertIsNone(p.context_window)

    def test_preset_apply_does_not_inject_context_window(self) -> None:
        """Presets intentionally do not pin context_window, leaving it to the
        user's TOML so we never misreport a value for a model they swap in."""
        merged = apply_preset({"id": "p1", "model": "gpt-4o"}, "openai")
        self.assertNotIn("context_window", merged)


if __name__ == "__main__":
    unittest.main()
