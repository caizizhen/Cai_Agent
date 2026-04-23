"""Command execution backends (Hermes H1-RT): local / docker / ssh / modal / daytona / singularity."""

from __future__ import annotations

from cai_agent.runtime.base import ExecResult, RuntimeBackend
from cai_agent.runtime.local import LocalRuntime
from cai_agent.runtime.registry import RUNTIME_REGISTRY, get_runtime_backend

__all__ = [
    "ExecResult",
    "RuntimeBackend",
    "LocalRuntime",
    "RUNTIME_REGISTRY",
    "get_runtime_backend",
]
