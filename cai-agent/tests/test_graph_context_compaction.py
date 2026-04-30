from __future__ import annotations

import json
from dataclasses import replace
from typing import Any
from unittest.mock import patch

from cai_agent.config import Settings
from cai_agent.graph import build_app


def _settings(**over: Any) -> Settings:
    base = Settings.from_env()
    defaults = {
        "max_iterations": 4,
        "mock": False,
        "context_window": 500,
        "context_compact_trigger_ratio": 0.5,
        "context_compact_mode": "heuristic",
        "context_compact_min_messages": 4,
        "context_compact_keep_tail_messages": 2,
        "context_compact_summary_max_chars": 2400,
    }
    defaults.update(over)
    return replace(
        base,
        **defaults,
    )


def test_graph_auto_compacts_messages_before_llm_call() -> None:
    seen: list[list[dict[str, Any]]] = []
    events: list[dict[str, Any]] = []

    def fake_chat(
        settings: Any,
        messages: list[dict[str, Any]],
        *,
        role: str = "active",
        route_conversation_phase: str | None = None,
    ) -> str:
        seen.append(list(messages))
        return json.dumps({"type": "finish", "message": "ok"}, ensure_ascii=False)

    state: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "goal"},
            {"role": "assistant", "content": "older " * 700},
            {
                "role": "user",
                "content": json.dumps(
                    {"tool": "read_file", "result": "cai-agent/src/cai_agent/graph.py\n" + ("body " * 700)},
                    ensure_ascii=False,
                ),
            },
            {"role": "assistant", "content": "recent assistant"},
            {"role": "user", "content": "recent user"},
        ],
        "iteration": 0,
        "pending": None,
        "finished": False,
        "tool_call_count": 1,
        "compact_last_message_count": 0,
    }

    with patch("cai_agent.graph.chat_completion_by_role", side_effect=fake_chat):
        app = build_app(_settings(), progress=events.append)
        final = app.invoke(state)

    assert seen
    flat = "\n".join(str(m.get("content", "")) for m in seen[0])
    assert "[context_summary_v1]" in flat
    assert "recent user" in flat
    assert "older " * 50 not in flat
    assert final.get("compact_generation") == 1
    assert any(e.get("phase") == "compact" for e in events)


def test_graph_skips_auto_compaction_when_ratio_disabled() -> None:
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

    state: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "goal"},
            {"role": "assistant", "content": "older " * 700},
            {"role": "user", "content": "tail " * 700},
        ],
        "iteration": 0,
        "pending": None,
        "finished": False,
    }

    with patch("cai_agent.graph.chat_completion_by_role", side_effect=fake_chat):
        app = build_app(_settings(context_compact_trigger_ratio=0.0))
        final = app.invoke(state)

    assert seen
    flat = "\n".join(str(m.get("content", "")) for m in seen[0])
    assert "[context_summary_v1]" not in flat
    assert final.get("compact_generation") is None


def test_graph_llm_compaction_uses_summary_payload() -> None:
    seen: list[list[dict[str, Any]]] = []
    events: list[dict[str, Any]] = []

    def fake_chat(
        settings: Any,
        messages: list[dict[str, Any]],
        *,
        role: str = "active",
        route_conversation_phase: str | None = None,
    ) -> str:
        seen.append(list(messages))
        if len(seen) == 1:
            return json.dumps(
                {
                    "goal": "ship compaction",
                    "decisions": ["use llm summary"],
                    "facts": ["semantic payload survives"],
                    "files_touched": ["cai-agent/src/cai_agent/graph.py"],
                    "tool_evidence": [],
                    "open_todos": ["verify"],
                    "risks": [],
                    "last_user_intent": "recent user",
                },
                ensure_ascii=False,
            )
        return json.dumps({"type": "finish", "message": "ok"}, ensure_ascii=False)

    state: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "goal"},
            {"role": "assistant", "content": "older " * 900},
            {"role": "user", "content": "middle " * 900},
            {"role": "assistant", "content": "recent assistant"},
            {"role": "user", "content": "recent user"},
        ],
        "iteration": 0,
        "pending": None,
        "finished": False,
        "compact_last_message_count": 0,
    }

    with patch("cai_agent.graph.chat_completion_by_role", side_effect=fake_chat):
        app = build_app(_settings(context_compact_mode="llm"), progress=events.append)
        final = app.invoke(state)

    assert len(seen) == 2
    main_flat = "\n".join(str(m.get("content", "")) for m in seen[1])
    assert '"summary_source": "llm"' in main_flat
    assert "semantic payload survives" in main_flat
    assert final.get("compact_generation") == 1
    assert any(e.get("phase") == "compact" and e.get("summary_source") == "llm" for e in events)


def test_graph_llm_compaction_falls_back_to_heuristic_on_bad_json() -> None:
    seen: list[list[dict[str, Any]]] = []
    events: list[dict[str, Any]] = []

    def fake_chat(
        settings: Any,
        messages: list[dict[str, Any]],
        *,
        role: str = "active",
        route_conversation_phase: str | None = None,
    ) -> str:
        seen.append(list(messages))
        if len(seen) == 1:
            return "not json"
        return json.dumps({"type": "finish", "message": "ok"}, ensure_ascii=False)

    state: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "goal"},
            {"role": "assistant", "content": "older " * 900},
            {"role": "user", "content": "middle " * 900},
            {"role": "assistant", "content": "recent assistant"},
            {"role": "user", "content": "recent user"},
        ],
        "iteration": 0,
        "pending": None,
        "finished": False,
        "compact_last_message_count": 0,
    }

    with patch("cai_agent.graph.chat_completion_by_role", side_effect=fake_chat):
        app = build_app(_settings(context_compact_mode="llm"), progress=events.append)
        final = app.invoke(state)

    assert len(seen) == 2
    main_flat = "\n".join(str(m.get("content", "")) for m in seen[1])
    assert '"summary_source": "heuristic"' in main_flat
    assert "llm_compaction_failed" in main_flat
    assert final.get("compact_generation") == 1
    assert any(e.get("phase") == "compact_fallback" for e in events)


def test_graph_llm_compaction_falls_back_when_quality_gate_fails() -> None:
    seen: list[list[dict[str, Any]]] = []
    events: list[dict[str, Any]] = []

    def fake_chat(
        settings: Any,
        messages: list[dict[str, Any]],
        *,
        role: str = "active",
        route_conversation_phase: str | None = None,
    ) -> str:
        seen.append(list(messages))
        if len(seen) == 1:
            return json.dumps(
                {
                    "goal": "ship compaction",
                    "decisions": ["too vague"],
                    "facts": ["missing retained tool evidence"],
                    "files_touched": [],
                    "tool_evidence": [],
                    "open_todos": [],
                    "risks": [],
                    "last_user_intent": "recent user",
                },
                ensure_ascii=False,
            )
        return json.dumps({"type": "finish", "message": "ok"}, ensure_ascii=False)

    state: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "goal"},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "tool": "read_file",
                        "result": "cai-agent/src/cai_agent/context_compaction.py\n" + ("body " * 900),
                    },
                    ensure_ascii=False,
                ),
            },
            {"role": "assistant", "content": "older " * 900},
            {"role": "assistant", "content": "recent assistant"},
            {"role": "user", "content": "recent user"},
        ],
        "iteration": 0,
        "pending": None,
        "finished": False,
        "compact_last_message_count": 0,
    }

    with patch("cai_agent.graph.chat_completion_by_role", side_effect=fake_chat):
        app = build_app(_settings(context_compact_mode="llm"), progress=events.append)
        final = app.invoke(state)

    assert len(seen) == 2
    main_flat = "\n".join(str(m.get("content", "")) for m in seen[1])
    assert '"summary_source": "heuristic"' in main_flat
    assert "llm_compaction_quality_failed" in main_flat
    assert "read_file" in main_flat
    assert "cai-agent/src/cai_agent/context_compaction.py" in main_flat
    assert final.get("compact_generation") == 1
    fallback = [e for e in events if e.get("phase") == "compact_fallback"]
    assert fallback
    assert "quality_failed" in str(fallback[-1].get("error"))


def test_graph_skips_auto_compaction_when_mode_off() -> None:
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

    state: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": "s"},
            {"role": "user", "content": "goal"},
            {"role": "assistant", "content": "older " * 900},
            {"role": "user", "content": "middle " * 900},
        ],
        "iteration": 0,
        "pending": None,
        "finished": False,
    }

    with patch("cai_agent.graph.chat_completion_by_role", side_effect=fake_chat):
        app = build_app(_settings(context_compact_mode="off"))
        final = app.invoke(state)

    assert len(seen) == 1
    flat = "\n".join(str(m.get("content", "")) for m in seen[0])
    assert "[context_summary_v1]" not in flat
    assert final.get("compact_generation") is None
