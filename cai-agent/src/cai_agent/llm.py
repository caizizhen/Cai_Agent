from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import httpx

from cai_agent.config import Settings

_RETRYABLE_STATUS = frozenset({429, 502, 503, 504})

_USAGE_PROMPT_TOKENS = 0
_USAGE_COMPLETION_TOKENS = 0
_USAGE_TOTAL_TOKENS = 0


def reset_usage_counters() -> None:
    """Reset per-process token usage counters."""
    global _USAGE_PROMPT_TOKENS, _USAGE_COMPLETION_TOKENS, _USAGE_TOTAL_TOKENS
    _USAGE_PROMPT_TOKENS = 0
    _USAGE_COMPLETION_TOKENS = 0
    _USAGE_TOTAL_TOKENS = 0


def get_usage_counters() -> dict[str, int]:
    """Return a snapshot of accumulated token usage counters."""
    return {
        "prompt_tokens": _USAGE_PROMPT_TOKENS,
        "completion_tokens": _USAGE_COMPLETION_TOKENS,
        "total_tokens": _USAGE_TOTAL_TOKENS,
    }


def add_usage(
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
) -> None:
    """Accumulate usage counters from any adapter (e.g. Anthropic)."""
    global _USAGE_PROMPT_TOKENS, _USAGE_COMPLETION_TOKENS, _USAGE_TOTAL_TOKENS
    if isinstance(prompt_tokens, int) and prompt_tokens > 0:
        _USAGE_PROMPT_TOKENS += prompt_tokens
    if isinstance(completion_tokens, int) and completion_tokens > 0:
        _USAGE_COMPLETION_TOKENS += completion_tokens
    if isinstance(total_tokens, int) and total_tokens > 0:
        _USAGE_TOTAL_TOKENS += total_tokens


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
    usage = data.get("usage")
    if isinstance(usage, dict):
        global _USAGE_PROMPT_TOKENS, _USAGE_COMPLETION_TOKENS, _USAGE_TOTAL_TOKENS
        pt = usage.get("prompt_tokens")
        ct = usage.get("completion_tokens")
        tt = usage.get("total_tokens")
        if isinstance(pt, int) and pt >= 0:
            _USAGE_PROMPT_TOKENS += pt
        if isinstance(ct, int) and ct >= 0:
            _USAGE_COMPLETION_TOKENS += ct
        if isinstance(tt, int) and tt >= 0:
            _USAGE_TOTAL_TOKENS += tt

    choice = (data.get("choices") or [{}])[0] if isinstance(data.get("choices"), list) else {}
    message = choice.get("message") if isinstance(choice, dict) else None
    if not isinstance(message, dict):
        message = {}
    return normalize_assistant_text(
        content=message.get("content"),
        message=message,
        choice=choice if isinstance(choice, dict) else {},
        usage=usage if isinstance(usage, dict) else {},
        provider_label="OpenAI-compatible",
    )


_THINK_BLOCK_RE = re.compile(r"<think\b[^>]*>[\s\S]*?</think>\s*", re.IGNORECASE)


def _stringify_content(content: Any) -> str:
    """Best-effort coerce ``message.content`` into a plain string.

    Some OpenAI-compatible servers return ``content`` as a list of
    ``{"type":"text","text":...}`` chunks instead of a bare string.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for it in content:
            if isinstance(it, dict):
                t = it.get("text") or it.get("content")
                if isinstance(t, str):
                    parts.append(t)
            elif isinstance(it, str):
                parts.append(it)
        return "\n".join(parts)
    return str(content)


def normalize_assistant_text(
    *,
    content: Any,
    message: dict[str, Any],
    choice: dict[str, Any],
    usage: dict[str, Any],
    provider_label: str = "LLM",
) -> str:
    """Return a non-empty assistant text, synthesising a ``finish`` envelope
    when the model produced no usable output.

    Triggered by reasoning-style models (Qwen3 / DeepSeek-R1 / LM Studio) which
    may emit ``content=""`` together with a huge ``reasoning_content`` once the
    reasoning budget is exhausted. Returning a finish envelope lets the graph
    surface the problem and stop cleanly instead of crashing on JSON parsing
    or spinning ``max_iterations``.
    """
    raw = _stringify_content(content)
    text = raw.strip()

    if text:
        stripped = _THINK_BLOCK_RE.sub("", text).strip()
        if stripped:
            return stripped

    return _empty_content_finish(
        message=message,
        choice=choice,
        usage=usage,
        provider_label=provider_label,
    )


def _empty_content_finish(
    *,
    message: dict[str, Any],
    choice: dict[str, Any],
    usage: dict[str, Any],
    provider_label: str,
) -> str:
    finish_reason = choice.get("finish_reason") if isinstance(choice, dict) else None
    reasoning_tokens: int | None = None
    details = usage.get("completion_tokens_details") if isinstance(usage, dict) else None
    if isinstance(details, dict):
        rt = details.get("reasoning_tokens")
        if isinstance(rt, int):
            reasoning_tokens = rt
    has_reasoning = isinstance(
        message.get("reasoning_content") or message.get("reasoning"), str,
    ) and bool((message.get("reasoning_content") or message.get("reasoning") or "").strip())

    meta_parts: list[str] = [f"provider={provider_label}"]
    if finish_reason:
        meta_parts.append(f"finish_reason={finish_reason}")
    if isinstance(reasoning_tokens, int):
        meta_parts.append(f"reasoning_tokens={reasoning_tokens}")
    meta = "; ".join(meta_parts)

    if has_reasoning or (isinstance(reasoning_tokens, int) and reasoning_tokens > 0):
        advice = (
            "模型把所有输出塞进了 reasoning_content（推理死循环或推理预算耗尽），"
            "未产生可用的最终回答。建议：切换到非 reasoning 模型（如 Qwen2.5-Instruct "
            "或 gpt-4o-mini），或在 profile 里把 temperature 调到 ≤0.3、给 max_tokens "
            "设上限。"
        )
    else:
        advice = (
            "模型返回了空 content 且无 reasoning_content。可能是被安全策略拦截、"
            "上下文过长被截断，或服务器返回异常。建议：缩减 messages 历史后重试，"
            "或检查服务端日志。"
        )

    return json.dumps(
        {
            "type": "finish",
            "message": f"[empty-completion] {meta}。{advice}",
        },
        ensure_ascii=False,
    )


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
