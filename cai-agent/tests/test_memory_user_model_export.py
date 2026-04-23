"""``memory user-model export`` → ``user_model_bundle_v1``（RFC 首包切片）。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"


def test_user_model_export_cli_schema(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_SRC)
    p = subprocess.run(
        [
            sys.executable,
            "-m",
            "cai_agent",
            "memory",
            "user-model",
            "export",
            "--days",
            "3",
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert p.returncode == 0, p.stderr
    bundle = json.loads((p.stdout or "").strip())
    assert bundle.get("schema_version") == "user_model_bundle_v1"
    assert bundle.get("bundle_kind") == "behavior_overview"
    assert isinstance(bundle.get("exported_at"), str)
    ov = bundle.get("overview")
    assert isinstance(ov, dict)
    assert ov.get("schema_version") == "memory_user_model_v1"
