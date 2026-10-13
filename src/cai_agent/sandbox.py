from __future__ import annotations

from pathlib import Path


class SandboxError(ValueError):
    pass


def resolve_workspace_path(workspace: str, rel: str) -> Path:
    root = Path(workspace).resolve()
    if not root.is_dir():
        raise SandboxError(f"工作目录不存在: {root}")
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as e:
        raise SandboxError("路径越界：必须在工作区内") from e
    return candidate
