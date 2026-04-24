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
COMPAT_MATRIX_CHECK_SCHEMA = "plugin_compat_matrix_check_v1"

# ECC-03b：治理 checklist 单源。改动 TOOLS_REGISTRY / 内置工具名 / harness 目标目录时需同步
# 矩阵行 + 相关说明文档，与 `docs/rfc/ECC_03A_PLUGIN_VERSION_GOVERNANCE.zh-CN.md` §2 对齐。
MATRIX_MAINTENANCE_CHECKLIST: tuple[str, ...] = (
    "更新 build_plugin_compat_matrix() 内的行并运行 test_plugin_compat_matrix",
    "同步 docs/PLUGIN_COMPAT_MATRIX.zh-CN.md 与 docs/PLUGIN_COMPAT_MATRIX.md",
    "同步 docs/CROSS_HARNESS_COMPATIBILITY.zh-CN.md / .md 中对应组件条目",
    "若影响 PARITY_MATRIX 叙事，在 docs/PARITY_MATRIX.zh-CN.md 中加注",
    "在 CHANGELOG / CHANGELOG.zh-CN 中声明推荐消费的 manifest 下限（若 target 列表变化）",
    "运行 scripts/smoke_new_features.py 并跑 cai-agent plugins --compat-check",
)


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
        "governance_rfc": "docs/rfc/ECC_03A_PLUGIN_VERSION_GOVERNANCE.zh-CN.md",
        "targets": targets,
        "components_vs_targets": rows,
        "maintenance_checklist": list(MATRIX_MAINTENANCE_CHECKLIST),
    }


def build_plugin_compat_matrix_check_v1(
    *,
    expected_components: tuple[str, ...] | None = None,
    expected_targets: tuple[str, ...] | None = None,
) -> dict[str, object]:
    """ECC-03b：最小可验证入口——校验矩阵行与目标是否与默认白名单一致。

    使用场景：CI 或 `cai-agent plugins --compat-check` 在改 `build_plugin_compat_matrix()`
    后快速发现未同步的组件 / 目标；返回 `plugin_compat_matrix_check_v1` 载荷。
    默认白名单：`PLUGIN_COMPONENTS` 中 hooks/rules/skills/commands/agents/mcp-configs；
    目标：cursor/codex/opencode。
    """
    matrix = build_plugin_compat_matrix()
    expected_comp = tuple(expected_components or PLUGIN_COMPONENTS)
    expected_tgt = tuple(expected_targets or ("cursor", "codex", "opencode"))

    rows = matrix.get("components_vs_targets") or []
    present_components = sorted(
        {
            str(r.get("component"))
            for r in rows
            if isinstance(r, dict) and isinstance(r.get("component"), str)
        },
    )
    missing_components = sorted(set(expected_comp) - set(present_components))

    targets = matrix.get("targets") or []
    present_targets = sorted(
        {
            str(t.get("id"))
            for t in targets
            if isinstance(t, dict) and isinstance(t.get("id"), str)
        },
    )
    missing_targets = sorted(set(expected_tgt) - set(present_targets))

    row_mismatches: list[dict[str, object]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        comp = str(r.get("component") or "")
        missing_keys = [k for k in expected_tgt if k not in r]
        if missing_keys:
            row_mismatches.append(
                {"component": comp, "missing_target_keys": missing_keys},
            )

    ok = not missing_components and not missing_targets and not row_mismatches

    return {
        "schema_version": COMPAT_MATRIX_CHECK_SCHEMA,
        "ok": ok,
        "expected_components": list(expected_comp),
        "present_components": present_components,
        "missing_components": missing_components,
        "expected_targets": list(expected_tgt),
        "present_targets": present_targets,
        "missing_targets": missing_targets,
        "row_mismatches": row_mismatches,
        "matrix_schema_version": str(matrix.get("schema_version") or ""),
        "governance_rfc": "docs/rfc/ECC_03A_PLUGIN_VERSION_GOVERNANCE.zh-CN.md",
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
