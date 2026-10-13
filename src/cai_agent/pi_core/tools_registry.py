from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


ToolHandler = Callable[[dict[str, Any]], Awaitable[str] | str]
# Returns True to allow, False to deny. Optional async gate before tool runs.
ApprovalGate = Callable[[str, dict[str, Any], str], Awaitable[bool] | bool]


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler


@dataclass
class ToolRegistry:
    tools: dict[str, ToolSpec] = field(default_factory=dict)
    approval_gate: ApprovalGate | None = None

    def register(self, spec: ToolSpec) -> None:
        self.tools[spec.name] = spec

    def openai_schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self.tools.values()
        ]

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any] | str,
        *,
        tool_call_id: str = "",
    ) -> str:
        if name not in self.tools:
            return f"error: unknown tool {name}"
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments or "{}")
            except json.JSONDecodeError:
                arguments = {"_raw": arguments}
        if not isinstance(arguments, dict):
            arguments = {}
        if self.approval_gate is not None:
            allowed = self.approval_gate(name, arguments, tool_call_id or "")
            if hasattr(allowed, "__await__"):
                allowed = await allowed  # type: ignore[misc]
            if not allowed:
                return f"error: tool '{name}' denied by approval policy"
        result = self.tools[name].handler(arguments)
        if hasattr(result, "__await__"):
            return await result  # type: ignore[misc]
        return str(result)
