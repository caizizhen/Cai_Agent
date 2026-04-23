from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any

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
        "anthropic_api_key",
        re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b"),
        "high",
        "high",
    ),
    (
        "openrouter_api_key",
        re.compile(r"\bsk-or-(?:v\d+-)?[A-Za-z0-9_\-]{20,}\b"),
        "high",
        "high",
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
    # M13：模型 profile / [llm] 段里把 api_key 以明文写死的高危告警。
    # 只匹配 `api_key = "..."` / `api_key: "..."`（非 api_key_env），避免误报
    # `api_key_env = "OPENAI_API_KEY"` 等安全写法。
    (
        "cai_profile_plaintext_api_key",
        re.compile(
            r"""(?ix)^\s*api_key\s*[:=]\s*['"][^'"\s]{1,}['"]""",
        ),
        "high",
        "high",
    ),
]

_DEFAULT_RULE_FLAGS = {
    "aws_access_key": True,
    "github_pat": True,
    "anthropic_api_key": True,
    "openrouter_api_key": True,
    "openai_like_key": True,
    "private_key_header": True,
    "cai_profile_plaintext_api_key": True,
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


_PROFILE_APIKEY_VALUE_RE = re.compile(
    r"""(?ix)api_key\s*[:=]\s*(['"])(?P<val>[^'"]*)\1""",
)

# 高风险供应商 key 前缀：若出现这些前缀，明文落盘就是真实泄漏。
_HIGH_RISK_PREFIXES = ("sk-ant-", "sk-or-", "sk-", "ghp_", "AKIA")

# 已知的本地/占位型值：LM Studio / Ollama / vLLM 等网关通常随便填，
# 这类值即使在 TOML 里出现也不算真实密钥泄漏。
_PLACEHOLDER_VALUES = frozenset(
    {
        "",
        "-",
        "none",
        "null",
        "empty",
        "placeholder",
        "local",
        "local-key",
        "lm-studio",
        "lmstudio",
        "ollama",
        "vllm",
        "dummy",
        "test",
        "optional-token",
        "your-copilot-proxy-token",
    },
)


def _line_context(line: str) -> str:
    s = line.lstrip()
    if s.startswith("#"):
        return "comment"
    if "add_argument(" in line and "help=" in line:
        return "help_literal"
    return "code"


def _classify_profile_apikey_value(line: str) -> tuple[bool, str | None]:
    """按 ``api_key = "<v>"`` 的值判定是否真实泄漏。

    Returns ``(is_real_leak, suppressed_reason_or_None)``。
    - 真实供应商前缀（``sk-ant- / sk-or- / sk- / ghp_ / AKIA``）→ 真实泄漏；
    - 已知占位符 / 空值 → 不算泄漏，`suppressed_reason=placeholder_value`；
    - 短（<20）且仅含 ``[a-zA-Z_-]`` → 视为占位符；
    - 其它 → 当作真实泄漏（保守）。
    """
    m = _PROFILE_APIKEY_VALUE_RE.search(line)
    if not m:
        return (True, None)
    val = (m.group("val") or "").strip()
    low = val.lower()
    for pref in _HIGH_RISK_PREFIXES:
        if val.startswith(pref):
            return (True, None)
    if low in _PLACEHOLDER_VALUES:
        return (False, "placeholder_value")
    if len(val) < 20 and re.fullmatch(r"[A-Za-z0-9_\-]*", val) and not any(c.isdigit() for c in val):
        return (False, "placeholder_value")
    return (True, None)


# 仅让 profile/[llm] 明文规则作用在这些扩展名上，避免对 Python 源码里
# 的普通 `api_key="k"` 字面量误报（它们不是用户的真实配置）。
_PROFILE_APIKEY_RULE_ALLOWED_EXTS = frozenset({".toml", ".yaml", ".yml", ".ini", ".conf"})


def _rule_applies_to_file(rule_id: str, rel_path: str) -> bool:
    if rule_id != "cai_profile_plaintext_api_key":
        return True
    rel_low = rel_path.lower()
    if any(rel_low.endswith(ext) for ext in _PROFILE_APIKEY_RULE_ALLOWED_EXTS):
        return True
    return False


def _effective_severity(
    rule_id: str,
    ctx: str,
    base_sev: str,
    base_conf: str,
    *,
    line: str | None = None,
) -> tuple[str, str, str | None]:
    """Return (severity, confidence, suppressed_reason or None)."""
    if ctx == "comment":
        return ("info", "low", f"suppressed_context_{ctx}")
    if ctx == "help_literal" and rule_id in (
        "aws_access_key",
        "github_pat",
        "openai_like_key",
        "anthropic_api_key",
        "openrouter_api_key",
    ):
        return ("info", "low", f"suppressed_context_{ctx}")
    if rule_id == "cai_profile_plaintext_api_key" and line is not None:
        is_real, reason = _classify_profile_apikey_value(line)
        if not is_real:
            return ("info", "low", reason or "placeholder_value")
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
                if not _rule_applies_to_file(rule_id, rel):
                    continue
                m = pattern.search(line)
                if not m:
                    continue
                sev, conf, suppressed = _effective_severity(
                    rule_id, ctx, base_sev, base_conf, line=line,
                )
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
        "schema_version": "security_scan_result_v1",
        "workspace": str(root),
        "ok": ok,
        "scanned_files": scanned_files,
        "excluded_globs": merged_excludes,
        "rule_flags": flags,
        "findings_count": len(findings),
        "findings": findings[:500],
    }


# ---------------------------------------------------------------------------
# PII / 敏感信息专项扫描（§22 补齐：面向 session/prompt 文件）
# ---------------------------------------------------------------------------

_PII_RULES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "credit_card",
        re.compile(
            r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}"
            r"|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12})\b"
        ),
        "high",
    ),
    (
        "cn_id_card",
        re.compile(r"\b[1-9]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b"),
        "high",
    ),
    (
        "cn_phone",
        re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
        "medium",
    ),
    (
        "us_ssn",
        re.compile(r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"),
        "high",
    ),
    (
        "email_address",
        re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"),
        "low",
    ),
    (
        "ipv4_private",
        re.compile(r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"),
        "low",
    ),
    (
        "jwt_token",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
        "high",
    ),
]

_DEFAULT_PII_RULE_FLAGS: dict[str, bool] = {
    "credit_card": True,
    "cn_id_card": True,
    "cn_phone": True,
    "us_ssn": True,
    "email_address": False,   # 邮箱信息量大，默认关闭，由调用方显式开启
    "ipv4_private": False,
    "jwt_token": True,
}

# 仅扫描这些扩展名的文件（session/prompt/日志类文件）
_PII_TARGET_EXTS: frozenset[str] = frozenset(
    {".json", ".jsonl", ".txt", ".log", ".md", ".csv", ".yaml", ".yml"}
)


def run_pii_scan(
    target: str | Path,
    *,
    rule_flags: dict[str, bool] | None = None,
    exclude_globs: list[str] | None = None,
    recursive: bool = True,
) -> dict[str, Any]:
    """对 prompt / session / 日志等文件执行 PII 敏感信息专项扫描。

    Args:
        target: 扫描目录或单个文件。
        rule_flags: 覆盖默认规则开关（key 为规则 ID，value 为 True/False）。
        exclude_globs: 额外排除 glob 模式。
        recursive: 是否递归扫描子目录（默认 True）。

    Returns:
        ``pii_scan_result_v1`` 结构。
    """
    base = Path(target).expanduser().resolve()
    flags = dict(_DEFAULT_PII_RULE_FLAGS)
    if rule_flags:
        flags.update(rule_flags)
    merged_excludes: list[str] = list(exclude_globs or [])
    ignore_names = {".git", ".venv", "__pycache__", "node_modules"}

    def _iter_files() -> list[Path]:
        if base.is_file():
            return [base]
        pattern = "**/*" if recursive else "*"
        return [p for p in base.glob(pattern) if p.is_file()]

    findings: list[dict[str, Any]] = []
    scanned_files = 0

    for p in _iter_files():
        if any(part in ignore_names for part in p.parts):
            continue
        try:
            rel = p.relative_to(base).as_posix() if not base.is_file() else p.name
        except ValueError:
            rel = p.name
        if _should_skip(rel, merged_excludes):
            continue
        if p.suffix.lower() not in _PII_TARGET_EXTS:
            continue
        if not _is_text_file(p, 1_048_576):  # 1 MB 上限
            continue
        scanned_files += 1
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines, start=1):
            for rule_id, pattern, sev in _PII_RULES:
                if not flags.get(rule_id, False):
                    continue
                m = pattern.search(line)
                if not m:
                    continue
                snippet = line.strip()[:200]
                findings.append(
                    {
                        "severity": sev,
                        "rule": rule_id,
                        "file": rel,
                        "line": i,
                        "match": m.group(0)[:60],
                        "snippet": snippet,
                    }
                )

    high_count = sum(1 for f in findings if f.get("severity") == "high")
    return {
        "schema_version": "pii_scan_result_v1",
        "target": str(base),
        "recursive": recursive,
        "rule_flags": flags,
        "excluded_globs": merged_excludes,
        "scanned_files": scanned_files,
        "findings_count": len(findings),
        "high_count": high_count,
        "ok": high_count == 0,
        "findings": findings[:1000],
    }
