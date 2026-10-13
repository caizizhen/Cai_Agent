from __future__ import annotations

import asyncio
import time
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
        *,
        images: list[dict[str, Any]] | None = None,
    ) -> list[AgentMessage]:
        """Append user message and run until idle. Returns newly produced messages."""
        self.clear_abort()
        produced: list[AgentMessage] = []
        meta: dict[str, Any] = {}
        if images:
            meta["images"] = list(images)
        user_msg = AgentMessage(role="user", content=user_text, meta=meta)
        produced.append(user_msg)
        history = list(history) + [user_msg]

        run_usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
        }
        run_metrics: dict[str, Any] = {
            "rounds": 1,
            "steps": 0,
            "model_ms": 0.0,
            "tool_ms": 0.0,
            "ttft_sum_ms": 0.0,
            "ttft_count": 0,
        }
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
                first_token_at: float | None = None
                llm_started = time.perf_counter()

                def on_chunk(ch: StreamChunk) -> None:
                    nonlocal first_token_at
                    if ch.kind == "text" and ch.text:
                        if first_token_at is None:
                            first_token_at = time.perf_counter()
                        text_acc.append(ch.text)
                        self._emit("message_update", delta=ch.text, kind="text")

                result: LLMResult = await self.llm.complete(
                    convert_to_llm(messages),
                    tools=self.tools.openai_schemas(),
                    on_chunk=on_chunk,
                )
                llm_ms = (time.perf_counter() - llm_started) * 1000.0
                run_metrics["model_ms"] += llm_ms
                run_metrics["steps"] += 1
                if first_token_at is not None:
                    run_metrics["ttft_sum_ms"] += (first_token_at - llm_started) * 1000.0
                    run_metrics["ttft_count"] += 1
                if self.aborted:
                    break

                content = result.content or "".join(text_acc)
                usage = dict(result.usage or {})
                if not usage.get("total_tokens"):
                    est = max(1, (len(content) + 3) // 4)
                    usage = {"prompt_tokens": 0, "completion_tokens": est, "total_tokens": est}
                for k in run_usage:
                    run_usage[k] += int(usage.get(k) or 0)
                assistant = AgentMessage(
                    role="assistant",
                    content=content,
                    tool_calls=list(result.tool_calls or []),
                    meta={"usage": usage},
                )
                produced.append(assistant)
                history.append(assistant)
                self._emit(
                    "message_end",
                    role="assistant",
                    content=assistant.content,
                    tool_calls=assistant.tool_calls,
                    usage=usage,
                )

                if not assistant.tool_calls:
                    self._emit("turn_end", tool_results=[], usage=usage)
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
                    tool_started = time.perf_counter()
                    try:
                        out = await self.tools.execute(name, args, tool_call_id=tc_id)
                    except Exception as e:
                        out = f"error: {e}"
                    run_metrics["tool_ms"] += (time.perf_counter() - tool_started) * 1000.0
                    run_metrics["steps"] += 1
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
            self._emit(
                "agent_end",
                messages=len(produced),
                usage=run_usage,
                metrics=run_metrics,
            )
