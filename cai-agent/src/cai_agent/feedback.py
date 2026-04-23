"""User feedback JSONL (G4 / P0-AS)：``.cai/feedback.jsonl``。"""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


FEEDBACK_REL = ".cai/feedback.jsonl"


def feedback_path(cwd: str | Path) -> Path:
    return Path(cwd).expanduser().resolve() / FEEDBACK_REL


def append_feedback(
    cwd: str | Path,
    *,
    text: str,
    source: str = "cli",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    p = feedback_path(cwd)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "schema_version": "feedback_event_v1",
        "ts": datetime.now(UTC).isoformat(),
        "text": (text or "")[:4000],
        "source": str(source or "cli")[:80],
    }
    if extra:
        row["extra"] = extra
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
    return {
        "schema_version": "feedback_stats_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "workspace": str(Path(cwd).expanduser().resolve()),
        "total": len(rows),
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
