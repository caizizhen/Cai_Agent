from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentMessage:
    role: str  # user | assistant | tool | system
    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_call_id: str = ""
    name: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


def convert_to_llm(messages: list[AgentMessage]) -> list[dict[str, Any]]:
    """Filter/convert AgentMessages to OpenAI chat messages."""
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "system":
            out.append({"role": "system", "content": m.content})
        elif m.role == "user":
            out.append({"role": "user", "content": m.content})
        elif m.role == "assistant":
            msg: dict[str, Any] = {"role": "assistant", "content": m.content or ""}
            if m.tool_calls:
                msg["tool_calls"] = m.tool_calls
            out.append(msg)
        elif m.role == "tool":
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": m.tool_call_id,
                    "name": m.name,
                    "content": m.content,
                },
            )
    return out
