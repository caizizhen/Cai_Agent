from __future__ import annotations

import asyncio
import json

import httpx
from starlette.testclient import TestClient

from cai_agent.llm.anthropic_messages import (
    AnthropicMessagesLLM,
    anthropic_content_to_openai,
    openai_messages_to_anthropic,
    openai_tools_to_anthropic,
)
from cai_agent.surfaces import web_api
from cai_agent.surfaces.web import SessionHub, build_app


def test_openai_to_anthropic_conversion():
    system, msgs = openai_messages_to_anthropic(
        [
            {"role": "system", "content": "be helpful"},
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": "ok",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "read", "arguments": '{"path":"a.py"}'},
                    },
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "name": "read",
                "content": "print(1)",
            },
        ],
    )
    assert "be helpful" in system
    assert msgs[0] == {"role": "user", "content": "hi"}
    assert msgs[1]["role"] == "assistant"
    assert msgs[1]["content"][0]["type"] == "text"
    assert msgs[1]["content"][1]["type"] == "tool_use"
    assert msgs[1]["content"][1]["name"] == "read"
    assert msgs[2]["role"] == "user"
    assert msgs[2]["content"][0]["type"] == "tool_result"


def test_anthropic_content_to_openai_tools():
    text, tcs = anthropic_content_to_openai(
        [
            {"type": "text", "text": "done"},
            {"type": "tool_use", "id": "t1", "name": "bash", "input": {"command": "ls"}},
        ],
    )
    assert text == "done"
    assert tcs[0]["function"]["name"] == "bash"
    assert json.loads(tcs[0]["function"]["arguments"])["command"] == "ls"


def test_openai_tools_schema():
    tools = openai_tools_to_anthropic(
        [
            {
                "type": "function",
                "function": {
                    "name": "read",
                    "description": "read file",
                    "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
                },
            },
        ],
    )
    assert tools[0]["name"] == "read"
    assert "input_schema" in tools[0]


def test_anthropic_complete_non_stream(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).endswith("/v1/messages")
        assert request.headers.get("x-api-key") == "sk-test"
        assert request.headers.get("anthropic-version")
        body = json.loads(request.content.decode())
        assert body["model"] == "claude-sonnet-4-5"
        assert body["stream"] is False
        assert body["system"]
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "hello from claude"}],
                "stop_reason": "end_turn",
            },
        )

    transport = httpx.MockTransport(handler)

    class PatchedClient(httpx.AsyncClient):
        def __init__(self, *a, **k):
            k["transport"] = transport
            super().__init__(*a, **k)

    monkeypatch.setattr(httpx, "AsyncClient", PatchedClient)
    llm = AnthropicMessagesLLM(
        base_url="https://api.anthropic.com",
        model="claude-sonnet-4-5",
        api_key="sk-test",
        stream=False,
    )
    result = asyncio.run(
        llm.complete(
            [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "hi"},
            ],
            stream=False,
        ),
    )
    assert result.content == "hello from claude"


def test_discover_anthropic_fallback(monkeypatch):
    class BoomClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            raise RuntimeError("nope")

    monkeypatch.setattr(httpx, "AsyncClient", BoomClient)
    models = asyncio.run(
        web_api.discover_models(
            "https://api.anthropic.com",
            "sk",
            provider="anthropic",
        ),
    )
    assert any(m["id"].startswith("claude") for m in models)


def test_ui_has_provider_select(tmp_path, monkeypatch):
    monkeypatch.setenv("CAI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CAI_WORKSPACE", str(tmp_path / "ws"))
    (tmp_path / "ws").mkdir()
    html = TestClient(build_app(SessionHub())).get("/").text
    assert "set-provider" in html
    assert "anthropic" in html


def test_runtime_persists_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("CAI_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CAI_WORKSPACE", str(tmp_path / "ws"))
    (tmp_path / "ws").mkdir()
    client = TestClient(build_app(SessionHub()))
    res = client.put(
        "/api/runtime",
        json={
            "provider": "anthropic",
            "base_url": "https://api.anthropic.com",
            "model": "claude-sonnet-4-5",
            "api_key": "sk-ant-test",
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["provider"] == "anthropic"
    assert body["base_url"] == "https://api.anthropic.com"
    assert not body["base_url"].endswith("/v1")
