from __future__ import annotations

import os
from pathlib import Path

from cai_agent.config import Settings
from cai_agent.ecc_layout import skills_dir
from cai_agent.skill_evolution import record_skill_usage, register_session_skill_touch


def _project_root(settings: Settings) -> Path:
    if settings.config_loaded_from:
        return Path(settings.config_loaded_from).expanduser().resolve().parent
    return Path.cwd().resolve()


def _skills_dir(settings: Settings) -> Path:
    return skills_dir(_project_root(settings))


def _read_skill(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def load_related_skill_texts(
    settings: Settings,
    key: str,
    *,
    limit: int = 3,
    goal_hint: str = "",
) -> list[str]:
    base = _skills_dir(settings)
    root = _project_root(settings)
    if not base.is_dir():
        return []
    stem = str(key).strip().lower().strip("/")
    if not stem:
        return []

    candidates: list[Path] = []
    exact = base / f"{stem}.md"
    if exact.is_file():
        candidates.append(exact)

    alt = stem.replace("-", "_")
    if alt != stem:
        p = base / f"{alt}.md"
        if p.is_file() and p not in candidates:
            candidates.append(p)

    # Prefix match to bind command/agent to nearby skills.
    for p in sorted(base.glob("*.md")):
        if p.name.lower() == "readme.md":
            continue
        s = p.stem.lower()
        if s.startswith(stem) or stem.startswith(s):
            if p not in candidates:
                candidates.append(p)

    out: list[str] = []
    gh = (goal_hint or "").strip()
    log_usage = os.environ.get("CAI_SKILLS_USAGE_LOG", "").strip().lower() not in ("0", "false", "no", "off")
    for p in candidates[: max(limit, 1)]:
        text = _read_skill(p)
        if text:
            try:
                sid = p.resolve().relative_to((root / "skills").resolve()).as_posix()
            except ValueError:
                sid = p.name
            if log_usage:
                record_skill_usage(root, sid, goal=gh, outcome="loaded")
            register_session_skill_touch(sid, gh)
            out.append(text)
    return out

