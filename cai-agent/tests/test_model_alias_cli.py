"""CLI ``cai-agent model`` non-interactive fallback."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"


def test_model_alias_non_interactive_json(tmp_path: Path) -> None:
    cfg = tmp_path / "cai-agent.toml"
    cfg.write_text(
        '[llm]\nbase_url = "http://127.0.0.1:9/v1"\nmodel = "m"\napi_key = "k"\n',
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_SRC)
    r = subprocess.run(
        [sys.executable, "-m", "cai_agent", "model", "--config", str(cfg)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr
    doc = json.loads(r.stdout)
    assert doc.get("schema_version") == "models_suggest_v1"


def test_models_list_providers_json(tmp_path: Path) -> None:
    cfg = tmp_path / "cai-agent.toml"
    cfg.write_text(
        '[llm]\nbase_url = "http://127.0.0.1:9/v1"\nmodel = "m"\napi_key = "k"\n',
        encoding="utf-8",
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_SRC)
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "cai_agent",
            "models",
            "--config",
            str(cfg),
            "list",
            "--providers",
            "--json",
        ],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr
    doc = json.loads(r.stdout)
    assert doc.get("schema_version") == "provider_registry_v1"
