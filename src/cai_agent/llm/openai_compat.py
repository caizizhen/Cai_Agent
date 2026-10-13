from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class StreamChunk:
    kind: str  # text | tool_call | done
    text: str = ""
    tool_call: dict[str, Any] | None = None
    raw: dict[str, Any] | None = None


@dataclass
class LLMResult:
    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    chunks: list[StreamChunk] = field(default_factory=list)


class OpenAICompatLLM:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str = "lm-studio",
        trust_env: bool = False,
        mock: bool = False,
        stream: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        if not self.base_url.endswith("/v1"):
            self.base_url += "/v1"
        self.model = model
        self.api_key = api_key
        self.trust_env = trust_env
        self.mock = mock
        self.stream_enabled = stream
        self._mock_handler: Callable[[list[dict[str, Any]]], LLMResult] | None = None

    def set_mock_handler(
        self,
        handler: Callable[[list[dict[str, Any]]], LLMResult],
    ) -> None:
        self._mock_handler = handler

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

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
                # Simulate incremental chunks for UI/tests
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
                # Fall back to non-stream if provider rejects streaming
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

    async def _complete_once(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None,
        temperature: float,
        on_chunk: Callable[[StreamChunk], None] | None,
    ) -> LLMResult:
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(
            timeout=180.0,
            trust_env=self.trust_env,
        ) as client:
            r = await client.post(url, json=payload, headers=self._headers())
        if r.status_code >= 400:
            raise RuntimeError(f"LLM HTTP {r.status_code}: {r.text}")
        data = r.json()
        msg = data["choices"][0]["message"]
        content = msg.get("content") or ""
        tool_calls = msg.get("tool_calls") or []
        result = LLMResult(content=content, tool_calls=list(tool_calls))
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
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        content_parts: list[str] = []
        # tool_index -> accumulating tool call
        tool_acc: dict[int, dict[str, Any]] = {}

        async with httpx.AsyncClient(
            timeout=180.0,
            trust_env=self.trust_env,
        ) as client:
            async with client.stream(
                "POST",
                url,
                json=payload,
                headers=self._headers(),
            ) as resp:
                if resp.status_code >= 400:
                    body = await resp.aread()
                    raise RuntimeError(
                        f"LLM HTTP {resp.status_code}: {body.decode('utf-8', 'replace')}",
                    )
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    if line.startswith(":"):
                        continue
                    if not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    piece = delta.get("content")
                    if piece:
                        content_parts.append(piece)
                        if on_chunk:
                            on_chunk(StreamChunk(kind="text", text=piece, raw=data))
                    for tc in delta.get("tool_calls") or []:
                        idx = int(tc.get("index") or 0)
                        slot = tool_acc.setdefault(
                            idx,
                            {
                                "id": "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            },
                        )
                        if tc.get("id"):
                            slot["id"] = tc["id"]
                        fn = tc.get("function") or {}
                        if fn.get("name"):
                            slot["function"]["name"] = fn["name"]
                        if fn.get("arguments"):
                            slot["function"]["arguments"] += fn["arguments"]

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


def make_llm_from_env(**overrides: Any) -> OpenAICompatLLM:
    """Backward-compatible helper; prefers factory when provider is set."""
    from cai_agent.llm.factory import make_llm_from_env as _factory

    return _factory(**overrides)  # type: ignore[return-value]
