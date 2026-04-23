"""Lightweight agentskills.io-style frontmatter checks (no PyYAML dependency)."""

from __future__ import annotations

import re
from typing import Any

_FM_BLOCK = re.compile(r"\A---\s*\r?\n(.*?)\r?\n---\s*\r?\n", re.DOTALL)


def _parse_fm_keys_and_nested(block: str) -> dict[str, Any]:
    """Parse ``key: value`` lines plus one-level nested maps (P0-AS v2-style ``metadata:``)."""
    lines = block.splitlines()
    meta: dict[str, Any] = {}
    i = 0
    while i < len(lines):
        raw_line = lines[i]
        line = raw_line.strip()
        if not line or line.startswith("#"):
            i += 1
            continue
        if ":" not in line:
            i += 1
            continue
        k, v = line.split(":", 1)
        key = k.strip()
        val_rest = v.strip()
        indent = len(raw_line) - len(raw_line.lstrip(" \t"))
        if val_rest == "" and raw_line.rstrip().endswith(":"):
            nested: dict[str, Any] = {}
            j = i + 1
            while j < len(lines):
                nraw = lines[j]
                if not nraw.strip():
                    j += 1
                    continue
                nind = len(nraw) - len(nraw.lstrip(" \t"))
                if nind > indent:
                    inn = nraw.strip()
                    if ":" in inn:
                        nk, nv = inn.split(":", 1)
                        nested[nk.strip()] = nv.strip().strip('"').strip("'")
                    j += 1
                    continue
                break
            if nested:
                meta[key] = nested
            i = j
            continue
        meta[key] = val_rest.strip('"').strip("'")
        i += 1
    return meta


def parse_yaml_like_frontmatter(raw: str) -> dict[str, Any]:
    """Parse a minimal ``key: value`` block after leading ``---``."""
    m = _FM_BLOCK.match(raw.lstrip("\ufeff"))
    if not m:
        return {}
    block = m.group(1)
    return _parse_fm_keys_and_nested(block)


def agentskills_compliant(meta: dict[str, Any], body: str) -> bool:
    name = str(meta.get("name") or "").strip()
    desc = str(meta.get("description") or "").strip()
    body_stripped = (body or "").strip()
    if not name or not desc or len(desc) < 8:
        return False
    if len(body_stripped) < 40:
        return False
    return True


def split_frontmatter_body(raw: str) -> tuple[dict[str, Any], str]:
    raw2 = raw.lstrip("\ufeff")
    m = _FM_BLOCK.match(raw2)
    if not m:
        return {}, raw2
    block = m.group(1)
    meta = _parse_fm_keys_and_nested(block)
    sm = re.search(r"(?m)^surfaces:\s*\[(.*?)\]\s*$", block)
    if sm:
        inner = sm.group(1) or ""
        meta["surfaces"] = [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
    return meta, raw2[m.end() :]
