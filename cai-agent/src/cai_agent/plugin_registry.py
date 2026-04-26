from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
LOCAL_CATALOG_SCHEMA = "local_catalog_v1"
PLUGINS_SYNC_HOME_PLAN_SCHEMA = "plugins_sync_home_plan_v1"
PLUGINS_HOME_SYNC_DRIFT_SCHEMA = "plugins_home_sync_drift_v1"
# 与 ``export_target`` / ``ecc sync-home`` 复制的顶层目录一致（不含独立 hooks 树；hooks 见 ecc scaffold）。
PLUGINS_SYNC_HOME_EXPORT_DIRS = ("rules", "skills", "agents", "commands")

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


def _harness_export_root_for_plugins_sync(root: Path, target: str) -> Path:
    """各 harness 导出根（与 ``cai_agent.exporter.ecc_export_root_for_target`` 路径一致，避免 plugin_registry 依赖 exporter 循环引用）。"""
    t = target.strip().lower()
    if t == "cursor":
        return root / ".cursor" / "cai-agent-export"
    if t == "codex":
        return root / ".codex" / "cai-agent-export"
    if t == "opencode":
        return root / ".opencode"
    raise ValueError(f"unsupported harness target: {target}")


def _normalize_plugins_sync_targets(raw: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for item in raw:
        x = str(item).strip().lower()
        if x == "all":
            return ["cursor", "codex", "opencode"]
        if x in ("cursor", "codex", "opencode") and x not in out:
            out.append(x)
    return out


def build_plugins_sync_home_plan_v1(
    settings: Settings,
    *,
    targets: tuple[str, ...],
) -> dict[str, object]:
    """CC-N03-D02：dry-run 计划，描述将 ``PLUGINS_SYNC_HOME_EXPORT_DIRS`` 同步到各 harness 导出目录的意图（不写盘）。"""
    root = _project_root(settings)
    norm = _normalize_plugins_sync_targets(targets)
    if not norm:
        return {
            "schema_version": PLUGINS_SYNC_HOME_PLAN_SCHEMA,
            "ok": False,
            "error": "no_targets",
            "hint": "使用 --target cursor|codex|opencode（可重复）或 --all-targets",
        }
    target_rows: list[dict[str, object]] = []
    for tgt in norm:
        try:
            dest_root = _harness_export_root_for_plugins_sync(root, tgt)
        except ValueError as e:
            target_rows.append({"target": tgt, "error": str(e)})
            continue
        mode = "manifest" if tgt == "codex" else ("structured" if tgt == "cursor" else "copy")
        comps: list[dict[str, object]] = []
        for name in PLUGINS_SYNC_HOME_EXPORT_DIRS:
            src = root / name
            nfiles = sum(1 for p in src.rglob("*") if p.is_file()) if src.is_dir() else 0
            if tgt == "codex":
                would_copy = False
                skip_reason: str | None = "codex_export_is_manifest_only"
            else:
                would_copy = src.is_dir()
                skip_reason = None if would_copy else "source_missing"
            comps.append(
                {
                    "component": name,
                    "source_path": str(src),
                    "dest_path": str(dest_root / name),
                    "source_file_count": nfiles,
                    "would_copy": bool(would_copy),
                    "skip_reason": skip_reason,
                },
            )
        manifest_path = dest_root / "cai-export-manifest.json"
        catalog_path = dest_root / "cai-local-catalog.json"
        target_rows.append(
            {
                "target": tgt,
                "mode": mode,
                "export_root": str(dest_root),
                "would_write_manifest": True,
                "would_write_local_catalog": True,
                "manifest_path": str(manifest_path),
                "local_catalog_path": str(catalog_path),
                "components": comps,
            },
        )
    return {
        "schema_version": PLUGINS_SYNC_HOME_PLAN_SCHEMA,
        "ok": True,
        "dry_run": True,
        "workspace": str(root),
        "targets": target_rows,
        "alignment_note": (
            "与 cai-agent export / ecc sync-home 一致：repo 根 rules|skills|agents|commands → 各 harness 导出根"
        ),
    }


def build_plugins_home_sync_drift_v1(settings: Settings) -> dict[str, Any]:
    """CC-N03-D03：与 ``ecc_home_sync_drift_v1`` 同源目录差分，供 plugins / doctor 叙事消费。

    在函数内 lazy-import ``exporter``，避免 ``exporter`` ↔ ``plugin_registry`` 的 import 环。
    """
    from cai_agent.exporter import build_ecc_home_sync_drift_v1

    ecc = build_ecc_home_sync_drift_v1(settings)
    drift_targets = [str(x) for x in (ecc.get("targets_with_drift") or [])]
    preview: list[str] = ["cai-agent plugins sync-home --all-targets --json"]
    apply_like: list[str] = []
    for t in drift_targets:
        preview.append(f"cai-agent plugins sync-home --target {t} --json")
        apply_like.append(f"cai-agent ecc sync-home --target {t} --apply")
    if not drift_targets:
        apply_like = ["cai-agent ecc sync-home --all-targets --dry-run --json"]
    return {
        "schema_version": PLUGINS_HOME_SYNC_DRIFT_SCHEMA,
        "workspace": ecc.get("workspace"),
        "targets_with_drift": ecc.get("targets_with_drift"),
        "diffs": ecc.get("diffs"),
        "parity_with": "ecc_home_sync_drift_v1",
        "preview_commands": preview,
        "apply_commands": apply_like,
        "note": (
            "对比仓库根 rules/skills/agents/commands 与各 harness 导出根；"
            "codex 为 manifest 导向，目录级差分可能长期非空。"
        ),
    }


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


def build_local_catalog_payload(
    settings: Settings,
    *,
    root_override: Path | None = None,
) -> dict[str, object]:
    """ECC-N03-D01: local catalog schema for rules/skills/hooks/plugins assets."""
    root = root_override if root_override is not None else _project_root(settings)
    surface = list_plugin_surface(settings)
    hooks_candidates = [
        root / "hooks" / "hooks.json",
        root / ".cai" / "hooks" / "hooks.json",
    ]
    hooks_file = next((p for p in hooks_candidates if p.is_file()), None)
    hooks_count = 0
    hooks_error: str | None = None
    if hooks_file is not None:
        try:
            raw = json.loads(hooks_file.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and isinstance(raw.get("hooks"), list):
                hooks_count = sum(1 for h in raw.get("hooks") if isinstance(h, dict))
            else:
                hooks_error = "invalid_hooks_document"
        except Exception:
            hooks_error = "invalid_hooks_json"

    def _count_md(dir_path: Path) -> int:
        if not dir_path.is_dir():
            return 0
        return sum(
            1
            for p in dir_path.rglob("*.md")
            if p.is_file() and p.name.lower() != "readme.md"
        )

    rules_dir = root / "rules"
    skills_dir = root / "skills"
    assets: list[dict[str, object]] = [
        {
            "id": "rules",
            "kind": "directory",
            "path": str(rules_dir),
            "exists": rules_dir.is_dir(),
            "items_count": _count_md(rules_dir),
        },
        {
            "id": "skills",
            "kind": "directory",
            "path": str(skills_dir),
            "exists": skills_dir.is_dir(),
            "items_count": _count_md(skills_dir),
        },
        {
            "id": "hooks",
            "kind": "file",
            "path": str(hooks_file) if hooks_file is not None else None,
            "exists": hooks_file is not None,
            "items_count": hooks_count,
            "error": hooks_error,
        },
        {
            "id": "plugins",
            "kind": "object",
            "path": str(root),
            "exists": True,
            "items_count": len(surface.get("components") or {}),
            "schema_version": surface.get("schema_version"),
            "plugin_version": surface.get("plugin_version"),
        },
    ]
    return {
        "schema_version": LOCAL_CATALOG_SCHEMA,
        "workspace": str(root),
        "plugin_version": PLUGIN_VERSION,
        "assets": assets,
        "components": surface.get("components") or {},
        "compatibility": surface.get("compatibility") or {},
        "health_score": int(surface.get("health_score") or 0),
    }
