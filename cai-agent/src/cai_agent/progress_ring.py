"""结构化进度流 ring buffer：收集 graph.py 的 progress 回调事件，供 observe 聚合。"""

from __future__ import annotations

import threading
from collections import deque
from typing import Any


_DEFAULT_RING_SIZE = 200


class ProgressRing:
    """线程安全的定长环形缓冲区，存储 LangGraph progress 阶段事件。"""

    def __init__(self, maxlen: int = _DEFAULT_RING_SIZE) -> None:
        self._buf: deque[dict[str, Any]] = deque(maxlen=max(1, int(maxlen)))
        self._lock = threading.Lock()

    def push(self, payload: dict[str, Any]) -> None:
        with self._lock:
            self._buf.append(dict(payload))

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._buf)

    def clear(self) -> None:
        with self._lock:
            self._buf.clear()

    def phase_distribution(self) -> dict[str, int]:
        """统计各 ``phase`` 出现次数（供 observe 聚合）。"""
        counts: dict[str, int] = {}
        with self._lock:
            for item in self._buf:
                phase = str(item.get("phase") or "unknown")
                counts[phase] = counts.get(phase, 0) + 1
        return counts


# 全局默认 ring，`build_app` 可直接使用
_global_ring = ProgressRing()


def global_ring() -> ProgressRing:
    """获取全局 ProgressRing 实例。"""
    return _global_ring


def reset_global_ring(maxlen: int = _DEFAULT_RING_SIZE) -> None:
    """重置全局 ring（测试用）。"""
    global _global_ring
    _global_ring = ProgressRing(maxlen=maxlen)


def build_progress_ring_summary(ring: ProgressRing | None = None) -> dict[str, Any]:
    """将 ring 事件聚合为摘要（供 `observe` / `board` 增量使用）。"""
    r = ring if ring is not None else _global_ring
    events = r.snapshot()
    total = len(events)
    phase_dist = r.phase_distribution()
    llm_calls = phase_dist.get("llm", 0)
    tool_calls = sum(
        1
        for ev in events
        if str(ev.get("phase") or "") in ("tool", "tool_result")
    )
    errors = sum(1 for ev in events if str(ev.get("phase") or "") == "error")
    return {
        "schema_version": "progress_ring_summary_v1",
        "total_events": total,
        "phase_distribution": phase_dist,
        "llm_calls": llm_calls,
        "tool_calls_in_ring": tool_calls,
        "errors_in_ring": errors,
    }
