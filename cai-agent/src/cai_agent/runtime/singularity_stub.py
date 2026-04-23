"""Singularity / Apptainer backend (P0-RT MVP)."""

from __future__ import annotations

import shlex
import shutil
import subprocess
from collections.abc import Mapping, Sequence

from cai_agent.runtime.base import ExecResult, RuntimeBackend


def _singularity_bin() -> str | None:
    if shutil.which("singularity"):
        return "singularity"
    if shutil.which("apptainer"):
        return "apptainer"
    return None


class SingularityRuntime(RuntimeBackend):
    name = "singularity"

    def __init__(
        self,
        *,
        sif_path: str = "",
        bind_paths: Sequence[str] | None = None,
    ) -> None:
        self._sif = (sif_path or "").strip()
        self._binds = tuple((bind_paths or ()))

    def exists(self) -> bool:
        return bool(self._sif) and _singularity_bin() is not None

    def exec(
        self,
        cmd: str | Sequence[str],
        *,
        cwd: str,
        env: Mapping[str, str] | None = None,
        timeout_sec: float | None = None,
    ) -> ExecResult:
        bin_name = _singularity_bin()
        if not bin_name:
            return ExecResult(
                "",
                "singularity: neither `singularity` nor `apptainer` found in PATH",
                127,
                "singularity_cli_not_found",
                self.name,
            )
        if not self._sif:
            return ExecResult(
                "",
                "singularity: set [runtime.singularity] sif_path",
                2,
                "singularity_not_configured",
                self.name,
            )
        if isinstance(cmd, str):
            inner = cmd
        else:
            inner = subprocess.list2cmdline(list(cmd))
        cwd_q = shlex.quote((cwd or ".").strip() or ".")
        remote = f"cd {cwd_q} && {inner}"
        argv: list[str] = [bin_name, "exec"]
        for b in self._binds:
            b = str(b).strip()
            if b:
                argv.extend(["-B", b])
        argv.append(self._sif)
        argv.extend(["sh", "-lc", remote])
        try:
            p = subprocess.run(
                argv,
                env=dict(env) if env else None,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            return ExecResult(str(e.stdout or ""), str(e.stderr or e), 124, "timeout", self.name)
        except OSError as e:
            return ExecResult("", str(e), 127, "os_error", self.name)
        rc = int(p.returncode or 0)
        ek = None if rc == 0 else "singularity_failed"
        return ExecResult(p.stdout or "", p.stderr or "", rc, ek, self.name)

    def describe(self) -> dict[str, object]:
        return {
            "name": self.name,
            "exists": self.exists(),
            "sif_path": self._sif or None,
            "bind_paths": list(self._binds),
        }
