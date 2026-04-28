from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cai_agent.config import Settings
from cai_agent.ecc_ingest_gate import build_ecc_ingest_trust_decision_v1, build_ecc_pack_ingest_gate_v1
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


_STRUCTURED_HOME_DIFF_EXAMPLE_CAP = 24


def _structured_home_diff_one_component(src: Path, dst: Path) -> dict[str, Any]:
    """单组件目录：相对路径级 add/update/skip/conflict（文件内容 SHA256）。"""
    src_fp = _relative_file_fingerprint(src) if src.is_dir() else {}
    dst_fp = _relative_file_fingerprint(dst) if dst.is_dir() else {}
    paths = sorted(set(src_fp) | set(dst_fp))
    add_paths: list[str] = []
    update_paths: list[str] = []
    skip_paths: list[str] = []
    conflict_paths: list[str] = []
    for rel in paths:
        s = src_fp.get(rel)
        d = dst_fp.get(rel)
        if s is None and d is not None:
            conflict_paths.append(rel)
        elif s is not None and d is None:
            add_paths.append(rel)
        elif s is not None and d is not None:
            if s == d:
                skip_paths.append(rel)
            else:
                update_paths.append(rel)

    def _examples(paths: list[str]) -> tuple[list[dict[str, str]], int]:
        head = paths[:_STRUCTURED_HOME_DIFF_EXAMPLE_CAP]
        return [{"path": p} for p in head], max(0, len(paths) - _STRUCTURED_HOME_DIFF_EXAMPLE_CAP)

    ae, at = _examples(add_paths)
    ue, ut = _examples(update_paths)
    ce, ct = _examples(conflict_paths)
    return {
        "counts": {
            "add": len(add_paths),
            "update": len(update_paths),
            "skip": len(skip_paths),
            "conflict": len(conflict_paths),
        },
        "examples": {
            "add": ae,
            "update": ue,
            "conflict": ce,
        },
        "truncated": {
            "add": at,
            "update": ut,
            "conflict": ct,
            "skip": 0,
        },
    }


def build_export_ecc_structured_home_diff_v1(settings: Settings, *, target: str) -> dict[str, Any]:
    """ECC-N03-D04：仓库 ``rules|skills|agents|commands`` 与各 harness 导出目录的结构化差分（add/update/skip/conflict）。"""
    root = _project_root(settings)
    t = str(target).strip().lower()
    if t not in {"cursor", "codex", "opencode"}:
        return {
            "schema_version": "ecc_structured_home_diff_v1",
            "target": t,
            "error": "unsupported_target",
            "hint": "支持 --target cursor|codex|opencode，对应 export 写入目录",
        }
    try:
        ecc = ecc_export_root_for_target(root, t)
    except ValueError as e:
        return {
            "schema_version": "ecc_structured_home_diff_v1",
            "target": t,
            "error": "unsupported_target",
            "hint": str(e),
        }
    dirs = ("rules", "skills", "agents", "commands")
    rows: list[dict[str, Any]] = []
    totals = {"add": 0, "update": 0, "skip": 0, "conflict": 0}
    for name in dirs:
        row = {"name": name, **_structured_home_diff_one_component(root / name, ecc / name)}
        rows.append(row)
        cts = row.get("counts") or {}
        if isinstance(cts, dict):
            for k in totals:
                totals[k] += int(cts.get(k) or 0)
    return {
        "schema_version": "ecc_structured_home_diff_v1",
        "target": t,
        "workspace": str(root),
        "ecc_export_root": str(ecc),
        "directories": rows,
        "totals": totals,
    }


def build_ecc_structured_home_diff_bundle_v1(settings: Settings) -> dict[str, Any]:
    """聚合三 harness 的结构化 home diff，供 doctor / repair 引用。"""
    root = _project_root(settings)
    targets: list[dict[str, Any]] = []
    pending: list[str] = []
    for t in ("cursor", "codex", "opencode"):
        rep = build_export_ecc_structured_home_diff_v1(settings, target=t)
        targets.append({"target": t, "report": rep})
        if not isinstance(rep, dict) or rep.get("error"):
            continue
        tot = rep.get("totals") or {}
        if not isinstance(tot, dict):
            continue
        n = int(tot.get("add") or 0) + int(tot.get("update") or 0) + int(tot.get("conflict") or 0)
        if n > 0:
            pending.append(t)
    return {
        "schema_version": "ecc_structured_home_diff_bundle_v1",
        "workspace": str(root),
        "targets": targets,
        "targets_with_pending_actions": sorted(set(pending)),
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


def _relative_file_fingerprint(root: Path) -> dict[str, tuple[int, str]]:
    if not root.is_dir():
        return {}
    out: dict[str, tuple[int, str]] = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        out[rel] = (int(p.stat().st_size), _sha256_file(p))
    return out


def _directory_matches(src: Path, dst: Path) -> bool:
    return _relative_file_fingerprint(src) == _relative_file_fingerprint(dst)


def _backup_path(path: Path, stamp: str) -> Path:
    candidate = path.with_name(f"{path.name}.backup-{stamp}")
    idx = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.backup-{stamp}-{idx}")
        idx += 1
    return candidate


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


def build_ecc_asset_pack_import_plan_v1(
    settings: Settings,
    *,
    from_workspace: str | Path,
) -> dict[str, Any]:
    """ECC-N02-D03: 预览将源 workspace 的资产目录导入当前 workspace。"""
    dst_root = Path(settings.workspace).expanduser().resolve() if settings.workspace else _project_root(settings)
    src_root = Path(from_workspace).expanduser().resolve()
    if not src_root.is_dir():
        return {
            "schema_version": "ecc_asset_pack_import_plan_v1",
            "ok": False,
            "error": "source_workspace_missing",
            "hint": "使用 --from-workspace 指向存在的目录",
            "source_workspace": str(src_root),
            "dest_workspace": str(dst_root),
        }
    rows: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for name in ("rules", "skills", "agents", "commands"):
        src = src_root / name
        dst = dst_root / name
        src_exists = src.is_dir()
        dst_exists = dst.is_dir()
        row: dict[str, Any] = {
            "component": name,
            "source_path": str(src),
            "dest_path": str(dst),
            "source_exists": src_exists,
            "dest_exists": dst_exists,
        }
        if not src_exists:
            row["action"] = "skip"
            row["reason"] = "source_missing"
        elif not dst_exists:
            row["action"] = "add"
        elif _directory_matches(src, dst):
            row["action"] = "skip"
            row["reason"] = "up_to_date"
        else:
            row["action"] = "conflict"
            row["reason"] = "destination_exists_and_differs"
            conflicts.append(
                {
                    "component": name,
                    "dest_path": str(dst),
                    "reason": "destination_exists_and_differs",
                    "resolution": "rerun with --apply --force to back up and replace",
                },
            )
        rows.append(row)
    plan_out: dict[str, Any] = {
        "schema_version": "ecc_asset_pack_import_plan_v1",
        "ok": True,
        "source_workspace": str(src_root),
        "dest_workspace": str(dst_root),
        "components": rows,
        "conflicts": conflicts,
    }
    plan_out["ingest_gate"] = build_ecc_pack_ingest_gate_v1(src_root)
    plan_out["trust_decision"] = build_ecc_ingest_trust_decision_v1(
        src_root,
        sanitizer_gate=plan_out["ingest_gate"],
    )
    return plan_out


def run_ecc_asset_pack_import_v1(
    settings: Settings,
    *,
    from_workspace: str | Path,
    apply: bool,
    force: bool = False,
    backup: bool = True,
) -> dict[str, Any]:
    """ECC-N02-D03: import/install pack assets into current workspace."""
    plan = build_ecc_asset_pack_import_plan_v1(settings, from_workspace=from_workspace)
    if not bool(plan.get("ok")):
        return {
            "schema_version": "ecc_asset_pack_import_result_v1",
            "ok": False,
            "dry_run": not apply,
            "plan": plan,
            "error": plan.get("error") or "plan_failed",
            "hint": plan.get("hint"),
        }
    if not apply:
        return {
            "schema_version": "ecc_asset_pack_import_result_v1",
            "ok": True,
            "dry_run": True,
            "plan": plan,
            "applied": [],
            "backups": [],
            "conflicts": plan.get("conflicts") or [],
        }
    ingate = plan.get("ingest_gate")
    if not isinstance(ingate, dict):
        ingate = build_ecc_pack_ingest_gate_v1(str(plan.get("source_workspace") or ""))
    if not bool(ingate.get("allow", True)):
        return {
            "schema_version": "ecc_asset_pack_import_result_v1",
            "ok": False,
            "dry_run": False,
            "error": "ingest_gate_rejected",
            "hint": "源 workspace 的 hooks.json 命中 ingest 与 hook_runtime 一致的危险命令规则，或存在 script 越界；请清理后再 --apply",
            "plan": plan,
            "ingest_gate": ingate,
            "applied": [],
            "backups": [],
            "conflicts": plan.get("conflicts") or [],
        }
    src_root = Path(str(plan.get("source_workspace") or "")).expanduser().resolve()
    trust_decision = plan.get("trust_decision")
    if not isinstance(trust_decision, dict):
        trust_decision = build_ecc_ingest_trust_decision_v1(src_root, sanitizer_gate=ingate)
    if not bool(trust_decision.get("allow_apply", False)):
        return {
            "schema_version": "ecc_asset_pack_import_result_v1",
            "ok": False,
            "dry_run": False,
            "error": "trust_gate_rejected",
            "hint": "source workspace lacks reviewed provenance/trust metadata; inspect trust_decision and rerun after adding ecc_asset_registry_v1 metadata",
            "plan": plan,
            "ingest_gate": ingate,
            "trust_decision": trust_decision,
            "applied": [],
            "backups": [],
            "conflicts": plan.get("conflicts") or [],
        }
    if (plan.get("conflicts") or []) and not force:
        return {
            "schema_version": "ecc_asset_pack_import_result_v1",
            "ok": False,
            "dry_run": False,
            "force": False,
            "backup": bool(backup),
            "plan": plan,
            "applied": [],
            "backups": [],
            "conflicts": plan.get("conflicts") or [],
            "hint": "resolve conflicts or rerun with --force",
        }
    dst_root = Path(str(plan.get("dest_workspace") or "")).expanduser().resolve()
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    applied: list[dict[str, Any]] = []
    backups: list[dict[str, Any]] = []
    for row in plan.get("components") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("action") or "") not in {"add", "conflict"}:
            continue
        name = str(row.get("component") or "")
        src = src_root / name
        dst = dst_root / name
        if not src.is_dir():
            continue
        backup_record: dict[str, Any] | None = None
        if dst.exists():
            if backup:
                bpath = _backup_path(dst, stamp)
                shutil.move(str(dst), str(bpath))
                backup_record = {"component": name, "from": str(dst), "backup_path": str(bpath)}
                backups.append(backup_record)
            elif dst.is_dir():
                shutil.rmtree(dst)
            else:
                dst.unlink()
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst)
        applied_row = {"component": name, "dest_path": str(dst), "backup": backup_record}
        applied.append(applied_row)
    return {
        "schema_version": "ecc_asset_pack_import_result_v1",
        "ok": True,
        "dry_run": False,
        "force": bool(force),
        "backup": bool(backup),
        "plan": plan,
        "applied": applied,
        "backups": backups,
        "conflicts": [],
    }


def _workspace_license_summary(root: Path) -> dict[str, Any]:
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"):
        p = root / name
        if p.is_file():
            return {"spdx_id": "UNKNOWN", "license_file": str(p), "detected": True}
    return {"spdx_id": "NOASSERTION", "license_file": None, "detected": False}


def _workspace_trust_summary(root: Path) -> dict[str, Any]:
    gate = build_ecc_pack_ingest_gate_v1(root)
    decision = build_ecc_ingest_trust_decision_v1(root, sanitizer_gate=gate)
    allow = bool(decision.get("allow_apply"))
    raw_level = str(decision.get("trust_level") or "").strip()
    level = raw_level or ("local_reviewed" if allow else "blocked")
    if not allow and level in {"", "unknown", "reviewed", "local_reviewed"}:
        level = "blocked"
    return {
        "schema_version": "ecc_asset_trust_summary_v1",
        "level": level,
        "decision": decision.get("combined_decision"),
        "allow": allow,
        "violations_count": len(gate.get("violations") or []),
        "ingest_gate": gate,
        "trust_decision": decision,
    }


def _market_asset_record(
    row: dict[str, Any],
    *,
    root: Path,
    license_summary: dict[str, Any],
    trust_summary: dict[str, Any],
) -> dict[str, Any]:
    aid = str(row.get("id") or "").strip()
    exists = bool(row.get("exists"))
    return {
        "asset_id": aid,
        "asset_type": str(row.get("kind") or "unknown"),
        "name": aid,
        "version": str(row.get("plugin_version") or "workspace"),
        "source": {"kind": "workspace", "origin": str(root)},
        "license": license_summary,
        "trust": {
            "schema_version": trust_summary.get("schema_version"),
            "level": trust_summary.get("level"),
            "decision": trust_summary.get("decision"),
            "allow": bool(trust_summary.get("allow")),
            "violations_count": int(trust_summary.get("violations_count") or 0),
        },
        "install": {
            "status": "installed" if exists else "missing",
            "path": row.get("path"),
            "items_count": int(row.get("items_count") or 0),
        },
    }


def build_ecc_asset_marketplace_catalog_v1(
    settings: Settings,
    *,
    root_override: str | Path | None = None,
) -> dict[str, Any]:
    """Marketplace-lite catalog over the local/workspace asset catalog."""
    root = Path(root_override).expanduser().resolve() if root_override is not None else _project_root(settings)
    local_catalog = build_local_catalog_payload(settings, root_override=root)
    license_summary = _workspace_license_summary(root)
    trust_summary = _workspace_trust_summary(root)
    assets = [
        _market_asset_record(row, root=root, license_summary=license_summary, trust_summary=trust_summary)
        for row in (local_catalog.get("assets") or [])
        if isinstance(row, dict)
    ]
    return {
        "schema_version": "ecc_asset_marketplace_catalog_v1",
        "marketplace_kind": "local_workspace",
        "workspace": str(root),
        "source": {"kind": "workspace", "origin": str(root)},
        "generated_at": datetime.now(UTC).isoformat(),
        "assets": assets,
        "summary": {
            "assets_count": len(assets),
            "installed_count": sum(1 for a in assets if (a.get("install") or {}).get("status") == "installed"),
            "missing_count": sum(1 for a in assets if (a.get("install") or {}).get("status") == "missing"),
            "trust_level": trust_summary.get("level"),
            "trust_allow": bool(trust_summary.get("allow")),
        },
        "license": license_summary,
        "trust": trust_summary,
        "local_catalog": local_catalog,
    }


def build_ecc_asset_marketplace_list_v1(
    settings: Settings,
    *,
    root_override: str | Path | None = None,
) -> dict[str, Any]:
    catalog = build_ecc_asset_marketplace_catalog_v1(settings, root_override=root_override)
    return {
        "schema_version": "ecc_asset_marketplace_list_v1",
        "workspace": catalog.get("workspace"),
        "marketplace_kind": catalog.get("marketplace_kind"),
        "assets": catalog.get("assets") or [],
        "summary": catalog.get("summary") or {},
    }


def build_ecc_asset_marketplace_upgrade_plan_v1(
    settings: Settings,
    *,
    from_workspace: str | Path,
) -> dict[str, Any]:
    src_root = Path(from_workspace).expanduser().resolve()
    dst_root = Path(settings.workspace).expanduser().resolve() if settings.workspace else _project_root(settings)
    if not src_root.is_dir():
        return {
            "schema_version": "ecc_asset_marketplace_upgrade_plan_v1",
            "ok": False,
            "error": "source_workspace_missing",
            "source_workspace": str(src_root),
            "dest_workspace": str(dst_root),
            "recommendations": [],
        }
    catalog = build_ecc_asset_marketplace_catalog_v1(settings, root_override=src_root)
    plan = build_ecc_asset_pack_import_plan_v1(settings, from_workspace=src_root)
    assets_by_id = {
        str(a.get("asset_id")): a
        for a in (catalog.get("assets") or [])
        if isinstance(a, dict)
    }
    recommendations: list[dict[str, Any]] = []
    for row in plan.get("components") or []:
        if not isinstance(row, dict):
            continue
        component = str(row.get("component") or "")
        action = str(row.get("action") or "skip")
        rec_action = {"add": "install", "conflict": "upgrade_with_force", "skip": "none"}.get(action, action)
        recommendations.append(
            {
                "asset_id": component,
                "asset": assets_by_id.get(component),
                "current_status": "installed" if row.get("dest_exists") else "missing",
                "source_status": "available" if row.get("source_exists") else "missing",
                "recommendation": rec_action,
                "reason": row.get("reason") or action,
                "source_path": row.get("source_path"),
                "dest_path": row.get("dest_path"),
                "install_command": (
                    f"cai-agent ecc pack-import --from-workspace {src_root} --apply --force --json"
                    if rec_action == "upgrade_with_force"
                    else f"cai-agent ecc pack-import --from-workspace {src_root} --apply --json"
                    if rec_action == "install"
                    else None
                ),
            },
        )
    trust = catalog.get("trust") if isinstance(catalog.get("trust"), dict) else {}
    return {
        "schema_version": "ecc_asset_marketplace_upgrade_plan_v1",
        "ok": bool(plan.get("ok")),
        "source_workspace": str(src_root),
        "dest_workspace": plan.get("dest_workspace"),
        "catalog": catalog,
        "pack_import_plan": plan,
        "trust": trust,
        "recommendations": recommendations,
        "summary": {
            "recommendations_count": len(recommendations),
            "install_count": sum(1 for r in recommendations if r.get("recommendation") == "install"),
            "upgrade_with_force_count": sum(1 for r in recommendations if r.get("recommendation") == "upgrade_with_force"),
            "up_to_date_count": sum(1 for r in recommendations if r.get("recommendation") == "none"),
            "trust_allow": bool(trust.get("allow", True)),
        },
    }


def _export_join(out_dir: Path, rel_posix: str) -> Path:
    parts = [p for p in str(rel_posix).strip("/").split("/") if p]
    return out_dir.joinpath(*parts) if parts else out_dir


def build_ecc_asset_pack_repair_report_v1(
    settings: Settings,
    *,
    targets: tuple[str, ...] = ("cursor", "codex", "opencode"),
) -> dict[str, Any]:
    """ECC-N02-D04: compare pack manifest expectations vs on-disk export + workspace catalog.

    Emits structured ``issues[]`` and deduplicated ``repair_suggestions`` (shell-oriented hints).
    """
    root = _project_root(settings)
    manifest = build_ecc_asset_pack_manifest_v1(settings, targets=targets)
    local_cat = build_local_catalog_payload(settings, root_override=root)
    cat_schema = str(local_cat.get("schema_version") or "")
    issues: list[dict[str, Any]] = []
    suggestions: list[str] = []

    for asset in local_cat.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        aid = str(asset.get("id") or "").strip()
        if aid in {"rules", "skills"}:
            p = root / aid
            if not p.is_dir():
                issues.append(
                    {
                        "kind": "workspace_component_missing",
                        "component": aid,
                        "path": str(p),
                        "severity": "info",
                    },
                )
                suggestions.append("cai-agent ecc scaffold  # or add rules/ and skills/")

    for tp in manifest.get("targets") or []:
        if not isinstance(tp, dict):
            continue
        target = str(tp.get("target") or "").strip().lower()
        if target not in {"cursor", "codex", "opencode"}:
            continue
        out_dir = Path(str(tp.get("output_dir") or "")).expanduser().resolve()
        for fe in tp.get("files") or []:
            if not isinstance(fe, dict):
                continue
            rel = str(fe.get("path") or "")
            exp_hash = str(fe.get("sha256") or "")
            if rel.startswith("__synthetic__/"):
                cat_path = out_dir / "cai-local-catalog.json"
                if not cat_path.is_file():
                    issues.append(
                        {
                            "kind": "missing_export_file",
                            "target": target,
                            "path": str(cat_path),
                            "role": "local_catalog_json",
                            "severity": "error",
                        },
                    )
                    suggestions.append(f"cai-agent export --target {target}")
                elif exp_hash:
                    act_hash = _sha256_file(cat_path)
                    if act_hash != exp_hash:
                        issues.append(
                            {
                                "kind": "export_catalog_drift",
                                "target": target,
                                "path": str(cat_path),
                                "expected_sha256": exp_hash,
                                "actual_sha256": act_hash,
                                "severity": "warning",
                            },
                        )
                        suggestions.append(f"cai-agent export --target {target}  # refresh cai-local-catalog.json")
                continue
            fp = _export_join(out_dir, rel)
            if not fp.is_file():
                issues.append(
                    {
                        "kind": "missing_export_file",
                        "target": target,
                        "path": str(fp),
                        "manifest_path": rel,
                        "severity": "error",
                    },
                )
                suggestions.append(f"cai-agent export --target {target}")
                continue
            if exp_hash:
                act_hash = _sha256_file(fp)
                if act_hash != exp_hash:
                    issues.append(
                        {
                            "kind": "export_content_drift",
                            "target": target,
                            "path": str(fp),
                            "manifest_path": rel,
                            "expected_sha256": exp_hash,
                            "actual_sha256": act_hash,
                            "severity": "warning",
                        },
                    )
                    suggestions.append(f"cai-agent export --target {target}  # resync export tree")

        man_path = out_dir / "cai-export-manifest.json"
        if man_path.is_file():
            try:
                man = json.loads(man_path.read_text(encoding="utf-8"))
                if isinstance(man, dict):
                    stored = str(man.get("local_catalog_schema_version") or "")
                    if stored and cat_schema and stored != cat_schema:
                        issues.append(
                            {
                                "kind": "export_manifest_schema_drift",
                                "target": target,
                                "path": str(man_path),
                                "stored_catalog_schema": stored,
                                "current_catalog_schema": cat_schema,
                                "severity": "info",
                            },
                        )
                        suggestions.append(
                            "cai-agent export --target "
                            + target
                            + "  # align cai-export-manifest.json with current catalog schema",
                        )
            except json.JSONDecodeError:
                issues.append(
                    {
                        "kind": "export_manifest_corrupt",
                        "target": target,
                        "path": str(man_path),
                        "severity": "warning",
                    },
                )
                suggestions.append(f"cai-agent export --target {target}  # rewrite manifest")

    compat_hints = [
        "cai-agent plugins --json --with-compat-matrix",
        "python scripts/gen_plugin_compat_snapshot.py --check",
    ]
    dedup_sug: list[str] = []
    seen: set[str] = set()
    for s in suggestions:
        if s not in seen:
            seen.add(s)
            dedup_sug.append(s)

    err_n = sum(1 for i in issues if str(i.get("severity") or "") == "error")
    ok = err_n == 0
    kinds: dict[str, int] = {}
    for i in issues:
        k = str(i.get("kind") or "unknown")
        kinds[k] = kinds.get(k, 0) + 1

    return {
        "schema_version": "ecc_asset_pack_repair_report_v1",
        "ok": ok,
        "workspace": str(root),
        "catalog_schema_version": cat_schema,
        "issues": issues,
        "issues_by_kind": kinds,
        "error_issues": err_n,
        "repair_suggestions": dedup_sug,
        "compat_hints": compat_hints,
    }
