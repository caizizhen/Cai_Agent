from __future__ import annotations

from pathlib import Path
from typing import Iterable

from cai_agent.config import Settings


def _read_text_files(paths: Iterable[Path]) -> list[str]:
    chunks: list[str] = []
    for p in paths:
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        text = text.strip()
        if text:
            chunks.append(text)
    return chunks


def _project_root_from_settings(settings: Settings) -> Path:
    """
    Best-effort project 根目录推断：
    - 优先使用配置文件所在目录；
    - 否则使用当前工作目录。
    """
    if settings.config_loaded_from:
        return Path(settings.config_loaded_from).expanduser().resolve().parent
    return Path.cwd()


def load_rule_text(settings: Settings) -> str:
    """
    加载 rules/ 下的通用规则文本，供 plan 阶段注入到 system prompt。

    当前实现策略：
    - 仅在项目根目录（推断自配置文件）下查找 rules/；
    - 读取 rules/common/*.md 与 rules/python/*.md；
    - 将所有文本拼接为一个简短说明块。
    """
    root = _project_root_from_settings(settings)
    rules_dir = root / "rules"
    if not rules_dir.is_dir():
        return ""

    common_dir = rules_dir / "common"
    python_dir = rules_dir / "python"
    chunks: list[str] = []

    if common_dir.is_dir():
        common_files = sorted(common_dir.glob("*.md"))
        chunks.extend(_read_text_files(common_files))

    if python_dir.is_dir():
        py_files = sorted(python_dir.glob("*.md"))
        chunks.extend(_read_text_files(py_files))

    if not chunks:
        return ""

    text = "\n\n".join(chunks)
    # 简单截断，避免 plan 提示过长
    if len(text) > 8000:
        text = text[:8000] + "\n\n...[规则文本已截断]"
    return text

