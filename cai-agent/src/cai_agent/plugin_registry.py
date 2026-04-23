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
COMPAT_MATRIX_SCHEMA = "plugin_compat_matrix_v1"


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


def build_plugin_compat_matrix() -> dict[str, object]:
    """机读兼容矩阵（与 ``docs/CROSS_HARNESS_COMPATIBILITY*.md`` 表一致，供 doctor / CI 消费）。

    状态取值：``supported`` | ``partial`` | ``absent``（相对各 harness 原生体验）。
    """
    targets = (
        {
            "id": "cursor",
            "label": "Cursor",
            "export_command": "cai-agent export --target cursor",
        },
        {
            "id": "codex",
            "label": "OpenAI Codex CLI",
            "export_command": "cai-agent export --target codex",
        },
        {
            "id": "opencode",
            "label": "OpenCode",
            "export_command": "cai-agent export --target opencode",
        },
    )
    rows: list[dict[str, str]] = [
        {
            "component": "rules",
            "cursor": "supported",
            "codex": "partial",
            "opencode": "partial",
            "notes": "统一源 rules/；导出见 export manifest",
        },
        {
            "component": "skills",
            "cursor": "partial",
            "codex": "partial",
            "opencode": "partial",
            "notes": "Markdown 技能；hub install / export 分流",
        },
        {
            "component": "commands",
            "cursor": "supported",
            "codex": "partial",
            "opencode": "partial",
            "notes": "commands/ 与 CLI 子命令同源",
        },
        {
            "component": "agents",
            "cursor": "supported",
            "codex": "supported",
            "opencode": "supported",
            "notes": "agents/*.md 模板",
        },
        {
            "component": "hooks",
            "cursor": "supported",
            "codex": "absent",
            "opencode": "supported",
            "notes": "Codex 侧弱；可降级为 quality-gate 包装",
        },
        {
            "component": "mcp-configs",
            "cursor": "supported",
            "codex": "supported",
            "opencode": "supported",
            "notes": "mcp-configs/ 与 MCP Bridge 工具",
        },
    ]
    return {
        "schema_version": COMPAT_MATRIX_SCHEMA,
        "doc_anchor": "docs/CROSS_HARNESS_COMPATIBILITY.zh-CN.md",
        "doc_anchor_en": "docs/CROSS_HARNESS_COMPATIBILITY.md",
        "detail_doc": "docs/PLUGIN_COMPAT_MATRIX.zh-CN.md",
        "detail_doc_en": "docs/PLUGIN_COMPAT_MATRIX.md",
        "targets": targets,
        "components_vs_targets": rows,
    }


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
