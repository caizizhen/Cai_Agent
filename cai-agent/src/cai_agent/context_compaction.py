from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from cai_agent.llm import estimate_tokens_from_messages


_PATH_RE = re.compile(
    r"(?:(?:[A-Za-z]:)?[./\\])?[\w.-]+(?:[/\\][\w.-]+)+",
)


@dataclass(frozen=True)
class ContextCompactionResult:
    messages: list[dict[str, Any]]
    compacted: bool
    original_message_count: int
    compacted_message_count: int
    original_estimated_tokens: int
    compacted_estimated_tokens: int
    summary_message: dict[str, Any] | None


@dataclass(frozen=True)
class ContextCompactionEvalResult:
    payload: dict[str, Any]


@dataclass(frozen=True)
class ContextCompactionRetentionResult:
    payload: dict[str, Any]

    @property
    def passed(self) -> bool:
        return bool(self.payload.get("passed"))

    @property
    def reason(self) -> str:
        reasons = self.payload.get("failed_reasons")
        if isinstance(reasons, list) and reasons:
            return ",".join(str(x) for x in reasons if str(x).strip())
        return "retention_check_failed"


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    if content is None:
        return ""
    return str(content)


def _truncate(text: str, limit: int) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 16)].rstrip() + " ...[truncated]"


def _retention_probe(text: str, limit: int = 80) -> str:
    return " ".join(str(text or "").split())[: max(1, int(limit))].strip()


def _extract_lines(text: str, *, limit: int = 6) -> list[str]:
    out: list[str] = []
    for line in str(text or "").replace("\\n", "\n").replace("\\r", "\n").splitlines():
        clean = line.strip()
        if not clean:
            continue
        out.append(_truncate(clean, 220))
        if len(out) >= limit:
            break
    return out


def _classify_tool_result(tool: str, result: str) -> dict[str, Any]:
    low_tool = tool.lower()
    low = result.lower()
    lines = _extract_lines(result, limit=8)
    paths = _extract_paths(result, limit=12)
    meta: dict[str, Any] = {}
    if paths:
        meta["paths"] = paths

    if "traceback" in low or "exception" in low:
        meta["tool_kind"] = "traceback"
        failure_lines = [
            line for line in lines if "traceback" in line.lower() or "error" in line.lower() or "exception" in line.lower()
        ]
        meta["failure_summary"] = failure_lines[-3:] if failure_lines else lines[-3:]
        return meta

    if "pytest" in low or "failed" in low or " passed" in low or " error" in low:
        meta["tool_kind"] = "test"
        failure_lines = [
            line
            for line in lines
            if "failed" in line.lower()
            or "error" in line.lower()
            or "traceback" in line.lower()
            or line.startswith("E ")
            or line.startswith("FAILED ")
        ]
        meta["failure_summary"] = failure_lines[:6] if failure_lines else lines[:6]
        return meta

    if "diff --git" in result or "\n+++" in result or "\n---" in result or low_tool in {"git_diff", "diff"}:
        added = sum(1 for line in result.splitlines() if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in result.splitlines() if line.startswith("-") and not line.startswith("---"))
        meta["tool_kind"] = "git_diff"
        meta["diff_stats"] = {"added_lines": added, "removed_lines": removed}
        meta["evidence"] = [line for line in lines if line.startswith("diff --git") or line.startswith("@@")][:6]
        return meta

    if "search" in low_tool or any(":" in line and _PATH_RE.search(line) for line in lines):
        meta["tool_kind"] = "search"
        meta["evidence"] = lines[:8]
        return meta

    if "read" in low_tool or "file" in low_tool:
        meta["tool_kind"] = "read"
        meta["evidence"] = lines[:6]
        return meta

    if "run" in low_tool or "command" in low_tool or "shell" in low_tool:
        meta["tool_kind"] = "command"
        meta["evidence"] = lines[:6]
        return meta

    meta["tool_kind"] = "generic"
    meta["evidence"] = lines[:4]
    return meta


def _tool_row(raw: str, *, limit: int) -> dict[str, Any] | None:
    try:
        obj = json.loads(raw)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    tool = obj.get("tool")
    if not isinstance(tool, str) or not tool.strip():
        return None
    result = _content_text(obj.get("result"))
    low = result.lower()
    is_error = (
        "工具执行失败" in result
        or "error" in low
        or "exception" in low
        or "traceback" in low
    )
    row = {
        "tool": tool.strip(),
        "error": bool(is_error),
        "result_preview": _truncate(result, limit),
    }
    row.update(_classify_tool_result(tool.strip(), result))
    return row


def _extract_paths(text: str, *, limit: int = 24) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    scan = str(text or "").replace("\\n", "\n").replace("\\r", "\n")
    for match in _PATH_RE.finditer(scan):
        val = match.group(0).strip(" .,;:()[]{}\"'")
        if not val or val in seen:
            continue
        seen.add(val)
        out.append(val)
        if len(out) >= limit:
            break
    return out


def _extract_tool_names(messages: list[dict[str, Any]], *, limit: int = 24) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        tool = _tool_row(_content_text(msg.get("content")), limit=80)
        if tool is None:
            continue
        name = str(tool.get("tool") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
        if len(out) >= limit:
            break
    return out


def _parse_context_summary_payload(content: Any) -> dict[str, Any] | None:
    text = _content_text(content).strip()
    if not text.startswith("[context_summary_v1]"):
        return None
    raw = text[len("[context_summary_v1]") :].strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("schema_version") != "context_compaction_summary_v1":
        return None
    return payload


def _append_unique(out: list[Any], items: Any, *, key: str | None = None, limit: int = 100) -> None:
    if not isinstance(items, list):
        return
    seen: set[str] = set()
    for existing in out:
        if key and isinstance(existing, dict):
            marker = str(existing.get(key) or "").strip()
        else:
            marker = json.dumps(existing, ensure_ascii=False, sort_keys=True)
        if marker:
            seen.add(marker)
    for item in items:
        if key and isinstance(item, dict):
            marker = str(item.get(key) or "").strip()
        else:
            marker = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if not marker or marker in seen:
            continue
        out.append(item)
        seen.add(marker)
        if len(out) >= limit:
            break


def evaluate_compaction_retention(
    source_messages: list[dict[str, Any]],
    compacted_messages: list[dict[str, Any]],
    *,
    keep_tail_messages: int = 8,
    required_markers: list[str] | tuple[str, ...] = (),
    min_path_retention_ratio: float = 0.80,
    min_tool_retention_ratio: float = 0.80,
) -> ContextCompactionRetentionResult:
    """Check whether a candidate compacted context retained critical evidence."""
    original = [dict(m) for m in source_messages if isinstance(m, dict)]
    compacted = [dict(m) for m in compacted_messages if isinstance(m, dict)]
    compacted_text = "\n".join(_content_text(m.get("content")) for m in compacted)
    source_text = "\n".join(_content_text(m.get("content")) for m in original)

    paths = _extract_paths(source_text)
    tools = _extract_tool_names(original)
    markers = [str(x).strip() for x in required_markers if str(x).strip()]

    marker_hits = [
        {"marker": marker, "retained": marker in compacted_text}
        for marker in markers
    ]
    path_hits = [
        {"path": path, "retained": path in compacted_text}
        for path in paths
    ]
    tool_hits = [
        {"tool": tool, "retained": tool in compacted_text}
        for tool in tools
    ]

    first_user = next((m for m in original if m.get("role") == "user"), None)
    first_user_text = _retention_probe(_content_text(first_user.get("content") if first_user else ""), 80)
    initial_goal_retained = bool(first_user_text) and first_user_text in compacted_text

    tail = original[-max(1, int(keep_tail_messages)) :]
    tail_texts = [
        _retention_probe(_content_text(m.get("content")), 80)
        for m in tail
        if _retention_probe(_content_text(m.get("content")), 80)
    ]
    tail_retained_count = sum(1 for text in tail_texts if text in compacted_text)
    tail_retention_ratio = float(tail_retained_count) / len(tail_texts) if tail_texts else 1.0

    def _ratio(rows: list[dict[str, Any]]) -> float:
        if not rows:
            return 1.0
        return float(sum(1 for row in rows if bool(row.get("retained")))) / len(rows)

    path_retention_ratio = _ratio(path_hits)
    tool_retention_ratio = _ratio(tool_hits)
    marker_retention_ratio = _ratio(marker_hits)

    checks = {
        "initial_goal_retained": initial_goal_retained,
        "tail_retained": tail_retention_ratio >= 1.0,
        "paths_retained": path_retention_ratio >= float(min_path_retention_ratio),
        "tools_retained": tool_retention_ratio >= float(min_tool_retention_ratio),
        "markers_retained": marker_retention_ratio >= 1.0,
    }
    failed_reasons = [name for name, ok in checks.items() if not bool(ok)]
    payload = {
        "schema_version": "context_compaction_retention_v1",
        "passed": not failed_reasons,
        "failed_reasons": failed_reasons,
        "checks": checks,
        "retention": {
            "initial_goal_retained": initial_goal_retained,
            "tail_retention_ratio": round(float(tail_retention_ratio), 4),
            "path_retention_ratio": round(float(path_retention_ratio), 4),
            "tool_retention_ratio": round(float(tool_retention_ratio), 4),
            "marker_retention_ratio": round(float(marker_retention_ratio), 4),
            "paths": path_hits,
            "tools": tool_hits,
            "markers": marker_hits,
        },
    }
    return ContextCompactionRetentionResult(payload=payload)


def _build_summary_payload(
    messages: list[dict[str, Any]],
    *,
    summary_max_chars: int,
) -> dict[str, Any]:
    role_counts: dict[str, int] = {}
    tool_calls: list[dict[str, Any]] = []
    notes: list[dict[str, str]] = []
    all_text: list[str] = []
    prior_summaries: list[dict[str, Any]] = []
    prior_source_message_count = 0
    note_budget = max(120, min(500, summary_max_chars // 10))
    tool_budget = max(120, min(700, summary_max_chars // 8))

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "unknown")
        role_counts[role] = role_counts.get(role, 0) + 1
        text = _content_text(msg.get("content"))
        prior = _parse_context_summary_payload(text)
        if prior is not None:
            prior_summaries.append(prior)
            try:
                prior_source_message_count += int(prior.get("source_message_count") or 0)
            except Exception:
                pass
            for key, value in (prior.get("role_counts") or {}).items():
                try:
                    role_counts[str(key)] = role_counts.get(str(key), 0) + int(value)
                except Exception:
                    continue
            continue
        if text:
            all_text.append(text)
        tool = _tool_row(text, limit=tool_budget)
        if tool is not None:
            tool_calls.append(tool)
            continue
        if role == "system":
            continue
        preview = _truncate(text, note_budget)
        if preview:
            notes.append({"role": role, "preview": preview})

    errors = [row for row in tool_calls if row.get("error")]
    important_paths = _extract_paths("\n".join(all_text))
    for prior in prior_summaries:
        _append_unique(important_paths, prior.get("important_paths"), limit=24)
        _append_unique(important_paths, prior.get("files_touched"), limit=24)
        _append_unique(tool_calls, prior.get("tool_calls"), key="tool", limit=20)
        _append_unique(notes, prior.get("conversation_notes"), key="preview", limit=24)
        for key in ("goal", "last_user_intent"):
            value = prior.get(key)
            if isinstance(value, str) and value.strip():
                notes.append({"role": "summary", "preview": _truncate(value, note_budget)})
        for key in ("decisions", "facts", "tool_evidence", "open_todos", "risks"):
            vals = prior.get(key)
            if isinstance(vals, list):
                for value in vals:
                    if isinstance(value, str) and value.strip():
                        notes.append({"role": f"summary.{key}", "preview": _truncate(value, note_budget)})
                        if len(notes) >= 24:
                            break
            if len(notes) >= 24:
                break
    errors = [row for row in tool_calls if row.get("error")]
    payload = {
        "schema_version": "context_compaction_summary_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_message_count": len(messages) + prior_source_message_count,
        "role_counts": role_counts,
        "tool_calls_count": len(tool_calls),
        "tool_errors_count": len(errors),
        "tool_calls": tool_calls[:20],
        "important_paths": important_paths[:24],
        "conversation_notes": notes[:24],
    }
    if prior_summaries:
        payload["merged_summary_count"] = len(prior_summaries)
        payload["merged_source_message_count"] = prior_source_message_count
    def _payload_len() -> int:
        return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))

    raw_len = _payload_len()
    if raw_len <= summary_max_chars:
        return payload
    keep_notes = max(4, len(notes) // 2)
    keep_tools = max(4, len(tool_calls) // 2)
    payload["conversation_notes"] = notes[:keep_notes]
    payload["tool_calls"] = tool_calls[:keep_tools]
    payload["truncated"] = True
    for row in payload["conversation_notes"]:
        if isinstance(row, dict) and isinstance(row.get("preview"), str):
            row["preview"] = _truncate(row["preview"], 180)
    for row in payload["tool_calls"]:
        if isinstance(row, dict) and isinstance(row.get("result_preview"), str):
            row["result_preview"] = _truncate(row["result_preview"], 220)
    payload["important_paths"] = payload["important_paths"][:12]
    raw_len = _payload_len()
    while raw_len > summary_max_chars and len(payload["conversation_notes"]) > 4:
        payload["conversation_notes"] = payload["conversation_notes"][:-1]
        raw_len = _payload_len()
    while raw_len > summary_max_chars and len(payload["tool_calls"]) > 4:
        payload["tool_calls"] = payload["tool_calls"][:-1]
        raw_len = _payload_len()
    if raw_len > summary_max_chars:
        payload["conversation_notes"] = payload["conversation_notes"][:2]
        payload["tool_calls"] = payload["tool_calls"][:2]
        payload["important_paths"] = payload["important_paths"][:6]
    return payload


def build_llm_compaction_prompt(
    messages: list[dict[str, Any]],
    *,
    max_source_chars: int = 12000,
) -> list[dict[str, str]]:
    """Build a bounded summarizer prompt that returns context_summary JSON."""
    chunks: list[str] = []
    used = 0
    cap = max(2000, int(max_source_chars))
    for idx, msg in enumerate(messages):
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "unknown")
        text = _truncate(_content_text(msg.get("content")), 1200)
        block = f"### message {idx} role={role}\n{text}\n"
        if used + len(block) > cap:
            remain = cap - used
            if remain > 200:
                chunks.append(block[:remain] + "\n...[source truncated]")
            break
        chunks.append(block)
        used += len(block)
    return [
        {
            "role": "system",
            "content": (
                "You summarize older agent conversation history for future context compaction. "
                "Return only one JSON object. Do not use markdown."
            ),
        },
        {
            "role": "user",
            "content": (
                "Summarize the source messages into this JSON shape: "
                '{"goal": string|null, "decisions": string[], "facts": string[], '
                '"files_touched": string[], "tool_evidence": string[], '
                '"open_todos": string[], "risks": string[], "last_user_intent": string|null}. '
                "Keep it concise, factual, and preserve paths, commands, errors, and current next steps.\n\n"
                + "\n".join(chunks)
            ),
        },
    ]


def compact_messages(
    messages: list[dict[str, Any]],
    *,
    keep_tail_messages: int = 8,
    summary_max_chars: int = 6000,
    summary_payload: dict[str, Any] | None = None,
    summary_source: str = "heuristic",
    fallback_reason: str | None = None,
) -> ContextCompactionResult:
    """Replace older conversation history with one deterministic summary.

    The first system block and the initial user goal are preserved. The most
    recent tail remains verbatim so the active tool/result context is not lost.
    """
    original = [dict(m) for m in messages if isinstance(m, dict)]
    original_tokens = estimate_tokens_from_messages(original)
    if len(original) < 4:
        return ContextCompactionResult(
            messages=original,
            compacted=False,
            original_message_count=len(original),
            compacted_message_count=len(original),
            original_estimated_tokens=original_tokens,
            compacted_estimated_tokens=original_tokens,
            summary_message=None,
        )

    keep_tail = max(1, int(keep_tail_messages))
    summary_limit = max(1000, int(summary_max_chars))

    prefix_end = 0
    while prefix_end < len(original) and original[prefix_end].get("role") == "system":
        prefix_end += 1
    first_user_idx = next(
        (
            idx
            for idx in range(prefix_end, len(original))
            if original[idx].get("role") == "user"
        ),
        None,
    )
    prefix_indices = set(range(prefix_end))
    if first_user_idx is not None:
        prefix_indices.add(first_user_idx)

    tail_start = max(0, len(original) - keep_tail)
    tail_indices = set(range(tail_start, len(original)))
    compress_indices = [
        idx
        for idx in range(len(original))
        if idx not in prefix_indices and idx not in tail_indices
    ]
    if not compress_indices:
        return ContextCompactionResult(
            messages=original,
            compacted=False,
            original_message_count=len(original),
            compacted_message_count=len(original),
            original_estimated_tokens=original_tokens,
            compacted_estimated_tokens=original_tokens,
            summary_message=None,
        )

    compressed_source = [original[idx] for idx in compress_indices]
    if isinstance(summary_payload, dict) and summary_payload:
        payload = dict(summary_payload)
        payload.setdefault("schema_version", "context_compaction_summary_v1")
        payload.setdefault("generated_at", datetime.now(UTC).isoformat())
        payload.setdefault("source_message_count", len(compressed_source))
        payload["summary_source"] = str(summary_source or "llm")
    else:
        payload = _build_summary_payload(
            compressed_source,
            summary_max_chars=summary_limit,
        )
        payload["summary_source"] = str(summary_source or "heuristic")
    if fallback_reason:
        payload["fallback_reason"] = str(fallback_reason)
    summary_message = {
        "role": "user",
        "content": "[context_summary_v1]\n"
        + json.dumps(payload, ensure_ascii=False, indent=2),
    }

    compacted: list[dict[str, Any]] = []
    for idx, msg in enumerate(original):
        if idx in prefix_indices:
            compacted.append(msg)
    compacted.append(summary_message)
    for idx in range(tail_start, len(original)):
        if idx not in prefix_indices:
            compacted.append(original[idx])

    compacted_tokens = estimate_tokens_from_messages(compacted)
    return ContextCompactionResult(
        messages=compacted,
        compacted=True,
        original_message_count=len(original),
        compacted_message_count=len(compacted),
        original_estimated_tokens=original_tokens,
        compacted_estimated_tokens=compacted_tokens,
        summary_message=summary_message,
    )


def evaluate_compaction_quality(
    messages: list[dict[str, Any]],
    *,
    keep_tail_messages: int = 8,
    summary_max_chars: int = 6000,
    required_markers: list[str] | tuple[str, ...] = (),
    min_token_reduction_ratio: float = 0.20,
    min_score: float = 0.80,
) -> ContextCompactionEvalResult:
    """Evaluate deterministic compaction quality for regression checks."""
    original = [dict(m) for m in messages if isinstance(m, dict)]
    comp = compact_messages(
        original,
        keep_tail_messages=keep_tail_messages,
        summary_max_chars=summary_max_chars,
    )
    retention_payload = evaluate_compaction_retention(
        original,
        comp.messages,
        keep_tail_messages=keep_tail_messages,
        required_markers=required_markers,
    ).payload
    retention = retention_payload.get("retention") or {}
    retention_checks = retention_payload.get("checks") or {}
    initial_goal_retained = bool(retention.get("initial_goal_retained"))
    tail_retention_ratio = float(retention.get("tail_retention_ratio") or 0.0)
    path_retention_ratio = float(retention.get("path_retention_ratio") or 0.0)
    tool_retention_ratio = float(retention.get("tool_retention_ratio") or 0.0)
    marker_retention_ratio = float(retention.get("marker_retention_ratio") or 0.0)
    token_reduction_ratio = 0.0
    if comp.original_estimated_tokens > 0:
        token_reduction_ratio = max(
            0.0,
            float(comp.original_estimated_tokens - comp.compacted_estimated_tokens)
            / float(comp.original_estimated_tokens),
        )

    checks = {
        "compacted": bool(comp.compacted),
        "token_reduction": token_reduction_ratio >= float(min_token_reduction_ratio),
        "initial_goal_retained": bool(retention_checks.get("initial_goal_retained")),
        "tail_retained": bool(retention_checks.get("tail_retained")),
        "paths_retained": bool(retention_checks.get("paths_retained")),
        "tools_retained": bool(retention_checks.get("tools_retained")),
        "markers_retained": bool(retention_checks.get("markers_retained")),
    }
    score_parts = [
        1.0 if checks["compacted"] else 0.0,
        min(1.0, token_reduction_ratio / max(0.01, float(min_token_reduction_ratio))),
        1.0 if initial_goal_retained else 0.0,
        tail_retention_ratio,
        path_retention_ratio,
        tool_retention_ratio,
        marker_retention_ratio,
    ]
    score = sum(score_parts) / len(score_parts)
    passed = score >= float(min_score) and all(bool(v) for v in checks.values())
    payload = {
        "schema_version": "context_compaction_eval_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "passed": bool(passed),
        "score": round(float(score), 4),
        "min_score": float(min_score),
        "checks": checks,
        "message_counts": {
            "original": comp.original_message_count,
            "compacted": comp.compacted_message_count,
        },
        "estimated_tokens": {
            "original": comp.original_estimated_tokens,
            "compacted": comp.compacted_estimated_tokens,
            "reduction_ratio": round(float(token_reduction_ratio), 4),
            "min_reduction_ratio": float(min_token_reduction_ratio),
        },
        "retention": {
            "initial_goal_retained": initial_goal_retained,
            "tail_retention_ratio": round(float(tail_retention_ratio), 4),
            "path_retention_ratio": round(float(path_retention_ratio), 4),
            "tool_retention_ratio": round(float(tool_retention_ratio), 4),
            "marker_retention_ratio": round(float(marker_retention_ratio), 4),
            "paths": retention.get("paths") or [],
            "tools": retention.get("tools") or [],
            "markers": retention.get("markers") or [],
        },
    }
    return ContextCompactionEvalResult(payload=payload)
