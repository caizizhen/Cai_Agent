from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from cai_agent.config import Settings
from cai_agent.llm.factory import LLMClient, make_llm
from cai_agent.pi_core.agent import Agent, AgentEvent
from cai_agent.pi_core.messages import AgentMessage
from cai_agent.pi_core.tools_registry import ToolRegistry
from cai_agent.pi_session.store import SessionStore
from cai_agent.tools import build_default_tools


class AgentSession:
    def __init__(
        self,
        *,
        session_id: str,
        agent: Agent,
        store: SessionStore,
        workspace: str,
    ) -> None:
        self.session_id = session_id
        self.agent = agent
        self.store = store
        self.workspace = workspace
        self._listeners: list[Callable[[AgentEvent], None]] = []
        self._busy = False
        self._task: asyncio.Task[None] | None = None
        self.agent.subscribe(self._fanout)

    def _fanout(self, ev: AgentEvent) -> None:
        for lis in list(self._listeners):
            try:
                lis(ev)
            except Exception:
                pass

    def subscribe(self, listener: Callable[[AgentEvent], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def unsub() -> None:
            try:
                self._listeners.remove(listener)
            except ValueError:
                pass

        return unsub

    @property
    def is_streaming(self) -> bool:
        return self._busy

    def messages(self) -> list[AgentMessage]:
        return self.store.load_messages(self.session_id)

    async def prompt(self, text: str) -> list[AgentMessage]:
        if self._busy:
            raise RuntimeError("session busy")
        self._busy = True
        try:
            history = self.store.load_messages(self.session_id)
            produced = await self.agent.run(history, text)
            for m in produced:
                self.store.append(self.session_id, m)
            return produced
        finally:
            self._busy = False

    async def abort(self) -> None:
        self.agent.request_abort()


def create_agent_session(
    *,
    workspace: str | None = None,
    session_id: str | None = None,
    settings: Settings | None = None,
    llm: LLMClient | None = None,
    store: SessionStore | None = None,
) -> AgentSession:
    settings = settings or Settings.from_env()
    workspace = workspace or settings.workspace
    store = store or SessionStore()
    sid = session_id or store.new_id()
    if llm is None:
        llm = make_llm(settings)
    registry = ToolRegistry()
    for spec in build_default_tools(workspace, timeout=settings.command_timeout_sec):
        registry.register(spec)
    agent = Agent(llm=llm, tools=registry, max_turns=settings.max_iterations)
    # ensure file exists + bind workspace for Harness-style sidebar tree
    store.path_for(sid)
    store.ensure_meta(sid, workspace=workspace)
    return AgentSession(session_id=sid, agent=agent, store=store, workspace=workspace)


# re-export for convenience
__all__ = ["AgentSession", "SessionStore", "create_agent_session"]
