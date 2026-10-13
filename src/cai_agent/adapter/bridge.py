"""Map Pi-engine internal events → unified :class:`AgentEvent` stream."""

from __future__ import annotations

from typing import Any

from cai_agent.adapter.bus import EventBus
from cai_agent.adapter.events import AgentEvent, EventKind
from cai_agent.pi_core.agent import AgentEvent as EngineEvent
from cai_agent.pi_session.session import AgentSession


class EngineBridge:
    """
    Adapter between the Pi-style :class:`AgentSession` and presentation UIs.

    UI code must only depend on :class:`EventBus` + :class:`AgentEvent`.
    """

    def __init__(self, bus: EventBus | None = None) -> None:
        self.bus = bus or EventBus()
        self._step = 0
        self._unsub: Any = None
        self._session: AgentSession | None = None

    def attach(self, session: AgentSession) -> None:
        """Bind a session; previous binding is replaced."""
        if self._unsub:
            self._unsub()
        self._session = session
        self._step = 0
        self._unsub = session.subscribe(self._on_engine)

    @property
    def session(self) -> AgentSession | None:
        return self._session

    def _on_engine(self, ev: EngineEvent) -> None:
        sid = self._session.session_id if self._session else ""
        typ = ev.type
        d = ev.data

        if typ in ("agent_start", "turn_start"):
            if typ == "turn_start":
                self._step += 1
            self.bus.publish(
                AgentEvent(
                    kind=EventKind.STEP_START,
                    session_id=sid,
                    step=self._step,
                    data={"engine": typ},
                ),
            )
            if typ == "turn_start":
                self.bus.publish(
                    AgentEvent(
                        kind=EventKind.THINKING_STREAM,
                        session_id=sid,
                        step=self._step,
                        delta="Planning next action…\n",
                    ),
                )
            return

        if typ == "message_update" and d.get("kind") == "text":
            self.bus.publish(
                AgentEvent(
                    kind=EventKind.MESSAGE_STREAM,
                    session_id=sid,
                    step=self._step,
                    delta=str(d.get("delta") or ""),
                ),
            )
            return

        if typ == "tool_execution_start":
            self.bus.publish(
                AgentEvent(
                    kind=EventKind.TOOL_INVOKE,
                    session_id=sid,
                    step=self._step,
                    tool_name=str(d.get("tool_name") or ""),
                    tool_call_id=str(d.get("tool_call_id") or ""),
                    data={"args": d.get("args")},
                ),
            )
            return

        if typ == "tool_execution_end":
            result = str(d.get("result") or "")
            ok = not result.startswith("error:")
            self.bus.publish(
                AgentEvent(
                    kind=EventKind.TOOL_RESULT,
                    session_id=sid,
                    step=self._step,
                    tool_name=str(d.get("tool_name") or ""),
                    tool_call_id=str(d.get("tool_call_id") or ""),
                    ok=ok,
                    data={"result": result},
                    delta=result[:500],
                ),
            )
            return

        if typ == "agent_end":
            self.bus.publish(
                AgentEvent(
                    kind=EventKind.FINISHED,
                    session_id=sid,
                    step=self._step,
                    data=d,
                ),
            )

    async def prompt(self, text: str) -> list[Any]:
        """Run a user prompt on the attached session."""
        if not self._session:
            raise RuntimeError("bridge has no session; call attach() first")
        return await self._session.prompt(text)

    async def abort(self) -> None:
        if self._session:
            await self._session.abort()
