"""Async-friendly in-process event bus."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from cai_agent.adapter.events import AgentEvent

Listener = Callable[[AgentEvent], Any]


class EventBus:
    """Publish/subscribe bus. Sync and async listeners are supported."""

    def __init__(self) -> None:
        self._listeners: list[Listener] = []
        self._queues: list[asyncio.Queue[AgentEvent]] = []

    def subscribe(self, listener: Listener) -> Callable[[], None]:
        """Register a callback; returns an unsubscribe function."""
        self._listeners.append(listener)

        def unsub() -> None:
            try:
                self._listeners.remove(listener)
            except ValueError:
                pass

        return unsub

    def add_queue(self) -> asyncio.Queue[AgentEvent]:
        """Create a queue that receives every published event (for SSE/UI)."""
        q: asyncio.Queue[AgentEvent] = asyncio.Queue()
        self._queues.append(q)
        return q

    def remove_queue(self, q: asyncio.Queue[AgentEvent]) -> None:
        try:
            self._queues.remove(q)
        except ValueError:
            pass

    def publish(self, event: AgentEvent) -> None:
        """Publish synchronously; schedule async listeners on the running loop."""
        for lis in list(self._listeners):
            try:
                result = lis(event)
                if asyncio.iscoroutine(result) or isinstance(result, Awaitable):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(result)  # type: ignore[arg-type]
                    except RuntimeError:
                        pass
            except Exception:
                pass
        for q in list(self._queues):
            try:
                q.put_nowait(event)
            except Exception:
                pass
