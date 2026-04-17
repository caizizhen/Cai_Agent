from __future__ import annotations

import fnmatch
import re
from pathlib import Path

from cai_agent.config import Settings

# (rule_id, regex, base_severity, base_confidence)
_RULES: list[tuple[str, re.Pattern[str], str, str]] = [
    (
        "aws_access_key",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "high",
        "medium",
    ),
    (
        "github_pat",
        re.compile(r"\bghp_[A-Za-z0-9]{36,}\b"),
        "high",
        "medium",
    ),
    (
        "openai_like_key",
        re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
        "high",
        "medium",
    ),
    (
        "private_key_header",
        re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        "high",
        "low",
    ),
]

_DEFAULT_RULE_FLAGS = {
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


def _line_context(line: str) -> str:
    s = line.lstrip()
    if s.startswith("#"):
        return "comment"
    if "add_argument(" in line and "help=" in line:
        return "help_literal"
    return "code"


def _effective_severity(rule_id: str, ctx: str, base_sev: str, base_conf: str) -> tuple[str, str, str | None]:
    """Return (severity, confidence, suppressed_reason or None)."""
    if ctx == "comment":
        return ("info", "low", f"suppressed_context_{ctx}")
    if ctx == "help_literal" and rule_id in ("aws_access_key", "github_pat", "openai_like_key"):
        return ("info", "low", f"suppressed_context_{ctx}")
    return (base_sev, base_conf, None)


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

    cfg_excludes = list(settings.security_scan_exclude_globs)
    if exclude_globs is None:
        extra: list[str] = []
    else:
        extra = [g for g in exclude_globs if g]
    merged_excludes = list(cfg_excludes) + extra

    flags = dict(_DEFAULT_RULE_FLAGS)
    flags.update(dict(settings.security_scan_rule_overrides))
    if rule_flags:
        flags.update(rule_flags)

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
            ctx = _line_context(line)
            for rule_id, pattern, base_sev, base_conf in _RULES:
                if not bool(flags.get(rule_id, True)):
                    continue
                m = pattern.search(line)
                if not m:
                    continue
                sev, conf, suppressed = _effective_severity(rule_id, ctx, base_sev, base_conf)
                if suppressed and sev == "info":
                    continue
                findings.append(
                    {
                        "severity": sev,
                        "confidence": conf,
                        "rule": rule_id,
                        "context": ctx,
                        "file": rel,
                        "line": i,
                        "match": m.group(0)[:80],
                        "snippet": line[:220],
                        "suppressed_reason": suppressed,
                    },
                )

    blocking = [f for f in findings if str(f.get("severity")) == "high"]
    ok = len(blocking) == 0
    return {
        "workspace": str(root),
        "ok": ok,
        "scanned_files": scanned_files,
        "excluded_globs": merged_excludes,
        "rule_flags": flags,
        "findings_count": len(findings),
        "findings": findings[:500],
    }
