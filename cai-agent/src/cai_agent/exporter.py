from __future__ import annotations

import json
import shutil
from pathlib import Path

from cai_agent.config import Settings


def _project_root(settings: Settings) -> Path:
    if settings.config_loaded_from:
        return Path(settings.config_loaded_from).expanduser().resolve().parent
    return Path.cwd().resolve()


def export_target(settings: Settings, target: str) -> dict[str, object]:
    """导出到跨 harness 目录：优先写入可识别的最小 manifest + README。"""
    root = _project_root(settings)
    t = target.strip().lower()
    if t not in {"cursor", "codex", "opencode"}:
        raise ValueError(f"unsupported target: {target}")

    manifest_core = {
        "exporter": "cai-agent",
        "schema": "export-v2",
        "manifest_version": "2.1.0",
        "target": t,
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
        manifest_path.write_text(
            json.dumps({**manifest_core, "copied": copied}, ensure_ascii=False, indent=2) + "\n",
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
        manifest_path.write_text(
            json.dumps({**manifest_core, "copied": [], "note": "copy+manifest_only"}, ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )
        return {
            "schema_version": "export_cli_v1",
            "target": t,
            "output_dir": str(out_dir),
            "manifest": str(manifest_path),
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
    (out_dir / "cai-export-manifest.json").write_text(
        json.dumps({**manifest_core, "copied": copied}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "schema_version": "export_cli_v1",
        "target": t,
        "output_dir": str(out_dir),
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
    """对比仓库根 ``rules|skills|agents|commands`` 与 Cursor ECC 导出目录（``.cursor/cai-agent-export``）文件集合差分。"""
    root = _project_root(settings)
    t = str(target).strip().lower()
    if t != "cursor":
        return {
            "schema_version": "export_ecc_dir_diff_v1",
            "target": t,
            "error": "unsupported_target",
            "hint": "当前仅实现 --target cursor 与 .cursor/cai-agent-export 目录对比",
        }
    ecc = root / ".cursor" / "cai-agent-export"
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
