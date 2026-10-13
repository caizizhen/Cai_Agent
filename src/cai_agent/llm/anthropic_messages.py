"""Anthropic Messages API client (same surface as OpenAICompatLLM)."""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

import httpx

from cai_agent.llm.openai_compat import LLMResult, StreamChunk

ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_ANTHROPIC_BASE = "https://api.anthropic.com"
DEFAULT_ANTHROPIC_MODELS = [
    {"id": "claude-opus-4-5", "name": "Claude Opus 4.5"},
    {"id": "claude-sonnet-4-5", "name": "Claude Sonnet 4.5"},
    {"id": "claude-haiku-4-5", "name": "Claude Haiku 4.5"},
    {"id": "claude-opus-4-1", "name": "Claude Opus 4.1"},
    {"id": "claude-sonnet-4-0", "name": "Claude Sonnet 4"},
    {"id": "claude-3-5-haiku-latest", "name": "Claude 3.5 Haiku"},
]


def normalize_anthropic_base(base_url: str) -> str:
    url = (base_url or DEFAULT_ANTHROPIC_BASE).rstrip("/")
    if url.endswith("/v1"):
        url = url[:-3].rstrip("/")
    return url or DEFAULT_ANTHROPIC_BASE


def openai_tools_to_anthropic(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t in tools or []:
        if not isinstance(t, dict):
            continue
        fn = t.get("function") if t.get("type") == "function" else t
        if not isinstance(fn, dict):
            continue
        name = str(fn.get("name") or "")
        if not name:
            continue
        out.append(
            {
                "name": name,
                "description": str(fn.get("description") or ""),
                "input_schema": fn.get("parameters")
                or {"type": "object", "properties": {}},
            },
        )
    return out


def openai_messages_to_anthropic(
    messages: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """Convert OpenAI-style chat messages → Anthropic system + messages."""
    system_parts: list[str] = []
    out: list[dict[str, Any]] = []

    def push(role: str, content: Any) -> None:
        if not content and content != 0:
            return
        if out and out[-1]["role"] == role:
            prev = out[-1]["content"]
            if isinstance(prev, str) and isinstance(content, str):
                out[-1]["content"] = prev + "\n" + content
                return
            if isinstance(prev, list) and isinstance(content, list):
                out[-1]["content"] = prev + content
                return
            if isinstance(prev, str) and isinstance(content, list):
                out[-1]["content"] = [{"type": "text", "text": prev}] + content
                return
            if isinstance(prev, list) and isinstance(content, str):
                out[-1]["content"] = prev + [{"type": "text", "text": content}]
                return
        out.append({"role": role, "content": content})

    for m in messages:
        role = str(m.get("role") or "")
        if role == "system":
            text = str(m.get("content") or "").strip()
            if text:
                system_parts.append(text)
            continue
        if role == "user":
            push("user", str(m.get("content") or ""))
            continue
        if role == "assistant":
            blocks: list[dict[str, Any]] = []
            text = str(m.get("content") or "")
            if text:
                blocks.append({"type": "text", "text": text})
            for tc in m.get("tool_calls") or []:
                fn = tc.get("function") or {}
                raw_args = fn.get("arguments") or "{}"
                if isinstance(raw_args, str):
                    try:
                        inp = json.loads(raw_args or "{}")
                    except json.JSONDecodeError:
                        inp = {"_raw": raw_args}
                elif isinstance(raw_args, dict):
                    inp = raw_args
                else:
                    inp = {}
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": str(tc.get("id") or uuid.uuid4().hex),
                        "name": str(fn.get("name") or ""),
                        "input": inp if isinstance(inp, dict) else {"value": inp},
                    },
                )
            if blocks:
                push("assistant", blocks)
            continue
        if role == "tool":
            push(
                "user",
                [
                    {
                        "type": "tool_result",
                        "tool_use_id": str(m.get("tool_call_id") or ""),
                        "content": str(m.get("content") or ""),
                    },
                ],
            )
            continue

    if not out:
        out.append({"role": "user", "content": "(empty)"})
    return "\n\n".join(system_parts), out


def anthropic_content_to_openai(content: Any) -> tuple[str, list[dict[str, Any]]]:
    """Parse Anthropic message content → text + OpenAI tool_calls."""
    if isinstance(content, str):
        return content, []
    texts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    if not isinstance(content, list):
        return "", []
    for block in content:
        if not isinstance(block, dict):
            continue
        btype = block.get("type")
        if btype == "text":
            texts.append(str(block.get("text") or ""))
        elif btype == "tool_use":
            inp = block.get("input")
            if not isinstance(inp, (dict, list)):
                inp = {}
            tool_calls.append(
                {
                    "id": str(block.get("id") or uuid.uuid4().hex),
                    "type": "function",
                    "function": {
                        "name": str(block.get("name") or ""),
                        "arguments": json.dumps(inp, ensure_ascii=False),
                    },
                },
            )
    return "".join(texts), tool_calls


class AnthropicMessagesLLM:
    """
    Anthropic Messages API (`POST /v1/messages`).

    Accepts OpenAI-shaped messages/tools from the agent loop and returns
    OpenAI-shaped ``tool_calls`` so the rest of the stack stays unchanged.
    """

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_ANTHROPIC_BASE,
        model: str,
        api_key: str = "",
        trust_env: bool = False,
        mock: bool = False,
        stream: bool = True,
        max_tokens: int = 8192,
    ) -> None:
        self.base_url = normalize_anthropic_base(base_url)
        self.model = model
        self.api_key = api_key
        self.trust_env = trust_env
        self.mock = mock
        self.stream_enabled = stream
        self.max_tokens = max_tokens
        self._mock_handler: Callable[[list[dict[str, Any]]], LLMResult] | None = None

    def set_mock_handler(
        self,
        handler: Callable[[list[dict[str, Any]]], LLMResult],
    ) -> None:
        self._mock_handler = handler

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key or "",
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

    def _messages_url(self) -> str:
        return f"{self.base_url}/v1/messages"

    def _mock_result(self, messages: list[dict[str, Any]]) -> LLMResult:
        if self._mock_handler:
            return self._mock_handler(messages)
        fixed = os.getenv("CAI_MOCK_REPLY")
        if fixed:
            return LLMResult(content=fixed)
        return LLMResult(content="ok")

    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
        on_chunk: Callable[[StreamChunk], None] | None = None,
        stream: bool | None = None,
    ) -> LLMResult:
        use_stream = self.stream_enabled if stream is None else stream

        if self.mock or self._mock_handler:
            result = self._mock_result(messages)
            if on_chunk and result.content:
                text = result.content
                step = max(1, len(text) // 4)
                for i in range(0, len(text), step):
                    on_chunk(StreamChunk(kind="text", text=text[i : i + step]))
            for tc in result.tool_calls:
                if on_chunk:
                    on_chunk(StreamChunk(kind="tool_call", tool_call=tc))
            if on_chunk:
                on_chunk(StreamChunk(kind="done"))
            return result

        if use_stream:
            try:
                return await self._complete_stream(
                    messages,
                    tools=tools,
                    temperature=temperature,
                    on_chunk=on_chunk,
                )
            except Exception:
                return await self._complete_once(
                    messages,
                    tools=tools,
                    temperature=temperature,
                    on_chunk=on_chunk,
                )
        return await self._complete_once(
            messages,
            tools=tools,
            temperature=temperature,
            on_chunk=on_chunk,
        )

    def _payload(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None,
        temperature: float,
        stream: bool,
    ) -> dict[str, Any]:
        system, anth_messages = openai_messages_to_anthropic(messages)
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": anth_messages,
            "max_tokens": self.max_tokens,
            "temperature": temperature,
            "stream": stream,
        }
        if system:
            payload["system"] = system
        anth_tools = openai_tools_to_anthropic(tools)
        if anth_tools:
            payload["tools"] = anth_tools
        return payload

    async def _complete_once(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None,
        temperature: float,
        on_chunk: Callable[[StreamChunk], None] | None,
    ) -> LLMResult:
        payload = self._payload(messages, tools=tools, temperature=temperature, stream=False)
        async with httpx.AsyncClient(timeout=180.0, trust_env=self.trust_env) as client:
            r = await client.post(self._messages_url(), json=payload, headers=self._headers())
        if r.status_code >= 400:
            raise RuntimeError(f"Anthropic HTTP {r.status_code}: {r.text}")
        data = r.json()
        content, tool_calls = anthropic_content_to_openai(data.get("content"))
        result = LLMResult(content=content, tool_calls=tool_calls)
        if on_chunk and content:
            on_chunk(StreamChunk(kind="text", text=content))
        for tc in tool_calls:
            if on_chunk:
                on_chunk(StreamChunk(kind="tool_call", tool_call=tc))
        if on_chunk:
            on_chunk(StreamChunk(kind="done"))
        return result

    async def _complete_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None,
        temperature: float,
        on_chunk: Callable[[StreamChunk], None] | None,
    ) -> LLMResult:
        payload = self._payload(messages, tools=tools, temperature=temperature, stream=True)
        content_parts: list[str] = []
        # index -> accumulating tool call (OpenAI shape)
        tool_acc: dict[int, dict[str, Any]] = {}
        # index -> raw json string for input
        tool_json: dict[int, str] = {}

        async with httpx.AsyncClient(timeout=180.0, trust_env=self.trust_env) as client:
            async with client.stream(
                "POST",
                self._messages_url(),
                json=payload,
                headers=self._headers(),
            ) as resp:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    raise RuntimeError(
                        f"Anthropic HTTP {resp.status_code}: {body.decode('utf-8', 'replace')}",
                    )
                async for line in resp.aiter_lines():
                    if not line or line.startswith(":"):
                        continue
                    if not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if not data_str or data_str == "[DONE]":
                        continue
                    try:
                        event = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    etype = event.get("type")
                    if etype == "content_block_start":
                        idx = int(event.get("index") or 0)
                        block = event.get("content_block") or {}
                        if block.get("type") == "tool_use":
                            tool_acc[idx] = {
                                "id": str(block.get("id") or uuid.uuid4().hex),
                                "type": "function",
                                "function": {
                                    "name": str(block.get("name") or ""),
                                    "arguments": "",
                                },
                            }
                            tool_json[idx] = ""
                    elif etype == "content_block_delta":
                        idx = int(event.get("index") or 0)
                        delta = event.get("delta") or {}
                        dtype = delta.get("type")
                        if dtype == "text_delta":
                            piece = str(delta.get("text") or "")
                            if piece:
                                content_parts.append(piece)
                                if on_chunk:
                                    on_chunk(StreamChunk(kind="text", text=piece, raw=event))
                        elif dtype == "input_json_delta":
                            piece = str(delta.get("partial_json") or "")
                            tool_json[idx] = tool_json.get(idx, "") + piece
                            if idx in tool_acc:
                                tool_acc[idx]["function"]["arguments"] = tool_json[idx]
                    elif etype == "content_block_stop":
                        idx = int(event.get("index") or 0)
                        if idx in tool_acc:
                            args = tool_acc[idx]["function"].get("arguments") or ""
                            if not args:
                                tool_acc[idx]["function"]["arguments"] = "{}"
                            elif args and not args.strip().startswith(("{", "[")):
                                # keep as-is; agent will wrap on parse failure
                                pass

        tool_calls = [tool_acc[i] for i in sorted(tool_acc)]
        for tc in tool_calls:
            if on_chunk:
                on_chunk(StreamChunk(kind="tool_call", tool_call=tc))
        if on_chunk:
            on_chunk(StreamChunk(kind="done"))
        return LLMResult(content="".join(content_parts), tool_calls=tool_calls)

    async def stream(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
    ) -> AsyncIterator[StreamChunk]:
        queue: list[StreamChunk] = []

        def on_chunk(ch: StreamChunk) -> None:
            queue.append(ch)

        await self.complete(
            messages,
            tools=tools,
            temperature=temperature,
            on_chunk=on_chunk,
            stream=True,
        )
        for ch in queue:
            yield ch
