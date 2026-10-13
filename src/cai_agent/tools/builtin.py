from __future__ import annotations

import asyncio
import os
import subprocess
from typing import Any

from cai_agent.pi_core.tools_registry import ToolSpec
from cai_agent.sandbox import SandboxError, resolve_workspace_path


def build_default_tools(workspace: str, *, timeout: float = 120.0) -> list[ToolSpec]:
    return [
        _read_tool(workspace),
        _write_tool(workspace),
        _edit_tool(workspace),
        _bash_tool(workspace, timeout=timeout),
    ]


def _read_tool(workspace: str) -> ToolSpec:
    async def handler(args: dict[str, Any]) -> str:
        path = str(args.get("path") or "")
        try:
            p = resolve_workspace_path(workspace, path)
        except SandboxError as e:
            return f"error: {e}"
        if not p.is_file():
            return f"error: not a file: {path}"
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"error: binary file ({p.stat().st_size} bytes)"
        if len(text) > 80_000:
            return text[:80_000] + "\n…[truncated]"
        return text

    return ToolSpec(
        name="read",
        description="Read a text file relative to the workspace cwd.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative file path"}},
            "required": ["path"],
        },
        handler=handler,
    )


def _write_tool(workspace: str) -> ToolSpec:
    async def handler(args: dict[str, Any]) -> str:
        path = str(args.get("path") or "")
        content = str(args.get("content") if args.get("content") is not None else "")
        try:
            p = resolve_workspace_path(workspace, path)
        except SandboxError as e:
            return f"error: {e}"
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        except OSError as e:
            return f"error: {e}"
        return f"Successfully wrote {len(content.encode('utf-8'))} bytes to {path}"

    return ToolSpec(
        name="write",
        description="Write content to a file. Creates parents; overwrites if exists.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
        handler=handler,
    )


def _edit_tool(workspace: str) -> ToolSpec:
    async def handler(args: dict[str, Any]) -> str:
        path = str(args.get("path") or "")
        old = str(args.get("old_str") if args.get("old_str") is not None else "")
        new = str(args.get("new_str") if args.get("new_str") is not None else "")
        if not old:
            return "error: old_str required"
        try:
            p = resolve_workspace_path(workspace, path)
        except SandboxError as e:
            return f"error: {e}"
        if not p.is_file():
            return f"error: not a file: {path}"
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return "error: binary file"
        count = text.count(old)
        if count == 0:
            return "error: old_str not found"
        if count > 1:
            return f"error: old_str matched {count} times; make it unique"
        updated = text.replace(old, new, 1)
        p.write_text(updated, encoding="utf-8")
        return f"edited {path}: replaced {len(old)} chars with {len(new)} chars"

    return ToolSpec(
        name="edit",
        description="Exact string replacement in a file. old_str must match exactly once.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_str": {"type": "string"},
                "new_str": {"type": "string"},
            },
            "required": ["path", "old_str", "new_str"],
        },
        handler=handler,
    )


def _bash_tool(workspace: str, *, timeout: float) -> ToolSpec:
    async def handler(args: dict[str, Any]) -> str:
        command = str(args.get("command") or "")
        if not command.strip():
            return "error: empty command"
        to = float(args.get("timeout") or timeout)
        if os.name == "nt":
            shell_cmd = ["powershell", "-NoProfile", "-Command", command]
        else:
            shell_cmd = ["bash", "-lc", command]

        def run() -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                shell_cmd,
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=to,
                env=os.environ.copy(),
            )

        try:
            proc = await asyncio.to_thread(run)
        except subprocess.TimeoutExpired:
            return f"error: timed out after {to}s"
        except FileNotFoundError as e:
            return f"error: shell not found: {e}"
        out = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
        out = out.strip()
        if len(out) > 60_000:
            out = out[-60_000:] + "\n…[truncated]"
        if proc.returncode != 0:
            return f"exit {proc.returncode}\n{out}" if out else f"exit {proc.returncode}"
        return out or "(no output)"

    return ToolSpec(
        name="bash",
        description="Execute a shell command in the workspace cwd. Returns stdout/stderr.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "number", "description": "Seconds"},
            },
            "required": ["command"],
        },
        handler=handler,
    )
