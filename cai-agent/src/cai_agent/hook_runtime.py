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


def _hooks_file_default(settings: Settings) -> Path:
    return _project_root(settings) / "hooks" / "hooks.json"


def resolve_hooks_json_path(
    settings: Settings,
    *,
    hooks_dir: str | None = None,
) -> Path | None:
    """解析项目内 `hooks.json` 路径。

    默认顺序：`hooks/hooks.json` → `.cai/hooks/hooks.json`。
    若传入 ``hooks_dir``（相对项目根），则优先使用 ``<hooks_dir>/hooks.json``。
    """
    root = _project_root(settings)
    candidates: list[Path] = []
    rel = (hooks_dir or "").strip().replace("\\", "/")
    if rel:
        candidates.append((root / rel).resolve())
    candidates.append(_hooks_file_default(settings))
    candidates.append((root / ".cai" / "hooks" / "hooks.json").resolve())
    for base in candidates:
        p = base if base.name == "hooks.json" else base / "hooks.json"
        if p.is_file():
            return p
    return None


def _disabled_ids(settings: Settings) -> frozenset[str]:
    return frozenset(x.lower() for x in settings.hooks_disabled_ids if x.strip())


def _load_hooks_doc(
    settings: Settings,
    *,
    hooks_path: Path | None = None,
) -> dict[str, Any] | None:
    p = hooks_path or resolve_hooks_json_path(settings)
    if p is None or not p.is_file():
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


def enabled_hook_ids(
    settings: Settings,
    event: str,
    *,
    hooks_path: Path | None = None,
) -> list[str]:
    doc = _load_hooks_doc(settings, hooks_path=hooks_path)
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


def _classify_hook_for_event(
    settings: Settings,
    event: str,
    h: dict[str, Any],
    *,
    dry_run: bool,
) -> dict[str, Any] | None:
    """单条 hook 在指定 event 下的分类；不匹配 event 返回 None。"""
    if str(h.get("event", "")).strip() != event:
        return None
    hid = str(h.get("id", "")).strip()
    if not hid:
        return {
            "id": "?",
            "status": "skipped",
            "reason": "missing_hook_id",
        }
    disabled = _disabled_ids(settings)
    if hid.lower() in disabled:
        return {"id": hid, "status": "skipped", "reason": "disabled_by_config"}
    if not bool(h.get("enabled", True)):
        return {"id": hid, "status": "skipped", "reason": "hook_disabled"}
    argv = _hook_command_argv(h)
    if argv is None:
        return {"id": hid, "status": "skipped", "reason": "no_command"}
    profile = settings.hooks_profile.strip().lower()
    if profile not in ("minimal", "standard", "strict"):
        profile = "standard"
    if profile == "minimal":
        return {"id": hid, "status": "skipped", "reason": "hooks.profile=minimal"}
    strict = profile == "strict"
    if _command_looks_dangerous(argv, strict=strict):
        return {"id": hid, "status": "blocked", "reason": "dangerous_command_pattern"}
    if dry_run:
        return {"id": hid, "status": "planned", "reason": "would_execute"}
    return {"id": hid, "status": "_run"}


def preview_project_hooks(
    settings: Settings,
    event: str,
    *,
    hooks_path: Path | None = None,
) -> list[dict[str, Any]]:
    """不执行子进程：返回若调用 `run_project_hooks` 时各 hook 的预期状态（planned/skipped/blocked）。"""
    doc = _load_hooks_doc(settings, hooks_path=hooks_path)
    if doc is None:
        return []
    hooks = doc.get("hooks")
    if not isinstance(hooks, list):
        return []
    out: list[dict[str, Any]] = []
    for h in hooks:
        if not isinstance(h, dict):
            continue
        row = _classify_hook_for_event(settings, event, h, dry_run=True)
        if row is None:
            continue
        out.append(row)
    return out


def describe_hooks_catalog(
    settings: Settings,
    *,
    hooks_path: Path | None = None,
) -> dict[str, Any]:
    """列出 hooks.json 中全部条目及在当前 profile/禁用列表下的摘要。"""
    p = hooks_path or resolve_hooks_json_path(settings)
    doc = _load_hooks_doc(settings, hooks_path=p)
    if doc is None:
        return {
            "schema_version": "hooks_catalog_v1",
            "hooks_file": str(p) if p is not None else None,
            "hooks_profile": settings.hooks_profile.strip().lower() or "standard",
            "hooks": [],
            "error": "hooks_json_not_found",
        }
    hooks = doc.get("hooks")
    if not isinstance(hooks, list):
        return {
            "schema_version": "hooks_catalog_v1",
            "hooks_file": str(p),
            "hooks_profile": settings.hooks_profile.strip().lower() or "standard",
            "hooks": [],
            "error": "invalid_hooks_document",
        }
    disabled = _disabled_ids(settings)
    profile = settings.hooks_profile.strip().lower()
    if profile not in ("minimal", "standard", "strict"):
        profile = "standard"
    rows: list[dict[str, Any]] = []
    for h in hooks:
        if not isinstance(h, dict):
            continue
        hid = str(h.get("id", "")).strip()
        ev = str(h.get("event", "")).strip()
        en = bool(h.get("enabled", True))
        argv = _hook_command_argv(h)
        has_cmd = argv is not None
        dis = bool(hid and hid.lower() in disabled)
        skip_reason: str | None = None
        if not hid:
            skip_reason = "missing_hook_id"
        elif dis:
            skip_reason = "disabled_by_config"
        elif not en:
            skip_reason = "hook_disabled"
        elif not has_cmd:
            skip_reason = "no_command"
        elif profile == "minimal":
            skip_reason = "hooks.profile=minimal"
        elif has_cmd and argv is not None:
            strict = profile == "strict"
            if _command_looks_dangerous(argv, strict=strict):
                skip_reason = "would_block_dangerous_command_pattern"
        rows.append(
            {
                "id": hid or None,
                "event": ev or None,
                "enabled": en,
                "has_command": has_cmd,
                "disabled_by_config": dis,
                "skip_or_block_reason": skip_reason,
            },
        )
    return {
        "schema_version": "hooks_catalog_v1",
        "hooks_file": str(p),
        "hooks_profile": profile,
        "hooks": rows,
    }


def run_project_hooks(
    settings: Settings,
    event: str,
    payload: dict[str, Any] | None,
    *,
    hooks_path: Path | None = None,
) -> list[dict[str, Any]]:
    """执行 hooks.json 中匹配 event 且含 command 数组的外部钩子（受 profile / 禁用 / 安全规则约束）。"""
    doc = _load_hooks_doc(settings, hooks_path=hooks_path)
    if doc is None:
        return []
    hooks = doc.get("hooks")
    if not isinstance(hooks, list):
        return []
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
        row = _classify_hook_for_event(settings, event, h, dry_run=False)
        if row is None:
            continue
        if row.get("status") != "_run":
            results.append(row)
            continue
        hid = str(row.get("id", "")).strip()
        argv = _hook_command_argv(h)
        if argv is None:
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
