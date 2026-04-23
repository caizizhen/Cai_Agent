"""Run / continue 会话事件：与 workflow 风格对齐的 ``events`` 信封与归一化读取。"""

from __future__ import annotations

from typing import Any

RUN_SCHEMA_VERSION = "1.1"
RUN_EVENTS_ENVELOPE_SCHEMA_VERSION = "run_events_envelope_v1"


def wrap_run_events(items: list[dict[str, Any]]) -> dict[str, Any]:
    """将事件列表包成稳定信封（写入会话 JSON / CLI ``--json``）。"""
    return {
        "schema_version": RUN_EVENTS_ENVELOPE_SCHEMA_VERSION,
        "items": list(items),
    }


def normalize_session_run_events(raw: Any) -> list[dict[str, Any]]:
    """兼容旧版 ``events: [...]`` 与新版 ``events: { schema_version, items }``。"""
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        ver = str(raw.get("schema_version") or "")
        items = raw.get("items")
        if ver == RUN_EVENTS_ENVELOPE_SCHEMA_VERSION and isinstance(items, list):
            return [x for x in items if isinstance(x, dict)]
    return []
