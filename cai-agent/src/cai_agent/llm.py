from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import httpx

from cai_agent.config import Settings
from cai_agent.http_trust import effective_http_trust_env

_RETRYABLE_STATUS = frozenset({429, 502, 503, 504})

_USAGE_PROMPT_TOKENS = 0
_USAGE_COMPLETION_TOKENS = 0
_USAGE_TOTAL_TOKENS = 0

# "Last call" snapshot — 独立于累计计数器，每次 chat_completion 成功响应都会覆盖。
# 提供给 UI（例如 TUI 的上下文进度条）展示"当前对话上下文占用"：
# 实际发送给模型的 prompt_tokens 就是当前这轮的真实 context 占用量。
_LAST_PROMPT_TOKENS = 0
_LAST_COMPLETION_TOKENS = 0
_LAST_TOTAL_TOKENS = 0


def reset_usage_counters() -> None:
    """Reset per-process token usage counters (both cumulative and last snapshot)."""
    global _USAGE_PROMPT_TOKENS, _USAGE_COMPLETION_TOKENS, _USAGE_TOTAL_TOKENS
    global _LAST_PROMPT_TOKENS, _LAST_COMPLETION_TOKENS, _LAST_TOTAL_TOKENS
    _USAGE_PROMPT_TOKENS = 0
    _USAGE_COMPLETION_TOKENS = 0
    _USAGE_TOTAL_TOKENS = 0
    _LAST_PROMPT_TOKENS = 0
    _LAST_COMPLETION_TOKENS = 0
    _LAST_TOTAL_TOKENS = 0


def get_usage_counters() -> dict[str, int]:
    """Return a snapshot of accumulated token usage counters."""
    return {
        "prompt_tokens": _USAGE_PROMPT_TOKENS,
        "completion_tokens": _USAGE_COMPLETION_TOKENS,
        "total_tokens": _USAGE_TOTAL_TOKENS,
    }


def get_last_usage() -> dict[str, int]:
    """Return usage tokens from the most recent LLM response.

    ``prompt_tokens`` reflects the **current** context size that was actually
    fed into the model on the last call — this is the number the UI should
    compare against the model's context window to show a fill progress bar.
    """
    return {
        "prompt_tokens": _LAST_PROMPT_TOKENS,
        "completion_tokens": _LAST_COMPLETION_TOKENS,
        "total_tokens": _LAST_TOTAL_TOKENS,
    }


def _record_last_usage(
    *,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
) -> None:
    """Overwrite the "last call" snapshot. Negative/unknown values become 0."""
    global _LAST_PROMPT_TOKENS, _LAST_COMPLETION_TOKENS, _LAST_TOTAL_TOKENS
    _LAST_PROMPT_TOKENS = max(0, int(prompt_tokens or 0))
    _LAST_COMPLETION_TOKENS = max(0, int(completion_tokens or 0))
    _LAST_TOTAL_TOKENS = max(0, int(total_tokens or (
        _LAST_PROMPT_TOKENS + _LAST_COMPLETION_TOKENS
    )))


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


def _is_cjk(ch: str) -> bool:
    """True for CJK ideographs / kana / hangul — characters that BPE
    tokenisers typically split at roughly 1 char ≈ 1 token (often a bit
    more, ~1.1–1.5). Much denser than English where 1 token ≈ 4 chars."""
    if not ch:
        return False
    cp = ord(ch)
    return (
        0x3040 <= cp <= 0x30FF       # Hiragana + Katakana
        or 0x3400 <= cp <= 0x4DBF   # CJK Ext-A
        or 0x4E00 <= cp <= 0x9FFF   # CJK Unified Ideographs
        or 0xAC00 <= cp <= 0xD7AF   # Hangul Syllables
        or 0xF900 <= cp <= 0xFAFF   # CJK Compat Ideographs
        or 0x20000 <= cp <= 0x2FFFF  # CJK Ext-B/C/D/E/F
        or 0xFF00 <= cp <= 0xFFEF   # Halfwidth/fullwidth forms (punct mostly)
    )


def _estimate_chunk_tokens(text: str) -> float:
    """Piecewise heuristic: CJK ~1.5 chars/token, ASCII ~4 chars/token.

    Empirically calibrated against OpenAI / Anthropic / Qwen tokenisers on
    mixed zh/en prompts. Errors are typically within ±20% of real
    ``prompt_tokens`` — good enough for a progress bar placeholder.
    """
    if not text:
        return 0.0
    cjk_chars = 0
    other_chars = 0
    for ch in text:
        if _is_cjk(ch):
            cjk_chars += 1
        else:
            other_chars += 1
    return cjk_chars / 1.5 + other_chars / 4.0


def estimate_tokens_from_messages(messages: list[dict[str, Any]]) -> int:
    """Token estimate for a message list, used before the first real API
    response arrives (when ``get_last_usage()`` is still zero) or when
    the server didn't return a ``usage`` block.

    Uses a CJK-aware piecewise heuristic (see ``_estimate_chunk_tokens``):
    * CJK characters  → ~1.5 chars/token (zh/ja/ko dense BPE)
    * Other characters → ~4 chars/token (OpenAI English rule of thumb)

    Plus ~4 tokens/message for the role/JSON scaffold overhead. Result is
    a rough estimate — the authoritative number comes from the server's
    ``usage.prompt_tokens`` and overwrites this on the next response.
    """
    if not isinstance(messages, list):
        return 0
    total = 0.0
    for m in messages:
        if not isinstance(m, dict):
            continue
        c = m.get("content")
        if isinstance(c, str):
            total += _estimate_chunk_tokens(c)
        elif isinstance(c, list):
            for it in c:
                if isinstance(it, dict):
                    t = it.get("text") or it.get("content")
                    if isinstance(t, str):
                        total += _estimate_chunk_tokens(t)
                elif isinstance(it, str):
                    total += _estimate_chunk_tokens(it)
        total += 4.0
    return max(0, int(round(total)))


def chat_completion(settings: Settings, messages: list[dict[str, Any]]) -> str:
    if settings.mock:
        fixed = os.getenv("CAI_MOCK_REPLY")
        if fixed:
            return fixed
        return '{"type":"finish","message":"CAI_MOCK=1（未设置 CAI_MOCK_REPLY）"}'

    url = f"{settings.base_url.rstrip('/')}/chat/completions"
    trust = effective_http_trust_env(
        trust_env=bool(getattr(settings, "http_trust_env", False)),
        request_url=url,
    )
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
    data: dict[str, Any] | None = None
    last_transport_exc: Exception | None = None
    with httpx.Client(timeout=timeout, trust_env=trust) as client:
        for attempt in range(5):
            try:
                last = client.post(url, json=payload, headers=headers)
                last_transport_exc = None
            except httpx.TransportError as exc:
                # Network/channel errors (e.g. "Channel Error" from llama.cpp,
                # RemoteProtocolError, ReadError) — retry with backoff.
                last_transport_exc = exc
                if attempt == 4:
                    raise RuntimeError(
                        f"LLM 连接失败（传输层错误，已重试 5 次）: {exc}",
                    ) from exc
                delay = min(2.0**attempt, 12.0)
                time.sleep(delay)
                continue
            if last.status_code < 400:
                try:
                    parsed = last.json()
                except (json.JSONDecodeError, ValueError) as exc:
                    if attempt == 4:
                        snippet = (last.text or "")[:500]
                        raise RuntimeError(
                            "LLM 返回了非 JSON 响应（已重试 5 次）: "
                            f"{exc}; body_snippet={snippet!r}",
                        ) from exc
                    delay = min(2.0**attempt, 12.0)
                    time.sleep(delay)
                    continue
                if not isinstance(parsed, dict):
                    if attempt == 4:
                        raise RuntimeError(
                            "LLM 返回 JSON 根对象不是 dict（已重试 5 次）",
                        )
                    delay = min(2.0**attempt, 12.0)
                    time.sleep(delay)
                    continue
                data = parsed
                break
            if last.status_code not in _RETRYABLE_STATUS or attempt == 4:
                hdr = "\n".join(f"  {k}: {v}" for k, v in last.headers.items())
                raise RuntimeError(
                    f"LLM HTTP {last.status_code} url={url}\nbody={last.text!r}\nheaders:\n{hdr}",
                )
            delay = min(2.0**attempt, 12.0)
            time.sleep(delay)

    if last_transport_exc is not None:
        raise RuntimeError(
            f"LLM 连接失败（传输层错误）: {last_transport_exc}",
        ) from last_transport_exc
    if data is None:
        raise RuntimeError("LLM 返回体解析失败（未知状态）")
    if last is None or last.status_code >= 400:
        raise RuntimeError("LLM 请求失败（未知状态）")
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
        _record_last_usage(
            prompt_tokens=pt if isinstance(pt, int) else 0,
            completion_tokens=ct if isinstance(ct, int) else 0,
            total_tokens=tt if isinstance(tt, int) else 0,
        )

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
