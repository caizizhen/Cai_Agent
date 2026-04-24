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
        container: str = "",
        image: str = "",
        workdir: str = "/workspace",
        volume_mounts: Sequence[str] | None = None,
        exec_options: Sequence[str] | None = None,
        cpus: str | None = None,
        memory: str | None = None,
    ) -> None:
        self._container = (container or "").strip()
        self._image = (image or "").strip()
        self._workdir = (workdir or "").strip() or "/workspace"
        self._volume_mounts = tuple(str(x).strip() for x in (volume_mounts or ()) if str(x).strip())
        self._exec_options = tuple(exec_options or ())
        self._cpus = (cpus or "").strip() or None
        self._memory = (memory or "").strip() or None

    def exists(self) -> bool:
        if not shutil.which("docker"):
            return False
        if self._image and not self._container:
            return True
        if not self._container:
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

    def _inner_cmd(self, cmd: str | Sequence[str]) -> str:
        if isinstance(cmd, str):
            return cmd
        return subprocess.list2cmdline(list(cmd))

    def _append_common_run_options(
        self,
        docker_cmd: list[str],
        *,
        include_limits: bool,
        include_mounts: bool,
    ) -> None:
        if include_limits and self._cpus:
            docker_cmd.extend(["--cpus", self._cpus])
        if include_limits and self._memory:
            docker_cmd.extend(["--memory", self._memory])
        if include_mounts:
            for mount in self._volume_mounts:
                docker_cmd.extend(["-v", mount])
        for opt in self._exec_options:
            if opt.strip():
                docker_cmd.append(opt.strip())

    def exec(
        self,
        cmd: str | Sequence[str],
        *,
        cwd: str,
        env: Mapping[str, str] | None = None,
        timeout_sec: float | None = None,
    ) -> ExecResult:
        inner = self._inner_cmd(cmd)
        docker_cmd: list[str]
        if self._container:
            docker_cmd = ["docker", "exec"]
            self._append_common_run_options(docker_cmd, include_limits=False, include_mounts=False)
            docker_cmd.extend(["-w", cwd, self._container, "sh", "-lc", inner])
        elif self._image:
            docker_cmd = ["docker", "run", "--rm"]
            self._append_common_run_options(docker_cmd, include_limits=True, include_mounts=True)
            docker_cmd.extend(["-w", self._workdir, self._image, "sh", "-lc", inner])
        else:
            return ExecResult("", "docker: missing container name or image", 2, "config", self.name)
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
            "mode": "exec" if self._container else "run" if self._image else "unconfigured",
            "container": self._container or None,
            "image": self._image or None,
            "workdir": self._workdir,
            "cpus": self._cpus,
            "memory": self._memory,
            "volume_mounts_count": len(self._volume_mounts),
            "volume_mounts": list(self._volume_mounts),
            "exec_options_count": len(self._exec_options),
        }
