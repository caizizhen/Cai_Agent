"""SSH backend via system ``ssh`` (zero extra deps, H1-RT-03 + P0-RT)."""

from __future__ import annotations

import shlex
import shutil
import subprocess
from collections.abc import Mapping, Sequence

from cai_agent.runtime.base import ExecResult, RuntimeBackend


class SSHRuntime(RuntimeBackend):
    name = "ssh"

    def __init__(
        self,
        *,
        host: str,
        user: str,
        key_path: str | None = None,
        strict_host_key: bool = True,
        known_hosts_path: str | None = None,
        connect_timeout_sec: float = 15.0,
    ) -> None:
        self._host = (host or "").strip()
        self._user = (user or "").strip()
        self._key = (key_path or "").strip() or None
        self._strict_host_key = bool(strict_host_key)
        self._known_hosts = (known_hosts_path or "").strip() or None
        self._connect_timeout = float(max(1.0, min(120.0, connect_timeout_sec)))

    def exists(self) -> bool:
        return bool(self._host and self._user and shutil.which("ssh"))

    def ensure_workspace(self, path: str) -> None:
        """Best-effort ``mkdir -p`` on the remote (requires non-interactive auth)."""
        p = (path or "").strip()
        if not p or not self.exists():
            return
        inner = f"mkdir -p {shlex.quote(p)}"
        self.exec(inner, cwd=".", env=None, timeout_sec=min(60.0, self._connect_timeout + 30.0))

    def exec(
        self,
        cmd: str | Sequence[str],
        *,
        cwd: str,
        env: Mapping[str, str] | None = None,
        timeout_sec: float | None = None,
    ) -> ExecResult:
        if not self.exists():
            return ExecResult("", "ssh: invalid host/user or ssh not in PATH", 2, "ssh_config", self.name)
        if isinstance(cmd, str):
            inner = cmd
        else:
            inner = subprocess.list2cmdline(list(cmd))
        cwd_q = shlex.quote((cwd or ".").strip() or ".")
        remote = f"cd {cwd_q} && {inner}"
        ssh_cmd: list[str] = ["ssh", "-o", "BatchMode=yes"]
        ct = int(max(1, min(120, round(self._connect_timeout))))
        ssh_cmd.extend(["-o", f"ConnectTimeout={ct}"])
        if self._strict_host_key:
            if self._known_hosts:
                ssh_cmd.extend(
                    [
                        "-o",
                        f"UserKnownHostsFile={self._known_hosts}",
                        "-o",
                        "StrictHostKeyChecking=yes",
                    ],
                )
            else:
                ssh_cmd.extend(["-o", "StrictHostKeyChecking=yes"])
        else:
            ssh_cmd.extend(["-o", "StrictHostKeyChecking=no"])
        if self._key:
            ssh_cmd.extend(["-i", self._key])
        ssh_cmd.append(f"{self._user}@{self._host}")
        ssh_cmd.append(remote)
        try:
            p = subprocess.run(
                ssh_cmd,
                env=dict(env) if env else None,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            return ExecResult(str(e.stdout or ""), str(e.stderr or e), 124, "timeout", self.name)
        except OSError as e:
            return ExecResult("", str(e), 127, "ssh_auth", self.name)
        rc = int(p.returncode or 0)
        if rc == 0:
            ek = None
        elif rc == 255:
            ek = "ssh_host_unreachable"
        else:
            ek = "ssh_failed"
        return ExecResult(p.stdout or "", p.stderr or "", rc, ek, self.name)

    def describe(self) -> dict[str, object]:
        return {
            "name": self.name,
            "exists": self.exists(),
            "host": self._host or None,
            "user": self._user or None,
            "strict_host_key": self._strict_host_key,
            "connect_timeout_sec": self._connect_timeout,
        }
