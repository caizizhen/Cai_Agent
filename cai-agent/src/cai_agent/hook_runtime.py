from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cai_agent.config import Settings


def _project_root(settings: Settings) -> Path:
    if settings.config_loaded_from:
        return Path(settings.config_loaded_from).expanduser().resolve().parent
    return Path.cwd().resolve()


def _hooks_file(settings: Settings) -> Path:
    return _project_root(settings) / "hooks" / "hooks.json"


def enabled_hook_ids(settings: Settings, event: str) -> list[str]:
    p = _hooks_file(settings)
    if not p.is_file():
        return []
    try:
        obj: Any = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(obj, dict):
        return []
    hooks = obj.get("hooks")
    if not isinstance(hooks, list):
        return []
    out: list[str] = []
    for h in hooks:
        if not isinstance(h, dict):
            continue
        if str(h.get("event", "")).strip() != event:
            continue
        if not bool(h.get("enabled", True)):
            continue
        hid = str(h.get("id", "")).strip()
        if hid:
            out.append(hid)
    return out

