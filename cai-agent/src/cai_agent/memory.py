from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, List


@dataclass(frozen=True)
class Instinct:
    """从历史会话中提炼出的经验/模式摘要."""

    title: str
    body: str
    tags: list[str]
    confidence: float


def _default_memory_dir(root: str | Path) -> Path:
    base = Path(root).expanduser().resolve()
    return base / "memory" / "instincts"


def save_instincts(root: str | Path, instincts: Iterable[Instinct]) -> Path | None:
    """将一组 Instinct 以 Markdown 形式持久化.

    当前实现采用简单的追加文件策略, 方便后续在 system prompt 中引用。
    """

    out_dir = _default_memory_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    target = out_dir / f"instincts-{ts}.md"
    lines: list[str] = ["# Instincts snapshot", f"- generated_at: {ts}", ""]
    for inst in instincts:
        lines.append(f"## {inst.title}")
        if inst.tags:
            lines.append(f"- tags: {', '.join(inst.tags)}")
        lines.append(f"- confidence: {inst.confidence:.2f}")
        lines.append("")
        lines.append(inst.body.strip())
        lines.append("")
    target.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return target


def extract_basic_instincts_from_session(session: dict[str, Any]) -> List[Instinct]:
    """从单个会话 JSON 中提取最小 Instinct 信息.

    目前只基于 goal/answer 概要生成一条通用 Instinct, 后续可以
    升级为调用 LLM 进行结构化总结。
    """

    goal = session.get("goal") or ""
    answer = session.get("answer") or ""
    if not isinstance(goal, str):
        goal = str(goal)
    if not isinstance(answer, str):
        answer = str(answer)
    title = goal.strip()[:60] or "general-instinct"
    body = (
        "## Goal\n"
        f"{goal.strip()}\n\n"
        "## Observed solution\n"
        f"{answer.strip()}\n"
    )
    tags = ["auto", "session"]
    return [Instinct(title=title, body=body, tags=tags, confidence=0.5)]

