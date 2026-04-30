from __future__ import annotations

import glob
import ipaddress
import json
import os
import shlex
import socket
import subprocess
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from urllib.parse import ParseResult, quote, urlparse
from typing import Any, Callable

import httpx

from cai_agent.config import Settings
from cai_agent.http_trust import effective_http_trust_env
from cai_agent.permissions import enforce_tool_permission
from cai_agent.runtime.registry import get_runtime_backend
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
        "curl",
        "wget",
    },
)

_MCP_TOOLS_CACHE: dict[str, tuple[float, list[str]]] = {}
_MCP_TOOLS_TTL_SEC = 15.0
_DANGEROUS_APPROVAL_LOCK = Lock()
_DANGEROUS_APPROVAL_BUDGET = 0
_SESSION_DANGER_LOCK = Lock()
_SESSION_MCP_DANGER_OK: set[str] = set()
_SESSION_FETCH_HTTP_HOSTS: set[str] = set()
_DANGER_AUDIT_SCHEMA = "dangerous_audit_event_v1"

_DEFAULT_HIGH_RISK_PATTERNS = (
    "rm -rf",
    "sudo ",
    "chmod 777",
    "mkfs",
    "dd if=",
    "shutdown",
    "reboot",
    "curl ",
    "wget ",
    "| bash",
)


def _reject_shell_metachar(s: str) -> None:
    bad = '&|;$`<>\n\r'
    if any(c in s for c in bad):
        raise SandboxError("参数含非法 shell 元字符")


def _reject_path_traversal_token(s: str, *, label: str) -> None:
    if ".." in s:
        raise SandboxError(f"{label} 不允许包含 '..'")
    if os.path.isabs(s):
        raise SandboxError(f"{label} 不允许绝对路径")


def _is_high_risk_command(settings: Settings, argv: list[str]) -> tuple[bool, str]:
    joined = " ".join(argv).lower()
    defaults = (
        "rm -rf",
        "mkfs",
        "dd if=",
        ":(){",
        "shutdown",
        "reboot",
        "format ",
        "rmdir /s",
        "del /f",
    )
    pats = tuple(settings.run_command_high_risk_patterns) or defaults
    for pat in pats:
        p = str(pat).strip().lower()
        if not p:
            continue
        if p in joined:
            return (True, p)
    return (False, "")


def grant_dangerous_approval_once(
    *,
    settings: Settings | None = None,
    audit_via: str | None = None,
) -> int:
    """Grant one dangerous-action approval for the current process."""
    global _DANGEROUS_APPROVAL_BUDGET
    with _DANGEROUS_APPROVAL_LOCK:
        _DANGEROUS_APPROVAL_BUDGET += 1
        out = int(_DANGEROUS_APPROVAL_BUDGET)
    if settings is not None and audit_via:
        append_dangerous_audit_log(
            settings,
            "dangerous_grant",
            {"via": audit_via, "budget_after": out},
        )
    return out


def _consume_dangerous_approval_once() -> bool:
    global _DANGEROUS_APPROVAL_BUDGET
    with _DANGEROUS_APPROVAL_LOCK:
        if _DANGEROUS_APPROVAL_BUDGET <= 0:
            return False
        _DANGEROUS_APPROVAL_BUDGET -= 1
        return True


def needs_dangerous_confirmation(
    settings: Settings,
    name: str,
    args: dict[str, Any],
) -> tuple[bool, str]:
    if not bool(getattr(settings, "unrestricted_mode", False)):
        return (False, "")
    if not bool(getattr(settings, "dangerous_confirmation_required", True)):
        return (False, "")
    if name == "run_command":
        argv = args.get("argv")
        if not isinstance(argv, list) or not argv:
            return (False, "")
        argv = [str(x) for x in argv]
        is_risky, pat = _is_high_risk_command(settings, argv)
        if not is_risky:
            return (False, "")
        return (True, f"run_command 命中高危模式: {pat!r}")
    if name == "write_file":
        rel = str(args.get("path", "")).strip().lower()
        if not rel:
            return (False, "")
        sensitive_suffixes = (".env", ".pem", ".key", "id_rsa", "id_ed25519", "known_hosts")
        if rel.endswith(sensitive_suffixes):
            return (True, f"write_file 目标疑似敏感文件: {rel}")
    if name == "mcp_call_tool":
        tool_name = str(args.get("name", "")).strip()
        if tool_name:
            return (True, f"mcp_call_tool 将调用外部 MCP 工具: {tool_name!r}")
        return (True, "mcp_call_tool 将调用外部 MCP 工具")
    if name == "fetch_url":
        url_raw = str(args.get("url", "")).strip()
        if not url_raw:
            return (False, "")
        try:
            parsed = urlparse(url_raw)
        except Exception:
            return (False, "")
        scheme = (parsed.scheme or "").lower()
        if scheme == "http":
            return (True, "fetch_url 使用明文 http（传输不可信）")
    return (False, "")


def dangerous_auto_approved_from_env() -> bool:
    raw = os.getenv("CAI_DANGEROUS_APPROVE", "")
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def peek_dangerous_approval_budget() -> int:
    """当前进程中尚未被 dispatch 消耗的预授权次数。"""
    with _DANGEROUS_APPROVAL_LOCK:
        return int(_DANGEROUS_APPROVAL_BUDGET)


def reset_dangerous_approval_budget_for_testing() -> None:
    """测试专用：清零进程内危险操作预授权与会话放行集合。"""
    global _DANGEROUS_APPROVAL_BUDGET
    with _DANGEROUS_APPROVAL_LOCK:
        _DANGEROUS_APPROVAL_BUDGET = 0
    clear_session_danger_tool_approvals()


def clear_session_danger_tool_approvals() -> None:
    """清空本会话（进程）内 MCP / 明文 HTTP 主机的危险放行集合。"""
    with _SESSION_DANGER_LOCK:
        _SESSION_MCP_DANGER_OK.clear()
        _SESSION_FETCH_HTTP_HOSTS.clear()


def register_session_mcp_tool_danger_approval(tool_name: str) -> None:
    """本会话内对指定 MCP 工具名跳过危险二次确认（仍须解限且 ``dangerous_confirmation_required``）。"""
    t = str(tool_name).strip()
    if not t:
        return
    with _SESSION_DANGER_LOCK:
        _SESSION_MCP_DANGER_OK.add(t)


def register_session_fetch_http_host_danger_approval(hostname: str) -> None:
    """本会话内对指定主机名的明文 ``http`` ``fetch_url`` 跳过危险二次确认。"""
    h = str(hostname).strip().lower()
    if not h:
        return
    with _SESSION_DANGER_LOCK:
        _SESSION_FETCH_HTTP_HOSTS.add(h)


def session_danger_preapproved(settings: Settings, name: str, args: dict[str, Any]) -> bool:
    """进程内会话放行：与 ``needs_dangerous_confirmation`` 语义一致且命中白名单时返回 True。"""
    need, _reason = needs_dangerous_confirmation(settings, name, args)
    if not need:
        return False
    if name == "mcp_call_tool":
        tn = str(args.get("name", "")).strip()
        if not tn:
            return False
        with _SESSION_DANGER_LOCK:
            return tn in _SESSION_MCP_DANGER_OK
    if name == "fetch_url":
        url_raw = str(args.get("url", "")).strip()
        try:
            parsed = urlparse(url_raw)
        except Exception:
            return False
        if (parsed.scheme or "").lower() != "http":
            return False
        host = (parsed.hostname or "").strip().lower()
        if not host:
            return False
        with _SESSION_DANGER_LOCK:
            return host in _SESSION_FETCH_HTTP_HOSTS
    return False


def _danger_audit_args_summary(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "mcp_call_tool":
        return {"mcp_tool": str(args.get("name", "")).strip()[:400]}
    if name == "fetch_url":
        u = str(args.get("url", "")).strip()[:800]
        try:
            host = (urlparse(u).hostname or "").strip().lower()
        except Exception:
            host = ""
        return {"url": u, "host": host}
    if name == "run_command":
        argv = args.get("argv")
        if isinstance(argv, list) and argv:
            return {"argv0": str(argv[0])[:200]}
        return {}
    if name == "write_file":
        return {"path": str(args.get("path", "")).strip()[:400]}
    return {}


def append_dangerous_audit_log(settings: Settings, event: str, detail: dict[str, Any]) -> None:
    """将一条 JSON 事件追加到 ``<workspace>/.cai/dangerous-approve.jsonl``（受配置开关控制）。"""
    if not bool(getattr(settings, "dangerous_audit_log_enabled", False)):
        return
    try:
        ws = str(getattr(settings, "workspace", "") or "").strip() or "."
        root = Path(ws).expanduser().resolve()
        cai = root / ".cai"
        cai.mkdir(parents=True, exist_ok=True)
        path = cai / "dangerous-approve.jsonl"
        rec: dict[str, Any] = {
            "schema": _DANGER_AUDIT_SCHEMA,
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "event": str(event),
            "detail": dict(detail),
        }
        line = json.dumps(rec, ensure_ascii=False) + "\n"
        with path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(line)
    except Exception:
        return


def prepare_interactive_dangerous_dispatch(
    settings: Settings,
    name: str,
    args: dict[str, Any],
    *,
    interactive_confirm: Callable[[dict[str, Any]], bool] | None,
) -> tuple[bool, str | None]:
    """交互式确认链路：在调用 ``dispatch`` 之前决定是否放行。

    返回 ``(允许调用 dispatch, 跳过 dispatch 时的合成错误正文)``。
    若不触发交互分支（或无预算且无交互），返回 ``(True, None)`` ，由 ``dispatch`` 自行校验。
    """
    need, reason = needs_dangerous_confirmation(settings, name, args)
    if not need:
        return (True, None)
    if dangerous_auto_approved_from_env():
        return (True, None)
    if peek_dangerous_approval_budget() > 0:
        return (True, None)
    if session_danger_preapproved(settings, name, args):
        return (True, None)
    if interactive_confirm is None:
        return (True, None)
    payload = {"name": name, "args": dict(args), "reason": reason}
    try:
        ok = bool(interactive_confirm(payload))
    except Exception:
        ok = False
    if ok:
        grant_dangerous_approval_once(settings=settings, audit_via="modal")
        return (True, None)
    return (
        False,
        "工具执行失败: 用户取消了危险操作确认。"
        f"（{reason}；可先输入 /danger-approve 预放行一次，或设置 CAI_DANGEROUS_APPROVE=1）",
    )


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


def tool_make_dir(workspace: str, args: dict[str, Any]) -> str:
    rel = str(args.get("path", "")).strip()
    if not rel:
        raise SandboxError("make_dir 需要 path")
    root = Path(workspace).resolve()
    p = resolve_workspace_path(workspace, rel)
    if p.exists() and not p.is_dir():
        raise SandboxError(f"路径已存在且不是目录: {p.relative_to(root)}")
    p.mkdir(parents=True, exist_ok=True)
    return f"已创建或已存在目录: {p.relative_to(root).as_posix()}"


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
    mode = str(getattr(settings, "run_command_approval_mode", "block_high_risk") or "block_high_risk").strip().lower()
    if mode not in ("block_high_risk", "allow_all"):
        mode = "block_high_risk"
    if mode == "block_high_risk" and not bool(getattr(settings, "unrestricted_mode", False)):
        joined = " ".join(argv).lower()
        patterns = tuple(getattr(settings, "run_command_high_risk_patterns", ()) or ()) or _DEFAULT_HIGH_RISK_PATTERNS
        for pat in patterns:
            p = str(pat or "").strip().lower()
            if p and p in joined:
                raise SandboxError(
                    f"run_command 命中高危模式并被阻断: {p!r}（可在 [permissions].run_command_approval_mode=allow_all 放开）",
                )
    cwd_arg = str(args.get("cwd", ".")).strip() or "."
    cwd_path = resolve_workspace_path(settings.workspace, cwd_arg)
    if not cwd_path.is_dir():
        raise SandboxError(f"run_command 的 cwd 不是目录: {cwd_path}")
    rb = str(getattr(settings, "runtime_backend", "local") or "local").strip().lower() or "local"
    backend = get_runtime_backend(rb, settings=settings)
    timeout = float(settings.command_timeout_sec)

    def _format_result(proc: subprocess.CompletedProcess[str]) -> str:
        out_l: list[str] = []
        if proc.stdout:
            out_l.append(proc.stdout)
        if proc.stderr:
            out_l.append("--- stderr ---\n" + proc.stderr)
        tail2 = "\n".join(out_l).strip()
        if len(tail2) > 80_000:
            tail2 = tail2[:80_000] + "\n...[已截断]"
        rel_cwd2 = cwd_path.relative_to(Path(settings.workspace).resolve()).as_posix()
        status2 = f"exit={proc.returncode} cwd={rel_cwd2} backend=local"
        return f"{status2}\n{tail2}" if tail2 else status2

    if backend.name == "local":
        try:
            proc = subprocess.run(
                argv,
                cwd=str(cwd_path),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            return f"[超时 {timeout}s] {' '.join(argv)} backend=local"
        return _format_result(proc)

    if not backend.exists():
        detail = backend.describe()
        return (
            f"[运行时 {backend.name} 不可用] exists={detail.get('exists')} "
            f"detail={detail!r}\nargv={' '.join(argv)} cwd={cwd_path}"
        )
    try:
        cmd_line = shlex.join(argv)
    except (TypeError, ValueError) as e:
        raise SandboxError(f"run_command argv 无法序列化: {e}") from e
    res = backend.exec(cmd_line, cwd=str(cwd_path), env=None, timeout_sec=timeout)
    if res.returncode == 124 or res.error_kind == "timeout":
        return f"[超时 {timeout}s] {' '.join(argv)} backend={res.backend}"
    out = []
    if res.stdout:
        out.append(res.stdout)
    if res.stderr:
        out.append("--- stderr ---\n" + res.stderr)
    tail = "\n".join(out).strip()
    if len(tail) > 80_000:
        tail = tail[:80_000] + "\n...[已截断]"
    rel_cwd = cwd_path.relative_to(Path(settings.workspace).resolve()).as_posix()
    ek = f" err_kind={res.error_kind}" if res.error_kind else ""
    status = f"exit={res.returncode} cwd={rel_cwd} backend={res.backend}{ek}"
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


def _fetch_url_effective_port(parsed: ParseResult, scheme: str) -> int:
    p = parsed.port
    if isinstance(p, int) and p > 0:
        return int(p)
    return 443 if scheme == "https" else 80


def _reject_fetch_url_resolved_unsafe_addrs(host: str, port: int) -> None:
    """拒绝 DNS 解析到私网/本机等地址（缓解 DNS rebinding / 内网 SSRF）。

    在发起 TCP 前做一次 ``getaddrinfo`` 校验；与真实连接之间仍存在极窄 TOCTOU 窗口，
    内网解析场景可显式开启 ``[fetch_url].allow_private_resolved_ips``。
    """
    try:
        infos = socket.getaddrinfo(
            host,
            port,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except OSError as e:
        raise SandboxError(f"fetch_url DNS 解析失败: {e}") from e
    if not infos:
        raise SandboxError("fetch_url DNS 无可用地址")
    seen: set[str] = set()
    for item in infos:
        if len(item) < 5:
            continue
        sockaddr = item[4]
        if not sockaddr:
            continue
        raw_ip = sockaddr[0]
        if not isinstance(raw_ip, str):
            continue
        if "%" in raw_ip:
            raw_ip = raw_ip.split("%", 1)[0]
        if raw_ip in seen:
            continue
        seen.add(raw_ip)
        try:
            addr = ipaddress.ip_address(raw_ip)
        except ValueError:
            continue
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
            or addr.is_unspecified
        ):
            raise SandboxError(
                "fetch_url 拒绝 DNS 解析到私网/本机/保留/组播地址（反 DNS rebinding）"
                f": {raw_ip!r}"
            )


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

    eff_port = _fetch_url_effective_port(parsed, scheme)
    if not settings.fetch_url_allow_private_resolved_ips:
        _reject_fetch_url_resolved_unsafe_addrs(host, eff_port)

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
        max_redirects=int(settings.fetch_url_max_redirects),
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
    mcp_url = f"{base}/tools"
    with httpx.Client(
        timeout=timeout,
        trust_env=effective_http_trust_env(
            trust_env=bool(settings.http_trust_env),
            request_url=mcp_url,
        ),
    ) as client:
        r = client.get(mcp_url, headers=_mcp_headers(settings))
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
    mcp_post = f"{base}/tools/{quote(name, safe='')}"
    with httpx.Client(
        timeout=timeout,
        trust_env=effective_http_trust_env(
            trust_env=bool(settings.http_trust_env),
            request_url=mcp_post,
        ),
    ) as client:
        r = client.post(
            mcp_post,
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
    need_confirm, reason = needs_dangerous_confirmation(settings, name, args)
    if need_confirm:
        pre = session_danger_preapproved(settings, name, args)
        env_ok = dangerous_auto_approved_from_env()
        consumed = _consume_dangerous_approval_once()
        if not (consumed or env_ok or pre):
            raise SandboxError(
                f"危险操作需要二次确认：{reason}。"
                "请先在 TUI 输入 /danger-approve（仅放行下一次高危操作），"
                "或在非交互场景设置 CAI_DANGEROUS_APPROVE=1；"
                "对 MCP 或明文 http 的 fetch，可用 /danger-session-mcp、/danger-session-fetch 本会话放行。",
            )
        if bool(getattr(settings, "dangerous_audit_log_enabled", False)):
            via = "session_exempt" if pre else ("env" if env_ok else "budget")
            append_dangerous_audit_log(
                settings,
                "dangerous_executed",
                {
                    "tool": name,
                    "via": via,
                    "reason": reason,
                    "args": _danger_audit_args_summary(name, args),
                },
            )
    if name == "read_file":
        return tool_read_file(ws, args)
    if name == "list_dir":
        return tool_list_dir(ws, args)
    if name == "list_tree":
        return tool_list_tree(ws, args)
    if name == "write_file":
        return tool_write_file(ws, args)
    if name == "make_dir":
        return tool_make_dir(ws, args)
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


DISPATCH_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "read_file",
        "list_dir",
        "list_tree",
        "write_file",
        "make_dir",
        "run_command",
        "glob_search",
        "search_text",
        "git_status",
        "git_diff",
        "mcp_list_tools",
        "mcp_call_tool",
        "fetch_url",
    }
)


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
- mcp_call_tool: {"name":"tool_name","args":{...}} — 调用 MCP Bridge 工具（需开启 MCP）；当 [safety].unrestricted_mode=true 且 dangerous_confirmation_required=true 时，每次调用需二次确认
- fetch_url: {"url": "https://..."} — GET；默认仅 HTTPS 且须 allow_hosts 白名单；[fetch_url].unrestricted=true 时可任意公网主机并允许 http；[fetch_url].max_redirects（1–50，默认 20）控制跟随重定向；请求前对 DNS 解析结果做私网/本机拒绝（反 DNS rebinding），内网解析需 [fetch_url].allow_private_resolved_ips=true 或 CAI_FETCH_URL_ALLOW_PRIVATE_RESOLVED_IPS=1；受 permissions.fetch_url 约束；明文 http 在解限且要求确认时需二次确认
- write_file: {"path": "相对路径", "content": "文件全文"}
- make_dir: {"path": "相对目录路径"} — 在工作区内递归创建目录（等同 mkdir -p）；权限同 write_file
- run_command: {"argv": ["python", "script.py"], "cwd": "."} — argv[0] 只能是允许基名之一，禁止路径与 shell 元字符；当 [safety].unrestricted_mode=true 且命中高危模式时，需先做二次确认
"""
