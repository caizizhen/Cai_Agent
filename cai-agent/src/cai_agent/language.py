from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List


@dataclass(frozen=True)
class LanguageAdapter:
    """多语言代码分析的最小抽象层."""

    name: str
    extensions: tuple[str, ...]

    def matches_file(self, path: Path) -> bool:
        return path.suffix.lower() in self.extensions


_LANG_REGISTRY: Dict[str, LanguageAdapter] = {}


def register_language(adapter: LanguageAdapter) -> None:
    _LANG_REGISTRY[adapter.name] = adapter


def get_language(name: str) -> LanguageAdapter | None:
    return _LANG_REGISTRY.get(name)


def guess_language_for_file(path: str | Path) -> LanguageAdapter | None:
    p = Path(path)
    for adapter in _LANG_REGISTRY.values():
        if adapter.matches_file(p):
            return adapter
    return None


def list_languages() -> List[LanguageAdapter]:
    return sorted(_LANG_REGISTRY.values(), key=lambda a: a.name)


# 预注册常见语言适配器，后续可扩展 AST / 依赖解析能力。
register_language(LanguageAdapter(name="python", extensions=(".py",)))
register_language(LanguageAdapter(name="typescript", extensions=(".ts", ".tsx")))
register_language(LanguageAdapter(name="javascript", extensions=(".js", ".jsx")))
register_language(LanguageAdapter(name="go", extensions=(".go",)))
register_language(LanguageAdapter(name="java", extensions=(".java",)))

