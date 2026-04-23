from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, List


@dataclass(frozen=True)
class Skill:
    """从 `skills/` 目录加载的可复用工作流/提示模版描述."""

    name: str
    path: Path
    content: str


def _is_skill_file(path: Path) -> bool:
    return path.suffix.lower() in {".md", ".markdown", ".txt"}


def load_skills(root: str | Path) -> List[Skill]:
    """从仓库根目录下的 `skills/` 目录加载全部技能文件.

    当前实现只负责读取文件内容, 不做语义解析, 便于后续在 CLI/TUI
    或 LLM 提示中引用这些模版。
    """

    base = Path(root).expanduser().resolve()
    skills_dir = base / "skills"
    if not skills_dir.is_dir():
        return []
    items: list[Skill] = []
    for p in sorted(skills_dir.rglob("*")):
        if not p.is_file() or not _is_skill_file(p):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        rel_name = p.relative_to(skills_dir).as_posix()
        items.append(Skill(name=rel_name, path=p, content=text))
    return items


def iter_skill_names(skills: Iterable[Skill]) -> list[str]:
    """提取技能名称列表, 便于在 UI 或 system prompt 中展示."""

    return sorted({s.name for s in skills})


def build_skills_hub_manifest(*, root: str | Path) -> dict[str, Any]:
    """Skills Hub 分发清单（``skills_hub_manifest_v1``）：扫描工作区 ``skills/`` 下可分发文件。"""
    base = Path(root).expanduser().resolve()
    skills = load_skills(base)
    entries: list[dict[str, Any]] = []
    for s in skills:
        try:
            st = s.path.stat()
        except OSError:
            continue
        try:
            rel = s.path.resolve().relative_to(base)
            rel_s = rel.as_posix()
        except ValueError:
            rel_s = str(s.path)
        entries.append(
            {
                "name": s.name,
                "path": rel_s,
                "size_bytes": int(st.st_size),
                "mtime_iso": datetime.fromtimestamp(st.st_mtime, tz=UTC).isoformat(),
            },
        )
    skills_dir = base / "skills"
    return {
        "schema_version": "skills_hub_manifest_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(base),
        "skills_dir": str(skills_dir),
        "skills_dir_exists": skills_dir.is_dir(),
        "count": len(entries),
        "entries": entries,
    }

