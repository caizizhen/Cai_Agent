"""Context window helpers (sliding / truncation)."""

from __future__ import annotations

from cai_agent.pi_core.messages import AgentMessage


def truncate_messages(
    messages: list[AgentMessage],
    *,
    max_messages: int = 80,
) -> list[AgentMessage]:
    """Keep the newest messages while avoiding cutting mid tool-result."""
    if max_messages <= 0 or len(messages) <= max_messages:
        return list(messages)
    start = len(messages) - max_messages
    while start > 0 and messages[start].role == "tool":
        start -= 1
    return list(messages[start:])
