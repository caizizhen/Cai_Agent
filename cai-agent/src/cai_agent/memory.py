from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, List

MEMORY_ENTRY_V1_FIELDS = frozenset(
    {"id", "category", "text", "confidence", "expires_at", "created_at"},
)


def validate_memory_entry_row(row: dict[str, Any]) -> list[str]:
    """校验与 memory_entry_v1.schema.json 一致的 JSONL 行（不依赖 jsonschema 运行时）。"""
    errs: list[str] = []
    extra = set(row.keys()) - MEMORY_ENTRY_V1_FIELDS
    if extra:
        errs.append(f"不允许的字段: {sorted(extra)}")
    for key in ("id", "category", "created_at"):
        v = row.get(key)
        if not isinstance(v, str) or not v.strip():
            errs.append(f"{key} 必须为非空字符串")
    if "text" not in row or not isinstance(row["text"], str):
        errs.append("text 必须为 string")
    conf = row.get("confidence")
    if isinstance(conf, bool) or not isinstance(conf, int | float):
        errs.append("confidence 必须为数字")
    else:
        c = float(conf)
        if c < 0.0 or c > 1.0:
            errs.append("confidence 须在 0~1")
    exp = row.get("expires_at")
    if exp is not None and exp != "" and not isinstance(exp, str):
        errs.append("expires_at 须为 string 或 null")
    return errs


@dataclass(frozen=True)
class Instinct:
    """从历史会话中提炼出的经验/模式摘要."""

    title: str
    body: str
    tags: list[str]
    confidence: float


@dataclass(frozen=True)
class MemoryEntry:
    id: str
    category: str
    text: str
    confidence: float
    expires_at: str | None
    created_at: str


def _default_memory_dir(root: str | Path) -> Path:
    base = Path(root).expanduser().resolve()
    return base / "memory" / "instincts"


def _entries_path(root: str | Path) -> Path:
    base = Path(root).expanduser().resolve()
    d = base / "memory"
    d.mkdir(parents=True, exist_ok=True)
    return d / "entries.jsonl"


def append_memory_entry(
    root: str | Path,
    *,
    category: str,
    text: str,
    confidence: float = 0.5,
    expires_at: str | None = None,
    entry_id: str | None = None,
) -> MemoryEntry:
    eid = entry_id or str(uuid.uuid4())
    created = datetime.now(UTC).isoformat()
    row = {
        "id": eid,
        "category": category,
        "text": text,
        "confidence": float(confidence),
        "expires_at": expires_at,
        "created_at": created,
    }
    bad = validate_memory_entry_row(row)
    if bad:
        msg = "; ".join(bad)
        raise ValueError(msg)
    path = _entries_path(root)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return MemoryEntry(
        id=eid,
        category=category,
        text=text,
        confidence=float(confidence),
        expires_at=expires_at,
        created_at=created,
    )


def load_memory_entries(root: str | Path) -> list[dict[str, Any]]:
    path = _entries_path(root)
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def search_memory_entries(root: str | Path, query: str, *, limit: int = 50) -> list[dict[str, Any]]:
    q = query.strip().lower()
    if not q:
        return []
    hits: list[dict[str, Any]] = []
    for row in load_memory_entries(root):
        text = str(row.get("text", "")).lower()
        cat = str(row.get("category", "")).lower()
        if q in text or q in cat:
            hits.append(row)
        if len(hits) >= limit:
            break
    return hits


def prune_expired_memory_entries(root: str | Path) -> int:
    """删除 expires_at 早于当前 UTC 的行；返回删除条数。"""
    path = _entries_path(root)
    if not path.is_file():
        return 0
    now = datetime.now(UTC)
    kept: list[str] = []
    removed = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            kept.append(raw)
            continue
        exp = obj.get("expires_at")
        if isinstance(exp, str) and exp.strip():
            try:
                exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=UTC)
                if exp_dt < now:
                    removed += 1
                    continue
            except ValueError:
                pass
        kept.append(raw)
    path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    return removed


def save_instincts(root: str | Path, instincts: Iterable[Instinct]) -> Path | None:
    """将一组 Instinct 以 Markdown 形式持久化.

    当前实现采用简单的追加文件策略, 方便后续在 system prompt 中引用。
    """

    out_dir = _default_memory_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
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


def extract_memory_entries_from_session(
    root: str | Path,
    session: dict[str, Any],
) -> MemoryEntry | None:
    goal = session.get("goal") or ""
    answer = session.get("answer") or ""
    if not isinstance(goal, str):
        goal = str(goal)
    if not isinstance(answer, str):
        answer = str(answer)
    text = f"{goal.strip()}\n\n{answer.strip()}".strip()
    if not text:
        return None
    return append_memory_entry(
        root,
        category="session",
        text=text,
        confidence=0.5,
        expires_at=None,
    )
