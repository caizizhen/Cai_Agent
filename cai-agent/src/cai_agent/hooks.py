from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, DefaultDict, Dict, List


HookHandler = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class Hook:
    """简单的 Hook 描述，用于注册事件回调."""

    name: str
    handler: HookHandler


_REGISTRY: DefaultDict[str, List[Hook]] = defaultdict(list)


def register(event: str, handler: HookHandler, *, name: str | None = None) -> None:
    """注册一个 Hook 到指定事件名称."""

    hook = Hook(name=name or handler.__name__, handler=handler)
    _REGISTRY[event].append(hook)


def get_hooks(event: str) -> List[Hook]:
    """列出指定事件下已注册的全部 Hook."""

    return list(_REGISTRY.get(event, []))


def emit(event: str, payload: Dict[str, Any]) -> None:
    """依次调用某个事件下的所有 Hook，忽略单个 Hook 的异常."""

    for hook in _REGISTRY.get(event, []):
        try:
            hook.handler(dict(payload))
        except Exception:
            # Hook 失败不应影响主流程。
            continue

