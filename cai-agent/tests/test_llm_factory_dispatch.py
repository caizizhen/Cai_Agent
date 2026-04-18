"""Tests for the provider dispatch factory (M11 skeleton).

The v5 factory exposes four public names:

* ``resolve_provider(settings)`` — canonicalise ``active_profile_provider``
  (priority) or ``provider`` into a well-known key.
* ``chat_completion(settings, messages)`` — pure dispatch, no profile
  projection; the caller is expected to have already put the right
  ``provider`` / ``model`` / ``base_url`` on ``settings``.
* ``resolve_role_profile(settings, role)`` — pick the :class:`Profile`
  for ``active / subagent / planner`` with a graceful fallback.
* ``chat_completion_by_role(settings, messages, *, role=...)`` —
  high-level: pick profile → project settings → dispatch.  Used by the
  Sprint 2 graph/workflow hookup.

Adapter stubs are installed by rebinding ``chat_completion`` on the
module aliases that the factory imported (``_openai_adapter`` /
``_anthropic_adapter``) so no real HTTP is ever issued.
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass, replace as dc_replace
from types import SimpleNamespace
from typing import Any

from cai_agent import llm_factory
from cai_agent.profiles import Profile


@dataclass
class _MockSettings:
    """Dataclass mirror required by ``chat_completion_by_role`` because
    ``_project_settings_for_profile`` uses ``dataclasses.replace``."""

    provider: str
    base_url: str
    model: str
    api_key: str
    temperature: float
    llm_timeout_sec: float
    http_trust_env: bool
    mock: bool
    profiles: tuple[Profile, ...]
    active_profile_id: str
    subagent_profile_id: str | None
    planner_profile_id: str | None
    active_api_key_env: str | None
    anthropic_version: str
    anthropic_max_tokens: int
    context_window: int = 8192
    context_window_source: str = "llm"


_ANTHROPIC_P = Profile(
    id="anthro",
    provider="anthropic",
    base_url="https://api.anthropic.com",
    model="claude-sonnet-4-5-20250929",
    api_key_env=None,
    api_key="test-anthro-key",
    temperature=0.2,
    timeout_sec=120.0,
    anthropic_version="2023-06-01",
    max_tokens=512,
)

_OPENAI_P = Profile(
    id="oai",
    provider="openai",
    base_url="https://api.openai.com/v1",
    model="gpt-4o",
    api_key_env=None,
    api_key="test-oai-key",
    temperature=0.3,
    timeout_sec=60.0,
)

_LOCAL_P = Profile(
    id="local",
    provider="openai_compatible",
    base_url="http://localhost:1234/v1",
    model="qwen2.5-coder-7b",
    api_key_env=None,
    api_key="local-key",
    temperature=0.1,
    timeout_sec=60.0,
)


def _make_settings(
    profiles: tuple[Profile, ...],
    *,
    active: str,
    subagent: str | None = None,
    planner: str | None = None,
) -> _MockSettings:
    active_profile = next(p for p in profiles if p.id == active)
    cw = int(active_profile.context_window or 8192)
    cws = "profile" if active_profile.context_window else "llm"
    return _MockSettings(
        provider=active_profile.provider,
        base_url=active_profile.base_url,
        model=active_profile.model,
        api_key=active_profile.resolve_api_key() or "seed-key",
        temperature=active_profile.temperature,
        llm_timeout_sec=active_profile.timeout_sec,
        http_trust_env=False,
        mock=False,
        profiles=profiles,
        active_profile_id=active,
        subagent_profile_id=subagent,
        planner_profile_id=planner,
        active_api_key_env=active_profile.api_key_env,
        anthropic_version=active_profile.anthropic_version or "2023-06-01",
        anthropic_max_tokens=int(active_profile.max_tokens or 4096),
        context_window=cw,
        context_window_source=cws,
    )


class _AdapterStubMixin:
    """Install fake ``chat_completion`` on both adapter modules and
    restore them on teardown.  Mixed into unittest.TestCase subclasses
    via ``setUp`` / ``tearDown`` delegation."""

    def _install_adapter_stubs(self) -> None:
        self._orig_openai = llm_factory._openai_adapter.chat_completion
        self._orig_anthropic = llm_factory._anthropic_adapter.chat_completion
        self._openai_calls: list[tuple[Any, Any]] = []
        self._anthropic_calls: list[tuple[Any, Any]] = []

        def fake_openai(settings: Any, messages: list[dict[str, Any]]) -> str:
            self._openai_calls.append((settings, messages))
            return "OPENAI_OK"

        def fake_anthropic(
            settings: Any, messages: list[dict[str, Any]],
        ) -> str:
            self._anthropic_calls.append((settings, messages))
            return "ANTHROPIC_OK"

        llm_factory._openai_adapter.chat_completion = fake_openai
        llm_factory._anthropic_adapter.chat_completion = fake_anthropic

    def _restore_adapters(self) -> None:
        llm_factory._openai_adapter.chat_completion = self._orig_openai
        llm_factory._anthropic_adapter.chat_completion = self._orig_anthropic


class ResolveProviderTests(unittest.TestCase):
    def test_anthropic_canonical(self) -> None:
        self.assertEqual(
            llm_factory.resolve_provider(SimpleNamespace(provider="anthropic")),
            "anthropic",
        )

    def test_anthropic_case_insensitive(self) -> None:
        self.assertEqual(
            llm_factory.resolve_provider(SimpleNamespace(provider="Anthropic")),
            "anthropic",
        )

    def test_claude_alias_to_anthropic(self) -> None:
        self.assertEqual(
            llm_factory.resolve_provider(SimpleNamespace(provider="claude")),
            "anthropic",
        )
        self.assertEqual(
            llm_factory.resolve_provider(
                SimpleNamespace(provider="claude-3-opus"),
            ),
            "anthropic",
        )

    def test_openai_passthrough(self) -> None:
        self.assertEqual(
            llm_factory.resolve_provider(SimpleNamespace(provider="openai")),
            "openai",
        )

    def test_openai_compatible_passthrough(self) -> None:
        self.assertEqual(
            llm_factory.resolve_provider(
                SimpleNamespace(provider="openai_compatible"),
            ),
            "openai_compatible",
        )

    def test_ollama_and_lmstudio_passthrough(self) -> None:
        self.assertEqual(
            llm_factory.resolve_provider(SimpleNamespace(provider="ollama")),
            "ollama",
        )
        self.assertEqual(
            llm_factory.resolve_provider(SimpleNamespace(provider="lmstudio")),
            "lmstudio",
        )

    def test_unknown_falls_back_to_openai_compatible(self) -> None:
        self.assertEqual(
            llm_factory.resolve_provider(SimpleNamespace(provider="whatever")),
            "openai_compatible",
        )

    def test_empty_and_missing_fall_back_to_openai_compatible(self) -> None:
        self.assertEqual(
            llm_factory.resolve_provider(SimpleNamespace(provider="")),
            "openai_compatible",
        )
        self.assertEqual(
            llm_factory.resolve_provider(SimpleNamespace()),
            "openai_compatible",
        )

    def test_active_profile_provider_takes_priority(self) -> None:
        settings = SimpleNamespace(
            provider="openai_compatible",
            active_profile_provider="anthropic",
        )
        self.assertEqual(llm_factory.resolve_provider(settings), "anthropic")


class ChatCompletionPureDispatchTests(_AdapterStubMixin, unittest.TestCase):
    """Verify ``chat_completion(settings, messages)`` picks the adapter
    purely from ``resolve_provider(settings)`` — no profile projection."""

    def setUp(self) -> None:
        self._install_adapter_stubs()

    def tearDown(self) -> None:
        self._restore_adapters()

    def test_anthropic_provider_goes_to_anthropic(self) -> None:
        out = llm_factory.chat_completion(
            SimpleNamespace(provider="anthropic"),
            [{"role": "user", "content": "hi"}],
        )
        self.assertEqual(out, "ANTHROPIC_OK")
        self.assertEqual(len(self._anthropic_calls), 1)
        self.assertEqual(len(self._openai_calls), 0)

    def test_claude_alias_goes_to_anthropic(self) -> None:
        out = llm_factory.chat_completion(
            SimpleNamespace(provider="claude-3-opus"), [],
        )
        self.assertEqual(out, "ANTHROPIC_OK")

    def test_openai_goes_to_openai(self) -> None:
        out = llm_factory.chat_completion(
            SimpleNamespace(provider="openai"), [],
        )
        self.assertEqual(out, "OPENAI_OK")

    def test_openai_compatible_goes_to_openai(self) -> None:
        out = llm_factory.chat_completion(
            SimpleNamespace(provider="openai_compatible"), [],
        )
        self.assertEqual(out, "OPENAI_OK")

    def test_unknown_falls_back_to_openai(self) -> None:
        out = llm_factory.chat_completion(
            SimpleNamespace(provider="whatever"), [],
        )
        self.assertEqual(out, "OPENAI_OK")

    def test_settings_passed_to_adapter_unchanged(self) -> None:
        settings = SimpleNamespace(provider="anthropic", foo="bar")
        messages = [{"role": "user", "content": "hi"}]
        llm_factory.chat_completion(settings, messages)
        call_settings, call_messages = self._anthropic_calls[0]
        self.assertIs(call_settings, settings)
        self.assertIs(call_messages, messages)


class ResolveRoleProfileTests(unittest.TestCase):
    def test_active_returns_active_profile(self) -> None:
        settings = _make_settings((_OPENAI_P, _ANTHROPIC_P), active="oai")
        self.assertEqual(
            llm_factory.resolve_role_profile(settings, "active").id, "oai",
        )

    def test_subagent_uses_subagent_id(self) -> None:
        settings = _make_settings(
            (_OPENAI_P, _ANTHROPIC_P, _LOCAL_P),
            active="oai",
            subagent="local",
        )
        self.assertEqual(
            llm_factory.resolve_role_profile(settings, "subagent").id, "local",
        )

    def test_subagent_falls_back_to_active(self) -> None:
        settings = _make_settings(
            (_OPENAI_P, _ANTHROPIC_P), active="anthro",
        )
        self.assertEqual(
            llm_factory.resolve_role_profile(settings, "subagent").id,
            "anthro",
        )

    def test_planner_uses_planner_id(self) -> None:
        settings = _make_settings(
            (_OPENAI_P, _ANTHROPIC_P),
            active="oai",
            planner="anthro",
        )
        self.assertEqual(
            llm_factory.resolve_role_profile(settings, "planner").id, "anthro",
        )

    def test_unknown_role_treated_as_active(self) -> None:
        settings = _make_settings((_OPENAI_P,), active="oai")
        self.assertEqual(
            llm_factory.resolve_role_profile(settings, "weird").id, "oai",
        )

    def test_empty_profiles_raises_runtime_error(self) -> None:
        @dataclass
        class _Empty:
            profiles: tuple[Profile, ...] = ()
            active_profile_id: str = ""
            subagent_profile_id: str | None = None
            planner_profile_id: str | None = None

        with self.assertRaises(RuntimeError):
            llm_factory.resolve_role_profile(_Empty(), "active")


class ChatCompletionByRoleTests(_AdapterStubMixin, unittest.TestCase):
    """End-to-end: role → profile → projected settings → adapter."""

    def setUp(self) -> None:
        self._install_adapter_stubs()

    def tearDown(self) -> None:
        self._restore_adapters()

    def test_active_anthropic_dispatches_to_anthropic_adapter(self) -> None:
        settings = _make_settings(
            (_OPENAI_P, _ANTHROPIC_P), active="anthro",
        )
        out = llm_factory.chat_completion_by_role(
            settings, [{"role": "user", "content": "hi"}],
        )
        self.assertEqual(out, "ANTHROPIC_OK")
        self.assertEqual(len(self._anthropic_calls), 1)
        self.assertEqual(len(self._openai_calls), 0)

        projected, _ = self._anthropic_calls[0]
        self.assertEqual(projected.provider, "anthropic")
        self.assertEqual(projected.model, _ANTHROPIC_P.model)
        self.assertEqual(projected.anthropic_max_tokens, 512)
        # Anthropic base_url must not end with ``/v1`` — the adapter
        # appends ``/v1/messages`` itself.
        self.assertFalse(projected.base_url.endswith("/v1"))

    def test_active_openai_dispatches_to_openai_adapter(self) -> None:
        settings = _make_settings(
            (_OPENAI_P, _ANTHROPIC_P), active="oai",
        )
        out = llm_factory.chat_completion_by_role(settings, [])
        self.assertEqual(out, "OPENAI_OK")
        self.assertEqual(len(self._openai_calls), 1)

        projected, _ = self._openai_calls[0]
        self.assertEqual(projected.provider, "openai")
        self.assertEqual(projected.model, _OPENAI_P.model)
        # OpenAI path keeps ``/v1`` so ``llm.py`` can append
        # ``/chat/completions``.
        self.assertTrue(projected.base_url.endswith("/v1"))

    def test_subagent_role_routes_to_subagent_profile(self) -> None:
        settings = _make_settings(
            (_OPENAI_P, _ANTHROPIC_P, _LOCAL_P),
            active="oai",
            subagent="local",
        )
        llm_factory.chat_completion_by_role(settings, [], role="subagent")
        self.assertEqual(len(self._openai_calls), 1)
        projected, _ = self._openai_calls[0]
        self.assertEqual(projected.model, _LOCAL_P.model)

    def test_planner_role_can_swap_provider_per_call(self) -> None:
        """Main loop runs on openai but planner delegates to anthropic."""
        settings = _make_settings(
            (_OPENAI_P, _ANTHROPIC_P),
            active="oai",
            planner="anthro",
        )
        llm_factory.chat_completion_by_role(settings, [], role="planner")
        self.assertEqual(len(self._anthropic_calls), 1)
        self.assertEqual(len(self._openai_calls), 0)

    def test_original_settings_not_mutated_by_projection(self) -> None:
        settings = _make_settings(
            (_OPENAI_P, _ANTHROPIC_P),
            active="oai",
            planner="anthro",
        )
        original_provider = settings.provider
        original_model = settings.model
        original_base_url = settings.base_url
        llm_factory.chat_completion_by_role(settings, [], role="planner")
        self.assertEqual(settings.provider, original_provider)
        self.assertEqual(settings.model, original_model)
        self.assertEqual(settings.base_url, original_base_url)

    def test_cli_model_override_passes_through_projection(self) -> None:
        """`cai-agent run --model X` (→ replace(settings, model=X)) must not
        be silently eaten by ``_project_settings_for_profile``; otherwise we
        regress a documented S1 DoD ("legacy --model behaviour unchanged")."""
        base = _make_settings(
            (_OPENAI_P, _ANTHROPIC_P, _LOCAL_P),
            active="oai",
            subagent="local",
            planner="anthro",
        )
        from dataclasses import replace as _dc_replace

        overridden = _dc_replace(base, model="gpt-4o-mini-override")

        llm_factory.chat_completion_by_role(overridden, [], role="active")
        projected, _ = self._openai_calls[-1]
        self.assertEqual(projected.model, "gpt-4o-mini-override")
        self.assertEqual(projected.provider, "openai")

        llm_factory.chat_completion_by_role(overridden, [], role="subagent")
        projected, _ = self._openai_calls[-1]
        self.assertEqual(projected.model, "gpt-4o-mini-override")

        llm_factory.chat_completion_by_role(overridden, [], role="planner")
        projected, _ = self._anthropic_calls[-1]
        self.assertEqual(projected.model, "gpt-4o-mini-override")
        self.assertEqual(projected.provider, "anthropic")

    def test_no_override_still_picks_role_profile_model(self) -> None:
        """Without an explicit override, role projection should still swap
        ``model`` to the role-specific profile."""
        settings = _make_settings(
            (_OPENAI_P, _ANTHROPIC_P, _LOCAL_P),
            active="oai",
            subagent="local",
        )
        llm_factory.chat_completion_by_role(settings, [], role="subagent")
        projected, _ = self._openai_calls[-1]
        self.assertEqual(projected.model, _LOCAL_P.model)

    def test_projection_context_window_source_when_profile_pins_window(self) -> None:
        """Role projection must carry context_window + context_window_source."""
        p = dc_replace(_OPENAI_P, context_window=65536)
        settings = _make_settings((p, _LOCAL_P), active="oai")
        llm_factory.chat_completion_by_role(settings, [], role="active")
        projected, _ = self._openai_calls[-1]
        self.assertEqual(projected.context_window, 65536)
        self.assertEqual(projected.context_window_source, "profile")


class ActivateProfileInMemoryTests(unittest.TestCase):
    def test_replaces_runtime_model_override_with_profile_model(self) -> None:
        """TUI / 面板显式切 profile 时必须用该 profile 的 model，而不是旧的 --model override。"""
        base = _make_settings(
            (_OPENAI_P, _ANTHROPIC_P, _LOCAL_P),
            active="oai",
        )
        overridden = dc_replace(base, model="gpt-4o-mini-override")
        out = llm_factory.activate_profile_in_memory(overridden, _LOCAL_P)
        self.assertEqual(out.model, _LOCAL_P.model)
        self.assertEqual(out.active_profile_id, "local")
        self.assertEqual(out.provider, "openai_compatible")

    def test_switch_without_prior_override(self) -> None:
        base = _make_settings((_OPENAI_P, _LOCAL_P), active="oai")
        out = llm_factory.activate_profile_in_memory(base, _LOCAL_P)
        self.assertEqual(out.model, _LOCAL_P.model)
        self.assertEqual(out.base_url.rstrip("/"), _LOCAL_P.base_url.rstrip("/"))


if __name__ == "__main__":
    unittest.main()
