from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentMessage:
    role: str  # user | assistant | tool | system
    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_call_id: str = ""
    name: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


def _image_data_url(img: dict[str, Any]) -> str | None:
    mime = str(img.get("mime") or "image/png").strip() or "image/png"
    data = str(img.get("data") or img.get("data_b64") or "").strip()
    if not data:
        url = str(img.get("url") or "").strip()
        return url or None
    if data.startswith("data:"):
        return data
    return f"data:{mime};base64,{data}"


def convert_to_llm(messages: list[AgentMessage]) -> list[dict[str, Any]]:
    """Filter/convert AgentMessages to OpenAI chat messages (incl. vision parts)."""
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "system":
            out.append({"role": "system", "content": m.content})
        elif m.role == "user":
            images = []
            if isinstance(m.meta, dict):
                raw = m.meta.get("images") or []
                if isinstance(raw, list):
                    images = [i for i in raw if isinstance(i, dict)]
            if images:
                parts: list[dict[str, Any]] = []
                text = (m.content or "").strip()
                if text:
                    parts.append({"type": "text", "text": text})
                for img in images:
                    url = _image_data_url(img)
                    if not url:
                        continue
                    parts.append({"type": "image_url", "image_url": {"url": url}})
                if not parts:
                    parts.append({"type": "text", "text": m.content or ""})
                out.append({"role": "user", "content": parts})
            else:
                out.append({"role": "user", "content": m.content})
        elif m.role == "assistant":
            msg: dict[str, Any] = {"role": "assistant", "content": m.content or ""}
            if m.tool_calls:
                msg["tool_calls"] = m.tool_calls
            out.append(msg)
        elif m.role == "tool":
            out.append(
                {
                    "role": "tool",
                    "tool_call_id": m.tool_call_id,
                    "name": m.name,
                    "content": m.content,
                },
            )
    return out
