from __future__ import annotations

import sys
from pathlib import Path

from cai_agent.runtime.local import LocalRuntime
from cai_agent.runtime.registry import get_runtime_backend, list_runtimes_payload


def test_local_runtime_echo(tmp_path: Path) -> None:
    rt = LocalRuntime()
    cmd = [sys.executable, "-c", "print('ok')"]
    res = rt.exec(cmd, cwd=str(tmp_path), timeout_sec=10.0)
    assert res.returncode == 0
    assert "ok" in res.stdout


def test_registry_list_schema() -> None:
    doc = list_runtimes_payload()
    assert doc["schema_version"] == "runtime_registry_v1"
    assert "local" in doc["backends"]


def test_get_runtime_backend_defaults() -> None:
    b = get_runtime_backend("local", settings=None)
    assert b.name == "local"
