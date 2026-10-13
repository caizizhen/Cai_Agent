"""High-level runtime helpers used by CLI and tests."""

from __future__ import annotations

import asyncio
from typing import Any

from cai_agent.config import Settings
from cai_agent.engine.factory import EngineHandle, create_engine
from cai_agent.llm.openai_compat import OpenAICompatLLM
from cai_agent.pi_session.store import SessionStore
from cai_agent.ui.cli_render import HarnessRenderer


async def run_once(
    goal: str,
    *,
    settings: Settings | None = None,
    session_id: str | None = None,
    llm: OpenAICompatLLM | None = None,
    quiet: bool = False,
    render: bool = True,
) -> dict[str, Any]:
    """
    Run one prompt through the layered engine + optional Harness renderer.

    Parameters
    ----------
    goal:
        User task text.
    quiet:
        If True, skip banner/tool chrome and only collect the reply.
    render:
        If True and not quiet, paint Harness-style terminal output from the bus.
    """
    settings = settings or Settings.from_env()
    handle = create_engine(settings=settings, session_id=session_id, llm=llm)
    renderer: HarnessRenderer | None = None
    if render and not quiet:
        renderer = HarnessRenderer(
            handle.bus,
            stream=settings.stream,
            debug=settings.debug,
        )
        renderer.print_banner(model=settings.model, workspace=handle.session.workspace)
    try:
        produced = await handle.prompt(goal)
    finally:
        if renderer:
            renderer.close()
    assistant_texts = [m.content for m in produced if m.role == "assistant" and m.content]
    return {
        "session_id": handle.session.session_id,
        "workspace": handle.session.workspace,
        "reply": assistant_texts[-1] if assistant_texts else "",
        "messages": len(produced),
        "architecture": "layered-pi+harness-ui",
    }


def run_sync(goal: str, **kwargs: Any) -> dict[str, Any]:
    """Synchronous wrapper around :func:`run_once`."""
    return asyncio.run(run_once(goal, **kwargs))


def list_sessions() -> list[dict[str, Any]]:
    store = SessionStore()
    return [{"id": sid, "preview": store.preview(sid)} for sid in store.list_ids()]


def dump_info(settings: Settings | None = None) -> dict[str, Any]:
    """Return a JSON-serializable dump of runtime configuration."""
    s = settings or Settings.from_env()
    return {
        "architecture": "layered-pi+harness-ui",
        "layers": ["ui", "adapter", "engine"],
        "version": __import__("cai_agent").__version__,
        "workspace": s.workspace,
        "model": s.model,
        "base_url": s.base_url,
        "max_steps": s.max_iterations,
        "stream": s.stream,
        "debug": s.debug,
        "tools": ["read", "write", "edit", "bash"],
        "mock": s.mock,
    }


__all__ = [
    "EngineHandle",
    "create_engine",
    "dump_info",
    "list_sessions",
    "run_once",
    "run_sync",
]
