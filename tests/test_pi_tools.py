from __future__ import annotations

import asyncio

from cai_agent.sandbox import SandboxError, resolve_workspace_path
from cai_agent.tools.builtin import build_default_tools


def test_read_write_edit_bash(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    tools = {t.name: t for t in build_default_tools(str(ws), timeout=30)}

    async def run():
        w = await tools["write"].handler({"path": "a.txt", "content": "hello\n"})
        assert "Successfully wrote" in w
        r = await tools["read"].handler({"path": "a.txt"})
        assert r == "hello\n"
        e = await tools["edit"].handler(
            {"path": "a.txt", "old_str": "hello", "new_str": "hi"},
        )
        assert "edited" in e
        assert (ws / "a.txt").read_text(encoding="utf-8") == "hi\n"
        b = await tools["bash"].handler({"command": "echo pi-ok"})
        assert "pi-ok" in b

    asyncio.run(run())


def test_path_escape(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    tools = {t.name: t for t in build_default_tools(str(ws))}

    async def run():
        out = await tools["read"].handler({"path": "../secret.txt"})
        assert out.startswith("error:")

    asyncio.run(run())
    try:
        resolve_workspace_path(str(ws), "../x")
        assert False, "expected SandboxError"
    except SandboxError:
        pass
