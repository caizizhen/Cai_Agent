from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from cai_agent.config import Settings
from cai_agent.memory import resolve_active_memory_provider
from cai_agent.plugin_registry import build_local_catalog_payload


def _project_root(settings: Settings) -> Path:
    if settings.config_loaded_from:
        return Path(settings.config_loaded_from).expanduser().resolve().parent
    return Path.cwd().resolve()


def ecc_export_root_for_target(root: Path, target: str) -> Path:
    """跨 harness 导出根目录（与 ``export_target`` 写入路径一致）。"""
    t = target.strip().lower()
    if t == "cursor":
        return root / ".cursor" / "cai-agent-export"
    if t == "codex":
        return root / ".codex" / "cai-agent-export"
    if t == "opencode":
        return root / ".opencode"
    raise ValueError(f"unsupported target: {target}")


def export_target(settings: Settings, target: str) -> dict[str, object]:
    """导出到跨 harness 目录：优先写入可识别的最小 manifest + README。"""
    root = _project_root(settings)
    t = target.strip().lower()
    if t not in {"cursor", "codex", "opencode"}:
        raise ValueError(f"unsupported target: {target}")

    local_catalog = build_local_catalog_payload(settings, root_override=root)
    mem_provider = resolve_active_memory_provider(root)
    manifest_core = {
        "exporter": "cai-agent",
        "schema": "export-v2",
        "manifest_version": "2.1.0",
        "target": t,
        "local_catalog_schema_version": str(local_catalog.get("schema_version") or ""),
        "active_memory_provider": str(mem_provider.get("active_provider") or ""),
        "active_memory_provider_source": str(mem_provider.get("active_provider_source") or "default"),
    }

    if t == "cursor":
        out_dir = root / ".cursor" / "cai-agent-export"
        out_dir.mkdir(parents=True, exist_ok=True)
        copied: list[str] = []
        for name in ("rules", "skills", "agents", "commands"):
            src = root / name
            if not src.exists():
                continue
            dst = out_dir / name
            if dst.exists():
                if dst.is_dir():
                    shutil.rmtree(dst)
                else:
                    dst.unlink()
            if src.is_dir():
                shutil.copytree(src, dst)
                copied.append(name)
        manifest_path = out_dir / "cai-export-manifest.json"
        catalog_path = out_dir / "cai-local-catalog.json"
        catalog_path.write_text(
            json.dumps(local_catalog, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest_path.write_text(
            json.dumps(
                {**manifest_core, "copied": copied, "local_catalog_file": str(catalog_path.name)},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        readme = out_dir / "README.md"
        readme.write_text(
            "# CAI Agent → Cursor 导出\n\n"
            "本目录由 `cai-agent export --target cursor` 生成。\n\n"
            "- `cai-export-manifest.json`：导出清单（机器可读）。\n"
            "- `rules/`、`skills/` 等为从仓库根目录复制的子树。\n\n"
            "**降级说明**：Cursor 原生规则格式可能与仓库 `rules/` 中 Markdown "
            "不完全一致；若需 `.mdc` frontmatter 规则，请在本机再执行一次转换或 "
            "手动迁移。目录约定与脚手架：`cai-agent ecc layout` / `ecc scaffold`；"
            "详见 `docs/CROSS_HARNESS_COMPATIBILITY.zh-CN.md`。\n",
            encoding="utf-8",
        )
        return {
            "schema_version": "export_cli_v1",
            "target": t,
            "output_dir": str(out_dir),
            "manifest": str(manifest_path),
            "local_catalog": str(catalog_path),
            "copied": copied,
            "mode": "structured",
        }

    if t == "codex":
        out_dir = root / ".codex" / "cai-agent-export"
        out_dir.mkdir(parents=True, exist_ok=True)
        placeholder = out_dir / "CODEX_EXPORT_README.md"
        placeholder.write_text(
            "# CAI Agent → Codex 导出\n\n"
            "本占位目录由 `cai-agent export --target codex` 生成。\n"
            "当前实现为 **manifest + 说明**，不假设 Codex CLI 的固定配置路径。\n\n"
            "请将 `commands/`、`skills/` 等按需同步到你的 Codex / 代理工作流。\n"
            "降级与限制见 `docs/CROSS_HARNESS_COMPATIBILITY.zh-CN.md`。\n",
            encoding="utf-8",
        )
        manifest_path = out_dir / "cai-export-manifest.json"
        catalog_path = out_dir / "cai-local-catalog.json"
        catalog_path.write_text(
            json.dumps(local_catalog, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest_path.write_text(
            json.dumps(
                {
                    **manifest_core,
                    "copied": [],
                    "note": "copy+manifest_only",
                    "local_catalog_file": str(catalog_path.name),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return {
            "schema_version": "export_cli_v1",
            "target": t,
            "output_dir": str(out_dir),
            "manifest": str(manifest_path),
            "local_catalog": str(catalog_path),
            "copied": [],
            "mode": "manifest",
        }

    # opencode: 保持目录复制 + manifest
    out_dir = root / f".{t}"
    out_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for name in ("rules", "skills", "agents", "commands"):
        src = root / name
        if not src.exists():
            continue
        dst = out_dir / name
        if dst.exists():
            if dst.is_dir():
                shutil.rmtree(dst)
            else:
                dst.unlink()
        if src.is_dir():
            shutil.copytree(src, dst)
            copied.append(name)
    catalog_path = out_dir / "cai-local-catalog.json"
    catalog_path.write_text(
        json.dumps(local_catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest_path = out_dir / "cai-export-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {**manifest_core, "copied": copied, "local_catalog_file": str(catalog_path.name)},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "schema_version": "export_cli_v1",
        "target": t,
        "output_dir": str(out_dir),
        "manifest": str(manifest_path),
        "local_catalog": str(catalog_path),
        "copied": copied,
        "mode": "copy",
    }


def _gather_rel_files(base: Path) -> frozenset[str]:
    if not base.is_dir():
        return frozenset()
    out: set[str] = set()
    for p in base.rglob("*"):
        if p.is_file():
            try:
                rel = p.relative_to(base).as_posix()
            except ValueError:
                continue
            out.add(rel)
    return frozenset(out)


def build_export_ecc_dir_diff_report(settings: Settings, *, target: str) -> dict[str, object]:
    """对比仓库根 ``rules|skills|agents|commands`` 与各 harness ECC 导出目录的文件集合差分。"""
    root = _project_root(settings)
    t = str(target).strip().lower()
    if t not in {"cursor", "codex", "opencode"}:
        return {
            "schema_version": "export_ecc_dir_diff_v1",
            "target": t,
            "error": "unsupported_target",
            "hint": "支持 --target cursor|codex|opencode，对应 export 写入目录",
        }
    try:
        ecc = ecc_export_root_for_target(root, t)
    except ValueError as e:
        return {
            "schema_version": "export_ecc_dir_diff_v1",
            "target": t,
            "error": "unsupported_target",
            "hint": str(e),
        }
    dirs = ("rules", "skills", "agents", "commands")
    rows: list[dict[str, object]] = []
    for name in dirs:
        src = root / name
        dst = ecc / name
        src_files = _gather_rel_files(src) if src.is_dir() else frozenset()
        dst_files = _gather_rel_files(dst) if dst.is_dir() else frozenset()
        only_src = sorted(src_files - dst_files)
        only_dst = sorted(dst_files - src_files)
        rows.append(
            {
                "name": name,
                "source_file_count": len(src_files),
                "export_file_count": len(dst_files),
                "only_in_source": only_src[:300],
                "only_in_export": only_dst[:300],
                "only_in_source_truncated": max(0, len(only_src) - 300),
                "only_in_export_truncated": max(0, len(only_dst) - 300),
            },
        )
    return {
        "schema_version": "export_ecc_dir_diff_v1",
        "target": t,
        "workspace": str(root),
        "ecc_export_root": str(ecc),
        "directories": rows,
    }


def plan_ecc_home_sync_v1(settings: Settings, *, target: str) -> dict[str, Any]:
    """不写入磁盘：描述 ``export_target`` 将对单 harness 执行的操作。"""
    root = _project_root(settings)
    t = target.strip().lower()
    if t not in {"cursor", "codex", "opencode"}:
        raise ValueError(f"unsupported target: {target}")
    out_dir = ecc_export_root_for_target(root, t)
    copied: list[str] = []
    if t != "codex":
        for name in ("rules", "skills", "agents", "commands"):
            src = root / name
            if src.is_dir():
                copied.append(name)
    mode = "manifest" if t == "codex" else ("structured" if t == "cursor" else "copy")
    return {
        "schema_version": "ecc_home_sync_plan_v1",
        "workspace": str(root),
        "target": t,
        "output_dir": str(out_dir),
        "would_copy_directories": copied,
        "would_write_manifest": True,
        "would_write_local_catalog": True,
        "mode": mode,
    }


def _normalize_ecc_sync_targets(raw: list[str]) -> list[str]:
    out: list[str] = []
    for item in raw:
        x = str(item).strip().lower()
        if x == "all":
            return ["cursor", "codex", "opencode"]
        if x in ("cursor", "codex", "opencode") and x not in out:
            out.append(x)
    return out


def run_ecc_home_sync_v1(
    settings: Settings,
    targets: list[str],
    *,
    dry_run: bool,
) -> dict[str, Any]:
    """``ecc sync-home``：``dry_run`` 时仅返回计划，否则等价于顺序 ``export_target``。"""
    norm = _normalize_ecc_sync_targets(targets)
    if not norm:
        return {
            "schema_version": "ecc_home_sync_result_v1",
            "ok": False,
            "error": "no_targets",
            "hint": "使用 --target cursor|codex|opencode（可重复）或 --all-targets",
        }
    if dry_run:
        plans = [plan_ecc_home_sync_v1(settings, target=t) for t in norm]
        return {
            "schema_version": "ecc_home_sync_result_v1",
            "ok": True,
            "dry_run": True,
            "targets": norm,
            "plans": plans,
        }
    exports = [export_target(settings, t) for t in norm]
    return {
        "schema_version": "ecc_home_sync_result_v1",
        "ok": True,
        "dry_run": False,
        "targets": norm,
        "exports": exports,
    }


def build_ecc_home_sync_drift_v1(settings: Settings) -> dict[str, Any]:
    """聚合各 harness 的 ``export_ecc_dir_diff_v1``，供 doctor / repair 引用。"""
    root = _project_root(settings)
    diffs: list[dict[str, Any]] = []
    dirty: list[str] = []
    for t in ("cursor", "codex", "opencode"):
        rep = build_export_ecc_dir_diff_report(settings, target=t)
        row: dict[str, Any] = {"target": t, "report": rep}
        diffs.append(row)
        if not isinstance(rep, dict):
            continue
        if rep.get("error"):
            dirty.append(t)
            continue
        has_delta = False
        for d in rep.get("directories") or []:
            if not isinstance(d, dict):
                continue
            if d.get("only_in_source") or d.get("only_in_export"):
                has_delta = True
                break
        if has_delta:
            dirty.append(t)
    return {
        "schema_version": "ecc_home_sync_drift_v1",
        "workspace": str(root),
        "diffs": diffs,
        "targets_with_drift": sorted(set(dirty)),
    }


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_ecc_asset_pack_manifest_v1(
    settings: Settings,
    *,
    targets: tuple[str, ...] = ("cursor", "codex", "opencode"),
) -> dict[str, Any]:
    """ECC-N02：按源目录 + 合成 catalog JSON 计算各 harness 的 dry-run 校验和。"""
    root = _project_root(settings)
    local_catalog = build_local_catalog_payload(settings, root_override=root)
    catalog_json = json.dumps(local_catalog, ensure_ascii=False, indent=2).encode("utf-8")
    catalog_digest = _sha256_bytes(catalog_json)
    target_payloads: list[dict[str, Any]] = []
    for raw_t in targets:
        t = str(raw_t).strip().lower()
        if t not in {"cursor", "codex", "opencode"}:
            continue
        entries: list[dict[str, str | int]] = []
        if t != "codex":
            for name in ("rules", "skills", "agents", "commands"):
                src = root / name
                if not src.is_dir():
                    continue
                for p in sorted(src.rglob("*")):
                    if p.is_file():
                        rel = f"{name}/" + p.relative_to(src).as_posix()
                        entries.append(
                            {
                                "path": rel,
                                "sha256": _sha256_file(p),
                                "size_bytes": int(p.stat().st_size),
                            },
                        )
        entries.append(
            {
                "path": "__synthetic__/cai-local-catalog.json",
                "sha256": catalog_digest,
                "size_bytes": len(catalog_json),
            },
        )
        mode = "manifest" if t == "codex" else ("structured" if t == "cursor" else "copy")
        index = "\n".join(f'{e["path"]}\t{e["sha256"]}' for e in entries).encode("utf-8")
        target_payloads.append(
            {
                "target": t,
                "mode": mode,
                "output_dir": str(ecc_export_root_for_target(root, t)),
                "files": entries,
                "files_count": len(entries),
                "pack_sha256": _sha256_bytes(index),
            },
        )
    return {
        "schema_version": "ecc_asset_pack_manifest_v1",
        "workspace": str(root),
        "targets": target_payloads,
    }
