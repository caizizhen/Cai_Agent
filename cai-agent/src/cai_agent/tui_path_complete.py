"""TUI 斜杠命令「路径补全」：/load、/save 后的相对 / 绝对路径。

路径必须解析后落在任一 ``root`` 目录之下（``Path.is_relative_to``），禁止跳出根目录。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

MAX_LIST_ENTRIES = 800


def _norm_seps(s: str) -> str:
    return s.replace("\\", "/")


def split_dir_fragment(suffix: str) -> tuple[str, str]:
    """(父路径 posix 片段, 最后一级名称前缀)。分隔符统一为 ``/``。"""
    s = _norm_seps(suffix)
    if not s:
        return "", ""
    if s.endswith("/"):
        core = s[:-1].strip("/")
        return (core, "") if core else ("", "")
    if "/" not in s:
        return "", s
    parent, frag = s.rsplit("/", 1)
    return parent, frag


def safe_descendant(root: Path, posix_rel: str) -> Path | None:
    """``posix_rel`` 用 ``/`` 分段；任一步跳出 ``root`` 则 ``None``。"""
    root_r = root.resolve()
    cur = root_r
    rel = posix_rel.replace("\\", "/").strip("/")
    if not rel:
        return root_r
    for part in rel.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            cur = cur.parent
        else:
            cur = cur / part
        try:
            cur2 = cur.resolve()
            cur2.relative_to(root_r)
        except (ValueError, OSError):
            return None
        cur = cur2
    return cur


def _is_abs_path(s: str) -> bool:
    sn = s.strip()
    if not sn:
        return False
    if Path(sn).is_absolute():
        return True
    return os.name == "nt" and len(sn) >= 2 and sn[1] == ":"


def listing_target(roots: Sequence[Path], suffix: str) -> tuple[Path, str] | None:
    """返回 ``(要列举的目录, 名称前缀)``；无法安全列举时 ``None``。"""
    if not roots:
        return None
    sn = _norm_seps(suffix.strip())
    if not sn:
        return roots[0].resolve(), ""

    if _is_abs_path(suffix.strip()):
        parent_rel, frag = split_dir_fragment(sn)
        if sn.endswith("/") and not frag:
            dir_p = Path(sn.rstrip("/"))
        elif parent_rel:
            dir_p = Path(parent_rel)
        else:
            p = Path(suffix.strip())
            dir_p = p.parent
        try:
            dp = dir_p.resolve()
        except OSError:
            return None
        if not dp.is_dir():
            return None
        for root in roots:
            try:
                dp.relative_to(root.resolve())
            except ValueError:
                continue
            return dp, frag
        return None

    parent_rel, frag = split_dir_fragment(sn)
    for root in roots:
        base = safe_descendant(root, parent_rel)
        if base is not None and base.is_dir():
            return base, frag
    return None


def _build_new_suffix_from_parts(parent_posix: str, entry_name: str, is_dir: bool) -> str:
    """``parent_posix`` 为相对于根的路径（无首尾 ``/``）；在其下追加 ``entry_name``。"""
    p = parent_posix.replace("\\", "/").strip("/")
    if p:
        tail = f"{p}/{entry_name}"
    else:
        tail = entry_name
    if is_dir:
        tail += "/"
    return tail


def suggest_path_after_command(
    *,
    cmd_prefix: str,
    line_value: str,
    roots: Sequence[Path],
    filter_json_files_only: bool,
) -> str | None:
    """返回整条输入补全，或 ``None``。"""
    if not line_value.startswith(cmd_prefix) or not roots:
        return None
    suffix = line_value[len(cmd_prefix) :]
    if not suffix.strip():
        return None

    picked = listing_target(roots, suffix)
    if picked is None:
        return None
    list_dir, fragment = picked
    sn = _norm_seps(suffix.strip())
    parent_rel, _frag2 = split_dir_fragment(sn)

    try:
        entries = sorted(
            list(list_dir.iterdir()),
            key=lambda e: (e.is_file(), e.name.lower()),
        )
    except OSError:
        return None

    n = 0
    for e in entries:
        n += 1
        if n > MAX_LIST_ENTRIES:
            break
        if e.name.startswith(".") and not fragment.startswith("."):
            continue
        if fragment and not e.name.startswith(fragment):
            continue
        if filter_json_files_only and e.is_file() and not e.name.endswith(".json"):
            continue
        new_suffix = _build_new_suffix_from_parts(parent_rel, e.name, e.is_dir())
        cand = cmd_prefix + new_suffix
        c0 = _norm_seps(cand)
        v0 = _norm_seps(line_value)
        if c0.startswith(v0) and len(cand) > len(line_value):
            return cand
    return None
