from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import httpx

from cai_agent.config import Settings

_RETRYABLE_STATUS = frozenset({429, 502, 503, 504})


def chat_completion(settings: Settings, messages: list[dict[str, Any]]) -> str:
    if settings.mock:
        fixed = os.getenv("CAI_MOCK_REPLY")
        if fixed:
            return fixed
        return '{"type":"finish","message":"CAI_MOCK=1（未设置 CAI_MOCK_REPLY）"}'

    url = f"{settings.base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.model,
        "messages": messages,
        "temperature": settings.temperature,
    }
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }
    timeout = httpx.Timeout(
        connect=30.0,
        read=settings.llm_timeout_sec,
        write=30.0,
        pool=30.0,
    )

    last: httpx.Response | None = None
    with httpx.Client(timeout=timeout, trust_env=settings.http_trust_env) as client:
        for attempt in range(5):
            last = client.post(url, json=payload, headers=headers)
            if last.status_code < 400:
                break
            if last.status_code not in _RETRYABLE_STATUS or attempt == 4:
                hdr = "\n".join(f"  {k}: {v}" for k, v in last.headers.items())
                raise RuntimeError(
                    f"LLM HTTP {last.status_code} url={url}\nbody={last.text!r}\nheaders:\n{hdr}",
                )
            delay = min(2.0**attempt, 12.0)
            time.sleep(delay)

    if last is None or last.status_code >= 400:
        raise RuntimeError("LLM 请求失败（未知状态）")

    data = last.json()
    return str(data["choices"][0]["message"]["content"])


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse first JSON object from model output (handles ``` fences)."""
    s = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", s, re.IGNORECASE)
    if fence:
        s = fence.group(1).strip()
    start = s.find("{")
    if start < 0:
        raise ValueError("未找到 JSON 对象")
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(s[start:])
    if not isinstance(obj, dict):
        raise ValueError("JSON 根须为对象")
    return obj
