"""Hermes S7-01：统一指标事件 ``metrics_schema_v1``（可选 JSONL 落盘）。"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict


METRICS_SCHEMA_VERSION = "metrics_schema_v1"


class MetricsEventV1(TypedDict, total=False):
    """单行指标事件（与文档 ``docs/schema/METRICS_JSON.zh-CN.md`` 对齐）。"""

    schema_version: str
    ts: str
    module: str
    event: str
    latency_ms: float
    tokens: int
    cost_usd: float
    success: bool


def metrics_event_v1(
    *,
    module: str,
    event: str,
    latency_ms: float = 0.0,
    tokens: int = 0,
    cost_usd: float | None = None,
    success: bool = True,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "schema_version": METRICS_SCHEMA_VERSION,
        "ts": datetime.now(UTC).isoformat(),
        "module": str(module).strip(),
        "event": str(event).strip(),
        "latency_ms": float(latency_ms),
        "tokens": int(tokens),
        "success": bool(success),
    }
    if cost_usd is not None:
        row["cost_usd"] = float(cost_usd)
    return row


def append_metrics_jsonl(path: str | Path, event: dict[str, Any]) -> None:
    """追加一行 JSON（UTF-8）。路径父目录不存在时创建。"""
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    ev = dict(event)
    ev.setdefault("schema_version", METRICS_SCHEMA_VERSION)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")


def maybe_append_metrics_from_env(event: dict[str, Any]) -> None:
    """若设置环境变量 ``CAI_METRICS_JSONL``，则追加一行指标。"""
    raw = str(os.environ.get("CAI_METRICS_JSONL", "") or "").strip()
    if not raw:
        return
    append_metrics_jsonl(raw, event)
