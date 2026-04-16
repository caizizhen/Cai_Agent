from __future__ import annotations

import shutil
from pathlib import Path

from cai_agent.config import Settings


def _project_root(settings: Settings) -> Path:
    if settings.config_loaded_from:
        return Path(settings.config_loaded_from).expanduser().resolve().parent
    return Path.cwd().resolve()


def export_target(settings: Settings, target: str) -> dict[str, object]:
    root = _project_root(settings)
    t = target.strip().lower()
    if t not in {"cursor", "codex", "opencode"}:
        raise ValueError(f"unsupported target: {target}")
    out_dir = root / f".{t}"
    out_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for name in ("rules", "skills", "agents", "commands"):
        src = root / name
        if not src.exists():
            continue
        dst = out_dir / name
        if dst.exists():
            if dst.is_dir():
                shutil.rmtree(dst)
            else:
                dst.unlink()
        if src.is_dir():
            shutil.copytree(src, dst)
            copied.append(name)
    return {
        "target": t,
        "output_dir": str(out_dir),
        "copied": copied,
    }
