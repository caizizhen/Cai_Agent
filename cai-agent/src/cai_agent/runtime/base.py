from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class ExecResult:
    """Normalized result from :meth:`RuntimeBackend.exec`."""

    stdout: str
    stderr: str
    returncode: int
    error_kind: str | None = None
    backend: str = "local"


class RuntimeBackend(ABC):
    """Abstract command runner (workspace-relative ``cwd``)."""

    name: str

    @abstractmethod
    def exec(
        self,
        cmd: str | Sequence[str],
        *,
        cwd: str,
        env: Mapping[str, str] | None = None,
        timeout_sec: float | None = None,
    ) -> ExecResult:
        raise NotImplementedError

    def exists(self) -> bool:
        """Whether this backend is reachable / configured."""
        return True

    def ensure_workspace(self, path: str) -> None:
        """Optional hook: create or mount workspace on remote backend."""
        return None

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "exists": self.exists()}
