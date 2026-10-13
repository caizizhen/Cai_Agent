"""Helpers for Web UI APIs (workspace tree, settings, runtime)."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from cai_agent.config import Settings, normalize_base_url
from cai_agent.paths import cai_home
from cai_agent.sandbox import SandboxError, resolve_workspace_path

SKIP_DIRS = {
    ".git",
    ".hg",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".cai",
    "dist",
    "build",
    ".egg-info",
}


def settings_path() -> Path:
    return cai_home() / "ui_settings.json"


def load_settings() -> dict[str, Any]:
    path = settings_path()
    defaults = {
        "theme": "dark",
        "approval": "auto",
        "sidebar_tab": "sessions",
    }
    if not path.is_file():
        return dict(defaults)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            defaults.update(data)
    except Exception:
        pass
    return defaults


def save_settings(patch: dict[str, Any]) -> dict[str, Any]:
    cur = load_settings()
    cur.update({k: v for k, v in patch.items() if v is not None})
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")
    return cur


def runtime_path() -> Path:
    return cai_home() / "runtime.json"


def load_runtime_file() -> dict[str, Any]:
    """Load persisted runtime overrides from ``$CAI_HOME/runtime.json``."""
    path = runtime_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_runtime_file(patch: dict[str, Any]) -> dict[str, Any]:
    """Merge and persist runtime overrides."""
    cur = load_runtime_file()
    for k, v in patch.items():
        if v is None:
            continue
        if k == "api_key" and isinstance(v, str) and v.strip() in ("", "********"):
            continue  # keep existing secret
        if k == "models" and isinstance(v, list):
            cur[k] = _merge_models_list(cur.get("models"), v)
            continue
        cur[k] = v
    # If caller patches top-level model fields, keep the active profile in sync
    # (do not sync-from-profile first — that would clobber the new top-level values).
    top_keys = {"provider", "base_url", "model", "api_key", "model_name"}
    if top_keys & set(patch.keys()) and "models" not in patch:
        models = list(cur.get("models") or []) if isinstance(cur.get("models"), list) else []
        active = str(cur.get("active_model_id") or "")
        if not models:
            boot = _profile_from_top(cur)
            cur["models"] = [boot]
            cur["active_model_id"] = boot["id"]
        else:
            updated = []
            matched = False
            for m in models:
                if not isinstance(m, dict):
                    continue
                if (not matched) and (str(m.get("id")) == active or not active):
                    provider = str(cur.get("provider") or m.get("provider") or "openai").lower()
                    if provider not in ("openai", "anthropic"):
                        provider = "openai"
                    key = cur.get("api_key")
                    if key is None or (isinstance(key, str) and key.strip() in ("", "********")):
                        key = m.get("api_key") or ""
                    pid = str(m.get("id") or uuid.uuid4().hex)
                    updated.append(
                        {
                            "id": pid,
                            "name": str(cur.get("model_name") or m.get("name") or cur.get("model") or "model"),
                            "provider": provider,
                            "base_url": normalize_base_url(
                                str(cur.get("base_url") or m.get("base_url") or ""),
                                provider,
                            ),
                            "model": str(cur.get("model") or m.get("model") or ""),
                            "api_key": str(key or ""),
                        },
                    )
                    cur["active_model_id"] = pid
                    matched = True
                else:
                    updated.append(m)
            cur["models"] = updated
    cur = _sync_active_from_models(cur)
    path = runtime_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")
    return cur


def mask_api_key(key: str) -> str:
    if not key or key in ("lm-studio",):
        return key
    if len(key) <= 8:
        return "********"
    return key[:3] + "********" + key[-2:]


def _profile_from_top(rt: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(rt.get("active_model_id") or "default"),
        "name": str(rt.get("model_name") or rt.get("model") or "default"),
        "provider": str(rt.get("provider") or "openai"),
        "base_url": str(rt.get("base_url") or ""),
        "model": str(rt.get("model") or ""),
        "api_key": str(rt.get("api_key") or ""),
    }


def _merge_models_list(existing: Any, incoming: list[Any]) -> list[dict[str, Any]]:
    old_by_id: dict[str, dict[str, Any]] = {}
    if isinstance(existing, list):
        for row in existing:
            if isinstance(row, dict) and row.get("id"):
                old_by_id[str(row["id"])] = row
    out: list[dict[str, Any]] = []
    for row in incoming:
        if not isinstance(row, dict):
            continue
        pid = str(row.get("id") or uuid.uuid4().hex)
        prev = old_by_id.get(pid) or {}
        key = row.get("api_key")
        if key is None or (isinstance(key, str) and key.strip() in ("", "********")):
            key = prev.get("api_key") or ""
        provider = str(row.get("provider") or prev.get("provider") or "openai").lower()
        if provider not in ("openai", "anthropic"):
            provider = "openai"
        model_id = str(row.get("model") or prev.get("model") or "")
        out.append(
            {
                "id": pid,
                "name": str(row.get("name") or prev.get("name") or model_id or "model"),
                "provider": provider,
                "base_url": normalize_base_url(
                    str(row.get("base_url") or prev.get("base_url") or ""),
                    provider,
                ),
                "model": model_id,
                "api_key": str(key or ""),
            },
        )
    return out


def _sync_active_from_models(rt: dict[str, Any]) -> dict[str, Any]:
    """Keep top-level provider/model/base_url/api_key aligned with active profile."""
    models = rt.get("models")
    if not isinstance(models, list) or not models:
        if rt.get("model") or rt.get("base_url"):
            boot = _profile_from_top(rt)
            rt["models"] = [boot]
            rt["active_model_id"] = boot["id"]
        return rt
    active = str(rt.get("active_model_id") or "")
    chosen = None
    for m in models:
        if isinstance(m, dict) and str(m.get("id")) == active:
            chosen = m
            break
    if chosen is None and isinstance(models[0], dict):
        chosen = models[0]
        rt["active_model_id"] = str(chosen.get("id") or "")
    if not isinstance(chosen, dict):
        return rt
    provider = str(chosen.get("provider") or "openai").lower()
    if provider not in ("openai", "anthropic"):
        provider = "openai"
    rt["provider"] = provider
    rt["base_url"] = normalize_base_url(str(chosen.get("base_url") or ""), provider)
    rt["model"] = str(chosen.get("model") or "")
    if chosen.get("api_key") is not None:
        rt["api_key"] = str(chosen.get("api_key") or "")
    rt["model_name"] = str(chosen.get("name") or rt["model"])
    return rt


def public_model_profile(p: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(p.get("id") or ""),
        "name": str(p.get("name") or p.get("model") or "model"),
        "provider": str(p.get("provider") or "openai"),
        "base_url": str(p.get("base_url") or ""),
        "model": str(p.get("model") or ""),
        "api_key": mask_api_key(str(p.get("api_key") or "")),
        "api_key_set": bool(p.get("api_key")),
    }


def list_model_profiles(runtime: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    rt = _sync_active_from_models(dict(runtime if runtime is not None else load_runtime_file()))
    models = rt.get("models") if isinstance(rt.get("models"), list) else []
    return [public_model_profile(m) for m in models if isinstance(m, dict)]


def upsert_model_profile(body: dict[str, Any]) -> dict[str, Any]:
    """Create or update a model profile; activate it by default when new."""
    rt = load_runtime_file()
    rt = _sync_active_from_models(rt)
    models = list(rt.get("models") or []) if isinstance(rt.get("models"), list) else []
    pid = str(body.get("id") or "").strip() or uuid.uuid4().hex
    existing = None
    for m in models:
        if isinstance(m, dict) and str(m.get("id")) == pid:
            existing = m
            break
    provider = str(body.get("provider") or (existing or {}).get("provider") or "openai").lower()
    if provider not in ("openai", "anthropic"):
        provider = "openai"
    key = body.get("api_key")
    if key is None or (isinstance(key, str) and key.strip() in ("", "********")):
        key = (existing or {}).get("api_key") or ""
    row = {
        "id": pid,
        "name": str(body.get("name") or (existing or {}).get("name") or body.get("model") or "model"),
        "provider": provider,
        "base_url": normalize_base_url(
            str(body.get("base_url") or (existing or {}).get("base_url") or ""),
            provider,
        ),
        "model": str(body.get("model") or (existing or {}).get("model") or ""),
        "api_key": str(key or ""),
    }
    if existing is None:
        models.append(row)
    else:
        models = [row if isinstance(m, dict) and str(m.get("id")) == pid else m for m in models]
    activate = body.get("activate")
    if activate is None:
        activate = existing is None or str(rt.get("active_model_id") or "") == pid
    patch: dict[str, Any] = {"models": models}
    if activate:
        patch["active_model_id"] = pid
    save_runtime_file(patch)
    return runtime_public_view(settings_with_runtime())


def delete_model_profile(profile_id: str) -> dict[str, Any]:
    pid = str(profile_id or "").strip()
    if not pid:
        raise ValueError("id required")
    rt = load_runtime_file()
    models = [m for m in (rt.get("models") or []) if isinstance(m, dict) and str(m.get("id")) != pid]
    if not models and (rt.get("model") or rt.get("base_url")):
        # keep at least empty list
        models = []
    patch: dict[str, Any] = {"models": models}
    if str(rt.get("active_model_id") or "") == pid:
        patch["active_model_id"] = str(models[0]["id"]) if models else ""
    save_runtime_file(patch)
    return runtime_public_view(settings_with_runtime())


def activate_model_profile(profile_id: str) -> dict[str, Any]:
    pid = str(profile_id or "").strip()
    if not pid:
        raise ValueError("id required")
    rt = load_runtime_file()
    models = rt.get("models") if isinstance(rt.get("models"), list) else []
    chosen = next((m for m in models if isinstance(m, dict) and str(m.get("id")) == pid), None)
    if not isinstance(chosen, dict):
        raise ValueError("model profile not found")
    # Persist active id AND top-level fields so Settings/engine never lag one switch behind.
    provider = str(chosen.get("provider") or "openai").lower()
    if provider not in ("openai", "anthropic"):
        provider = "openai"
    save_runtime_file(
        {
            "active_model_id": pid,
            "provider": provider,
            "base_url": normalize_base_url(str(chosen.get("base_url") or ""), provider),
            "model": str(chosen.get("model") or ""),
            "model_name": str(chosen.get("name") or chosen.get("model") or ""),
            "api_key": chosen.get("api_key") if chosen.get("api_key") is not None else None,
        },
    )
    return runtime_public_view(settings_with_runtime())


def runtime_public_view(settings: Settings, ui: dict[str, Any] | None = None) -> dict[str, Any]:
    """JSON-safe runtime view for Settings UI (api_key masked)."""
    ui = ui or load_settings()
    ws = list_workspaces(settings.workspace)
    rt = _sync_active_from_models(load_runtime_file())
    return {
        "provider": settings.provider,
        "model": settings.model,
        "base_url": settings.base_url,
        "api_key": mask_api_key(settings.api_key),
        "api_key_set": bool(settings.api_key),
        "model_name": str(rt.get("model_name") or settings.model),
        "active_model_id": str(rt.get("active_model_id") or ""),
        "models": list_model_profiles(rt),
        "max_steps": settings.max_iterations,
        "stream": settings.stream,
        "debug": settings.debug,
        "mock": settings.mock,
        "workspace": settings.workspace,
        "workspaces": ws["items"],
        "approval": ui.get("approval") or "auto",
        "theme": ui.get("theme") or "dark",
    }


def apply_runtime_to_settings(base: Settings, runtime: dict[str, Any]) -> Settings:
    """Apply runtime.json fields onto a Settings instance."""
    runtime = _sync_active_from_models(dict(runtime))
    workspace = runtime.get("workspace")
    model = runtime.get("model")
    base_url = runtime.get("base_url")
    api_key = runtime.get("api_key")
    max_steps = runtime.get("max_steps")
    stream = runtime.get("stream")
    debug = runtime.get("debug")
    mock = runtime.get("mock")
    provider = str(runtime.get("provider") or base.provider or "openai").lower()
    if provider not in ("openai", "anthropic"):
        provider = "openai"
    url = normalize_base_url(str(base_url) if base_url else base.base_url, provider)

    return Settings(
        workspace=os.path.abspath(str(workspace)) if workspace else base.workspace,
        base_url=url,
        model=str(model) if model else base.model,
        api_key=str(api_key) if api_key and str(api_key) != "********" else base.api_key,
        http_trust_env=base.http_trust_env,
        max_iterations=int(max_steps) if max_steps is not None else base.max_iterations,
        command_timeout_sec=base.command_timeout_sec,
        mock=bool(mock) if mock is not None else base.mock,
        stream=bool(stream) if stream is not None else base.stream,
        debug=bool(debug) if debug is not None else base.debug,
        provider=provider,
    )


def settings_with_runtime(config_path: str | Path | None = None) -> Settings:
    """Load Settings from env/yaml, then overlay ``runtime.json``."""
    base = Settings.from_env(config_path=config_path)
    return apply_runtime_to_settings(base, load_runtime_file())


def workspaces_path() -> Path:
    return cai_home() / "workspaces.json"


def list_workspaces(current: str | None = None) -> dict[str, Any]:
    """Return registered workspaces + current path."""
    path = workspaces_path()
    items: list[str] = []
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("items"), list):
                items = [str(x) for x in data["items"] if x]
            elif isinstance(data, list):
                items = [str(x) for x in data if x]
        except Exception:
            items = []
    cur = os.path.abspath(current) if current else ""
    if cur and cur not in items:
        items.insert(0, cur)
    # drop missing dirs but keep current
    cleaned: list[str] = []
    for p in items:
        ap = os.path.abspath(p)
        if ap == cur or Path(ap).is_dir():
            if ap not in cleaned:
                cleaned.append(ap)
    return {"current": cur, "items": cleaned}


def add_workspace(path: str, *, make_current: bool = True) -> dict[str, Any]:
    """Register a workspace directory and optionally switch to it."""
    ap = os.path.abspath(path)
    if not Path(ap).is_dir():
        raise ValueError(f"not a directory: {ap}")
    data = list_workspaces()
    prev_current = data.get("current") or ""
    items = list(data["items"])
    if ap in items:
        items.remove(ap)
    items.insert(0, ap)
    workspaces_path().parent.mkdir(parents=True, exist_ok=True)
    workspaces_path().write_text(
        json.dumps({"items": items}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if make_current:
        save_runtime_file({"workspace": ap})
        os.environ["CAI_WORKSPACE"] = ap
        return list_workspaces(ap)
    return list_workspaces(prev_current)


def remove_workspace(path: str) -> dict[str, Any]:
    ap = os.path.abspath(path)
    data = list_workspaces()
    items = [p for p in data["items"] if p != ap]
    workspaces_path().write_text(
        json.dumps({"items": items}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return list_workspaces(data.get("current"))


async def discover_models(
    base_url: str,
    api_key: str = "",
    *,
    trust_env: bool = False,
    provider: str = "openai",
) -> list[dict[str, str]]:
    """
    Query provider model list.

    - openai: ``GET {base}/models`` (Bearer)
    - anthropic: ``GET {base}/v1/models`` (x-api-key); curated fallback
    """
    import httpx

    from cai_agent.llm.anthropic_messages import (
        ANTHROPIC_VERSION,
        DEFAULT_ANTHROPIC_MODELS,
        normalize_anthropic_base,
    )

    prov = (provider or "openai").lower()
    if prov in ("anthropic", "anthropic-messages", "claude"):
        root = normalize_anthropic_base(base_url)
        headers = {
            "x-api-key": api_key or "",
            "anthropic-version": ANTHROPIC_VERSION,
        }
        try:
            async with httpx.AsyncClient(timeout=30.0, trust_env=trust_env) as client:
                r = await client.get(f"{root}/v1/models", headers=headers)
            if r.status_code >= 400:
                return list(DEFAULT_ANTHROPIC_MODELS)
            data = r.json()
            rows = data.get("data") if isinstance(data, dict) else data
            if not isinstance(rows, list) or not rows:
                return list(DEFAULT_ANTHROPIC_MODELS)
            out: list[dict[str, str]] = []
            for row in rows:
                if isinstance(row, str):
                    out.append({"id": row, "name": row})
                elif isinstance(row, dict):
                    mid = str(row.get("id") or row.get("display_name") or "")
                    if mid:
                        out.append(
                            {
                                "id": mid,
                                "name": str(row.get("display_name") or row.get("name") or mid),
                            },
                        )
            out.sort(key=lambda x: x["id"].lower())
            return out or list(DEFAULT_ANTHROPIC_MODELS)
        except Exception:
            return list(DEFAULT_ANTHROPIC_MODELS)

    url = normalize_base_url(base_url, "openai")
    if not url:
        raise ValueError("base_url required")
    headers = {"Authorization": f"Bearer {api_key or 'lm-studio'}"}
    async with httpx.AsyncClient(timeout=30.0, trust_env=trust_env) as client:
        r = await client.get(f"{url}/models", headers=headers)
    if r.status_code >= 400:
        raise ValueError(f"models HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    rows = data.get("data") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("unexpected models response")
    out = []
    for row in rows:
        if isinstance(row, str):
            out.append({"id": row, "name": row})
        elif isinstance(row, dict):
            mid = str(row.get("id") or row.get("name") or "")
            if mid:
                out.append({"id": mid, "name": str(row.get("name") or mid)})
    out.sort(key=lambda x: x["id"].lower())
    return out


def list_workspace_tree(
    workspace: str,
    rel: str = ".",
    *,
    depth: int = 2,
    max_entries: int = 400,
) -> list[dict[str, Any]]:
    try:
        root = resolve_workspace_path(workspace, rel or ".")
    except SandboxError as e:
        raise ValueError(str(e)) from e
    if not root.is_dir():
        raise ValueError("not a directory")

    entries: list[dict[str, Any]] = []

    def walk(path: Path, prefix: str, remaining: int) -> None:
        if len(entries) >= max_entries or remaining < 0:
            return
        try:
            children = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return
        for child in children:
            if len(entries) >= max_entries:
                return
            name = child.name
            if name in SKIP_DIRS or name.endswith(".egg-info"):
                continue
            rel_path = f"{prefix}/{name}".lstrip("./").lstrip("/")
            if not prefix or prefix == ".":
                rel_path = name
            else:
                rel_path = f"{prefix}/{name}"
            item: dict[str, Any] = {
                "name": name,
                "path": rel_path.replace("\\", "/"),
                "type": "dir" if child.is_dir() else "file",
            }
            entries.append(item)
            if child.is_dir() and remaining > 0:
                walk(child, item["path"], remaining - 1)

    walk(root, "." if rel in ("", ".") else rel.replace("\\", "/"), max(0, depth))
    return entries


def read_workspace_file(workspace: str, rel: str, *, max_chars: int = 80_000) -> dict[str, Any]:
    try:
        path = resolve_workspace_path(workspace, rel)
    except SandboxError as e:
        raise ValueError(str(e)) from e
    if not path.is_file():
        raise ValueError("not a file")
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return {
            "path": rel,
            "binary": True,
            "size": len(raw),
            "content": f"[binary {len(raw)} bytes]",
        }
    truncated = len(text) > max_chars
    if truncated:
        text = text[:max_chars]
    return {
        "path": rel,
        "binary": False,
        "size": len(raw),
        "truncated": truncated,
        "content": text,
    }


_MAX_WRITE_BYTES = 500_000


def _safe_rel(rel: str) -> str:
    rel = (rel or "").replace("\\", "/").strip().lstrip("/")
    if not rel or rel in (".", "..") or ".." in rel.split("/"):
        raise ValueError("invalid path")
    if any(part in SKIP_DIRS for part in rel.split("/")):
        raise ValueError("path under skipped directory")
    return rel


def write_workspace_file(
    workspace: str,
    rel: str,
    content: str,
    *,
    create_parents: bool = True,
) -> dict[str, Any]:
    rel = _safe_rel(rel)
    if not isinstance(content, str):
        raise ValueError("content must be string")
    raw = content.encode("utf-8")
    if len(raw) > _MAX_WRITE_BYTES:
        raise ValueError(f"content too large (max {_MAX_WRITE_BYTES} bytes)")
    try:
        path = resolve_workspace_path(workspace, rel)
    except SandboxError as e:
        raise ValueError(str(e)) from e
    if path.exists() and path.is_dir():
        raise ValueError("path is a directory")
    if create_parents:
        path.parent.mkdir(parents=True, exist_ok=True)
    elif not path.parent.is_dir():
        raise ValueError("parent directory missing")
    path.write_text(content, encoding="utf-8")
    return {"path": rel, "size": len(raw), "ok": True}


def mkdir_workspace(workspace: str, rel: str) -> dict[str, Any]:
    rel = _safe_rel(rel)
    try:
        path = resolve_workspace_path(workspace, rel)
    except SandboxError as e:
        raise ValueError(str(e)) from e
    if path.exists() and not path.is_dir():
        raise ValueError("path exists as file")
    path.mkdir(parents=True, exist_ok=True)
    return {"path": rel, "type": "dir", "ok": True}


def create_workspace_entry(
    workspace: str,
    rel: str,
    *,
    kind: str = "file",
    content: str = "",
) -> dict[str, Any]:
    """Create a new file or directory; fail if file already exists."""
    rel = _safe_rel(rel)
    try:
        path = resolve_workspace_path(workspace, rel)
    except SandboxError as e:
        raise ValueError(str(e)) from e
    if kind == "dir":
        if path.exists() and not path.is_dir():
            raise ValueError("path exists as file")
        path.mkdir(parents=True, exist_ok=True)
        return {"path": rel, "type": "dir", "ok": True, "created": True}
    if path.exists():
        raise ValueError("already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not isinstance(content, str):
        raise ValueError("content must be string")
    raw = content.encode("utf-8")
    if len(raw) > _MAX_WRITE_BYTES:
        raise ValueError(f"content too large (max {_MAX_WRITE_BYTES} bytes)")
    path.write_text(content, encoding="utf-8")
    return {"path": rel, "type": "file", "size": len(raw), "ok": True, "created": True}

