from __future__ import annotations

import glob
import ipaddress
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlparse
from typing import Any, Callable

import httpx

from cai_agent.config import Settings
from cai_agent.permissions import enforce_tool_permission
from cai_agent.sandbox import SandboxError, resolve_workspace_path


ALLOWED_CMD_NAMES = frozenset(
    {
        "python",
        "py",
        "pip",
        "git",
        "npm",
        "npx",
        "node",
    },
)

_MCP_TOOLS_CACHE: dict[str, tuple[float, list[str]]] = {}
_MCP_TOOLS_TTL_SEC = 15.0


def _reject_shell_metachar(s: str) -> None:
    bad = '&|;$`<>\n\r'
    if any(c in s for c in bad):
        raise SandboxError("参数含非法 shell 元字符")


def _reject_path_traversal_token(s: str, *, label: str) -> None:
    if ".." in s:
        raise SandboxError(f"{label} 不允许包含 '..'")
    if os.path.isabs(s):
        raise SandboxError(f"{label} 不允许绝对路径")


def tool_read_file(workspace: str, args: dict[str, Any]) -> str:
    rel = str(args.get("path", "")).strip()
    if not rel:
        raise SandboxError("read_file 需要 path")
    p = resolve_workspace_path(workspace, rel)
    if not p.is_file():
        raise SandboxError(f"不是文件: {p}")
    data = p.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return f"[二进制或非 UTF-8 文件，{len(data)} 字节]"

    ls_raw = args.get("line_start", 1)
    ls = int(ls_raw) if not isinstance(ls_raw, bool) else 1
    if ls < 1:
        raise SandboxError("read_file 的 line_start 须 >= 1")
    lines = text.splitlines()
    le_raw = args.get("line_end")
    if le_raw is None or le_raw == "":
        chunk_lines = lines[ls - 1 :]
        span = f"{ls}-EOF"
    else:
        le = int(le_raw)
        if le < ls:
            raise SandboxError("read_file 的 line_end 不能小于 line_start")
        chunk_lines = lines[ls - 1 : le]
        span = f"{ls}-{le}"
    body = "\n".join(chunk_lines)
    header = f"[read_file 行 {span}，共 {len(chunk_lines)} 行]\n"
    out = header + body
    if len(out) > 120_000:
        return out[:120_000] + "\n...[已截断]"
    return out


def tool_list_dir(workspace: str, args: dict[str, Any]) -> str:
    rel = str(args.get("path", ".")).strip() or "."
    p = resolve_workspace_path(workspace, rel)
    if not p.is_dir():
        raise SandboxError(f"不是目录: {p}")
    names = sorted(p.iterdir(), key=lambda x: x.name.lower())
    lines = []
    for n in names[:500]:
        kind = "d" if n.is_dir() else "f"
        lines.append(f"{kind}\t{n.name}")
    if len(names) > 500:
        lines.append(f"... 共 {len(names)} 项，仅显示前 500")
    return "\n".join(lines) if lines else "(空目录)"


def tool_list_tree(workspace: str, args: dict[str, Any]) -> str:
    rel = str(args.get("path", ".")).strip() or "."
    root = resolve_workspace_path(workspace, rel)
    if not root.is_dir():
        raise SandboxError(f"不是目录: {root}")

    md_raw = args.get("max_depth", 3)
    max_depth = int(md_raw) if not isinstance(md_raw, bool) else 3
    max_depth = min(max(max_depth, 1), 8)

    me_raw = args.get("max_entries", 400)
    max_entries = int(me_raw) if not isinstance(me_raw, bool) else 400
    max_entries = min(max(max_entries, 10), 2000)

    root_real = Path(workspace).resolve()
    lines_out: list[str] = []
    count = 0

    rel_root = root.relative_to(root_real).as_posix() if root != root_real else "."
    lines_out.append(f"{rel_root}/")
    count += 1
    truncated = False

    def walk_dir(d: Path, prefix: str, depth_left: int) -> None:
        nonlocal count, truncated
        if depth_left <= 0:
            return
        if count >= max_entries:
            return
        try:
            children = sorted(
                d.iterdir(),
                key=lambda x: (not x.is_dir(), x.name.lower()),
            )
        except OSError as e:
            lines_out.append(f"{prefix}[列出失败: {e}]")
            count += 1
            return
        for i, ch in enumerate(children):
            if count >= max_entries:
                truncated = True
                return
            is_last = i == len(children) - 1
            branch = "└── " if is_last else "├── "
            name = ch.name + ("/" if ch.is_dir() else "")
            lines_out.append(f"{prefix}{branch}{name}")
            count += 1
            if ch.is_dir() and count < max_entries:
                ext = "    " if is_last else "│   "
                walk_dir(ch, prefix + ext, depth_left - 1)

    walk_dir(root, "", max_depth)
    if truncated:
        lines_out.append(f"[已截断: max_entries={max_entries}]")
    return "\n".join(lines_out)


def tool_write_file(workspace: str, args: dict[str, Any]) -> str:
    rel = str(args.get("path", "")).strip()
    content = args.get("content", "")
    if not rel:
        raise SandboxError("write_file 需要 path")
    if not isinstance(content, str):
        content = str(content)
    p = resolve_workspace_path(workspace, rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8", newline="\n")
    return f"已写入 {p.relative_to(Path(workspace).resolve())}（{len(content)} 字符）"


def tool_run_command(settings: Settings, args: dict[str, Any]) -> str:
    argv = args.get("argv")
    if not isinstance(argv, list) or not argv:
        raise SandboxError("run_command 需要 argv 非空数组")
    argv = [str(x) for x in argv]
    for a in argv:
        _reject_shell_metachar(a)
    exe = Path(argv[0]).name.lower()
    if argv[0] != exe or "/" in argv[0] or "\\" in argv[0]:
        raise SandboxError("run_command 仅允许可执行文件基名（不能用路径）")
    if exe not in ALLOWED_CMD_NAMES:
        raise SandboxError(
            f"不允许的命令: {exe}，允许: {', '.join(sorted(ALLOWED_CMD_NAMES))}",
        )
    cwd_arg = str(args.get("cwd", ".")).strip() or "."
    cwd_path = resolve_workspace_path(settings.workspace, cwd_arg)
    if not cwd_path.is_dir():
        raise SandboxError(f"run_command 的 cwd 不是目录: {cwd_path}")
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=settings.command_timeout_sec,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return f"[超时 {settings.command_timeout_sec}s] {' '.join(argv)}"
    out = []
    if proc.stdout:
        out.append(proc.stdout)
    if proc.stderr:
        out.append("--- stderr ---\n" + proc.stderr)
    tail = "\n".join(out).strip()
    if len(tail) > 80_000:
        tail = tail[:80_000] + "\n...[已截断]"
    rel_cwd = cwd_path.relative_to(Path(settings.workspace).resolve()).as_posix()
    status = f"exit={proc.returncode} cwd={rel_cwd}"
    return f"{status}\n{tail}" if tail else status


def tool_glob_search(workspace: str, args: dict[str, Any]) -> str:
    pattern = str(args.get("pattern", "")).strip()
    if not pattern:
        raise SandboxError('glob_search 需要 pattern，例如 "**/*.py"')
    _reject_path_traversal_token(pattern, label="pattern")
    root_rel = str(args.get("root", ".")).strip() or "."
    root = resolve_workspace_path(workspace, root_rel)
    if not root.is_dir():
        raise SandboxError(f"不是目录: {root}")
    max_hits = args.get("max_matches", 200)
    if isinstance(max_hits, bool):
        max_hits = 200
    max_hits = int(max_hits)
    max_hits = min(max(max_hits, 1), 500)

    root_real = Path(workspace).resolve()
    paths_raw = sorted(
        {Path(p).resolve() for p in glob.glob(str(root / pattern), recursive=True)},
    )
    rel_lines: list[str] = []
    for p in paths_raw:
        if not p.is_file() and not p.is_dir():
            continue
        try:
            rel = p.relative_to(root_real)
        except ValueError:
            continue
        rel_lines.append(rel.as_posix())
        if len(rel_lines) >= max_hits:
            break
    if len(paths_raw) > len(rel_lines):
        note = f"（仅显示前 {max_hits} 条）"
    else:
        note = ""
    if not rel_lines:
        return f"无匹配项: pattern={pattern!r} root={root_rel!r}{note}"
    return f"共 {len(rel_lines)} 条{note}\n" + "\n".join(rel_lines)


def tool_search_text(workspace: str, args: dict[str, Any]) -> str:
    query = str(args.get("query", ""))
    if not query.strip():
        raise SandboxError("search_text 需要 query（子串，区分大小写）")
    if "\n" in query or "\r" in query:
        raise SandboxError("search_text 的 query 不允许换行")
    if len(query) > 400:
        raise SandboxError("query 过长（>400）")

    root_rel = str(args.get("root", ".")).strip() or "."
    root = resolve_workspace_path(workspace, root_rel)
    if not root.is_dir():
        raise SandboxError(f"不是目录: {root}")

    glob_pat = str(args.get("glob", "**/*")).strip() or "**/*"
    _reject_path_traversal_token(glob_pat, label="glob")
    if os.path.isabs(glob_pat):
        raise SandboxError("glob 不允许绝对路径")

    mf = args.get("max_files", 100)
    mf = int(mf) if not isinstance(mf, bool) else 100
    mf = min(max(mf, 1), 300)

    mh = args.get("max_matches", 80)
    mh = int(mh) if not isinstance(mh, bool) else 80
    mh = min(max(mh, 1), 200)

    max_bytes = int(args.get("max_file_bytes", 400_000))
    max_bytes = min(max(max_bytes, 1024), 2_000_000)

    root_real = Path(workspace).resolve()
    candidates = sorted(
        {
            Path(p)
            for p in glob.glob(str(root / glob_pat), recursive=True)
            if Path(p).is_file()
        },
    )
    hits: list[str] = []
    files_scanned = 0
    for path in candidates:
        if files_scanned >= mf:
            break
        try:
            rp = path.resolve()
            rp.relative_to(root_real)
        except ValueError:
            continue
        try:
            sz = path.stat().st_size
        except OSError:
            continue
        if sz > max_bytes:
            continue
        files_scanned += 1
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(root_real).as_posix()
        for i, line in enumerate(text.splitlines(), start=1):
            if query in line:
                hits.append(f"{rel}:{i}:{line[:500]}")
                if len(hits) >= mh:
                    break
        if len(hits) >= mh:
            break

    if not hits:
        return (
            f"无匹配。已扫描最多 {files_scanned} 个不超过 {max_bytes} 字节的文本文件。"
        )
    tail = f"\n... 已达 max_matches={mh}" if len(hits) >= mh else ""
    return f"匹配 {len(hits)} 处（扫描文件约 {files_scanned} 个）{tail}\n" + "\n".join(hits)


def tool_git_status(settings: Settings, args: dict[str, Any]) -> str:
    root = Path(settings.workspace).resolve()
    short = bool(args.get("short", True))
    argv = ["git", "-C", str(root), "status"]
    if short:
        argv.extend(["--short", "--branch"])
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=min(settings.command_timeout_sec, 20.0),
            shell=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return f"[git_status 失败] {e}"
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    body = out if out else "(无输出)"
    if err:
        body += f"\n--- stderr ---\n{err}"
    return f"exit={proc.returncode}\n{body}"


def tool_git_diff(settings: Settings, args: dict[str, Any]) -> str:
    root = Path(settings.workspace).resolve()
    staged = bool(args.get("staged", False))
    target = str(args.get("path", "")).strip()
    if target:
        p = resolve_workspace_path(str(root), target)
        rel = p.relative_to(root).as_posix()
    else:
        rel = ""
    argv = ["git", "-C", str(root), "diff"]
    if staged:
        argv.append("--staged")
    if rel:
        argv.extend(["--", rel])
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=min(settings.command_timeout_sec, 30.0),
            shell=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return f"[git_diff 失败] {e}"
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if len(out) > 120_000:
        out = out[:120_000] + "\n...[已截断]"
    body = out if out else "(无差异)"
    if err:
        body += f"\n--- stderr ---\n{err}"
    return f"exit={proc.returncode}\n{body}"


def _mcp_base(settings: Settings) -> str:
    if not settings.mcp_enabled:
        raise SandboxError("MCP 未启用（请设置 MCP_ENABLED=1 或 [agent].mcp_enabled=true）")
    if not settings.mcp_base_url:
        raise SandboxError("MCP 已启用但未配置 MCP_BASE_URL / [mcp].base_url")
    return settings.mcp_base_url.rstrip("/")


def _mcp_headers(settings: Settings) -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if settings.mcp_api_key:
        h["Authorization"] = f"Bearer {settings.mcp_api_key}"
    return h


def _mcp_cache_key(settings: Settings) -> str:
    return f"{settings.mcp_base_url}|{settings.mcp_api_key or ''}"


def _hostname_matches_fetch_allowlist(host: str, patterns: tuple[str, ...]) -> bool:
    h = host.lower().strip().rstrip(".")
    for raw in patterns:
        pat = raw.lower().strip().rstrip(".")
        if not pat:
            continue
        if pat.startswith("*."):
            suf = pat[2:]
            if h == suf or h.endswith("." + suf):
                return True
        else:
            if h == pat or h.endswith("." + pat):
                return True
    return False


_BLOCKED_FETCH_HOSTNAMES = frozenset(
    {
        "localhost",
        "metadata.google.internal",
        "metadata.goog",
        "metadata",
    },
)


def _reject_blocked_fetch_hostname(host: str) -> None:
    h = host.lower().strip(".")
    if h in _BLOCKED_FETCH_HOSTNAMES:
        raise SandboxError(f"fetch_url 拒绝访问主机名: {host!r}")


def _reject_private_ip_literal(host: str) -> None:
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return
    if (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
    ):
        raise SandboxError("fetch_url 拒绝访问保留/私网/组播地址")


def tool_fetch_url(settings: Settings, args: dict[str, Any]) -> str:
    if not settings.fetch_url_enabled:
        raise SandboxError(
            "fetch_url 未启用（配置 [fetch_url].enabled=true 或 CAI_FETCH_URL_ENABLED=1）"
        )
    if not settings.fetch_url_unrestricted and not settings.fetch_url_allowed_hosts:
        raise SandboxError(
            "fetch_url 需要配置主机白名单 [fetch_url].allow_hosts 或 CAI_FETCH_URL_ALLOW_HOSTS；"
            "或设置 [fetch_url].unrestricted=true / CAI_FETCH_URL_UNRESTRICTED=1 跳过白名单（仍禁止本机/私网字面 IP）"
        )
    url_raw = str(args.get("url", "")).strip()
    if not url_raw:
        raise SandboxError("fetch_url 需要参数 url")
    parsed = urlparse(url_raw)
    scheme = parsed.scheme.lower()
    if settings.fetch_url_unrestricted:
        if scheme not in ("http", "https"):
            raise SandboxError("fetch_url 仅允许 http 或 https")
    elif scheme != "https":
        raise SandboxError("fetch_url 仅允许 https")
    host = parsed.hostname
    if not host:
        raise SandboxError("fetch_url URL 无效：缺少主机名")
    _reject_blocked_fetch_hostname(host)
    _reject_private_ip_literal(host)
    if not settings.fetch_url_unrestricted and not _hostname_matches_fetch_allowlist(
        host, settings.fetch_url_allowed_hosts
    ):
        raise SandboxError(f"fetch_url 主机不在白名单: {host!r}")

    headers = {
        "User-Agent": "cai-agent-fetch_url/1",
        "Accept": "text/html,text/plain,application/json;q=0.9,*/*;q=0.1",
    }
    timeout = httpx.Timeout(settings.fetch_url_timeout_sec)
    max_b = settings.fetch_url_max_bytes
    with httpx.Client(
        timeout=timeout,
        trust_env=settings.http_trust_env,
        follow_redirects=True,
    ) as client:
        try:
            r = client.get(url_raw, headers=headers)
        except httpx.TooManyRedirects as e:
            return f"[fetch_url 失败] 重定向过多: {e}"
        except httpx.HTTPError as e:
            return f"[fetch_url 失败] {e}"
    ct = (r.headers.get("content-type") or "").split(";")[0].strip()
    body_bytes = r.content or b""
    truncated = len(body_bytes) > max_b
    chunk = body_bytes[:max_b]
    try:
        text = chunk.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = chunk.decode("latin-1")
        except UnicodeDecodeError:
            text = f"[非 UTF-8 响应，显示十六进制前缀 {chunk[:200]!r}…]"
    if len(text) > 120_000:
        text = text[:120_000] + "\n...[已截断]"
    head = (
        f"[fetch_url] HTTP {r.status_code} url={r.url!s} "
        f"content-type={ct or '(none)'} bytes={len(body_bytes)}"
    )
    if truncated:
        head += f" truncated_to={max_b}"
    return f"{head}\n\n{text}"


def tool_mcp_list_tools(settings: Settings, args: dict[str, Any]) -> str:
    force = bool(args.get("force", False))
    base = _mcp_base(settings)
    key = _mcp_cache_key(settings)
    now = time.time()
    if not force:
        cached = _MCP_TOOLS_CACHE.get(key)
        if cached and now - cached[0] <= _MCP_TOOLS_TTL_SEC:
            tools = cached[1]
            if not tools:
                return "(无 MCP 工具) [cache]"
            return "\n".join(tools[:300]) + "\n[cache]"

    timeout = httpx.Timeout(settings.mcp_timeout_sec)
    with httpx.Client(timeout=timeout, trust_env=settings.http_trust_env) as client:
        r = client.get(f"{base}/tools", headers=_mcp_headers(settings))
    if r.status_code >= 400:
        return f"[mcp_list_tools 失败] HTTP {r.status_code} body={r.text!r}"
    data: Any = r.json()
    rows: list[Any]
    if isinstance(data, dict) and isinstance(data.get("tools"), list):
        rows = data["tools"]
    elif isinstance(data, list):
        rows = data
    else:
        return f"[mcp_list_tools 异常返回] {json.dumps(data, ensure_ascii=False)[:4000]}"
    out: list[str] = []
    for item in rows:
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            desc = str(item.get("description", "")).strip()
            if name:
                out.append(f"{name}\t{desc}")
        elif isinstance(item, str) and item.strip():
            out.append(item.strip())
    _MCP_TOOLS_CACHE[key] = (now, list(out))
    if not out:
        return "(无 MCP 工具)"
    return "\n".join(out[:300])


def tool_mcp_call_tool(settings: Settings, args: dict[str, Any]) -> str:
    base = _mcp_base(settings)
    name = str(args.get("name", "")).strip()
    if not name:
        raise SandboxError("mcp_call_tool 需要 name")
    targs = args.get("args")
    if not isinstance(targs, dict):
        targs = {}
    timeout = httpx.Timeout(settings.mcp_timeout_sec)
    body = {"args": targs}
    with httpx.Client(timeout=timeout, trust_env=settings.http_trust_env) as client:
        r = client.post(
            f"{base}/tools/{quote(name, safe='')}",
            json=body,
            headers=_mcp_headers(settings),
        )
    if r.status_code >= 400:
        return f"[mcp_call_tool 失败] HTTP {r.status_code} body={r.text!r}"
    try:
        data = r.json()
    except Exception:
        txt = r.text
        return txt[:100_000] + ("\n...[已截断]" if len(txt) > 100_000 else "")
    txt = json.dumps(data, ensure_ascii=False)
    return txt[:100_000] + ("...[已截断]" if len(txt) > 100_000 else "")


def dispatch(settings: Settings, name: str, args: dict[str, Any]) -> str:
    ws = settings.workspace
    enforce_tool_permission(settings, name)
    if name == "read_file":
        return tool_read_file(ws, args)
    if name == "list_dir":
        return tool_list_dir(ws, args)
    if name == "list_tree":
        return tool_list_tree(ws, args)
    if name == "write_file":
        return tool_write_file(ws, args)
    if name == "run_command":
        return tool_run_command(settings, args)
    if name == "glob_search":
        return tool_glob_search(ws, args)
    if name == "search_text":
        return tool_search_text(ws, args)
    if name == "git_status":
        return tool_git_status(settings, args)
    if name == "git_diff":
        return tool_git_diff(settings, args)
    if name == "mcp_list_tools":
        return tool_mcp_list_tools(settings, args)
    if name == "mcp_call_tool":
        return tool_mcp_call_tool(settings, args)
    if name == "fetch_url":
        return tool_fetch_url(settings, args)
    raise SandboxError(f"未知工具: {name}")


def tools_spec_markdown() -> str:
    return """可用工具（通过 JSON 调用）：
- read_file: {"path": "...", "line_start": 1, "line_end": 120} — line_end 可省略表示读到文件末尾
- list_dir: {"path": "." 或子目录}
- list_tree: {"path": ".", "max_depth": 3, "max_entries": 400} — 目录树（深度与条数受限）
- glob_search: {"pattern": "**/*.py", "root": ".", "max_matches": 200}
- search_text: {"query": "子串", "root": ".", "glob": "**/*.py", "max_files": 100, "max_matches": 80, "max_file_bytes": 400000}
- git_status: {"short": true} — 只读 git 状态
- git_diff: {"staged": false, "path": "可选相对路径"} — 只读 git diff
- mcp_list_tools: {"force": false} — 从 MCP Bridge 拉取工具清单（短时缓存，需开启 MCP）
- mcp_call_tool: {"name":"tool_name","args":{...}} — 调用 MCP Bridge 工具（需开启 MCP）
- fetch_url: {"url": "https://..."} — GET；默认仅 HTTPS 且须 allow_hosts 白名单；[fetch_url].unrestricted=true 时可任意公网主机并允许 http；受 permissions.fetch_url 约束
- write_file: {"path": "相对路径", "content": "文件全文"}
- run_command: {"argv": ["python", "script.py"], "cwd": "."} — argv[0] 只能是允许基名之一，禁止路径与 shell 元字符
"""
