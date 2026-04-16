from __future__ import annotations

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
    return {
        "project_root": str(root),
        "plugin_version": PLUGIN_VERSION,
        "compatibility": {
            "cursor": "partial",
            "codex": "partial",
            "opencode": "partial",
        },
        "health_score": 72,
        "components": components,
    }
