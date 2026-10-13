"""Factory: build a Pi engine session + adapter bridge."""

from __future__ import annotations

from dataclasses import dataclass

from cai_agent.adapter.bridge import EngineBridge
from cai_agent.adapter.bus import EventBus
from cai_agent.config import Settings
from cai_agent.llm.factory import LLMClient
from cai_agent.pi_session.session import AgentSession, create_agent_session
from cai_agent.pi_session.store import SessionStore


@dataclass
class EngineHandle:
    """Bundled session + event bridge for UI surfaces."""

    session: AgentSession
    bridge: EngineBridge
    bus: EventBus
    settings: Settings

    async def prompt(self, text: str):
        return await self.bridge.prompt(text)

    async def abort(self) -> None:
        await self.bridge.abort()


def create_engine(
    *,
    workspace: str | None = None,
    session_id: str | None = None,
    settings: Settings | None = None,
    llm: LLMClient | None = None,
    store: SessionStore | None = None,
    bus: EventBus | None = None,
) -> EngineHandle:
    """
    Create a Pi-style agent session wired to a presentation :class:`EventBus`.

    Parameters
    ----------
    workspace:
        Sandbox root (defaults to settings.workspace).
    session_id:
        Resume an existing session id, or allocate a new one.
    settings / llm / store / bus:
        Optional overrides for tests and custom surfaces.
    """
    settings = settings or Settings.from_env()
    bus = bus or EventBus()
    session = create_agent_session(
        workspace=workspace,
        session_id=session_id,
        settings=settings,
        llm=llm,
        store=store,
    )
    # Apply max steps from settings
    session.agent.max_turns = settings.max_iterations
    bridge = EngineBridge(bus)
    bridge.attach(session)
    return EngineHandle(session=session, bridge=bridge, bus=bus, settings=settings)
