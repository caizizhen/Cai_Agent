"""Runtime skill usage logging and optional auto-improvement (H1-SK)."""

from __future__ import annotations

import json
import os
import re
import threading
from collections import Counter
from datetime import UTC, datetime, timedelta
import uuid
from pathlib import Path
from typing import Any

_USAGE_FILENAME = "skill-usage.jsonl"
_HISTORY_FILENAME = "skill-history.jsonl"
_TOUCH_LOCK = threading.Lock()
# Per-process session buffer: cleared at CLI run start; appended when skills load.
_SESSION_TOUCHES: list[dict[str, str]] = []


def clear_session_skill_touches() -> None:
    with _TOUCH_LOCK:
        _SESSION_TOUCHES.clear()


def register_session_skill_touch(skill_id: str, goal_hint: str = "") -> None:
    sid = str(skill_id or "").strip()
    if not sid or sid.lower() == "readme.md":
        return
    gh = (goal_hint or "").strip()[:500]
    with _TOUCH_LOCK:
        _SESSION_TOUCHES.append({"skill_id": sid, "goal_hint": gh})


def iter_session_skill_touches() -> list[dict[str, str]]:
    with _TOUCH_LOCK:
        return list(_SESSION_TOUCHES)


def _usage_path(root: Path) -> Path:
    return root / ".cai" / _USAGE_FILENAME


def _history_path(root: Path) -> Path:
    return root / ".cai" / _HISTORY_FILENAME


def append_skill_history_line(root: str | Path, record: dict[str, Any]) -> None:
    p = _history_path(Path(root).expanduser().resolve())
    p.parent.mkdir(parents=True, exist_ok=True)
    line = dict(record)
    line.setdefault("schema_version", "skill_history_v1")
    line.setdefault("ts", datetime.now(UTC).isoformat())
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def should_trigger_auto_improve(
    root: str | Path,
    skill_id: str,
    *,
    min_usage_count: int = 1,
    min_days_since_last_improve: int = 0,
) -> tuple[bool, str]:
    """按用量与冷却窗口判断是否应对某技能追加 auto-improve 记录。"""
    base = Path(root).expanduser().resolve()
    n = len(_read_usage_lines(base, skill_id=str(skill_id or "").strip().replace("\\", "/"), max_lines=50_000))
    if n < max(1, int(min_usage_count)):
        return False, "below_min_usage_count"
    if int(min_days_since_last_improve) > 0:
        hp = _history_path(base)
        if hp.is_file():
            try:
                for raw in reversed(hp.read_text(encoding="utf-8").splitlines()):
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        obj = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(obj, dict):
                        continue
                    if str(obj.get("skill_id") or "") != str(skill_id).strip().replace("\\", "/"):
                        continue
                    ts_raw = obj.get("ts")
                    if not isinstance(ts_raw, str):
                        continue
                    try:
                        dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                    except ValueError:
                        continue
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=UTC)
                    age = datetime.now(UTC) - dt.astimezone(UTC)
                    if age.days < int(min_days_since_last_improve):
                        return False, "cooldown_active"
                    break
            except OSError:
                pass
    return True, "ok"


def build_skills_usage_trend_v1(
    root: str | Path,
    *,
    days: int = 14,
    skill_id: str | None = None,
) -> dict[str, Any]:
    """按 UTC 日历日聚合 ``skill-usage.jsonl`` 事件次数（``skills_usage_trend_v1``）。"""
    ndays = max(1, min(366, int(days)))
    clock = datetime.now(UTC)
    end_d = clock.date()
    start_d = end_d - timedelta(days=ndays - 1)
    base = Path(root).expanduser().resolve()
    lines = _read_usage_lines(base, skill_id=skill_id, max_lines=50_000)
    by_day: dict[str, int] = {}
    for d in range((end_d - start_d).days + 1):
        dk = (start_d + timedelta(days=d)).isoformat()
        by_day[dk] = 0
    for row in lines:
        ts_raw = row.get("ts")
        if not isinstance(ts_raw, str):
            continue
        try:
            dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        dk = dt.astimezone(UTC).date().isoformat()
        if dk in by_day:
            by_day[dk] += 1
    series = [{"date": k, "count": int(by_day[k])} for k in sorted(by_day.keys())]
    ma3: list[float | None] = []
    for i, row in enumerate(series):
        if i < 2:
            ma3.append(None)
        else:
            s = int(series[i - 2]["count"]) + int(series[i - 1]["count"]) + int(row["count"])
            ma3.append(round(float(s) / 3.0, 3))
    return {
        "schema_version": "skills_usage_trend_v1",
        "generated_at": clock.isoformat(),
        "workspace": str(base),
        "filter_skill_id": skill_id,
        "window_days": ndays,
        "series": [{"date": s["date"], "count": s["count"], "ma3": ma3[i]} for i, s in enumerate(series)],
    }


def record_skill_usage(
    root: str | Path,
    skill_id: str,
    *,
    goal: str = "",
    outcome: str = "loaded",
) -> None:
    """Append one JSONL line under ``.cai/skill-usage.jsonl``."""
    base = Path(root).expanduser().resolve()
    p = _usage_path(base)
    p.parent.mkdir(parents=True, exist_ok=True)
    sid = str(skill_id or "").strip()
    if not sid:
        return
    line = {
        "ts": datetime.now(UTC).isoformat(),
        "skill_id": sid.replace("\\", "/"),
        "goal": (goal or "")[:500],
        "outcome": (outcome or "loaded")[:80],
    }
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def count_skill_usage_events(root: str | Path, skill_id: str, *, max_lines: int = 50_000) -> int:
    """统计 ``skill-usage.jsonl`` 中匹配 ``skill_id``（相对 ``skills/`` 的 posix 路径）的事件行数。"""
    sid = str(skill_id or "").strip().replace("\\", "/")
    if not sid:
        return 0
    return len(_read_usage_lines(Path(root).expanduser().resolve(), skill_id=sid, max_lines=max_lines))


def _read_usage_lines(root: Path, *, skill_id: str | None = None, max_lines: int = 2000) -> list[dict[str, Any]]:
    p = _usage_path(root)
    if not p.is_file():
        return []
    out: list[dict[str, Any]] = []
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError:
        return []
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if skill_id is not None and str(obj.get("skill_id") or "") != skill_id:
            continue
        out.append(obj)
        if len(out) >= max_lines:
            break
    return out


def aggregate_skill_usage(
    root: str | Path,
    *,
    skill_id: str | None = None,
) -> dict[str, Any]:
    """Return ``skills_usage_aggregate_v1`` for CLI / metrics."""
    base = Path(root).expanduser().resolve()
    lines = _read_usage_lines(base, skill_id=skill_id, max_lines=5000)
    c = Counter(str(x.get("skill_id") or "") for x in lines if str(x.get("skill_id") or ""))
    return {
        "schema_version": "skills_usage_aggregate_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(base),
        "filter_skill_id": skill_id,
        "total_events": len(lines),
        "by_skill_id": dict(c.most_common()),
        "recent": lines[-50:] if len(lines) > 50 else lines,
    }


def _append_history_section(path: Path, body: str) -> None:
    prev = path.read_text(encoding="utf-8") if path.is_file() else ""
    sep = "" if prev.endswith("\n") else "\n"
    path.write_text(prev + sep + body, encoding="utf-8")


def improve_skill_append_note(
    *,
    root: str | Path,
    skill_id: str,
    note_md: str,
    apply: bool = False,
) -> dict[str, Any]:
    """Append a ``## 历史改进`` subsection to ``skills/<skill_id>`` (dry-run by default)."""
    base = Path(root).expanduser().resolve()
    rel = str(skill_id or "").strip().replace("\\", "/").lstrip("/")
    if ".." in rel or rel.startswith("/"):
        raise ValueError("invalid_skill_id")
    skill_path = (base / "skills" / rel).resolve()
    skills_root = (base / "skills").resolve()
    try:
        skill_path.relative_to(skills_root)
    except ValueError as e:
        raise ValueError("skill_not_under_skills_dir") from e
    if not skill_path.is_file():
        raise ValueError("skill_not_found")
    iso = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    hid = str(uuid.uuid4())
    block = (
        f"\n<!-- cai:hist id={hid} ts={iso} -->\n"
        f"## 历史改进\n\n"
        f"### {iso}\n\n"
        f"{note_md.strip()}\n\n"
    )
    written = False
    if apply:
        _append_history_section(skill_path, block)
        append_skill_history_line(
            base,
            {
                "hist_id": hid,
                "skill_id": rel,
                "kind": "append_history",
                "bytes": len(block.encode("utf-8")),
            },
        )
        written = True
    return {
        "schema_version": "skills_evolution_runtime_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(base),
        "skill_id": rel,
        "apply": bool(apply),
        "written": written,
        "preview_append": block[:1200],
        "hist_id": hid,
    }


def revert_skill_append_by_hist_id(
    *,
    root: str | Path,
    skill_id: str,
    hist_id: str,
    apply: bool = False,
) -> dict[str, Any]:
    """移除 ``<!-- cai:hist id=...>`` 锚点起的单次 ``历史改进`` 追加块（默认预览）。"""
    base = Path(root).expanduser().resolve()
    rel = str(skill_id or "").strip().replace("\\", "/").lstrip("/")
    hid = str(hist_id or "").strip()
    if not hid or ".." in rel:
        raise ValueError("invalid_hist_or_skill")
    skill_path = (base / "skills" / rel).resolve()
    skills_root = (base / "skills").resolve()
    try:
        skill_path.relative_to(skills_root)
    except ValueError as e:
        raise ValueError("skill_not_under_skills_dir") from e
    if not skill_path.is_file():
        raise ValueError("skill_not_found")
    text = skill_path.read_text(encoding="utf-8")
    marker = f"<!-- cai:hist id={hid}"
    pos = text.find(marker)
    if pos < 0:
        raise ValueError("hist_marker_not_found")
    rest = text[pos + len(marker) :]
    close_idx = rest.find("-->")
    if close_idx < 0:
        raise ValueError("hist_marker_malformed")
    start = pos
    after_open = pos + len(marker) + close_idx + 3
    nxt = text.find("<!-- cai:hist id=", after_open)
    end = len(text) if nxt < 0 else nxt
    removed = text[start:end]
    new_text = text[:start] + text[end:]
    preview = new_text[:800]
    written = False
    if apply:
        skill_path.write_text(new_text, encoding="utf-8")
        append_skill_history_line(
            base,
            {"hist_id": hid, "skill_id": rel, "kind": "revert_history", "removed_chars": len(removed)},
        )
        written = True
    return {
        "schema_version": "skills_revert_v1",
        "skill_id": rel,
        "hist_id": hid,
        "apply": bool(apply),
        "written": written,
        "removed_preview": removed[:1200],
        "file_preview": preview,
    }


def build_default_improve_note(root: str | Path, skill_id: str) -> str:
    """CLI ``skills improve``：无 ``--llm`` 时根据 ``skill-usage.jsonl`` 生成说明。"""
    base = Path(root).expanduser().resolve()
    return _build_usage_note_for_skill(base, str(skill_id or "").strip(), [])


def _build_usage_note_for_skill(root: Path, skill_id: str, goal_hints: list[str]) -> str:
    recent = _read_usage_lines(root, skill_id=skill_id, max_lines=200)
    n = len(recent)
    hints = [g for g in goal_hints if g.strip()]
    uniq_hints = list(dict.fromkeys(hints))[:5]
    bullets = "\n".join(f"- `{h[:200]}`" for h in uniq_hints) if uniq_hints else "- （无关联目标片段）"
    return (
        f"自动记录：最近 **{n}** 条 `skill-usage` 命中。\n\n"
        f"**本会话关联目标片段**\n{bullets}\n"
    )


def run_session_auto_improve(
    *,
    root: str | Path,
    apply: bool = False,
    min_usage_count: int = 1,
    min_days_since_last_improve: int = 0,
) -> dict[str, Any]:
    """For each skill touched in-session, append a usage-driven note (optional apply)."""
    base = Path(root).expanduser().resolve()
    touches = iter_session_skill_touches()
    by_skill: dict[str, list[str]] = {}
    for t in touches:
        sid = str(t.get("skill_id") or "")
        if not sid:
            continue
        by_skill.setdefault(sid, []).append(str(t.get("goal_hint") or ""))
    results: list[dict[str, Any]] = []
    skipped_by_threshold: list[dict[str, Any]] = []
    min_u = max(1, int(min_usage_count))
    min_d = max(0, int(min_days_since_last_improve))
    for sid, hints in by_skill.items():
        ok, reason = should_trigger_auto_improve(
            base,
            sid,
            min_usage_count=min_u,
            min_days_since_last_improve=min_d,
        )
        if not ok:
            skipped_by_threshold.append({"skill_id": sid, "reason": reason})
            continue
        note = _build_usage_note_for_skill(base, sid, hints)
        try:
            results.append(
                improve_skill_append_note(
                    root=base,
                    skill_id=sid,
                    note_md=note,
                    apply=apply,
                ),
            )
        except ValueError as e:
            results.append(
                {
                    "schema_version": "skills_evolution_runtime_v1",
                    "skill_id": sid,
                    "error": str(e),
                    "written": False,
                },
            )
    return {
        "schema_version": "skills_session_auto_improve_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(base),
        "apply": bool(apply),
        "touched_skills": list(by_skill.keys()),
        "results": results,
        "skipped_by_threshold": skipped_by_threshold,
        "policy": {
            "min_usage_count": min_u,
            "min_days_since_last_improve": min_d,
        },
    }


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def maybe_run_session_auto_improve_after_task(*, root: str | Path) -> dict[str, Any] | None:
    if not _truthy_env("CAI_SKILLS_AUTO_IMPROVE"):
        return None
    apply = _truthy_env("CAI_SKILLS_AUTO_IMPROVE_APPLY")
    min_u = 1
    min_d = 0
    if os.getenv("CAI_SKILLS_AUTO_IMPROVE_MIN_USAGE") is not None:
        try:
            min_u = max(1, int(os.environ["CAI_SKILLS_AUTO_IMPROVE_MIN_USAGE"]))
        except ValueError:
            min_u = 1
    if os.getenv("CAI_SKILLS_AUTO_IMPROVE_MIN_DAYS") is not None:
        try:
            min_d = max(0, int(os.environ["CAI_SKILLS_AUTO_IMPROVE_MIN_DAYS"]))
        except ValueError:
            min_d = 0
    try:
        from cai_agent.config import Settings

        st = Settings.from_env(config_path=None, workspace_hint=str(Path(root).resolve()))
        if os.getenv("CAI_SKILLS_AUTO_IMPROVE_MIN_USAGE") is None:
            min_u = max(1, int(getattr(st, "skills_auto_improve_min_usage_count", 1) or 1))
        if os.getenv("CAI_SKILLS_AUTO_IMPROVE_MIN_DAYS") is None:
            min_d = max(0, int(getattr(st, "skills_auto_improve_min_days_since_last_improve", 0) or 0))
    except Exception:
        pass
    return run_session_auto_improve(
        root=root,
        apply=apply,
        min_usage_count=min_u,
        min_days_since_last_improve=min_d,
    )


def improve_skill_with_llm_summary(
    *,
    root: str | Path,
    skill_id: str,
    settings: Any,
    apply: bool = False,
) -> dict[str, Any]:
    """Optional LLM summary of recent usage + append as history (used by CLI --llm)."""
    from cai_agent.llm_factory import chat_completion

    base = Path(root).expanduser().resolve()
    rel = str(skill_id or "").strip().replace("\\", "/").lstrip("/")
    recent = _read_usage_lines(base, skill_id=rel, max_lines=80)
    if not recent:
        raise ValueError("no_usage_for_skill")
    blob = json.dumps(recent[-40:], ensure_ascii=False)[:6000]
    messages = [
        {
            "role": "system",
            "content": "你是技能文档编辑。根据 JSON 使用记录写 3~8 条中文要点，帮助改进技能正文。只输出 Markdown 列表，不要标题。",
        },
        {"role": "user", "content": f"skill_id={rel}\n\n使用记录:\n{blob}"},
    ]
    summary = chat_completion(settings, messages).strip()
    if not summary:
        raise ValueError("llm_empty")
    return improve_skill_append_note(
        root=base,
        skill_id=rel,
        note_md=f"（LLM 摘要）\n\n{summary}",
        apply=apply,
    )


def load_skill_extract_prompt_template() -> str:
    from importlib import resources

    try:
        return resources.files("cai_agent.prompts").joinpath("skill_extract.md").read_text(encoding="utf-8")
    except (OSError, FileNotFoundError, TypeError):
        return ""


def parse_skill_extract_llm_json(text: str) -> dict[str, Any] | None:
    t = (text or "").strip()
    if not t:
        return None
    m = re.search(r"\{[\s\S]*\}\s*$", t)
    if m:
        t = m.group(0)
    try:
        obj = json.loads(t)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    return obj
