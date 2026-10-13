"""Interactive Harness-style REPL (async), driven by EventBus."""

from __future__ import annotations

import asyncio
import sys

from cai_agent.config import Settings
from cai_agent.engine.factory import create_engine
from cai_agent.ui.cli_render import HarnessRenderer


async def run_tui(settings: Settings) -> int:
    """
    Run an interactive prompt loop.

    Type a task and press Enter. Empty line or ``/exit`` quits.
    ``/abort`` cancels the current turn.
    """
    handle = create_engine(settings=settings)
    renderer = HarnessRenderer(
        handle.bus,
        stream=settings.stream,
        debug=settings.debug,
    )
    renderer.print_banner(model=settings.model, workspace=handle.session.workspace)
    print(f"session={handle.session.session_id}", file=sys.stderr)
    print("Commands: /exit  /abort  /help\n", file=sys.stderr)

    try:
        while True:
            try:
                line = await asyncio.to_thread(input, "cai › ")
            except (EOFError, KeyboardInterrupt):
                print()
                break
            text = line.strip()
            if not text:
                continue
            if text in ("/exit", "/quit", ":q"):
                break
            if text == "/help":
                print("  /exit  /abort  — or type a coding task")
                continue
            if text == "/abort":
                await handle.abort()
                continue
            try:
                await handle.prompt(text)
            except Exception as e:
                print(f"error: {e}", file=sys.stderr)
    finally:
        renderer.close()
    return 0


def run_tui_sync(settings: Settings) -> int:
    return asyncio.run(run_tui(settings))
