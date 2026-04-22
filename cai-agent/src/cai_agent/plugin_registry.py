from __future__ import annotations

import json
from pathlib import Path

from cai_agent.config import Settings


PLUGIN_COMPONENTS = (
    "skills",
    "commands",
    "agents",
    "hooks",
    "rules",
    "mcp-configs",
)
PLUGIN_VERSION = "0.1.0"


def _project_root(settings: Settings) -> Path:
    if settings.config_loaded_from:
        return Path(settings.config_loaded_from).expanduser().resolve().parent
    return Path.cwd().resolve()


def _compute_health_score(root: Path, components: dict[str, dict[str, object]]) -> int:
    score = 100
    hooks_json_candidates = [
        root / "hooks" / "hooks.json",
        root / ".cai" / "hooks" / "hooks.json",
    ]
    hooks_json = next((p for p in hooks_json_candidates if p.is_file()), None)
    if hooks_json is not None:
        try:
            data = json.loads(hooks_json.read_text(encoding="utf-8"))
            if not isinstance(data, dict) and not isinstance(data, list):
                score -= 15
        except (OSError, json.JSONDecodeError):
            score -= 40
    elif (root / "hooks").is_dir() or (root / ".cai" / "hooks").is_dir():
        score -= 8

    readme = root / "README.md"
    if not readme.is_file():
        score -= 12

    for name, meta in components.items():
        if not isinstance(meta, dict):
            continue
        exists = bool(meta.get("exists"))
        fc = int(meta.get("files_count", 0))
        if exists and fc == 0:
            score -= 5
        if name in ("skills", "commands") and not exists:
            score -= 3

    return max(0, min(100, score))


def list_plugin_surface(settings: Settings) -> dict[str, object]:
    root = _project_root(settings)
    components: dict[str, dict[str, object]] = {}
    for name in PLUGIN_COMPONENTS:
        p = root / name
        files_count = 0
        if p.is_dir():
            files_count = sum(1 for x in p.rglob("*") if x.is_file())
        components[name] = {
            "exists": p.exists(),
            "path": str(p),
            "files_count": files_count,
        }
    health = _compute_health_score(root, components)
    return {
        "schema_version": "plugins_surface_v1",
        "project_root": str(root),
        "plugin_version": PLUGIN_VERSION,
        "compatibility": {
            "cursor": "partial",
            "codex": "partial",
            "opencode": "partial",
        },
        "health_score": health,
        "components": components,
    }
