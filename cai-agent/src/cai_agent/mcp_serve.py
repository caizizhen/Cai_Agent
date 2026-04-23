"""MCP stdio server MVP (Hermes H3-MCP): ``initialize`` + ``tools/list`` for built-ins."""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO


def _builtin_tools() -> list[dict[str, Any]]:
    """Subset of graph tools（名称与 tools 模块对齐，供 Host 探测）。"""
    names = [
        ("list_dir", "列出目录内容"),
        ("list_tree", "递归列出目录树"),
        ("glob_search", "按 glob 搜索文件"),
        ("search_text", "在文件中搜索文本/正则"),
        ("read_file", "读取文本文件"),
        ("write_file", "写入文本文件"),
        ("run_command", "在沙箱策略下执行 shell 命令"),
        ("git_status", "查看 git 状态"),
        ("fetch_url", "抓取允许列表内的 HTTP(S) URL 文本"),
        ("mcp_list_tools", "列出 MCP Bridge 工具"),
        ("mcp_call_tool", "调用 MCP 工具"),
    ]
    return [{"name": n, "description": d} for n, d in names]


def _reply(
    msg_id: Any,
    result: dict[str, Any] | None,
    err: dict[str, Any] | None,
    *,
    stream: TextIO,
) -> None:
    out: dict[str, Any] = {"jsonrpc": "2.0", "id": msg_id}
    if err is not None:
        out["error"] = err
    else:
        out["result"] = result or {}
    stream.write(json.dumps(out, ensure_ascii=False) + "\n")
    stream.flush()


def run_stdio_mcp_server(
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> int:
    """阻塞读取 stdin，处理 MCP JSON-RPC（最小子集）。"""
    sin = stdin or sys.stdin
    sout = stdout or sys.stdout
    for line in sin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = str(msg.get("method") or "")
        if method.startswith("notifications/"):
            continue
        mid = msg.get("id")
        if method == "initialize":
            _reply(
                mid,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "cai-agent-mcp", "version": "0.1-mvp"},
                },
                None,
                stream=sout,
            )
        elif method == "tools/list":
            _reply(mid, {"tools": _builtin_tools()}, None, stream=sout)
        else:
            if mid is None:
                continue
            _reply(
                mid,
                None,
                {"code": -32601, "message": f"Method not implemented: {method}"},
                stream=sout,
            )
    return 0
