from __future__ import annotations

from pathlib import Path

from cai_agent.config import Settings


def _project_root(settings: Settings) -> Path:
    if settings.config_loaded_from:
        return Path(settings.config_loaded_from).expanduser().resolve().parent
    return Path.cwd().resolve()


def _commands_dir(settings: Settings) -> Path:
    return _project_root(settings) / "commands"


def list_command_names(settings: Settings) -> list[str]:
    base = _commands_dir(settings)
    if not base.is_dir():
        return []
    names: list[str] = []
    for p in sorted(base.glob("*.md")):
        if p.name.lower() == "readme.md":
            continue
        names.append(p.stem)
    return names


def load_command_text(settings: Settings, name: str) -> str:
    stem = str(name).strip().lstrip("/")
    if not stem:
        return ""
    p = _commands_dir(settings) / f"{stem}.md"
    if not p.is_file():
        return ""
    try:
        return p.read_text(encoding="utf-8").strip()
    except OSError:
        return ""

