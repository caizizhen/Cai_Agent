from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, List

MEMORY_ENTRY_V1_FIELDS = frozenset(
    {"id", "category", "text", "confidence", "expires_at", "created_at"},
)

MEMORY_STATES = ("active", "stale", "expired")


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


def load_memory_entries_validated(
    root: str | Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    """逐行校验 schema；无效行记入 warnings，不进入返回列表。"""
    path = _entries_path(root)
    if not path.is_file():
        return [], []
    valid: list[dict[str, Any]] = []
    warnings: list[str] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            warnings.append(f"行 {lineno}: JSON 解析失败 ({e})")
            continue
        if not isinstance(obj, dict):
            warnings.append(f"行 {lineno}: 根类型须为 object")
            continue
        errs = validate_memory_entry_row(obj)
        if errs:
            warnings.append(f"行 {lineno}: " + "; ".join(errs))
            continue
        valid.append(obj)
    return valid, warnings


def export_memory_entries_bundle(root: str | Path) -> dict[str, Any]:
    valid, warnings = load_memory_entries_validated(root)
    return {
        "schema_version": "memory_entries_bundle_v1",
        "entries": valid,
        "export_warnings": warnings,
    }


def import_memory_entries_bundle(root: str | Path, bundle: dict[str, Any]) -> int:
    """导入 `export_memory_entries_bundle` 或同结构 JSON；任一行校验失败则整批失败。"""
    if not isinstance(bundle, dict):
        msg = "根对象须为 JSON object"
        raise ValueError(msg)
    entries = bundle.get("entries")
    if not isinstance(entries, list):
        msg = "缺少 entries 数组"
        raise ValueError(msg)
    to_write: list[dict[str, Any]] = []
    for i, row in enumerate(entries, start=1):
        if not isinstance(row, dict):
            msg = f"entries[{i}] 须为 object"
            raise ValueError(msg)
        errs = validate_memory_entry_row(row)
        if errs:
            msg = f"entries[{i}] schema 无效: " + "; ".join(errs)
            raise ValueError(msg)
        to_write.append(row)
    path = _entries_path(root)
    with path.open("a", encoding="utf-8") as f:
        for row in to_write:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(to_write)


def _parse_created_at(row: dict[str, Any]) -> float:
    raw = row.get("created_at")
    if not isinstance(raw, str) or not raw.strip():
        return 0.0
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.timestamp()
    except ValueError:
        return 0.0


def sort_memory_rows(rows: list[dict[str, Any]], sort: str) -> None:
    """就地排序；sort 为 none/空则不变。"""
    s = sort.strip().lower()
    if s in ("", "none", "file"):
        return
    if s == "confidence":
        rows.sort(key=_confidence_val, reverse=True)
    elif s in ("created_at", "created"):
        rows.sort(key=_parse_created_at, reverse=True)


def _confidence_val(row: dict[str, Any]) -> float:
    c = row.get("confidence")
    if isinstance(c, bool) or not isinstance(c, int | float):
        return 0.0
    return float(c)


def _parse_dt(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def memory_entry_state(
    row: dict[str, Any],
    *,
    now: datetime | None = None,
    stale_after_days: int = 14,
    min_active_confidence: float = 0.5,
) -> str:
    now_dt = now or datetime.now(UTC)
    exp = _parse_dt(row.get("expires_at"))
    if exp is not None and exp < now_dt:
        return "expired"
    created = _parse_dt(row.get("created_at"))
    conf = _confidence_val(row)
    stale_after = max(1, int(stale_after_days))
    if created is not None and created < (now_dt - timedelta(days=stale_after)):
        return "stale"
    if conf < max(0.0, min(1.0, float(min_active_confidence))):
        return "stale"
    return "active"


def annotate_memory_states(
    rows: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    stale_after_days: int = 14,
    min_active_confidence: float = 0.5,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        st = memory_entry_state(
            row,
            now=now,
            stale_after_days=stale_after_days,
            min_active_confidence=min_active_confidence,
        )
        reason = "active"
        exp = _parse_dt(row.get("expires_at"))
        created = _parse_dt(row.get("created_at"))
        conf = _confidence_val(row)
        stale_after = max(1, int(stale_after_days))
        now_dt = now or datetime.now(UTC)
        if exp is not None and exp < now_dt:
            reason = "expired_by_ttl"
        elif created is not None and created < (now_dt - timedelta(days=stale_after)):
            reason = "stale_by_age"
        elif conf < max(0.0, min(1.0, float(min_active_confidence))):
            reason = "stale_by_confidence"
        out.append({**row, "state": st, "state_reason": reason})
    return out


def evaluate_memory_entry_states(
    root: str | Path,
    *,
    stale_after_days: int = 14,
    min_active_confidence: float = 0.5,
) -> dict[str, Any]:
    rows, warnings = load_memory_entries_validated(root)
    annotated = annotate_memory_states(
        rows,
        stale_after_days=stale_after_days,
        min_active_confidence=min_active_confidence,
    )
    counts = {"active": 0, "stale": 0, "expired": 0}
    for row in annotated:
        st = str(row.get("state") or "").strip().lower()
        if st in counts:
            counts[st] += 1
    return {
        "schema_version": "memory_state_eval_v1",
        "rows": annotated,
        "counts": counts,
        "warnings": warnings,
        "stale_after_days": int(max(1, stale_after_days)),
        "min_active_confidence": float(max(0.0, min(1.0, min_active_confidence))),
    }


def search_memory_entries(
    root: str | Path,
    query: str,
    *,
    limit: int = 50,
    sort: str | None = None,
) -> list[dict[str, Any]]:
    q = query.strip().lower()
    if not q:
        return []
    hits: list[dict[str, Any]] = []
    s = (sort or "").strip().lower()
    want_sort = s in ("confidence", "created_at", "created")
    for row in load_memory_entries(root):
        text = str(row.get("text", "")).lower()
        cat = str(row.get("category", "")).lower()
        if q in text or q in cat:
            hits.append(row)
            if not want_sort and len(hits) >= limit:
                return hits
    if s == "confidence":
        hits.sort(key=_confidence_val, reverse=True)
    elif s in ("created_at", "created"):
        hits.sort(key=_parse_created_at, reverse=True)
    return hits[:limit]


def prune_expired_memory_entries(
    root: str | Path,
    *,
    min_confidence: float | None = None,
    max_entries: int | None = None,
    drop_non_active: bool = False,
    stale_after_days: int = 30,
    min_active_confidence: float = 0.4,
) -> dict[str, int]:
    """按策略清理记忆条目并返回统计。

    清理顺序：
    1) 删除 expires_at 已过期条目；
    2) 若设置 min_confidence，删除低于阈值条目；
    3) 若设置 max_entries，按 created_at 新到旧保留前 N 条，其余删除。
    """
    path = _entries_path(root)
    if not path.is_file():
        return {
            "removed_total": 0,
            "removed_expired": 0,
            "removed_low_confidence": 0,
            "removed_over_limit": 0,
            "kept_total": 0,
        }
    now = datetime.now(UTC)
    remove_expired = 0
    remove_low_conf = 0
    remove_limit = 0
    remove_non_active = 0
    cand: list[dict[str, Any]] = []

    low_conf_cutoff = None
    if isinstance(min_confidence, int | float) and not isinstance(min_confidence, bool):
        low_conf_cutoff = max(0.0, min(1.0, float(min_confidence)))

    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            cand.append({"raw": raw, "created_ts": 0.0})
            continue
        exp = obj.get("expires_at")
        if isinstance(exp, str) and exp.strip():
            try:
                exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=UTC)
                if exp_dt < now:
                    remove_expired += 1
                    continue
            except ValueError:
                pass
        if low_conf_cutoff is not None and isinstance(obj, dict):
            conf = obj.get("confidence")
            conf_val = float(conf) if isinstance(conf, int | float) and not isinstance(conf, bool) else 0.0
            if conf_val < low_conf_cutoff:
                remove_low_conf += 1
                continue
        if bool(drop_non_active) and isinstance(obj, dict):
            st = memory_entry_state(
                obj,
                stale_after_days=int(max(1, stale_after_days)),
                min_active_confidence=float(max(0.0, min(1.0, min_active_confidence))),
            )
            if st != "active":
                remove_non_active += 1
                continue
        created_ts = _parse_created_at(obj) if isinstance(obj, dict) else 0.0
        cand.append({"raw": raw, "created_ts": created_ts})

    kept: list[str] = [str(x["raw"]) for x in cand]
    if isinstance(max_entries, int) and max_entries > 0:
        cap = int(max_entries)
        if len(cand) > cap:
            sorted_cand = sorted(cand, key=lambda x: float(x["created_ts"]), reverse=True)
            kept_set = {str(x["raw"]) for x in sorted_cand[:cap]}
            remove_limit = len(cand) - len(kept_set)
            kept = [str(x["raw"]) for x in cand if str(x["raw"]) in kept_set]

    path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    removed_total = remove_expired + remove_low_conf + remove_limit + remove_non_active
    return {
        "removed_total": removed_total,
        "removed_expired": remove_expired,
        "removed_low_confidence": remove_low_conf,
        "removed_over_limit": remove_limit,
        "removed_non_active": remove_non_active,
        "kept_total": len(kept),
    }


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
