"""DeepSeek Harness–inspired terminal renderer driven by AgentEvent bus."""

from __future__ import annotations

import sys
from typing import TextIO

from cai_agent.adapter.bus import EventBus
from cai_agent.adapter.events import AgentEvent, EventKind

try:
    from rich.console import Console
    from rich.live import Live
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.spinner import Spinner
    from rich.status import Status
    from rich.text import Text

    HAS_RICH = True
except ImportError:  # pragma: no cover
    HAS_RICH = False


BANNER = r"""
   ____    _    ___
  / ___|  / \  |_ _|
 | |     / _ \  | |
 | |___ / ___ \ | |
  \____/_/   \_\___|  Pi engine · Harness UI
"""


class HarnessRenderer:
    """
    Subscribe to :class:`EventBus` and paint a Harness-like terminal view.

    Shows step banners, thinking lines, tool invoke/result cards, and
    streaming assistant markdown.
    """

    def __init__(
        self,
        bus: EventBus,
        *,
        stream: bool = True,
        debug: bool = False,
        file: TextIO[str] | None = None,
    ) -> None:
        self.bus = bus
        self.stream = stream
        self.debug = debug
        self._file = file or sys.stdout
        self._console = Console(file=self._file, highlight=False) if HAS_RICH else None
        self._msg_buf: list[str] = []
        self._thinking_open = False
        self._unsub = bus.subscribe(self.on_event)

    def close(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    def print_banner(self, *, model: str, workspace: str) -> None:
        if self._console:
            self._console.print(BANNER, style="bold cyan")
            self._console.print(
                f"  model=[bold]{model}[/]  cwd=[dim]{workspace}[/]\n",
            )
        else:
            print(BANNER, file=self._file)
            print(f"  model={model}  cwd={workspace}\n", file=self._file)

    def on_event(self, event: AgentEvent) -> None:
        if event.kind == EventKind.STEP_START:
            self._msg_buf.clear()
            self._line(f"── step {event.step} ──", style="dim cyan")
        elif event.kind == EventKind.THINKING_STREAM:
            self._thinking_open = True
            self._line(f"💭 {event.delta.rstrip()}", style="italic yellow")
        elif event.kind == EventKind.TOOL_INVOKE:
            args = str((event.data or {}).get("args") or "")[:120]
            self._line(f"⚙  {event.tool_name}  {args}", style="bold blue")
        elif event.kind == EventKind.TOOL_RESULT:
            mark = "✓" if event.ok else "✗"
            style = "green" if event.ok else "red"
            preview = (event.delta or "").replace("\n", " ")[:160]
            self._line(f"{mark} {event.tool_name}: {preview}", style=style)
        elif event.kind == EventKind.MESSAGE_STREAM:
            if self.stream:
                self._write(event.delta)
            self._msg_buf.append(event.delta)
        elif event.kind == EventKind.FINISHED:
            if self._msg_buf and not self.stream:
                text = "".join(self._msg_buf)
                if self._console:
                    self._console.print(Panel(Markdown(text), title="CAI", border_style="cyan"))
                else:
                    print(text, file=self._file)
            elif self._msg_buf and self.stream:
                self._write("\n")
            self._line("■ finished", style="dim")
            if self.debug:
                self._line(f"debug: {event.data}", style="dim")

    def _line(self, text: str, *, style: str = "") -> None:
        if self._console:
            self._console.print(text, style=style or None)
        else:
            print(text, file=self._file)

    def _write(self, text: str) -> None:
        if self._console:
            self._console.print(text, end="", soft_wrap=True, highlight=False)
        else:
            self._file.write(text)
            self._file.flush()
