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
