"""User feedback JSONL (G4 / P0-AS)：``.cai/feedback.jsonl``。"""

from __future__ import annotations

import json
import os
import platform
import re
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


FEEDBACK_REL = ".cai/feedback.jsonl"

_BUG_CATEGORY_SET = frozenset(
    {"crash", "wrong_result", "ux", "docs", "perf", "security", "other"},
)
BUG_REPORT_CATEGORIES: tuple[str, ...] = tuple(sorted(_BUG_CATEGORY_SET))


def feedback_path(cwd: str | Path) -> Path:
    return Path(cwd).expanduser().resolve() / FEEDBACK_REL


def sanitize_feedback_text(text: str, *, max_len: int = 8000) -> str:
    """Best-effort redaction before persisting or posting feedback (tokens, obvious secrets)."""
    s = (text or "")[:max_len]
    s = re.sub(r"(?i)sk-[a-z0-9_-]{10,}", "sk-<redacted>", s)
    s = re.sub(r"(?i)Bearer\s+[A-Za-z0-9._=-]{8,}", "Bearer <redacted>", s)
    s = re.sub(
        r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",
        "eyJ<redacted>",
        s,
    )
    s = re.sub(r"AKIA[0-9A-Z]{16}", "AKIA<redacted>", s)
    s = re.sub(r"(?i)gh[pousr]_[A-Za-z0-9]{30,}", "gh_token_<redacted>", s)
    s = re.sub(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        "<email-redacted>",
        s,
    )
    s = re.sub(
        r"(?i)(api[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret|password)\s*[:=]\s*"
        r"['\"]?[A-Za-z0-9_+/=\-]{12,}['\"]?",
        r"\1=<redacted>",
        s,
    )
    s = re.sub(r"(https?://)[^/\s:@]+:[^/\s@]+@", r"\1<redacted>:<redacted>@", s)
    s = re.sub(r"(?i)([A-Za-z]:\\Users\\)[^\\]+\\", r"\1<user>\\", s)
    s = re.sub(r"/Users/[^/\s]+/", "/Users/<user>/", s)
    return s


def _sanitize_bundle_value(value: Any, *, workspace: Path) -> Any:
    if isinstance(value, str):
        s = value.replace(str(workspace), "<workspace>")
        try:
            s = s.replace(str(workspace).replace("\\", "/"), "<workspace>")
        except Exception:
            pass
        return sanitize_feedback_text(s, max_len=20_000)
    if isinstance(value, list):
        return [_sanitize_bundle_value(v, workspace=workspace) for v in value]
    if isinstance(value, dict):
        return {
            str(k): _sanitize_bundle_value(v, workspace=workspace)
            for k, v in value.items()
        }
    return value


def _append_feedback_row(cwd: str | Path, row: dict[str, Any]) -> dict[str, Any]:
    p = feedback_path(cwd)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    hook = str(os.environ.get("CAI_FEEDBACK_WEBHOOK_URL", "") or "").strip()
    if hook:
        try:
            payload = json.dumps(row, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                hook,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=8.0)  # noqa: S310 — controlled env URL
        except Exception:
            row["webhook_ok"] = False
        else:
            row["webhook_ok"] = True
    return row


def append_feedback(
    cwd: str | Path,
    *,
    text: str,
    source: str = "cli",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "schema_version": "feedback_event_v1",
        "ts": datetime.now(UTC).isoformat(),
        "text": (text or "")[:4000],
        "source": str(source or "cli")[:80],
    }
    if extra:
        row["extra"] = extra
    return _append_feedback_row(cwd, row)


def append_bug_report(
    cwd: str | Path,
    *,
    summary: str,
    detail: str = "",
    repro_steps: list[str] | tuple[str, ...] | None = None,
    expected: str = "",
    actual: str = "",
    attachments: list[str] | tuple[str, ...] | None = None,
    category: str = "other",
    cai_agent_version: str = "",
) -> dict[str, Any]:
    """Structured bug-style report → same JSONL as `append_feedback` (TUI `/bug` CLI 等价)."""
    cat = (category or "other").strip().lower()
    if cat not in _BUG_CATEGORY_SET:
        cat = "other"
    summary_s = sanitize_feedback_text((summary or "").strip())[:800]
    detail_s = sanitize_feedback_text((detail or "").strip())[:3500]
    steps_s = [
        sanitize_feedback_text(str(step).strip())[:1000]
        for step in (repro_steps or ())
        if str(step).strip()
    ][:50]
    expected_s = sanitize_feedback_text((expected or "").strip())[:2000]
    actual_s = sanitize_feedback_text((actual or "").strip())[:2000]
    attachments_s = [
        sanitize_feedback_text(str(item).strip())[:1000]
        for item in (attachments or ())
        if str(item).strip()
    ][:50]
    if not summary_s:
        raise ValueError("bug summary is empty")
    text = f"[bug:{cat}] {summary_s}"[:4000]
    row: dict[str, Any] = {
        "schema_version": "feedback_bug_report_v1",
        "ts": datetime.now(UTC).isoformat(),
        "source": "bug",
        "category": cat,
        "summary": summary_s,
        "detail": detail_s,
        "repro_steps": steps_s,
        "expected": expected_s,
        "actual": actual_s,
        "attachments": attachments_s,
        "text": text,
        "redaction": "sanitize_feedback_text_v1",
        "cai_agent_version": (cai_agent_version or "")[:48],
    }
    return _append_feedback_row(cwd, row)


def list_feedback(cwd: str | Path, *, limit: int = 50) -> list[dict[str, Any]]:
    p = feedback_path(cwd)
    if not p.is_file():
        return []
    lim = max(1, min(500, int(limit)))
    lines = p.read_text(encoding="utf-8").splitlines()[-lim:]
    out: list[dict[str, Any]] = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            o = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if isinstance(o, dict):
            out.append(o)
    return out


def feedback_stats(cwd: str | Path) -> dict[str, Any]:
    rows = list_feedback(cwd, limit=10_000)
    latest_ts = None
    sources: dict[str, int] = {}
    for row in rows:
        ts = str(row.get("ts") or "").strip() or None
        if ts and (latest_ts is None or ts > latest_ts):
            latest_ts = ts
        source = str(row.get("source") or "unknown").strip() or "unknown"
        sources[source] = sources.get(source, 0) + 1
    return {
        "schema_version": "feedback_stats_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(Path(cwd).expanduser().resolve()),
        "total": len(rows),
        "latest_ts": latest_ts,
        "sources": sources,
    }


def export_feedback_jsonl(
    cwd: str | Path,
    *,
    dest: str | Path,
    limit: int | None = None,
) -> dict[str, Any]:
    """Copy recent feedback rows to a standalone JSONL file (``feedback_export_v1``)."""
    lim = 50_000 if limit is None else max(1, min(200_000, int(limit)))
    rows = list_feedback(cwd, limit=lim)
    dest_p = Path(dest).expanduser().resolve()
    dest_p.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else "")
    dest_p.write_text(body, encoding="utf-8")
    return {
        "schema_version": "feedback_export_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(Path(cwd).expanduser().resolve()),
        "dest": str(dest_p),
        "rows": len(rows),
    }


def build_feedback_bundle_payload(
    cwd: str | Path,
    *,
    settings: Any,
    limit: int | None = None,
    include_repair_plan: bool = True,
) -> dict[str, Any]:
    """Build a redacted support bundle for local issue triage."""
    root = Path(cwd).expanduser().resolve()
    lim = 200 if limit is None else max(1, min(2000, int(limit)))
    rows = list_feedback(root, limit=lim)
    from cai_agent import __version__
    from cai_agent.doctor import build_api_doctor_summary_v1, build_repair_plan

    doctor_summary = build_api_doctor_summary_v1(settings)
    repair_plan = build_repair_plan(settings) if include_repair_plan else None
    payload: dict[str, Any] = {
        "schema_version": "feedback_bundle_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "cai_agent_version": __version__,
        "workspace": "<workspace>",
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
        },
        "redaction": {
            "strategy": "sanitize_feedback_text_v1",
            "workspace": "<workspace>",
            "notes": [
                "feedback text is redacted for common tokens and emails",
                "workspace absolute path is replaced with <workspace>",
            ],
        },
        "feedback": {
            "path": ".cai/feedback.jsonl",
            "rows": len(rows),
            "items": rows,
        },
        "doctor_summary": doctor_summary,
        "repair_plan": repair_plan,
        "triage": {
            "recommended_flow": [
                "cai-agent doctor --json",
                "cai-agent repair --dry-run --json",
                "cai-agent feedback bug <summary> --detail <steps> --json",
                "cai-agent feedback bundle --dest dist/feedback-bundle.json --json",
            ],
        },
    }
    return _sanitize_bundle_value(payload, workspace=root)


def export_feedback_bundle_json(
    cwd: str | Path,
    *,
    settings: Any,
    dest: str | Path,
    limit: int | None = None,
) -> dict[str, Any]:
    root = Path(cwd).expanduser().resolve()
    dest_p = Path(dest).expanduser().resolve()
    bundle = build_feedback_bundle_payload(root, settings=settings, limit=limit)
    dest_p.parent.mkdir(parents=True, exist_ok=True)
    dest_p.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "schema_version": "feedback_bundle_export_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(root),
        "dest": str(dest_p),
        "bundle_schema_version": bundle.get("schema_version"),
        "rows": int((bundle.get("feedback") or {}).get("rows") or 0),
        "redaction": bundle.get("redaction"),
    }
