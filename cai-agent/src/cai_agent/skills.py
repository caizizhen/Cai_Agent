from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


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

