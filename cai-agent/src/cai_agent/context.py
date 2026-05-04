from __future__ import annotations

from datetime import UTC, datetime
import os
import subprocess
from pathlib import Path
from typing import Any

from cai_agent.config import Settings
from cai_agent.memory import build_structured_memory_prompt_block
from cai_agent.session import list_session_files, load_session

INSTRUCTION_FILE_NAMES = (
    "CAI.md",
    "AGENTS.md",
    "CLAUDE.md",
)


def _read_limited(path: Path, limit: int) -> str:
    data = path.read_bytes()
    if len(data) > limit:
        data = data[:limit]
        suffix = "\n...[文件过长已截断]"
    else:
        suffix = ""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return f"[跳过非 UTF-8 文本: {path.name}]"
    return text + suffix


def workspace_instructions(workspace: str, *, per_file_cap: int, total_cap: int) -> str:
    """拼接工作区根目录下常见项目说明文件（若存在）。"""
    root = Path(workspace).resolve()
    if not root.is_dir():
        return ""
    chunks: list[str] = []
    total = 0
    for name in INSTRUCTION_FILE_NAMES:
        p = root / name
        if not p.is_file():
            continue
        body = _read_limited(p, per_file_cap)
        block = f"### {name}\n{body.strip()}\n"
        if total + len(block) > total_cap:
            remain = total_cap - total - 40
            if remain > 200:
                block = f"### {name}\n{body.strip()[:remain]}...\n[总长度限制截断]\n"
                chunks.append(block)
            break
        chunks.append(block)
        total += len(block)
    if not chunks:
        return ""
    return "\n---\n## 项目说明（工作区根目录）\n" + "\n".join(chunks)


def git_workspace_summary(workspace: str, *, timeout_sec: float = 4.0) -> str:
    """在工作区执行只读 git 命令，失败则返回空串。"""
    root = Path(workspace).resolve()
    if not root.is_dir():
        return ""
    try:
        sha = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            shell=False,
        )
        st = subprocess.run(
            ["git", "-C", str(root), "status", "--short", "--branch"],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            shell=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return ""
    if sha.returncode != 0:
        return ""
    head = (sha.stdout or "").strip()
    status_lines = (st.stdout or "").strip() if st.returncode == 0 else ""
    if not status_lines:
        status_lines = "(git status 无输出或失败)"
    return f"\n---\n## Git（工作区）\nHEAD: {head}\n```\n{status_lines[:8000]}\n```\n"


def augment_system_prompt(settings: Settings, base: str) -> str:
    """在基础 system prompt 后附加可选上下文。"""
    parts = [base.rstrip()]
    pers = (os.environ.get("CAI_PERSONALITY") or "").strip()
    if pers:
        parts.append(f"\n---\n## Personality（CAI_PERSONALITY）\n{pers}\n")
    if settings.project_context:
        inst = workspace_instructions(
            settings.workspace,
            per_file_cap=24_000,
            total_cap=40_000,
        )
        if inst:
            parts.append(inst)
    if settings.git_context:
        g = git_workspace_summary(settings.workspace)
        if g:
            parts.append(g)
    if settings.memory_inject_enabled:
        mem = build_structured_memory_prompt_block(
            settings.workspace,
            max_entries=settings.memory_inject_max_entries,
            max_chars=settings.memory_inject_max_chars,
            include_stale=settings.memory_inject_include_stale,
            stale_after_days=settings.memory_inject_stale_after_days,
            min_active_confidence=settings.memory_inject_min_active_confidence,
        )
        if mem:
            parts.append(mem.rstrip())
    return "\n".join(parts).strip() + "\n"


def _session_answer_preview(sess: dict[str, Any], *, limit: int = 120) -> str:
    ans = sess.get("answer")
    if not isinstance(ans, str):
        return ""
    s = ans.strip()
    if not s:
        return ""
    return s[:limit] + ("…" if len(s) > limit else "")


def build_session_recap_v1(
    *,
    workspace: str,
    pattern: str = ".cai-session*.json",
    limit: int = 20,
) -> dict[str, Any]:
    """CC-N04: stable recap payload for replaying recent session context."""
    root = Path(workspace).expanduser().resolve()
    files = list_session_files(cwd=str(root), pattern=pattern, limit=max(1, int(limit)))
    items: list[dict[str, Any]] = []
    parse_skipped = 0
    for p in files:
        try:
            sess = load_session(str(p))
        except Exception:
            parse_skipped += 1
            continue
        mtime = datetime.fromtimestamp(p.stat().st_mtime, UTC).isoformat()
        td = sess.get("task")
        task_id = None
        if isinstance(td, dict):
            tid = str(td.get("task_id") or "").strip()
            task_id = tid or None
        items.append(
            {
                "name": p.name,
                "path": str(p),
                "mtime": mtime,
                "goal": str(sess.get("goal") or "").strip() or None,
                "task_id": task_id,
                "total_tokens": int(sess.get("total_tokens") or 0),
                "error_count": int(sess.get("error_count") or 0),
                "answer_preview": _session_answer_preview(sess),
            },
        )
    replay_commands = [
        "cai-agent sessions --json --details --limit 20",
        "cai-agent observe --json --limit 20",
        "cai-agent continue --last --json",
    ]
    latest = items[0] if items else None
    summary = {
        "sessions_parsed": len(items),
        "parse_skipped": parse_skipped,
        "errors_total": sum(int(x.get("error_count") or 0) for x in items),
        "tokens_total": sum(int(x.get("total_tokens") or 0) for x in items),
        "latest_session_path": latest.get("path") if isinstance(latest, dict) else None,
    }
    return {
        "schema_version": "session_recap_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(root),
        "pattern": pattern,
        "limit": max(1, int(limit)),
        "summary": summary,
        "sessions": items,
        "replay_commands": replay_commands,
    }
