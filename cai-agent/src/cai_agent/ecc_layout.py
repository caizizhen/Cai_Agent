"""ECC-01a：rules / skills / hooks 资产目录约定与最小脚手架（单源路径）。"""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any, Iterator

from cai_agent.config import Settings

RULES_DIRNAME = "rules"
RULES_COMMON = "rules/common"
RULES_PYTHON = "rules/python"
SKILLS_DIRNAME = "skills"
HOOKS_PRIMARY_RELP = "hooks/hooks.json"
HOOKS_FALLBACK_RELP = ".cai/hooks/hooks.json"


def project_root_for_ecc(settings: Settings) -> Path:
    if settings.config_loaded_from:
        return Path(settings.config_loaded_from).expanduser().resolve().parent
    return Path.cwd().resolve()


def rules_dir(root: Path) -> Path:
    return root / RULES_DIRNAME


def rules_common_dir(root: Path) -> Path:
    return root.joinpath(*RULES_COMMON.split("/"))


def rules_python_dir(root: Path) -> Path:
    return root.joinpath(*RULES_PYTHON.split("/"))


def skills_dir(root: Path) -> Path:
    return root / SKILLS_DIRNAME


def iter_hooks_json_paths(root: Path, *, hooks_dir: str | None = None) -> Iterator[Path]:
    """与 :func:`cai_agent.hook_runtime.resolve_hooks_json_path` 相同的候选顺序。"""
    rel = (hooks_dir or "").strip().replace("\\", "/")
    if rel:
        base = (root / rel).resolve()
        yield base if base.name == "hooks.json" else base / "hooks.json"
    yield (root / "hooks" / "hooks.json").resolve()
    yield (root / ".cai" / "hooks" / "hooks.json").resolve()


def build_ecc_asset_layout_payload(
    settings: Settings,
    *,
    root_override: Path | None = None,
) -> dict[str, Any]:
    """机读契约 ``ecc_asset_layout_v1``：列出约定路径与职责。

    ``root_override``：CLI ``-w`` 显式工作区时优先于从 ``settings`` 推断的根。
    """
    root = root_override if root_override is not None else project_root_for_ecc(settings)
    entries: list[dict[str, Any]] = [
        {
            "id": "rules",
            "path": str(rules_dir(root)),
            "kind": "directory",
            "role": "plan 注入：读取 rules/common/*.md 与 rules/python/*.md（见 rules.load_rule_text）",
        },
        {
            "id": "skills",
            "path": str(skills_dir(root)),
            "kind": "directory",
            "role": "技能库：*.md（排除 readme），供会话绑定与 skills hub",
        },
        {
            "id": "hooks_json_primary",
            "path": str(root / HOOKS_PRIMARY_RELP),
            "kind": "file",
            "role": "hooks.json 首选路径",
        },
        {
            "id": "hooks_json_fallback",
            "path": str(root / HOOKS_FALLBACK_RELP),
            "kind": "file",
            "role": "hooks.json 次选路径（与 doctor cai_dir_health 一致）",
        },
        {
            "id": "export_cursor",
            "path": str(root / ".cursor" / "cai-agent-export"),
            "kind": "directory",
            "role": "`cai-agent export --target cursor` 输出根（含 manifest + rules/skills/… 复制）",
        },
    ]
    hooks_resolved: str | None = None
    for p in iter_hooks_json_paths(root):
        if p.is_file():
            hooks_resolved = str(p)
            break
    return {
        "schema_version": "ecc_asset_layout_v1",
        "workspace": str(root),
        "hooks_resolved_path": hooks_resolved,
        "entries": entries,
        "human_doc_zh": "docs/CROSS_HARNESS_COMPATIBILITY.zh-CN.md",
        "human_doc_en": "docs/CROSS_HARNESS_COMPATIBILITY.md",
    }


def _harness_export_root(root: Path, target: str) -> Path:
    """与 ``exporter.ecc_export_root_for_target`` / ``plugin_registry`` 路径一致（避免 ecc_layout 依赖 exporter）。"""
    t = target.strip().lower()
    if t == "cursor":
        return root / ".cursor" / "cai-agent-export"
    if t == "codex":
        return root / ".codex" / "cai-agent-export"
    if t == "opencode":
        return root / ".opencode"
    raise ValueError(f"unsupported harness target: {target}")


def _count_files_recursive(dir_path: Path) -> int:
    if not dir_path.is_dir():
        return 0
    return sum(1 for p in dir_path.rglob("*") if p.is_file())


def build_ecc_harness_target_inventory_v1(
    settings: Settings,
    *,
    root_override: Path | None = None,
) -> dict[str, Any]:
    """ECC-N03-D01：跨 harness 导出目标与 workspace 源 assets 的机读清单。"""
    root = root_override if root_override is not None else project_root_for_ecc(settings)
    modes = {"cursor": "structured", "codex": "manifest", "opencode": "copy"}
    targets: list[dict[str, Any]] = []
    for t in ("cursor", "codex", "opencode"):
        er = _harness_export_root(root, t)
        man = er / "cai-export-manifest.json"
        cat = er / "cai-local-catalog.json"
        comps: list[dict[str, Any]] = []
        for name in ("rules", "skills", "agents", "commands"):
            p = er / name
            comps.append(
                {
                    "component": name,
                    "path": str(p),
                    "exists": p.exists(),
                    "is_directory": p.is_dir(),
                    "file_count": _count_files_recursive(p) if p.is_dir() else 0,
                },
            )
        targets.append(
            {
                "target": t,
                "mode": modes[t],
                "export_root": str(er),
                "export_root_exists": er.is_dir(),
                "manifest_path": str(man),
                "manifest_exists": man.is_file(),
                "local_catalog_path": str(cat),
                "local_catalog_exists": cat.is_file(),
                "export_components": comps,
            },
        )
    sources: list[dict[str, Any]] = []
    for name in ("rules", "skills", "agents", "commands"):
        p = root / name
        sources.append(
            {
                "component": name,
                "path": str(p),
                "exists": p.exists(),
                "is_directory": p.is_dir(),
                "file_count": _count_files_recursive(p) if p.is_dir() else 0,
            },
        )
    return {
        "schema_version": "ecc_harness_target_inventory_v1",
        "workspace": str(root.resolve()),
        "targets": targets,
        "workspace_sources": sources,
    }


def _tpl_bytes(name: str) -> bytes:
    base = resources.files("cai_agent").joinpath("templates", "ecc", name)
    return base.read_bytes()


def ecc_scaffold_workspace(root: Path, *, dry_run: bool = False) -> dict[str, Any]:
    """从包内 ``templates/ecc/*`` 创建最小样例；已有文件不覆盖。"""
    created: list[str] = []
    skipped: list[str] = []

    def _write(rel: str, name: str) -> None:
        dest = (root / rel).resolve()
        if dest.exists():
            skipped.append(rel)
            return
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(_tpl_bytes(name))
        created.append(rel)

    # README under rules/common
    _write("rules/common/README.md", "rules_common_README.md")
    # skills README
    _write("skills/README.md", "skills_README.md")
    # optional sample skill
    _write("skills/_ecc_sample_skill.md", "skill_sample.md")
    # hooks.json only when no candidate exists
    has_hooks = any(p.is_file() for p in iter_hooks_json_paths(root))
    if not has_hooks:
        dest = (root / "hooks" / "hooks.json").resolve()
        if dest.exists():
            skipped.append(HOOKS_PRIMARY_RELP)
        elif dry_run:
            created.append(HOOKS_PRIMARY_RELP)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(_tpl_bytes("hooks.min.json"))
            created.append(HOOKS_PRIMARY_RELP)
    else:
        skipped.append("hooks/hooks.json (already_present)")
    return {
        "schema_version": "ecc_scaffold_result_v1",
        "workspace": str(root.resolve()),
        "dry_run": dry_run,
        "created": created,
        "skipped": skipped,
    }
