from __future__ import annotations

import tempfile
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

from cai_agent.config import Settings
from cai_agent.runtime.docker import DockerRuntime, _docker_error_kind
from cai_agent.runtime.registry import get_runtime_backend


def test_docker_error_kind_mapping() -> None:
    assert _docker_error_kind(0) is None
    assert _docker_error_kind(125) == "docker_daemon_error"
    assert _docker_error_kind(127) == "docker_exec_not_found"


def test_docker_exec_keeps_exec_options_but_not_run_limits() -> None:
    rt = DockerRuntime(
        container="c1",
        exec_options=("--user", "1000"),
        cpus="2",
        memory="512m",
    )
    mock_run = MagicMock(return_value=MagicMock(stdout="ok", stderr="", returncode=0))
    with patch("cai_agent.runtime.docker.subprocess.run", mock_run):
        r = rt.exec(["echo", "hi"], cwd="/w", timeout_sec=9.0)
    assert r.returncode == 0
    assert "ok" in r.stdout
    argv = mock_run.call_args[0][0]
    assert argv[:2] == ["docker", "exec"]
    assert "--cpus" not in argv
    assert "--memory" not in argv
    assert "--user" in argv
    assert "-w" in argv and "/w" in argv and "c1" in argv and "sh" in argv and "-lc" in argv


def test_docker_run_mode_uses_image_volume_and_limits() -> None:
    rt = DockerRuntime(
        image="python:3.13-slim",
        workdir="/workspace",
        volume_mounts=("/host:/workspace:rw",),
        cpus="1",
        memory="1g",
    )
    mock_run = MagicMock(return_value=MagicMock(stdout="ok", stderr="", returncode=0))
    with patch("cai_agent.runtime.docker.subprocess.run", mock_run):
        r = rt.exec(["python", "-V"], cwd="/ignored", timeout_sec=9.0)
    assert r.returncode == 0
    argv = mock_run.call_args[0][0]
    assert argv[:3] == ["docker", "run", "--rm"]
    assert "--cpus" in argv and "1" in argv
    assert "--memory" in argv and "1g" in argv
    assert "-v" in argv and "/host:/workspace:rw" in argv
    assert "-w" in argv and "/workspace" in argv
    assert "python:3.13-slim" in argv


def test_docker_describe_reports_productization_fields() -> None:
    rt = DockerRuntime(
        image="img",
        workdir="/w",
        volume_mounts=("a:b", "c:d:ro"),
        cpus="2",
        memory="512m",
    )
    with patch("cai_agent.runtime.docker.shutil.which", return_value="docker"):
        d = rt.describe()
    assert d["mode"] == "run"
    assert d["image"] == "img"
    assert d["workdir"] == "/w"
    assert d["volume_mounts_count"] == 2
    assert d["cpus"] == "2"
    assert d["memory"] == "512m"


def test_runtime_docker_settings_parse_image_and_volumes() -> None:
    root = Path(tempfile.mkdtemp()).resolve()
    toml = textwrap.dedent(
        f"""
        [llm]
        base_url = "http://localhost:1/v1"
        model = "m"
        api_key = "k"
        [agent]
        workspace = "{root.as_posix()}"
        [runtime]
        backend = "docker"
        [runtime.docker]
        image = "python:3.13-slim"
        workdir = "/workspace"
        volume_mounts = ["{root.as_posix()}:/workspace:rw"]
        cpus = "1"
        memory = "1g"
        """,
    )
    with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False, encoding="utf-8") as f:
        f.write(toml)
        cfg = f.name
    try:
        settings = Settings.from_env(config_path=cfg)
        rt = get_runtime_backend("docker", settings=settings)
        desc = rt.describe()
        assert desc["mode"] == "run"
        assert desc["image"] == "python:3.13-slim"
        assert desc["volume_mounts_count"] == 1
    finally:
        import os

        os.unlink(cfg)
