from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from cai_agent.config import Settings
from cai_agent.ecc_layout import iter_hooks_json_paths


def _project_root(settings: Settings) -> Path:
    if settings.config_loaded_from:
        return Path(settings.config_loaded_from).expanduser().resolve().parent
    return Path.cwd().resolve()


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
    for p in iter_hooks_json_paths(root, hooks_dir=hooks_dir):
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


def _hook_script_argv(
    hook: dict[str, Any],
    *,
    hooks_file: Path,
    project_root: Path,
) -> tuple[list[str] | None, str | None]:
    """将 ``script`` 解析为可执行 argv；路径相对 ``hooks.json`` 所在目录且必须在项目根下。"""
    raw = hook.get("script")
    if not isinstance(raw, str) or not raw.strip():
        return None, None
    rel = raw.strip().replace("\\", "/")
    candidate = (hooks_file.parent / rel).resolve()
    try:
        candidate.relative_to(project_root.resolve())
    except ValueError:
        return None, "script_outside_workspace"
    if not candidate.is_file():
        return None, "script_missing"
    ext = candidate.suffix.lower()
    if ext == ".py":
        return [sys.executable, str(candidate)], None
    if ext == ".sh":
        if sys.platform == "win32":
            sh = shutil.which("bash") or shutil.which("sh")
            if not sh:
                return None, "script_runner_missing"
            return [sh, str(candidate)], None
        return ["/bin/sh", str(candidate)], None
    if ext == ".ps1" and sys.platform == "win32":
        pw = shutil.which("powershell.exe") or shutil.which("pwsh")
        if not pw:
            return None, "script_runner_missing"
        return [str(pw), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(candidate)], None
    if sys.platform == "win32" and ext in (".cmd", ".bat"):
        return ["cmd.exe", "/c", str(candidate)], None
    return [str(candidate)], None


def _hook_argv_for_hook(
    hook: dict[str, Any],
    *,
    hooks_file: Path | None,
    project_root: Path,
) -> tuple[list[str] | None, str | None]:
    """优先 ``command``；否则尝试 ``script``（需能解析 ``hooks.json`` 路径）。"""
    cmd = _hook_command_argv(hook)
    if cmd is not None:
        return cmd, None
    if hooks_file is None:
        return None, "no_command"
    return _hook_script_argv(hook, hooks_file=hooks_file, project_root=project_root)


def _normalize_hook_argv_for_platform(argv: list[str]) -> list[str]:
    """在 Windows 上将 hooks.json 中的 POSIX 路径转为原生路径，便于 subprocess 定位脚本/解释器。"""
    if sys.platform != "win32":
        return argv
    out: list[str] = []
    for part in argv:
        if "/" not in part and "\\" not in part:
            out.append(part)
            continue
        try:
            p = Path(part)
            out.append(str(p))
        except (OSError, ValueError):
            out.append(part)
    return out


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
    """列出在当前 profile / 禁用列表 / 安全规则下**将会执行**（非 skipped/blocked）的 hook id。

    与 `run_project_hooks` / `preview_project_hooks` 的分类规则一致，避免状态行误报。
    """
    doc = _load_hooks_doc(settings, hooks_path=hooks_path)
    if doc is None:
        return []
    hooks = doc.get("hooks")
    if not isinstance(hooks, list):
        return []
    hf = hooks_path or resolve_hooks_json_path(settings)
    root = _project_root(settings)
    out: list[str] = []
    for h in hooks:
        if not isinstance(h, dict):
            continue
        row = _classify_hook_for_event(
            settings,
            event,
            h,
            dry_run=False,
            hooks_file=hf,
            project_root=root,
        )
        if row is None:
            continue
        if row.get("status") != "_run":
            continue
        hid = str(row.get("id", "")).strip()
        if hid:
            out.append(hid)
    return out


def _classify_hook_for_event(
    settings: Settings,
    event: str,
    h: dict[str, Any],
    *,
    dry_run: bool,
    hooks_file: Path | None = None,
    project_root: Path | None = None,
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
    root = project_root or _project_root(settings)
    argv, scr_reason = _hook_argv_for_hook(h, hooks_file=hooks_file, project_root=root)
    if argv is None:
        reason = scr_reason or "no_command"
        return {"id": hid, "status": "skipped", "reason": reason}
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
    hf = hooks_path or resolve_hooks_json_path(settings)
    root = _project_root(settings)
    out: list[dict[str, Any]] = []
    for h in hooks:
        if not isinstance(h, dict):
            continue
        row = _classify_hook_for_event(
            settings,
            event,
            h,
            dry_run=True,
            hooks_file=hf,
            project_root=root,
        )
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
    root = _project_root(settings)
    rows: list[dict[str, Any]] = []
    for h in hooks:
        if not isinstance(h, dict):
            continue
        hid = str(h.get("id", "")).strip()
        ev = str(h.get("event", "")).strip()
        en = bool(h.get("enabled", True))
        argv, _sr = _hook_argv_for_hook(h, hooks_file=p, project_root=root)
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
            skip_reason = _sr or "no_command"
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
                "has_script": bool(isinstance(h.get("script"), str) and str(h.get("script")).strip()),
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
    """执行 hooks.json 中匹配 event 且含 ``command`` 或可解析 ``script`` 的外部钩子（受 profile / 禁用 / 安全规则约束）。"""
    doc = _load_hooks_doc(settings, hooks_path=hooks_path)
    if doc is None:
        return []
    hooks = doc.get("hooks")
    if not isinstance(hooks, list):
        return []
    hooks_file = hooks_path or resolve_hooks_json_path(settings)
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
        row = _classify_hook_for_event(
            settings,
            event,
            h,
            dry_run=False,
            hooks_file=hooks_file,
            project_root=root,
        )
        if row is None:
            continue
        if row.get("status") != "_run":
            results.append(row)
            continue
        hid = str(row.get("id", "")).strip()
        argv, _ = _hook_argv_for_hook(h, hooks_file=hooks_file, project_root=root)
        if argv is None:
            continue
        argv = _normalize_hook_argv_for_platform(argv)
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
