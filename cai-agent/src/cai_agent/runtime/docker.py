"""Docker backend: ``docker exec`` (H1-RT-02 MVP + P0-RT hardening)."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Mapping, Sequence

from cai_agent.runtime.base import ExecResult, RuntimeBackend


def _docker_error_kind(rc: int) -> str | None:
    if rc == 0:
        return None
    if rc == 125:
        return "docker_daemon_error"
    if rc == 126:
        return "docker_exec_not_executable"
    if rc == 127:
        return "docker_exec_not_found"
    return "docker_exec_failed"


class DockerRuntime(RuntimeBackend):
    name = "docker"

    def __init__(
        self,
        *,
        container: str,
        exec_options: Sequence[str] | None = None,
        cpus: str | None = None,
        memory: str | None = None,
    ) -> None:
        self._container = (container or "").strip()
        self._exec_options = tuple(exec_options or ())
        self._cpus = (cpus or "").strip() or None
        self._memory = (memory or "").strip() or None

    def exists(self) -> bool:
        if not self._container:
            return False
        if not shutil.which("docker"):
            return False
        try:
            r = subprocess.run(
                ["docker", "inspect", self._container],
                capture_output=True,
                text=True,
                timeout=8.0,
                check=False,
            )
            return r.returncode == 0
        except OSError:
            return False

    def exec(
        self,
        cmd: str | Sequence[str],
        *,
        cwd: str,
        env: Mapping[str, str] | None = None,
        timeout_sec: float | None = None,
    ) -> ExecResult:
        if not self._container:
            return ExecResult("", "docker: missing container name", 2, "config", self.name)
        if isinstance(cmd, str):
            inner = cmd
        else:
            inner = subprocess.list2cmdline(list(cmd))
        docker_cmd: list[str] = ["docker", "exec"]
        if self._cpus:
            docker_cmd.extend(["--cpus", self._cpus])
        if self._memory:
            docker_cmd.extend(["--memory", self._memory])
        for opt in self._exec_options:
            if opt.strip():
                docker_cmd.append(opt.strip())
        docker_cmd.extend(["-w", cwd, self._container, "sh", "-lc", inner])
        try:
            p = subprocess.run(
                docker_cmd,
                env=dict(env) if env else None,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            return ExecResult(
                str(e.stdout or ""),
                str(e.stderr or e),
                124,
                "timeout",
                self.name,
            )
        except OSError as e:
            return ExecResult("", str(e), 127, "os_error", self.name)
        rc = int(p.returncode or 0)
        return ExecResult(
            p.stdout or "",
            p.stderr or "",
            rc,
            _docker_error_kind(rc),
            self.name,
        )

    def describe(self) -> dict[str, object]:
        return {
            "name": self.name,
            "exists": self.exists(),
            "container": self._container or None,
            "cpus": self._cpus,
            "memory": self._memory,
            "exec_options_count": len(self._exec_options),
        }
