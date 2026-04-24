"""SSH backend via system ``ssh`` (zero extra deps, H1-RT-03 + P0-RT)."""

from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

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
        audit_log_path: str | None = None,
        audit_label: str | None = None,
        audit_include_command: bool = False,
    ) -> None:
        self._host = (host or "").strip()
        self._user = (user or "").strip()
        self._key = (key_path or "").strip() or None
        self._strict_host_key = bool(strict_host_key)
        self._known_hosts = (known_hosts_path or "").strip() or None
        self._connect_timeout = float(max(1.0, min(120.0, connect_timeout_sec)))
        self._audit_log_path = (audit_log_path or "").strip() or None
        self._audit_label = (audit_label or "").strip() or None
        self._audit_include_command = bool(audit_include_command)

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
        started_at = datetime.now(UTC).isoformat()
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
            self._write_audit_event(
                started_at=started_at,
                cwd=cwd,
                cmd=cmd,
                returncode=124,
                error_kind="timeout",
                timeout_sec=timeout_sec,
            )
            return ExecResult(str(e.stdout or ""), str(e.stderr or e), 124, "timeout", self.name)
        except OSError as e:
            self._write_audit_event(
                started_at=started_at,
                cwd=cwd,
                cmd=cmd,
                returncode=127,
                error_kind="ssh_auth",
                timeout_sec=timeout_sec,
            )
            return ExecResult("", str(e), 127, "ssh_auth", self.name)
        rc = int(p.returncode or 0)
        if rc == 0:
            ek = None
        elif rc == 255:
            ek = "ssh_host_unreachable"
        else:
            ek = "ssh_failed"
        self._write_audit_event(
            started_at=started_at,
            cwd=cwd,
            cmd=cmd,
            returncode=rc,
            error_kind=ek,
            timeout_sec=timeout_sec,
        )
        return ExecResult(p.stdout or "", p.stderr or "", rc, ek, self.name)

    def _write_audit_event(
        self,
        *,
        started_at: str,
        cwd: str,
        cmd: str | Sequence[str],
        returncode: int,
        error_kind: str | None,
        timeout_sec: float | None,
    ) -> None:
        if not self._audit_log_path:
            return
        event: dict[str, object] = {
            "schema_version": "runtime_ssh_audit_v1",
            "started_at": started_at,
            "finished_at": datetime.now(UTC).isoformat(),
            "backend": self.name,
            "host": self._host,
            "user": self._user,
            "cwd": str(cwd or "."),
            "returncode": int(returncode),
            "error_kind": error_kind,
            "timeout_sec": timeout_sec,
            "label": self._audit_label,
        }
        if isinstance(cmd, str):
            event["command_kind"] = "shell"
            event["argv_count"] = None
            if self._audit_include_command:
                event["command_preview"] = cmd[:200]
        else:
            event["command_kind"] = "argv"
            event["argv_count"] = len(list(cmd))
            if self._audit_include_command:
                event["command_preview"] = subprocess.list2cmdline(list(cmd))[:200]
        p = Path(self._audit_log_path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def describe(self) -> dict[str, object]:
        key_exists = Path(self._key).expanduser().is_file() if self._key else None
        known_hosts_exists = Path(self._known_hosts).expanduser().is_file() if self._known_hosts else None
        return {
            "name": self.name,
            "exists": self.exists(),
            "ssh_binary_present": bool(shutil.which("ssh")),
            "host": self._host or None,
            "user": self._user or None,
            "key_path_configured": bool(self._key),
            "key_path_exists": key_exists,
            "strict_host_key": self._strict_host_key,
            "known_hosts_path": self._known_hosts,
            "known_hosts_exists": known_hosts_exists,
            "connect_timeout_sec": self._connect_timeout,
            "audit_enabled": bool(self._audit_log_path),
            "audit_log_path": self._audit_log_path,
            "audit_label": self._audit_label,
            "audit_include_command": self._audit_include_command,
        }
