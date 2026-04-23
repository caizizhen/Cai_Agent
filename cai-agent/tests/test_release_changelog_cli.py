from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
_REPO = Path(__file__).resolve().parents[2]


def test_release_changelog_from_repo_root() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_SRC)
    r = subprocess.run(
        [sys.executable, "-m", "cai_agent", "release-changelog", "--json"],
        cwd=str(_REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr
    doc = json.loads(r.stdout)
    assert doc.get("schema_version") == "changelog_bilingual_check_v1"
    assert doc.get("ok") is True
