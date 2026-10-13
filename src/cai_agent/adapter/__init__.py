"""Adapter layer: EventBus + EngineBridge (UI ↔ Pi engine decoupling)."""

from cai_agent.adapter.bridge import EngineBridge
from cai_agent.adapter.bus import EventBus
from cai_agent.adapter.events import AgentEvent, EventKind

__all__ = ["AgentEvent", "EngineBridge", "EventBus", "EventKind"]
