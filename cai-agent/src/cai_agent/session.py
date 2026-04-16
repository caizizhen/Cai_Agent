from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def save_session(path: str, payload: dict[str, Any]) -> None:
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_session(path: str) -> dict[str, Any]:
    p = Path(path).expanduser().resolve()
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("会话文件根对象必须是 JSON object")
    return data


def list_session_files(
    *,
    cwd: str | None = None,
    pattern: str = ".cai-session*.json",
    limit: int = 50,
) -> list[Path]:
    base = Path(cwd or ".").expanduser().resolve()
    files = [p for p in base.glob(pattern) if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[: max(limit, 1)]


def aggregate_sessions(
    *,
    cwd: str | None = None,
    pattern: str = ".cai-session*.json",
    limit: int = 100,
) -> dict[str, Any]:
    files = list_session_files(cwd=cwd, pattern=pattern, limit=limit)
    sessions_count = 0
    total_elapsed = 0
    total_tokens = 0
    failed_count = 0
    for p in files:
        try:
            s = load_session(str(p))
        except Exception:
            continue
        sessions_count += 1
        elapsed = s.get("elapsed_ms")
        if isinstance(elapsed, int):
            total_elapsed += elapsed
        tt = s.get("total_tokens")
        if isinstance(tt, int):
            total_tokens += tt
        if bool(s.get("error_count", 0)):
            failed_count += 1
    return {
        "sessions_count": sessions_count,
        "elapsed_ms_total": total_elapsed,
        "total_tokens": total_tokens,
        "failed_count": failed_count,
        "failure_rate": (float(failed_count) / sessions_count) if sessions_count else 0.0,
    }
