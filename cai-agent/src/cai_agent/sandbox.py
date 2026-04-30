from __future__ import annotations

from pathlib import Path


class SandboxError(ValueError):
    pass


def resolve_tool_path(workspace: str, rel: str, *, unrestricted: bool = False) -> Path:
    """Resolve a tool filesystem path.

    By default paths are workspace-relative (no ``..``); resolved paths must stay under
    ``workspace``.

    When ``unrestricted`` is True and ``rel`` is absolute (after strip), resolve anywhere
    on the filesystem (still ``expanduser``); used only with ``[safety].unrestricted_mode``.
    """
    r = str(rel or "").strip()
    if not r:
        raise SandboxError("路径为空")
    root = Path(workspace).resolve()
    if not root.is_dir():
        raise SandboxError(f"工作目录不存在: {root}")
    cand = Path(r)
    if cand.is_absolute():
        if not unrestricted:
            raise SandboxError("非解限模式下不允许绝对路径（请使用相对工作区的路径）")
        return cand.expanduser().resolve()
    if ".." in r:
        raise SandboxError("路径不允许包含 '..'")
    candidate = (root / r).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as e:
        raise SandboxError("路径越界：必须在工作区内") from e
    return candidate


def resolve_workspace_path(workspace: str, rel: str) -> Path:
    """Backward-compatible alias: always workspace-relative (absolute paths rejected)."""
    return resolve_tool_path(workspace, rel, unrestricted=False)
