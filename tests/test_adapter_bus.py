from __future__ import annotations

import asyncio
import json

from cai_agent.adapter.bus import EventBus
from cai_agent.adapter.events import AgentEvent, EventKind
from cai_agent.config import Settings
from cai_agent.engine.factory import create_engine
from cai_agent.llm.openai_compat import LLMResult, OpenAICompatLLM
from cai_agent.pi_session.store import SessionStore
from cai_agent.ui.cli_render import HarnessRenderer


def test_event_kinds_roundtrip():
    ev = AgentEvent(kind=EventKind.TOOL_INVOKE, tool_name="read", step=1)
    assert ev.as_dict()["kind"] == "ToolInvoke"


def test_bridge_emits_unified_events(tmp_path, monkeypatch):
    monkeypatch.setenv("CAI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CAI_WORKSPACE", str(tmp_path / "ws"))
    (tmp_path / "ws").mkdir()

    calls = {"n": 0}

    def handler(_msgs):
        calls["n"] += 1
        if calls["n"] == 1:
            return LLMResult(
                content="",
                tool_calls=[
                    {
                        "id": "t1",
                        "type": "function",
                        "function": {
                            "name": "read",
                            "arguments": json.dumps({"path": "missing.txt"}),
                        },
                    },
                ],
            )
        return LLMResult(content="all done")

    llm = OpenAICompatLLM(base_url="http://x/v1", model="m", mock=True)
    llm.set_mock_handler(handler)
    settings = Settings.from_env().with_overrides(mock=True, max_steps=4)
    store = SessionStore(tmp_path / "home" / "sessions")
    kinds: list[str] = []
    handle = create_engine(
        workspace=str(tmp_path / "ws"),
        settings=settings,
        llm=llm,
        store=store,
    )
    handle.bus.subscribe(lambda e: kinds.append(e.kind.value))
    asyncio.run(handle.prompt("read a file"))
    assert "StepStart" in kinds
    assert "ThinkingStream" in kinds
    assert "ToolInvoke" in kinds
    assert "ToolResult" in kinds
    assert "MessageStream" in kinds or "Finished" in kinds
    assert kinds[-1] == "Finished"


def test_harness_renderer_subscribes():
    bus = EventBus()
    r = HarnessRenderer(bus, stream=False)
    bus.publish(AgentEvent(kind=EventKind.STEP_START, step=1))
    bus.publish(AgentEvent(kind=EventKind.MESSAGE_STREAM, delta="hi"))
    bus.publish(AgentEvent(kind=EventKind.FINISHED))
    r.close()
