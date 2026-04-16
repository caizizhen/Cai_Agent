from __future__ import annotations

import fnmatch
from pathlib import Path

from cai_agent.config import Settings

_PATTERNS: list[tuple[str, str, str, str]] = [
    ("high", "medium", "aws_access_key", "AKIA"),
    ("high", "medium", "github_pat", "ghp_"),
    ("high", "medium", "openai_like_key", "sk-"),
    ("high", "low", "private_key_header", "-----BEGIN"),
]
_PATTERN_FLAGS = {
    "aws_access_key": True,
    "github_pat": True,
    "openai_like_key": True,
    "private_key_header": True,
}


def _is_text_file(path: Path, max_bytes: int) -> bool:
    try:
        if path.stat().st_size > max_bytes:
            return False
        data = path.read_bytes()
    except OSError:
        return False
    if b"\x00" in data:
        return False
    return True


def _should_skip(rel: str, exclude_globs: list[str]) -> bool:
    for pat in exclude_globs:
        if fnmatch.fnmatch(rel, pat):
            return True
    return False


def run_security_scan(
    settings: Settings,
    *,
    exclude_globs: list[str] | None = None,
    rule_flags: dict[str, bool] | None = None,
) -> dict[str, object]:
    root = Path(settings.workspace).resolve()
    findings: list[dict[str, object]] = []
    scanned_files = 0
    max_bytes = 512_000
    ignore_names = {".git", ".venv", "__pycache__", "node_modules"}
    if exclude_globs is None:
        exclude_globs = list(settings.security_scan_exclude_globs)
    if rule_flags is None:
        rule_flags = dict(_PATTERN_FLAGS)
    # 默认排除规则/文档中的示例字符串，减少自匹配误报
    defaults = [
        "cai-agent/src/cai_agent/security_scan.py",
        "commands/security-scan.md",
        "skills/security-scan-light.md",
        "docs/**",
    ]
    merged_excludes = defaults + [g for g in exclude_globs if g]

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in ignore_names for part in p.parts):
            continue
        rel = p.relative_to(root).as_posix()
        if _should_skip(rel, merged_excludes):
            continue
        if not _is_text_file(p, max_bytes):
            continue
        scanned_files += 1
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines, start=1):
            for severity, confidence, rule, token in _PATTERNS:
                if not bool(rule_flags.get(rule, True)):
                    continue
                if token in line:
                    findings.append(
                        {
                            "severity": severity,
                            "confidence": confidence,
                            "rule": rule,
                            "token": token,
                            "file": rel,
                            "line": i,
                            "snippet": line[:220],
                        },
                    )

    ok = len(findings) == 0
    return {
        "workspace": str(root),
        "ok": ok,
        "scanned_files": scanned_files,
        "excluded_globs": merged_excludes,
        "rule_flags": rule_flags,
        "findings_count": len(findings),
        "findings": findings[:500],
    }
