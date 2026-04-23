from __future__ import annotations

import io
import json

from cai_agent.mcp_serve import run_stdio_mcp_server


def test_mcp_serve_initialize_and_tools_list_in_memory() -> None:
    blob = (
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        + "\n"
        + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        + "\n"
    )
    stdin = io.StringIO(blob)
    stdout = io.StringIO()
    rc = run_stdio_mcp_server(stdin=stdin, stdout=stdout)
    assert rc == 0
    lines = [x for x in stdout.getvalue().splitlines() if x.strip()]
    assert len(lines) >= 2
    o1 = json.loads(lines[0])
    assert o1["id"] == 1 and "result" in o1
    o2 = json.loads(lines[1])
    tools = o2.get("result", {}).get("tools") or []
    assert any(t.get("name") == "list_dir" for t in tools)
