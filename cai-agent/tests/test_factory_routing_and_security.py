"""Sprint 2 回归：M8 路由 + M11 工厂接入 + M13 security-scan 新规则。

覆盖点：
- ``graph.build_app`` 将 LLM 调用转接到 :func:`cai_agent.llm_factory.chat_completion_by_role`，
  角色通过 ``role=`` 传参；
- ``agents.create_agent`` 的非 default 角色在执行时会把 ``role="subagent"`` 透传；
- ``__main__`` 的 ``plan`` 命令走 ``role="planner"``；
- ``security_scan`` 的 ``sk-ant-`` / ``sk-or-`` / ``cai_profile_plaintext_api_key``
  规则生效，且本地占位符（``"lm-studio"``）不会被误报为 high。
"""
from __future__ import annotations

import os
import tempfile
import textwrap
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from cai_agent import llm_factory
from cai_agent.agents import create_agent
from cai_agent.config import Settings
from cai_agent.graph import build_app
from cai_agent.profiles import Profile
from cai_agent.security_scan import run_security_scan


def _mk_profile(pid: str, provider: str, model: str) -> Profile:
    return Profile(
        id=pid,
        provider=provider,
        base_url="https://api.anthropic.com" if provider == "anthropic" else "http://localhost:1234/v1",
        model=model,
        api_key_env=None,
        api_key="literal",
        temperature=0.2,
        timeout_sec=60.0,
        anthropic_version="2023-06-01" if provider == "anthropic" else None,
        max_tokens=512 if provider == "anthropic" else None,
    )


class _StubMessages:
    """可被 build_app 消化的最小消息列表容器。"""


def _minimal_settings(**over: Any) -> Any:
    """捏一个够用的 Settings 替身，避免触发真实 config 加载。"""
    base = Settings.from_env()
    profiles = over.pop("profiles", None) or (
        _mk_profile("oai", "openai", "gpt-4o"),
        _mk_profile("anthro", "anthropic", "claude-sonnet-4-5"),
        _mk_profile("local", "openai_compatible", "qwen"),
    )
    return replace(
        base,
        profiles=profiles,
        profiles_explicit=True,
        active_profile_id=over.pop("active", "oai"),
        subagent_profile_id=over.pop("subagent", None),
        planner_profile_id=over.pop("planner", None),
        provider=over.pop("provider", "openai"),
        model=over.pop("model", "gpt-4o"),
        base_url=over.pop("base_url", "https://api.openai.com/v1"),
        api_key=over.pop("api_key", "seed"),
        max_iterations=over.pop("max_iterations", 1),
        mock=False,
    )


class GraphRoutingTests(unittest.TestCase):
    """主循环 ``build_app`` 通过 llm_factory 派发，默认角色 active。"""

    def test_graph_uses_factory_by_role_default_active(self) -> None:
        calls: list[dict[str, Any]] = []

        def fake(settings: Any, messages: list[dict[str, Any]], *, role: str = "active") -> str:
            calls.append({"role": role, "provider": getattr(settings, "provider", None)})
            return '{"type":"finish","message":"ok"}'

        settings = _minimal_settings(planner="anthro")
        with patch("cai_agent.graph.chat_completion_by_role", side_effect=fake):
            app = build_app(settings)
            state = {
                "messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
                "iteration": 0,
                "pending": None,
                "finished": False,
            }
            app.invoke(state)
        self.assertGreaterEqual(len(calls), 1)
        self.assertEqual(calls[0]["role"], "active")

    def test_graph_build_app_accepts_role_kwarg(self) -> None:
        calls: list[str] = []

        def fake(settings: Any, messages: list[dict[str, Any]], *, role: str = "active") -> str:
            calls.append(role)
            return '{"type":"finish","message":"ok"}'

        settings = _minimal_settings(subagent="local")
        with patch("cai_agent.graph.chat_completion_by_role", side_effect=fake):
            app = build_app(settings, role="subagent")
            state = {
                "messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}],
                "iteration": 0,
                "pending": None,
                "finished": False,
            }
            app.invoke(state)
        self.assertIn("subagent", calls)


class AgentsRoutingTests(unittest.TestCase):
    def test_non_default_role_routes_as_subagent(self) -> None:
        calls: list[str] = []

        def fake(settings: Any, messages: list[dict[str, Any]], *, role: str = "active") -> str:
            calls.append(role)
            return '{"type":"finish","message":"ok"}'

        settings = _minimal_settings(subagent="local")
        agent = create_agent(settings, role="explorer", max_iterations=1)
        with patch("cai_agent.graph.chat_completion_by_role", side_effect=fake):
            agent.run("hello")
        self.assertTrue(calls, "chat_completion_by_role 未被调用")
        self.assertEqual(calls[0], "subagent")

    def test_default_role_routes_as_active(self) -> None:
        calls: list[str] = []

        def fake(settings: Any, messages: list[dict[str, Any]], *, role: str = "active") -> str:
            calls.append(role)
            return '{"type":"finish","message":"ok"}'

        settings = _minimal_settings()
        agent = create_agent(settings, role="default", max_iterations=1)
        with patch("cai_agent.graph.chat_completion_by_role", side_effect=fake):
            agent.run("hello")
        self.assertEqual(calls[:1], ["active"])


class FactoryDispatchProjectionTests(unittest.TestCase):
    """把 llm_factory 当作黑盒：role 切换后底层 adapter 拿到的 settings 已投影。"""

    def setUp(self) -> None:
        self._orig_openai = llm_factory._openai_adapter.chat_completion
        self._orig_anthropic = llm_factory._anthropic_adapter.chat_completion
        self.calls: list[tuple[str, Any]] = []

        def fake_oai(s: Any, m: list[dict[str, Any]]) -> str:
            self.calls.append(("openai", s))
            return "oai"

        def fake_anth(s: Any, m: list[dict[str, Any]]) -> str:
            self.calls.append(("anthropic", s))
            return "ant"

        llm_factory._openai_adapter.chat_completion = fake_oai
        llm_factory._anthropic_adapter.chat_completion = fake_anth

    def tearDown(self) -> None:
        llm_factory._openai_adapter.chat_completion = self._orig_openai
        llm_factory._anthropic_adapter.chat_completion = self._orig_anthropic

    def test_planner_role_projects_to_anthropic(self) -> None:
        settings = _minimal_settings(planner="anthro")
        llm_factory.chat_completion_by_role(settings, [], role="planner")
        self.assertEqual(len(self.calls), 1)
        adapter, projected = self.calls[0]
        self.assertEqual(adapter, "anthropic")
        self.assertEqual(projected.model, "claude-sonnet-4-5")
        # Anthropic base_url 不能以 /v1 结尾，适配器自己拼 /v1/messages
        self.assertFalse(projected.base_url.endswith("/v1"))

    def test_subagent_role_projects_to_local_openai_compatible(self) -> None:
        settings = _minimal_settings(subagent="local")
        llm_factory.chat_completion_by_role(settings, [], role="subagent")
        adapter, projected = self.calls[0]
        self.assertEqual(adapter, "openai")  # openai_compatible 走 openai 适配器
        self.assertEqual(projected.model, "qwen")
        self.assertTrue(projected.base_url.endswith("/v1"))


# ---------------------------------------------------------------------------
# M13 security-scan 新规则
# ---------------------------------------------------------------------------


class SecurityScanProfileRuleTests(unittest.TestCase):
    def _scan(self, files: dict[str, str]) -> dict[str, Any]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for rel, content in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        s = replace(Settings.from_env(), workspace=str(root))
        return run_security_scan(s)

    def test_anthropic_sk_ant_flagged_high(self) -> None:
        # 把“像真实 key”的字符串在源代码里拆开构造，避免对本文件自扫描时误触发。
        fake_anth = "sk" + "-ant-" + "api03-" + "ABCDEFGHIJKLMN0123456789"
        result = self._scan(
            {
                "secret.toml": textwrap.dedent(
                    f"""
                    [[models.profile]]
                    id = "c"
                    provider = "anthropic"
                    api_key = "{fake_anth}"
                    """,
                ),
            },
        )
        highs = [f for f in result["findings"] if f["severity"] == "high"]
        rules = {f["rule"] for f in highs}
        self.assertIn("anthropic_api_key", rules)
        self.assertIn("cai_profile_plaintext_api_key", rules)
        self.assertFalse(result["ok"])

    def test_openrouter_sk_or_flagged_high(self) -> None:
        fake_or = "sk" + "-or-" + "v1-" + "abcdefghijklmnopqrstuvwxyz0123456789"
        result = self._scan({"note.md": f"OPENROUTER_API_KEY={fake_or}\n"})
        rules = {f["rule"] for f in result["findings"] if f["severity"] == "high"}
        self.assertIn("openrouter_api_key", rules)

    def test_placeholder_api_key_not_flagged_high(self) -> None:
        """本地占位符（lm-studio 等）不算真实泄漏，不应让 ok=False。"""
        result = self._scan(
            {
                "cai-agent.toml": textwrap.dedent(
                    """
                    [llm]
                    provider = "openai_compatible"
                    base_url = "http://localhost:1234/v1"
                    model = "m"
                    api_key = "lm-studio"
                    """,
                ),
            },
        )
        profile_highs = [
            f for f in result["findings"]
            if f["rule"] == "cai_profile_plaintext_api_key" and f["severity"] == "high"
        ]
        self.assertEqual(profile_highs, [])
        # 没有其它 high 规则命中
        self.assertTrue(result["ok"], f"不该阻断: {result['findings']}")

    def test_api_key_env_does_not_trigger_profile_rule(self) -> None:
        """`api_key_env = "..."` 是推荐写法，不应命中明文规则。"""
        result = self._scan(
            {
                "cfg.toml": textwrap.dedent(
                    """
                    [[models.profile]]
                    id = "p"
                    provider = "anthropic"
                    api_key_env = "ANTHROPIC_API_KEY"
                    """,
                ),
            },
        )
        rules = {f["rule"] for f in result["findings"]}
        self.assertNotIn("cai_profile_plaintext_api_key", rules)


if __name__ == "__main__":
    unittest.main()
