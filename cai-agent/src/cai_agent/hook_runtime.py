from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from cai_agent.config import Settings


def _project_root(settings: Settings) -> Path:
    if settings.config_loaded_from:
        return Path(settings.config_loaded_from).expanduser().resolve().parent
    return Path.cwd().resolve()


def _hooks_file(settings: Settings) -> Path:
    return _project_root(settings) / "hooks" / "hooks.json"


def _disabled_ids(settings: Settings) -> frozenset[str]:
    return frozenset(x.lower() for x in settings.hooks_disabled_ids if x.strip())


def _load_hooks_doc(settings: Settings) -> dict[str, Any] | None:
    p = _hooks_file(settings)
    if not p.is_file():
        return None
    try:
        obj: Any = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def _hook_command_argv(hook: dict[str, Any]) -> list[str] | None:
    raw = hook.get("command")
    if isinstance(raw, list) and raw and all(isinstance(x, str) for x in raw):
        return [str(x) for x in raw]
    return None


_DANGEROUS_STANDARD = (
    "rm -rf",
    "rm / ",
    "rm /\n",
    "mkfs",
    "dd if=",
    ":(){",
    "| bash",
    "curl ",
    "wget ",
    "powershell -e",
    "certutil",
    "format ",
    "del /f",
    "rmdir /s",
    "shutdown",
    "reboot",
)

_DANGEROUS_STRICT_EXTRA = (
    "&&",
    "||",
    ";rm",
    "invoke-expression",
    "bitsadmin",
    "regsvr32",
)


def _command_looks_dangerous(argv: list[str], *, strict: bool) -> bool:
    joined = " ".join(argv).lower()
    for frag in _DANGEROUS_STANDARD:
        if frag in joined:
            return True
    if strict:
        for frag in _DANGEROUS_STRICT_EXTRA:
            if frag in joined:
                return True
    return False


def enabled_hook_ids(settings: Settings, event: str) -> list[str]:
    doc = _load_hooks_doc(settings)
    if doc is None:
        return []
    hooks = doc.get("hooks")
    if not isinstance(hooks, list):
        return []
    disabled = _disabled_ids(settings)
    out: list[str] = []
    for h in hooks:
        if not isinstance(h, dict):
            continue
        if str(h.get("event", "")).strip() != event:
            continue
        if not bool(h.get("enabled", True)):
            continue
        hid = str(h.get("id", "")).strip()
        if not hid:
            continue
        if hid.lower() in disabled:
            continue
        out.append(hid)
    return out


def run_project_hooks(
    settings: Settings,
    event: str,
    payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """执行 hooks.json 中匹配 event 且含 command 数组的外部钩子（受 profile / 禁用 / 安全规则约束）。"""
    doc = _load_hooks_doc(settings)
    if doc is None:
        return []
    hooks = doc.get("hooks")
    if not isinstance(hooks, list):
        return []
    disabled = _disabled_ids(settings)
    profile = settings.hooks_profile.strip().lower()
    if profile not in ("minimal", "standard", "strict"):
        profile = "standard"
    timeout = float(settings.hooks_timeout_sec)
    if profile == "strict":
        timeout = min(timeout, 20.0)
    root = _project_root(settings)
    env_base = os.environ.copy()
    env_base["CAI_HOOK_EVENT"] = event
    try:
        env_base["CAI_HOOK_PAYLOAD"] = json.dumps(payload or {}, ensure_ascii=False)[:8192]
    except Exception:
        env_base["CAI_HOOK_PAYLOAD"] = "{}"
    env_base["CAI_HOOK_WORKSPACE"] = str(root)
    results: list[dict[str, Any]] = []
    for h in hooks:
        if not isinstance(h, dict):
            continue
        if str(h.get("event", "")).strip() != event:
            continue
        if not bool(h.get("enabled", True)):
            continue
        hid = str(h.get("id", "")).strip()
        if not hid or hid.lower() in disabled:
            continue
        argv = _hook_command_argv(h)
        if argv is None:
            continue
        if profile == "minimal":
            results.append(
                {"id": hid, "status": "skipped", "reason": "hooks.profile=minimal"},
            )
            continue
        strict = profile == "strict"
        if _command_looks_dangerous(argv, strict=strict):
            results.append(
                {"id": hid, "status": "blocked", "reason": "dangerous_command_pattern"},
            )
            continue
        try:
            cp = subprocess.run(
                argv,
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
                env=env_base,
            )
            results.append(
                {
                    "id": hid,
                    "status": "ok" if cp.returncode == 0 else "error",
                    "returncode": cp.returncode,
                    "stdout": (cp.stdout or "")[:4000],
                    "stderr": (cp.stderr or "")[:4000],
                },
            )
        except subprocess.TimeoutExpired:
            results.append({"id": hid, "status": "error", "reason": "timeout"})
        except OSError as e:
            results.append({"id": hid, "status": "error", "reason": str(e)})
    return results
