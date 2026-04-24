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


def test_release_changelog_semantic_report_from_repo_root() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_SRC)
    r = subprocess.run(
        [sys.executable, "-m", "cai_agent", "release-changelog", "--json", "--semantic"],
        cwd=str(_REPO),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr
    doc = json.loads(r.stdout)
    assert doc.get("schema_version") == "release_changelog_report_v1"
    assert doc.get("ok") is True
    bilingual = doc.get("bilingual") or {}
    semantic = doc.get("semantic") or {}
    runbook = doc.get("runbook") or {}
    assert bilingual.get("schema_version") == "changelog_bilingual_check_v1"
    assert semantic.get("schema_version") == "changelog_semantic_v1"
    assert runbook.get("schema_version") == "release_runbook_v1"
    assert isinstance(runbook.get("runbook_steps"), list)
