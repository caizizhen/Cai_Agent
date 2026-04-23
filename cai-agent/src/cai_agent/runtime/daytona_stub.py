"""Daytona CLI backend (P0-RT): detect CLI; exec bridge optional."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Mapping, Sequence

from cai_agent.runtime.base import ExecResult, RuntimeBackend


class DaytonaRuntime(RuntimeBackend):
    name = "daytona"

    def __init__(self, *, workspace: str = "") -> None:
        self._workspace = (workspace or "").strip()

    def exists(self) -> bool:
        return bool(shutil.which("daytona"))

    def exec(
        self,
        cmd: str | Sequence[str],
        *,
        cwd: str,
        env: Mapping[str, str] | None = None,
        timeout_sec: float | None = None,
    ) -> ExecResult:
        if not shutil.which("daytona"):
            return ExecResult(
                "",
                "daytona: CLI not found in PATH (install https://www.daytona.io/docs/)",
                127,
                "daytona_cli_not_found",
                self.name,
            )
        if not self._workspace:
            return ExecResult(
                "",
                "daytona: configure [runtime.daytona] workspace (workspace id)",
                2,
                "daytona_not_configured",
                self.name,
            )
        if isinstance(cmd, str):
            inner = cmd
        else:
            inner = subprocess.list2cmdline(list(cmd))
        _ = (cwd, env, timeout_sec, inner)
        # CLI surface evolves; keep a conservative bridge — users can shell out until SDK lands.
        return ExecResult(
            "",
            (
                "daytona: workspace is set but automated `exec` is not wired to a stable CLI yet; "
                "use backend=local/docker or extend runtime/daytona_stub.py for your Daytona version."
            ),
            2,
            "daytona_exec_not_implemented",
            self.name,
        )

    def describe(self) -> dict[str, object]:
        return {
            "name": self.name,
            "exists": self.exists(),
            "workspace": self._workspace or None,
        }
