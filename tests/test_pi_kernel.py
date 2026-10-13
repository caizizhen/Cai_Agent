from __future__ import annotations

import asyncio
import json

from cai_agent.llm.openai_compat import LLMResult, OpenAICompatLLM
from cai_agent.pi_core.agent import Agent
from cai_agent.pi_core.context import truncate_messages
from cai_agent.pi_core.messages import AgentMessage, convert_to_llm
from cai_agent.pi_core.tools_registry import ToolRegistry, ToolSpec
from cai_agent.pi_session.session import create_agent_session
from cai_agent.pi_session.store import SessionStore


def test_agent_plain_reply():
    llm = OpenAICompatLLM(base_url="http://localhost/v1", model="m", mock=True)
    llm.set_mock_handler(lambda _msgs: LLMResult(content="hello-pi"))
    reg = ToolRegistry()
    agent = Agent(llm=llm, tools=reg, max_turns=2)
    events = []
    agent.subscribe(lambda e: events.append(e.type))
    out = asyncio.run(agent.run([], "hi"))
    assert any(m.role == "assistant" and m.content == "hello-pi" for m in out)
    assert "agent_start" in events and "agent_end" in events


def test_agent_tool_then_reply():
    calls = {"n": 0}

    def handler(msgs):
        calls["n"] += 1
        if calls["n"] == 1:
            return LLMResult(
                content="",
                tool_calls=[
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "echo", "arguments": json.dumps({"x": "1"})},
                    },
                ],
            )
        return LLMResult(content="done")

    llm = OpenAICompatLLM(base_url="http://localhost/v1", model="m", mock=True)
    llm.set_mock_handler(handler)
    reg = ToolRegistry()

    async def echo(args):
        return f"echo:{args.get('x')}"

    reg.register(
        ToolSpec(
            name="echo",
            description="echo",
            parameters={"type": "object", "properties": {"x": {"type": "string"}}},
            handler=echo,
        ),
    )
    agent = Agent(llm=llm, tools=reg, max_turns=4)
    out = asyncio.run(agent.run([], "use echo"))
    assert any(m.role == "tool" and m.content == "echo:1" for m in out)
    assert any(m.role == "assistant" and m.content == "done" for m in out)


def test_truncate_messages_keeps_tail():
    msgs = [AgentMessage(role="user", content=str(i)) for i in range(10)]
    out = truncate_messages(msgs, max_messages=3)
    assert len(out) == 3
    assert out[0].content == "7"


def test_convert_to_llm():
    msgs = [
        AgentMessage(role="user", content="a"),
        AgentMessage(
            role="assistant",
            content="",
            tool_calls=[{"id": "1", "type": "function", "function": {"name": "read", "arguments": "{}"}}],
        ),
        AgentMessage(role="tool", content="x", tool_call_id="1", name="read"),
    ]
    llm_msgs = convert_to_llm(msgs)
    assert llm_msgs[0]["role"] == "user"
    assert llm_msgs[1]["tool_calls"]
    assert llm_msgs[2]["role"] == "tool"


def test_session_persist(tmp_path, monkeypatch):
    monkeypatch.setenv("CAI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CAI_WORKSPACE", str(tmp_path / "ws"))
    (tmp_path / "ws").mkdir()
    llm = OpenAICompatLLM(base_url="http://localhost/v1", model="m", mock=True)
    llm.set_mock_handler(lambda _m: LLMResult(content="ok"))
    store = SessionStore(tmp_path / "home" / "sessions")
    sess = create_agent_session(workspace=str(tmp_path / "ws"), llm=llm, store=store)
    asyncio.run(sess.prompt("hello"))
    loaded = store.load_messages(sess.session_id)
    assert loaded[0].role == "user"
    assert loaded[1].role == "assistant"
    assert "hello" in store.preview(sess.session_id)
