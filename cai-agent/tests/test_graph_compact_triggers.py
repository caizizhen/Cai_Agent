"""F2：graph 在工具失败 / 成功轮次里程碑时注入 compact 类 user 提示。"""
from __future__ import annotations

import json
import unittest
from dataclasses import replace
from typing import Any
from unittest.mock import patch

from cai_agent.config import Settings
from cai_agent.graph import build_app


def _minimal_settings(**over: Any) -> Settings:
    base = Settings.from_env()
    return replace(
        base,
        max_iterations=4,
        mock=False,
        context_compact_after_iterations=0,
        context_compact_min_messages=8,
        context_compact_on_tool_error=over.pop(
            "context_compact_on_tool_error",
            True,
        ),
        context_compact_after_tool_calls=over.pop(
            "context_compact_after_tool_calls",
            0,
        ),
        **over,
    )


class GraphCompactToolErrorTests(unittest.TestCase):
    def test_injects_hint_when_tool_error_pending(self) -> None:
        seen: list[list[dict[str, Any]]] = []

        def fake_chat(
            settings: Any,
            messages: list[dict[str, Any]],
            *,
            role: str = "active",
            route_conversation_phase: str | None = None,
        ) -> str:
            seen.append(list(messages))
            return json.dumps({"type": "finish", "message": "ok"}, ensure_ascii=False)

        settings = _minimal_settings(context_compact_on_tool_error=True)
        state: dict[str, Any] = {
            "messages": [
                {"role": "system", "content": "s"},
                {"role": "user", "content": "goal"},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"tool": "read_file", "result": "工具执行失败: nope"},
                        ensure_ascii=False,
                    ),
                },
            ],
            "iteration": 0,
            "pending": None,
            "finished": False,
            "tool_error_compact_pending": True,
        }
        with patch("cai_agent.graph.chat_completion_by_role", side_effect=fake_chat):
            app = build_app(settings)
            app.invoke(state)
        self.assertTrue(seen, "LLM 未被调用")
        flat = "\n".join(str(m.get("content", "")) for m in seen[0])
        self.assertIn("[工具执行失败后的压缩建议]", flat)

    def test_no_hint_when_tool_error_compact_disabled(self) -> None:
        seen: list[list[dict[str, Any]]] = []

        def fake_chat(
            settings: Any,
            messages: list[dict[str, Any]],
            *,
            role: str = "active",
            route_conversation_phase: str | None = None,
        ) -> str:
            seen.append(list(messages))
            return json.dumps({"type": "finish", "message": "ok"}, ensure_ascii=False)

        settings = _minimal_settings(context_compact_on_tool_error=False)
        state: dict[str, Any] = {
            "messages": [
                {"role": "system", "content": "s"},
                {"role": "user", "content": "goal"},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"tool": "read_file", "result": "工具执行失败: nope"},
                        ensure_ascii=False,
                    ),
                },
            ],
            "iteration": 0,
            "pending": None,
            "finished": False,
            "tool_error_compact_pending": True,
        }
        with patch("cai_agent.graph.chat_completion_by_role", side_effect=fake_chat):
            app = build_app(settings)
            app.invoke(state)
        self.assertTrue(seen)
        flat = "\n".join(str(m.get("content", "")) for m in seen[0])
        self.assertNotIn("[工具执行失败后的压缩建议]", flat)


class GraphCompactMilestoneTests(unittest.TestCase):
    def test_milestone_after_n_successful_tool_rounds(self) -> None:
        seen: list[list[dict[str, Any]]] = []

        def fake_chat(
            settings: Any,
            messages: list[dict[str, Any]],
            *,
            role: str = "active",
            route_conversation_phase: str | None = None,
        ) -> str:
            seen.append(list(messages))
            return json.dumps({"type": "finish", "message": "done"}, ensure_ascii=False)

        settings = _minimal_settings(
            context_compact_on_tool_error=False,
            context_compact_after_tool_calls=2,
        )
        state: dict[str, Any] = {
            "messages": [
                {"role": "system", "content": "s"},
                {"role": "user", "content": "x"},
            ],
            "iteration": 0,
            "pending": None,
            "finished": False,
            "tool_call_count": 2,
            "compact_milestone_last_tc": 0,
            "tool_error_compact_pending": False,
        }
        with patch("cai_agent.graph.chat_completion_by_role", side_effect=fake_chat):
            app = build_app(settings)
            app.invoke(state)
        self.assertTrue(seen)
        flat = "\n".join(str(m.get("content", "")) for m in seen[0])
        self.assertIn("[工具里程碑", flat)
        self.assertIn("已成功工具轮次=2", flat)
