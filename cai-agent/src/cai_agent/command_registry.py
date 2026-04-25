from __future__ import annotations

from pathlib import Path

from cai_agent.config import Settings


def _project_root(settings: Settings) -> Path:
    if settings.config_loaded_from:
        return Path(settings.config_loaded_from).expanduser().resolve().parent
    return Path.cwd().resolve()


def _commands_dir(settings: Settings) -> Path:
    return _project_root(settings) / "commands"


def _candidate_command_dirs(root: Path) -> tuple[Path, ...]:
    """支持两类模板目录：项目 ``commands`` 与 Cursor ``.cursor/commands``。"""
    return (root / "commands", root / ".cursor" / "commands")


def _command_dirs(settings: Settings) -> list[Path]:
    roots: list[Path] = []
    if settings.config_loaded_from:
        roots.append(Path(settings.config_loaded_from).expanduser().resolve().parent)
    workspace = str(getattr(settings, "workspace", "") or "").strip()
    if workspace:
        roots.append(Path(workspace).expanduser().resolve())
    roots.append(Path.cwd().resolve())

    out: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        for base in _candidate_command_dirs(root):
            key = str(base)
            if key in seen:
                continue
            seen.add(key)
            out.append(base)
    return out


def list_command_names(settings: Settings) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for base in _command_dirs(settings):
        if not base.is_dir():
            continue
        for p in sorted(base.glob("*.md")):
            if p.name.lower() == "readme.md" or p.stem in seen:
                continue
            seen.add(p.stem)
            names.append(p.stem)
    return sorted(names)


def load_command_text(settings: Settings, name: str) -> str:
    stem = str(name).strip().lstrip("/")
    if not stem:
        return ""
    for base in _command_dirs(settings):
        p = base / f"{stem}.md"
        if not p.is_file():
            continue
        try:
            return p.read_text(encoding="utf-8").strip()
        except OSError:
            return ""
    return ""

