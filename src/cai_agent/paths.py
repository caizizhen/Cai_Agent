from __future__ import annotations

import os
from pathlib import Path


def cai_home() -> Path:
    return Path(os.getenv("CAI_HOME", Path.home() / ".cai")).expanduser()


def sessions_root() -> Path:
    return cai_home() / "sessions"


def plugins_root() -> Path:
    return cai_home() / "plugins"
