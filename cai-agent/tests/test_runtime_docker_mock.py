from __future__ import annotations

from unittest.mock import MagicMock, patch

from cai_agent.runtime.docker import DockerRuntime, _docker_error_kind


def test_docker_error_kind_mapping() -> None:
    assert _docker_error_kind(0) is None
    assert _docker_error_kind(125) == "docker_daemon_error"
    assert _docker_error_kind(127) == "docker_exec_not_found"


def test_docker_exec_injects_resource_flags() -> None:
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
    assert "--cpus" in argv and "2" in argv
    assert "--memory" in argv and "512m" in argv
    assert "--user" in argv
    assert "-w" in argv and "/w" in argv and "c1" in argv and "sh" in argv and "-lc" in argv
