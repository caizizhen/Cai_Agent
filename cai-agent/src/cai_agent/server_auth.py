from __future__ import annotations

import os


def resolve_bearer_token(*env_names: str) -> str | None:
    """Return first non-empty token from env names."""
    for name in env_names:
        raw = (os.environ.get(str(name)) or "").strip()
        if raw:
            return raw
    return None


__all__ = ["resolve_bearer_token"]
