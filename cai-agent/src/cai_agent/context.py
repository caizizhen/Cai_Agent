from __future__ import annotations

import os
import subprocess
from pathlib import Path

from cai_agent.config import Settings

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
    return "\n".join(parts).strip() + "\n"
