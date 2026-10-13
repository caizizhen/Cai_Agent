from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from cai_agent.llm.openai_compat import LLMResult, StreamChunk
from cai_agent.pi_core.context import truncate_messages
from cai_agent.pi_core.messages import AgentMessage, convert_to_llm
from cai_agent.pi_core.tools_registry import ToolRegistry


class _LLM(Protocol):
    async def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.2,
        on_chunk: Callable[[StreamChunk], None] | None = None,
        stream: bool | None = None,
    ) -> LLMResult: ...


@dataclass
class AgentEvent:
    """Internal engine event (not for UI). Prefer adapter.AgentEvent in surfaces."""

    type: str
    data: dict[str, Any] = field(default_factory=dict)


Listener = Callable[[AgentEvent], None]


DEFAULT_SYSTEM = """You are CAI, a minimal coding agent (Pi-style).
Use tools to inspect and change files in the workspace. Prefer small, correct edits.
Available tools: read, write, edit, bash.
When done, reply with a short summary — no unnecessary tool calls."""


class Agent:
    """
    Pi-inspired agent loop: sequential tool turns until the model stops.

    Emits internal events (`agent_start`, `turn_start`, `message_update`,
    `tool_execution_*`, `agent_end`). Presentation layers should listen via
    :class:`cai_agent.adapter.bridge.EngineBridge` instead of this class.
    """

    def __init__(
        self,
        *,
        llm: _LLM,
        tools: ToolRegistry,
        system_prompt: str = DEFAULT_SYSTEM,
        max_turns: int = 16,
        max_context_messages: int = 80,
    ) -> None:
        self.llm = llm
        self.tools = tools
        self.system_prompt = system_prompt
        self.max_turns = max_turns
        self.max_context_messages = max_context_messages
        self._listeners: list[Listener] = []
        self._abort = asyncio.Event()

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        self._listeners.append(listener)

        def unsub() -> None:
            try:
                self._listeners.remove(listener)
            except ValueError:
                pass

        return unsub

    def _emit(self, typ: str, **data: Any) -> None:
        ev = AgentEvent(type=typ, data=data)
        for lis in list(self._listeners):
            try:
                lis(ev)
            except Exception:
                pass

    def request_abort(self) -> None:
        self._abort.set()

    def clear_abort(self) -> None:
        self._abort = asyncio.Event()

    @property
    def aborted(self) -> bool:
        return self._abort.is_set()

    async def run(
        self,
        history: list[AgentMessage],
        user_text: str,
    ) -> list[AgentMessage]:
        """Append user message and run until idle. Returns newly produced messages."""
        self.clear_abort()
        produced: list[AgentMessage] = []
        user_msg = AgentMessage(role="user", content=user_text)
        produced.append(user_msg)
        history = list(history) + [user_msg]

        self._emit("agent_start")
        try:
            for _ in range(self.max_turns):
                if self.aborted:
                    break
                self._emit("turn_start")
                self._emit("message_start", role="user" if False else "assistant")

                ctx = truncate_messages(history, max_messages=self.max_context_messages)
                messages = [AgentMessage(role="system", content=self.system_prompt)] + ctx

                text_acc: list[str] = []

                def on_chunk(ch: StreamChunk) -> None:
                    if ch.kind == "text" and ch.text:
                        text_acc.append(ch.text)
                        self._emit("message_update", delta=ch.text, kind="text")

                result: LLMResult = await self.llm.complete(
                    convert_to_llm(messages),
                    tools=self.tools.openai_schemas(),
                    on_chunk=on_chunk,
                )
                if self.aborted:
                    break

                assistant = AgentMessage(
                    role="assistant",
                    content=result.content or "".join(text_acc),
                    tool_calls=list(result.tool_calls or []),
                )
                produced.append(assistant)
                history.append(assistant)
                self._emit(
                    "message_end",
                    role="assistant",
                    content=assistant.content,
                    tool_calls=assistant.tool_calls,
                )

                if not assistant.tool_calls:
                    self._emit("turn_end", tool_results=[])
                    break

                tool_results_meta: list[dict[str, Any]] = []
                for tc in assistant.tool_calls:
                    if self.aborted:
                        break
                    fn = tc.get("function") or {}
                    name = str(fn.get("name") or "")
                    args = fn.get("arguments") or "{}"
                    tc_id = str(tc.get("id") or uuid.uuid4().hex)
                    self._emit(
                        "tool_execution_start",
                        tool_call_id=tc_id,
                        tool_name=name,
                        args=args,
                    )
                    try:
                        out = await self.tools.execute(name, args)
                    except Exception as e:
                        out = f"error: {e}"
                    self._emit(
                        "tool_execution_end",
                        tool_call_id=tc_id,
                        tool_name=name,
                        result=out[:4000],
                    )
                    tr = AgentMessage(
                        role="tool",
                        content=out,
                        tool_call_id=tc_id,
                        name=name,
                    )
                    produced.append(tr)
                    history.append(tr)
                    tool_results_meta.append({"id": tc_id, "name": name})
                    self._emit("message_end", role="tool", name=name, content=out[:2000])

                self._emit("turn_end", tool_results=tool_results_meta)
            return produced
        finally:
            self._emit("agent_end", messages=len(produced))
