"""Modal backend placeholder (SDK optional; H1-RT-04 + P0-RT config surface)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from cai_agent.runtime.base import ExecResult, RuntimeBackend


class ModalRuntime(RuntimeBackend):
    name = "modal"

    def __init__(
        self,
        *,
        app_name: str = "",
        hibernate_idle_seconds: int | None = None,
    ) -> None:
        self._app = (app_name or "").strip()
        self._hibernate = hibernate_idle_seconds

    def exists(self) -> bool:
        try:
            import modal  # noqa: F401
        except ImportError:
            return False
        return bool(self._app)

    def exec(
        self,
        cmd: str | Sequence[str],
        *,
        cwd: str,
        env: Mapping[str, str] | None = None,
        timeout_sec: float | None = None,
    ) -> ExecResult:
        return ExecResult(
            "",
            "modal backend: install `modal` SDK and configure [runtime.modal] (MVP stub)",
            2,
            "modal_not_installed",
            self.name,
        )

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "exists": self.exists(),
            "app_name": self._app or None,
            "hibernate_idle_seconds": self._hibernate,
        }
