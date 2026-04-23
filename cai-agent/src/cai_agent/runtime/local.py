from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from typing import Any

from cai_agent.runtime.base import ExecResult, RuntimeBackend


class LocalRuntime(RuntimeBackend):
    """Default backend: ``subprocess.run`` on the host OS."""

    name = "local"

    def exec(
        self,
        cmd: str | Sequence[str],
        *,
        cwd: str,
        env: Mapping[str, str] | None = None,
        timeout_sec: float | None = None,
    ) -> ExecResult:
        shell = isinstance(cmd, str)
        try:
            p = subprocess.run(
                cmd,
                cwd=cwd,
                env=dict(env) if env else None,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            out = (e.stdout or "") if isinstance(e.stdout, str) else ""
            err = (e.stderr or "") if isinstance(e.stderr, str) else str(e)
            return ExecResult(
                stdout=out,
                stderr=err,
                returncode=124,
                error_kind="timeout",
                backend=self.name,
            )
        except OSError as e:
            return ExecResult(
                stdout="",
                stderr=str(e),
                returncode=127,
                error_kind="os_error",
                backend=self.name,
            )
        return ExecResult(
            stdout=p.stdout or "",
            stderr=p.stderr or "",
            returncode=int(p.returncode or 0),
            error_kind=None if p.returncode == 0 else "nonzero_exit",
            backend=self.name,
        )

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "exists": True, "kind": "subprocess"}
