"""Unified presentation-facing agent events (Harness UI ↔ Pi engine)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventKind(str, Enum):
    """Canonical event kinds for UI adapters."""

    STEP_START = "StepStart"
    THINKING_STREAM = "ThinkingStream"
    TOOL_INVOKE = "ToolInvoke"
    TOOL_RESULT = "ToolResult"
    MESSAGE_STREAM = "MessageStream"
    FINISHED = "Finished"


@dataclass(frozen=True)
class AgentEvent:
    """
    Presentation-neutral agent event.

    The engine never imports UI code; UIs subscribe to an :class:`EventBus`
    and render these events only.
    """

    kind: EventKind
    session_id: str = ""
    step: int = 0
    delta: str = ""
    tool_name: str = ""
    tool_call_id: str = ""
    ok: bool = True
    data: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "session_id": self.session_id,
            "step": self.step,
            "delta": self.delta,
            "tool_name": self.tool_name,
            "tool_call_id": self.tool_call_id,
            "ok": self.ok,
            "data": self.data,
        }
