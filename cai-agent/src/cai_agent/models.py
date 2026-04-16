from __future__ import annotations

from typing import Any

import httpx

from cai_agent.config import Settings


def fetch_models(settings: Settings) -> list[str]:
    """从 OpenAI 兼容 /models 端点获取模型 id 列表。"""
    url = f"{settings.base_url.rstrip('/')}/models"
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(
        connect=15.0,
        read=30.0,
        write=15.0,
        pool=15.0,
    )
    with httpx.Client(timeout=timeout, trust_env=settings.http_trust_env) as client:
        r = client.get(url, headers=headers)
    if r.status_code >= 400:
        raise RuntimeError(f"/models 请求失败: HTTP {r.status_code} body={r.text!r}")
    data: Any = r.json()
    rows = data.get("data")
    if not isinstance(rows, list):
        raise RuntimeError("/models 返回格式异常：缺少 data 数组")
    ids: list[str] = []
    for item in rows:
        if isinstance(item, dict):
            mid = item.get("id")
            if isinstance(mid, str) and mid.strip():
                ids.append(mid.strip())
    return sorted(set(ids))
