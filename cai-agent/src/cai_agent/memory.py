from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, List

MEMORY_ENTRY_V1_FIELDS = frozenset(
    {"id", "category", "text", "confidence", "expires_at", "created_at", "source"},
)

MEMORY_STATES = ("active", "stale", "expired")


class MemoryEntryInvalid(ValueError):
    """memory_entry_v1 行校验失败（写入前拦截）。"""


def classify_memory_entry_skip_reason(message: str) -> str:
    """将校验错误映射为 ``memory_extract_structured_v1.skipped_invalid[].reason`` 枚举。"""
    m = (message or "").strip().lower()
    if "confidence" in m and ("0~1" in m or "0-1" in m or "须" in message):
        return "invalid_confidence"
    if "不允许的字段" in message or "extra" in m:
        return "extra_fields"
    if "text" in m and ("string" in m or "必须为" in message):
        return "invalid_text"
    if "category" in m and "必须" in message:
        return "invalid_category"
    if "id" in m and "必须" in message:
        return "invalid_id"
    if "created_at" in m:
        return "invalid_created_at"
    if "expires_at" in m:
        return "invalid_expires_at"
    if "source" in m:
        return "invalid_source"
    return "schema_validation_failed"


def validate_memory_entry_row(row: dict[str, Any]) -> list[str]:
    """校验与 memory_entry_v1.schema.json 一致的 JSONL 行（不依赖 jsonschema 运行时）。"""
    errs: list[str] = []
    extra = set(row.keys()) - MEMORY_ENTRY_V1_FIELDS
    if extra:
        errs.append(f"不允许的字段: {sorted(extra)}")
    for key in ("id", "category", "created_at"):
        v = row.get(key)
        if not isinstance(v, str) or not v.strip():
            errs.append(f"{key} 必须为非空字符串")
    if "text" not in row or not isinstance(row["text"], str):
        errs.append("text 必须为 string")
    conf = row.get("confidence")
    if isinstance(conf, bool) or not isinstance(conf, int | float):
        errs.append("confidence 必须为数字")
    else:
        c = float(conf)
        if c < 0.0 or c > 1.0:
            errs.append("confidence 须在 0~1")
    exp = row.get("expires_at")
    if exp is not None and exp != "" and not isinstance(exp, str):
        errs.append("expires_at 须为 string 或 null")
    if "source" in row:
        src = row.get("source")
        if not isinstance(src, str) or not src.strip():
            errs.append("source 若存在须为非空字符串")
    return errs


@dataclass(frozen=True)
class Instinct:
    """从历史会话中提炼出的经验/模式摘要."""

    title: str
    body: str
    tags: list[str]
    confidence: float


@dataclass(frozen=True)
class MemoryEntry:
    id: str
    category: str
    text: str
    confidence: float
    expires_at: str | None
    created_at: str


def _default_memory_dir(root: str | Path) -> Path:
    base = Path(root).expanduser().resolve()
    return base / "memory" / "instincts"


def _entries_path(root: str | Path) -> Path:
    base = Path(root).expanduser().resolve()
    d = base / "memory"
    d.mkdir(parents=True, exist_ok=True)
    return d / "entries.jsonl"


def _entries_file_readonly(root: str | Path) -> Path:
    """``memory/entries.jsonl`` 路径（不自动创建目录）。"""
    return Path(root).expanduser().resolve() / "memory" / "entries.jsonl"


def append_memory_entry(
    root: str | Path,
    *,
    category: str,
    text: str,
    confidence: float = 0.5,
    expires_at: str | None = None,
    entry_id: str | None = None,
    source: str | None = None,
) -> MemoryEntry:
    eid = entry_id or str(uuid.uuid4())
    created = datetime.now(UTC).isoformat()
    row: dict[str, Any] = {
        "id": eid,
        "category": category,
        "text": text,
        "confidence": float(confidence),
        "expires_at": expires_at,
        "created_at": created,
    }
    if source is not None and str(source).strip():
        row["source"] = str(source).strip()
    bad = validate_memory_entry_row(row)
    if bad:
        msg = "; ".join(bad)
        raise MemoryEntryInvalid(msg)
    require_memory_entries_jsonl_clean_before_write(root)
    path = _entries_path(root)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return MemoryEntry(
        id=eid,
        category=category,
        text=text,
        confidence=float(confidence),
        expires_at=expires_at,
        created_at=created,
    )


def load_memory_entries(root: str | Path) -> list[dict[str, Any]]:
    path = _entries_path(root)
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def load_memory_entries_validated(
    root: str | Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    """逐行校验 schema；无效行记入 warnings，不进入返回列表。"""
    path = _entries_file_readonly(root)
    if not path.is_file():
        return [], []
    valid: list[dict[str, Any]] = []
    warnings: list[str] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            warnings.append(f"行 {lineno}: JSON 解析失败 ({e})")
            continue
        if not isinstance(obj, dict):
            warnings.append(f"行 {lineno}: 根类型须为 object")
            continue
        errs = validate_memory_entry_row(obj)
        if errs:
            warnings.append(f"行 {lineno}: " + "; ".join(errs))
            continue
        valid.append(obj)
    return valid, warnings


def build_memory_entries_jsonl_validate_report(root: str | Path) -> dict[str, Any]:
    """对 ``memory/entries.jsonl`` 做行级 memory_entry_v1 校验（与 ``schemas/memory_entry_v1.schema.json`` 一致）。"""
    path = _entries_file_readonly(root)
    if not path.is_file():
        return {
            "schema_version": "memory_entries_file_validate_v1",
            "memory_entry_schema_version": "1.0",
            "entries_file": str(path),
            "exists": False,
            "ok": True,
            "lines_scanned": 0,
            "valid_lines": 0,
            "invalid_lines": [],
        }
    invalid: list[dict[str, Any]] = []
    valid_n = 0
    scanned = 0
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        scanned += 1
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            invalid.append({"line": lineno, "errors": [f"JSON 解析失败: {e}"]})
            continue
        if not isinstance(obj, dict):
            invalid.append({"line": lineno, "errors": ["根类型须为 object"]})
            continue
        row_errs = validate_memory_entry_row(obj)
        if row_errs:
            invalid.append({"line": lineno, "errors": list(row_errs)})
            continue
        valid_n += 1
    return {
        "schema_version": "memory_entries_file_validate_v1",
        "memory_entry_schema_version": "1.0",
        "entries_file": str(path),
        "exists": True,
        "ok": len(invalid) == 0,
        "lines_scanned": scanned,
        "valid_lines": valid_n,
        "invalid_lines": invalid,
    }


def build_memory_provider_contract_payload(root: str | Path) -> dict[str, Any]:
    """Describe the local memory provider surface without initializing stores."""
    builtin_specs = list_builtin_memory_provider_specs()
    base = Path(root).expanduser().resolve()
    entries_path = _entries_file_readonly(base)
    entries_report = build_memory_entries_jsonl_validate_report(base)
    valid_entries = int(entries_report.get("valid_lines") or 0)
    invalid_entries = len(entries_report.get("invalid_lines") or [])
    from cai_agent.user_model_store import list_recent_beliefs, user_model_store_path

    store_path = user_model_store_path(base)
    beliefs_count = 0
    store_ok = True
    store_error: str | None = None
    if store_path.is_file():
        try:
            beliefs_count = len(list_recent_beliefs(base, limit=500))
        except Exception as e:  # pragma: no cover - defensive around corrupt local sqlite
            store_ok = False
            store_error = str(e)[:300]
    providers = [
        {
            "id": "local_entries_jsonl",
            "kind": "memory_entries",
            "status": "active",
            "default": True,
            "path": str(entries_path),
            "exists": entries_path.is_file(),
            "schema_version": "memory_entry_v1",
            "read_surface": ["memory health", "memory state", "memory export-entries"],
            "write_surface": ["memory add", "memory import-entries"],
            "counts": {
                "valid_entries": valid_entries,
                "invalid_entries": invalid_entries,
            },
        },
        {
            "id": "local_user_model_sqlite",
            "kind": "user_model_store",
            "status": "active" if store_path.is_file() else "available",
            "default": True,
            "path": str(store_path),
            "exists": store_path.is_file(),
            "schema_version": "user_model_store_snapshot_v1",
            "read_surface": ["memory user-model", "memory user-model store list", "memory user-model query"],
            "write_surface": ["memory user-model store init", "memory user-model learn"],
            "counts": {
                "beliefs": beliefs_count,
            },
            "ok": store_ok,
            "error": store_error,
        },
    ]
    builtin_ids = [
        str(row.get("id") or "")
        for row in builtin_specs
        if isinstance(row, dict) and str(row.get("id") or "").strip()
    ]
    return {
        "schema_version": "memory_provider_contract_v1",
        "workspace": str(base),
        "default_provider": "local_entries_jsonl",
        "providers": providers,
        "builtin_registry": {
            "schema_version": "memory_provider_builtin_registry_v1",
            "provider_ids": builtin_ids,
            "default_provider": "local_entries_jsonl",
        },
        "external_adapters": [
            {
                "id": "honcho_external",
                "status": "mock_http_available",
                "requires_credentials": True,
                "network_enabled_by_default": False,
                "env": {
                    "base_url": "CAI_MEMORY_EXTERNAL_MOCK_URL",
                    "api_key": "CAI_MEMORY_EXTERNAL_API_KEY",
                },
            },
        ],
        "user_model_provider_coverage": {
            "behavior_overview": "local_sessions",
            "belief_store": "local_user_model_sqlite",
            "memory_entries": "local_entries_jsonl",
            "external_graph": None,
        },
        "ok": bool(entries_report.get("ok")) and store_ok,
    }


def _test_external_mock_provider() -> dict[str, Any]:
    base_url = str(os.environ.get("CAI_MEMORY_EXTERNAL_MOCK_URL", "") or "").strip()
    api_key = str(os.environ.get("CAI_MEMORY_EXTERNAL_API_KEY", "") or "").strip()
    if not base_url:
        return {
            "ok": False,
            "error": "missing_base_url",
            "message": "设置 CAI_MEMORY_EXTERNAL_MOCK_URL 后可进行 mock HTTP 健康探测。",
            "configured": False,
            "api_key_present": bool(api_key),
        }
    url = base_url.rstrip("/") + "/health"
    headers = {"User-Agent": "cai-agent/memory-provider-test"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            status = int(getattr(resp, "status", 200) or 200)
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return {
            "ok": False,
            "configured": True,
            "api_key_present": bool(api_key),
            "error": "http_error",
            "status": int(e.code),
            "message": str(e),
            "url": url,
        }
    except Exception as e:
        return {
            "ok": False,
            "configured": True,
            "api_key_present": bool(api_key),
            "error": "request_failed",
            "message": str(e),
            "url": url,
        }
    body: dict[str, Any] | None = None
    try:
        parsed = json.loads(raw)
        body = parsed if isinstance(parsed, dict) else None
    except Exception:
        body = None
    remote_ok = bool(body.get("ok")) if isinstance(body, dict) else False
    return {
        "ok": status < 400 and remote_ok,
        "configured": True,
        "api_key_present": bool(api_key),
        "status": status,
        "url": url,
        "remote_schema_version": (body or {}).get("schema_version") if isinstance(body, dict) else None,
    }


def list_builtin_memory_provider_specs() -> list[dict[str, Any]]:
    """HM-N09-D02: explicit builtin local provider registration specs."""
    return [
        {
            "id": "local_entries_jsonl",
            "kind": "memory_entries",
            "schema_version": "memory_entry_v1",
            "default": True,
            "read_surface": ["memory health", "memory state", "memory export-entries"],
            "write_surface": ["memory add", "memory import-entries"],
        },
        {
            "id": "local_user_model_sqlite",
            "kind": "user_model_store",
            "schema_version": "user_model_store_snapshot_v1",
            "default": True,
            "read_surface": ["memory user-model", "memory user-model store list", "memory user-model query"],
            "write_surface": ["memory user-model store init", "memory user-model learn"],
        },
    ]


def _memory_provider_state_path(root: str | Path) -> Path:
    base = Path(root).expanduser().resolve()
    p = base / ".cai" / "memory-provider.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _read_memory_provider_state(root: str | Path) -> dict[str, Any]:
    p = _memory_provider_state_path(root)
    if not p.is_file():
        return {}
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _write_memory_provider_state(root: str | Path, obj: dict[str, Any]) -> Path:
    p = _memory_provider_state_path(root)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def build_memory_provider_registry_payload(root: str | Path) -> dict[str, Any]:
    """HM-N09-D01: registry payload with active provider pointer."""
    base = Path(root).expanduser().resolve()
    contract = build_memory_provider_contract_payload(base)
    providers = contract.get("providers") if isinstance(contract.get("providers"), list) else []
    provider_ids = [
        str(row.get("id") or "")
        for row in providers
        if isinstance(row, dict) and str(row.get("id") or "").strip()
    ]
    state = _read_memory_provider_state(base)
    configured = str(state.get("active_provider") or "").strip()
    default_id = str(contract.get("default_provider") or "local_entries_jsonl")
    active = configured if configured in provider_ids else default_id
    return {
        "schema_version": "memory_provider_registry_v1",
        "workspace": str(base),
        "active_provider": active,
        "active_provider_source": "config" if active == configured and configured else "default",
        "providers": providers,
        "provider_ids": provider_ids,
        "default_provider": default_id,
        "builtin_registry": contract.get("builtin_registry") if isinstance(contract.get("builtin_registry"), dict) else {},
        "state_file": str(_memory_provider_state_path(base)),
        "ok": bool(contract.get("ok")),
    }


def resolve_active_memory_provider(root: str | Path) -> dict[str, Any]:
    """HM-N09-D04: stable active-provider view for doctor/export/profile surfaces."""
    reg = build_memory_provider_registry_payload(root)
    return {
        "schema_version": "memory_active_provider_v1",
        "active_provider": str(reg.get("active_provider") or ""),
        "active_provider_source": str(reg.get("active_provider_source") or "default"),
        "default_provider": str(reg.get("default_provider") or ""),
        "state_file": str(reg.get("state_file") or ""),
        "ok": bool(reg.get("ok")),
    }


def set_active_memory_provider(root: str | Path, provider_id: str) -> dict[str, Any]:
    """HM-N09-D01: select active memory provider (local registry pointer)."""
    base = Path(root).expanduser().resolve()
    reg = build_memory_provider_registry_payload(base)
    pid = str(provider_id or "").strip()
    provider_ids = reg.get("provider_ids") if isinstance(reg.get("provider_ids"), list) else []
    if not pid:
        return {
            "schema_version": "memory_provider_use_v1",
            "ok": False,
            "error": "invalid_provider_id",
            "message": "provider id 不能为空",
            "providers": provider_ids,
        }
    if pid not in provider_ids:
        return {
            "schema_version": "memory_provider_use_v1",
            "ok": False,
            "error": "provider_not_found",
            "provider_id": pid,
            "providers": provider_ids,
        }
    written = _write_memory_provider_state(
        base,
        {
            "schema_version": "memory_provider_state_v1",
            "active_provider": pid,
            "updated_at": datetime.now(UTC).isoformat(),
        },
    )
    return {
        "schema_version": "memory_provider_use_v1",
        "ok": True,
        "active_provider": pid,
        "state_file": str(written),
    }


def test_memory_provider(root: str | Path, provider_id: str | None = None) -> dict[str, Any]:
    """HM-N09-D01: provider connectivity/health smoke check (local-only)."""
    base = Path(root).expanduser().resolve()
    reg = build_memory_provider_registry_payload(base)
    pid = str(provider_id or reg.get("active_provider") or "").strip() or "local_entries_jsonl"
    provider_ids = reg.get("provider_ids") if isinstance(reg.get("provider_ids"), list) else []
    if pid not in provider_ids and pid != "honcho_external":
        return {
            "schema_version": "memory_provider_test_v1",
            "ok": False,
            "provider_id": pid,
            "error": "provider_not_found",
            "providers": provider_ids,
        }
    if pid == "local_entries_jsonl":
        rep = build_memory_entries_jsonl_validate_report(base)
        return {
            "schema_version": "memory_provider_test_v1",
            "ok": bool(rep.get("ok")),
            "provider_id": pid,
            "checks": {
                "entries_file": rep.get("entries_file"),
                "exists": rep.get("exists"),
                "valid_lines": rep.get("valid_lines"),
                "invalid_lines_count": len(rep.get("invalid_lines") or []),
            },
        }
    if pid == "local_user_model_sqlite":
        from cai_agent.user_model_store import list_recent_beliefs, user_model_store_path

        store = user_model_store_path(base)
        if not store.is_file():
            return {
                "schema_version": "memory_provider_test_v1",
                "ok": True,
                "provider_id": pid,
                "checks": {
                    "store_path": str(store),
                    "exists": False,
                    "beliefs_count": 0,
                    "message": "store_not_initialized",
                },
            }
        try:
            beliefs = list_recent_beliefs(base, limit=20)
            return {
                "schema_version": "memory_provider_test_v1",
                "ok": True,
                "provider_id": pid,
                "checks": {
                    "store_path": str(store),
                    "exists": True,
                    "beliefs_count": len(beliefs),
                },
            }
        except Exception as e:  # pragma: no cover - defensive around corrupt sqlite
            return {
                "schema_version": "memory_provider_test_v1",
                "ok": False,
                "provider_id": pid,
                "error": "store_read_failed",
                "message": str(e)[:300],
                "checks": {"store_path": str(store), "exists": True},
            }
    ext = _test_external_mock_provider()
    ext_ok = bool(ext.get("ok"))
    return {
        "schema_version": "memory_provider_test_v1",
        "ok": ext_ok,
        "provider_id": pid,
        "checks": ext,
        "error": None if ext_ok else str(ext.get("error") or "external_check_failed"),
    }


def fix_memory_entries_jsonl(
    root: str | Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """移除无法通过 ``memory_entry_v1`` 校验的行并重写 ``memory/entries.jsonl``（原子替换）。

    空行与非 JSON 行丢弃；仅保留 ``validate_memory_entry_row`` 通过的 object 行。
    """
    path = _entries_file_readonly(root)
    if not path.is_file():
        return {
            "schema_version": "memory_entries_fix_v1",
            "entries_file": str(path),
            "dry_run": bool(dry_run),
            "ok": True,
            "lines_before": 0,
            "lines_after": 0,
            "dropped": 0,
            "rewritten": False,
            "message": "entries.jsonl 不存在，无需修复",
        }
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    kept: list[dict[str, Any]] = []
    dropped = 0
    for raw in raw_lines:
        line = raw.strip()
        if not line:
            dropped += 1
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            dropped += 1
            continue
        if not isinstance(obj, dict):
            dropped += 1
            continue
        row_errs = validate_memory_entry_row(obj)
        if row_errs:
            dropped += 1
            continue
        kept.append(obj)
    lines_before = sum(1 for x in raw_lines if x.strip())
    lines_after = len(kept)
    rewritten = False
    if not dry_run and (dropped > 0 or lines_after != lines_before):
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as f:
                for row in kept:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            tmp.replace(path)
            rewritten = True
        except OSError:
            if tmp.is_file():
                try:
                    tmp.unlink()
                except OSError:
                    pass
            raise
    return {
        "schema_version": "memory_entries_fix_v1",
        "entries_file": str(path),
        "dry_run": bool(dry_run),
        "ok": True,
        "lines_before": lines_before,
        "lines_after": lines_after,
        "dropped": dropped,
        "rewritten": rewritten and not dry_run,
        "message": "dry_run 未写盘" if dry_run else ("已重写" if rewritten else "无需变更"),
    }


def _memory_entries_jsonl_write_guard_disabled() -> bool:
    return os.environ.get("CAI_MEMORY_ALLOW_DIRTY_ENTRIES_JSONL", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def require_memory_entries_jsonl_clean_before_write(root: str | Path) -> None:
    """在追加写入 ``memory/entries.jsonl`` 前要求整文件无无效行（与 validate-entries 同源规则）。

    可通过环境变量 ``CAI_MEMORY_ALLOW_DIRTY_ENTRIES_JSONL=1`` 跳过（迁移/救急）。
    """
    if _memory_entries_jsonl_write_guard_disabled():
        return
    rep = build_memory_entries_jsonl_validate_report(root)
    if not rep.get("exists"):
        return
    if rep.get("ok"):
        return
    raise ValueError(
        "memory/entries.jsonl 存在未通过 memory_entry_v1 校验的行；"
        "请先运行 `cai-agent memory validate-entries` 修复后再写入。"
        "若需临时跳过检查，可设置环境变量 CAI_MEMORY_ALLOW_DIRTY_ENTRIES_JSONL=1。"
    )


def export_memory_entries_bundle(root: str | Path) -> dict[str, Any]:
    valid, warnings = load_memory_entries_validated(root)
    return {
        "schema_version": "memory_entries_bundle_v1",
        "entries": valid,
        "export_warnings": warnings,
    }


def import_memory_entries_bundle(root: str | Path, bundle: dict[str, Any]) -> int:
    """导入 `export_memory_entries_bundle` 或同结构 JSON；任一行校验失败则整批失败。"""
    if not isinstance(bundle, dict):
        msg = "根对象须为 JSON object"
        raise ValueError(msg)
    entries = bundle.get("entries")
    if not isinstance(entries, list):
        msg = "缺少 entries 数组"
        raise ValueError(msg)
    to_write: list[dict[str, Any]] = []
    for i, row in enumerate(entries, start=1):
        if not isinstance(row, dict):
            msg = f"entries[{i}] 须为 object"
            raise ValueError(msg)
        errs = validate_memory_entry_row(row)
        if errs:
            msg = f"entries[{i}] schema 无效: " + "; ".join(errs)
            raise ValueError(msg)
        to_write.append(row)
    require_memory_entries_jsonl_clean_before_write(root)
    path = _entries_path(root)
    with path.open("a", encoding="utf-8") as f:
        for row in to_write:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(to_write)


def validate_memory_entries_bundle(
    bundle: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """校验 bundle 内容并返回可写行与结构化错误（不写入磁盘）。"""
    if not isinstance(bundle, dict):
        return [], [{"entry_index": None, "path": "root", "errors": ["根对象须为 JSON object"]}]
    entries = bundle.get("entries")
    if not isinstance(entries, list):
        return [], [{"entry_index": None, "path": "root.entries", "errors": ["缺少 entries 数组"]}]
    valid_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for i, row in enumerate(entries, start=1):
        if not isinstance(row, dict):
            errors.append({"entry_index": i, "path": f"entries[{i}]", "errors": ["须为 object"]})
            continue
        row_errs = validate_memory_entry_row(row)
        if row_errs:
            errors.append({"entry_index": i, "path": f"entries[{i}]", "errors": list(row_errs)})
            continue
        valid_rows.append(row)
    return valid_rows, errors


def _parse_created_at(row: dict[str, Any]) -> float:
    raw = row.get("created_at")
    if not isinstance(raw, str) or not raw.strip():
        return 0.0
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.timestamp()
    except ValueError:
        return 0.0


def sort_memory_rows(rows: list[dict[str, Any]], sort: str) -> None:
    """就地排序；sort 为 none/空则不变。"""
    s = sort.strip().lower()
    if s in ("", "none", "file"):
        return
    if s == "confidence":
        rows.sort(key=_confidence_val, reverse=True)
    elif s in ("created_at", "created"):
        rows.sort(key=_parse_created_at, reverse=True)


def _confidence_val(row: dict[str, Any]) -> float:
    c = row.get("confidence")
    if isinstance(c, bool) or not isinstance(c, int | float):
        return 0.0
    return float(c)


def _parse_dt(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def memory_entry_state(
    row: dict[str, Any],
    *,
    now: datetime | None = None,
    stale_after_days: int = 14,
    min_active_confidence: float = 0.5,
) -> str:
    now_dt = now or datetime.now(UTC)
    exp = _parse_dt(row.get("expires_at"))
    if exp is not None and exp < now_dt:
        return "expired"
    created = _parse_dt(row.get("created_at"))
    conf = _confidence_val(row)
    stale_after = max(1, int(stale_after_days))
    if created is not None and created < (now_dt - timedelta(days=stale_after)):
        return "stale"
    if conf < max(0.0, min(1.0, float(min_active_confidence))):
        return "stale"
    return "active"


def annotate_memory_states(
    rows: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    stale_after_days: int = 14,
    min_active_confidence: float = 0.5,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        st = memory_entry_state(
            row,
            now=now,
            stale_after_days=stale_after_days,
            min_active_confidence=min_active_confidence,
        )
        reason = "active"
        exp = _parse_dt(row.get("expires_at"))
        created = _parse_dt(row.get("created_at"))
        conf = _confidence_val(row)
        stale_after = max(1, int(stale_after_days))
        now_dt = now or datetime.now(UTC)
        if exp is not None and exp < now_dt:
            reason = "expired_by_ttl"
        elif created is not None and created < (now_dt - timedelta(days=stale_after)):
            reason = "stale_by_age"
        elif conf < max(0.0, min(1.0, float(min_active_confidence))):
            reason = "stale_by_confidence"
        out.append({**row, "state": st, "state_reason": reason})
    return out


def evaluate_memory_entry_states(
    root: str | Path,
    *,
    stale_after_days: int = 14,
    min_active_confidence: float = 0.5,
) -> dict[str, Any]:
    rows, warnings = load_memory_entries_validated(root)
    annotated = annotate_memory_states(
        rows,
        stale_after_days=stale_after_days,
        min_active_confidence=min_active_confidence,
    )
    counts = {"active": 0, "stale": 0, "expired": 0}
    for row in annotated:
        st = str(row.get("state") or "").strip().lower()
        if st in counts:
            counts[st] += 1
    return {
        "schema_version": "memory_state_eval_v1",
        "total_entries": len(annotated),
        "rows": annotated,
        "counts": counts,
        "warnings": warnings,
        "stale_after_days": int(max(1, stale_after_days)),
        "min_active_confidence": float(max(0.0, min(1.0, min_active_confidence))),
    }


def build_structured_memory_prompt_block(
    root: str | Path,
    *,
    max_entries: int = 24,
    max_chars: int = 6000,
    include_stale: bool = False,
    stale_after_days: int = 14,
    min_active_confidence: float = 0.5,
    per_entry_max_chars: int = 480,
) -> str:
    """将校验通过的 ``memory/entries.jsonl`` 条目格式化为可注入 system prompt 的 Markdown（只读，不创建目录）。"""
    base = Path(root).expanduser().resolve()
    rows, _warns = load_memory_entries_validated(base)
    if not rows:
        return ""
    ann = annotate_memory_states(
        rows,
        stale_after_days=int(max(1, stale_after_days)),
        min_active_confidence=float(max(0.0, min(1.0, min_active_confidence))),
    )
    picked: list[dict[str, Any]] = []
    for row in ann:
        st = str(row.get("state") or "").strip().lower()
        if st == "expired":
            continue
        if st == "stale" and not include_stale:
            continue
        if st == "active" or (include_stale and st == "stale"):
            picked.append(row)
    if not picked:
        return ""
    sort_memory_rows(picked, "confidence")
    me = max(1, min(500, int(max_entries)))
    mc = max(200, min(100_000, int(max_chars)))
    pec = max(32, min(8000, int(per_entry_max_chars)))
    header = "\n---\n## 结构化记忆（memory/entries.jsonl）\n"
    body_parts: list[str] = []
    used = len(header)
    for row in picked[:me]:
        cat = str(row.get("category") or "general").strip() or "general"
        text = str(row.get("text") or "").strip()
        text = " ".join(text.split())
        if len(text) > pec:
            text = text[: pec - 1] + "…"
        line = f"- **{cat}** {text}\n"
        if used + len(line) > mc:
            break
        body_parts.append(line)
        used += len(line)
    if not body_parts:
        return ""
    return header + "".join(body_parts)


def search_memory_entries(
    root: str | Path,
    query: str,
    *,
    limit: int = 50,
    sort: str | None = None,
) -> list[dict[str, Any]]:
    q = query.strip().lower()
    if not q:
        return []
    hits: list[dict[str, Any]] = []
    s = (sort or "").strip().lower()
    want_sort = s in ("confidence", "created_at", "created")
    for row in load_memory_entries(root):
        text = str(row.get("text", "")).lower()
        cat = str(row.get("category", "")).lower()
        if q in text or q in cat:
            hits.append(row)
            if not want_sort and len(hits) >= limit:
                return hits
    if s == "confidence":
        hits.sort(key=_confidence_val, reverse=True)
    elif s in ("created_at", "created"):
        hits.sort(key=_parse_created_at, reverse=True)
    return hits[:limit]


def _prune_non_active_reason(
    row: dict[str, Any],
    *,
    now: datetime,
    stale_after_days: int,
    min_active_confidence: float,
) -> str:
    """与 `annotate_memory_states` 的 state_reason 一致，用于 prune 分桶（仅非 active 路径）。"""
    exp = _parse_dt(row.get("expires_at"))
    created = _parse_dt(row.get("created_at"))
    conf = _confidence_val(row)
    stale_after = max(1, int(stale_after_days))
    if exp is not None and exp < now:
        return "expired_by_ttl"
    if created is not None and created < (now - timedelta(days=stale_after)):
        return "stale_by_age"
    if conf < max(0.0, min(1.0, float(min_active_confidence))):
        return "stale_by_confidence"
    return "unknown"


def prune_expired_memory_entries(
    root: str | Path,
    *,
    min_confidence: float | None = None,
    max_entries: int | None = None,
    drop_non_active: bool = False,
    stale_after_days: int = 30,
    min_active_confidence: float = 0.4,
) -> dict[str, Any]:
    """按策略清理记忆条目并返回统计。

    清理顺序：
    1) 删除 expires_at 已过期条目；
    2) 若设置 min_confidence，删除低于阈值条目；
    3) 若设置 max_entries，按 created_at 新到旧保留前 N 条，其余删除。
    """
    path = _entries_path(root)
    if not path.is_file():
        return {
            "schema_version": "memory_prune_result_v1",
            "removed_total": 0,
            "removed_expired": 0,
            "removed_low_confidence": 0,
            "removed_over_limit": 0,
            "removed_non_active": 0,
            "invalid_json_lines": 0,
            "removed_by_reason": {
                "expired_by_ttl": 0,
                "low_confidence": 0,
                "over_limit": 0,
                "stale_by_age": 0,
                "stale_by_confidence": 0,
                "unknown_non_active": 0,
            },
            "kept_total": 0,
        }
    now = datetime.now(UTC)
    remove_expired = 0
    remove_low_conf = 0
    remove_limit = 0
    remove_non_active = 0
    invalid_json_lines = 0
    by_reason: dict[str, int] = {
        "expired_by_ttl": 0,
        "low_confidence": 0,
        "over_limit": 0,
        "stale_by_age": 0,
        "stale_by_confidence": 0,
        "unknown_non_active": 0,
    }
    cand: list[dict[str, Any]] = []

    low_conf_cutoff = None
    if isinstance(min_confidence, int | float) and not isinstance(min_confidence, bool):
        low_conf_cutoff = max(0.0, min(1.0, float(min_confidence)))

    for line in path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            invalid_json_lines += 1
            cand.append({"raw": raw, "created_ts": 0.0})
            continue
        exp = obj.get("expires_at")
        if isinstance(exp, str) and exp.strip():
            try:
                exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=UTC)
                if exp_dt < now:
                    remove_expired += 1
                    by_reason["expired_by_ttl"] += 1
                    continue
            except ValueError:
                pass
        if low_conf_cutoff is not None and isinstance(obj, dict):
            conf = obj.get("confidence")
            conf_val = float(conf) if isinstance(conf, int | float) and not isinstance(conf, bool) else 0.0
            if conf_val < low_conf_cutoff:
                remove_low_conf += 1
                by_reason["low_confidence"] += 1
                continue
        if bool(drop_non_active) and isinstance(obj, dict):
            st = memory_entry_state(
                obj,
                stale_after_days=int(max(1, stale_after_days)),
                min_active_confidence=float(max(0.0, min(1.0, min_active_confidence))),
            )
            if st != "active":
                remove_non_active += 1
                reason = _prune_non_active_reason(
                    obj,
                    now=now,
                    stale_after_days=int(max(1, stale_after_days)),
                    min_active_confidence=float(max(0.0, min(1.0, min_active_confidence))),
                )
                if reason == "stale_by_age":
                    by_reason["stale_by_age"] += 1
                elif reason == "stale_by_confidence":
                    by_reason["stale_by_confidence"] += 1
                elif reason == "expired_by_ttl":
                    by_reason["expired_by_ttl"] += 1
                else:
                    by_reason["unknown_non_active"] += 1
                continue
        created_ts = _parse_created_at(obj) if isinstance(obj, dict) else 0.0
        cand.append({"raw": raw, "created_ts": created_ts})

    kept: list[str] = [str(x["raw"]) for x in cand]
    if isinstance(max_entries, int) and max_entries > 0:
        cap = int(max_entries)
        if len(cand) > cap:
            sorted_cand = sorted(cand, key=lambda x: float(x["created_ts"]), reverse=True)
            kept_set = {str(x["raw"]) for x in sorted_cand[:cap]}
            remove_limit = len(cand) - len(kept_set)
            by_reason["over_limit"] += remove_limit
            kept = [str(x["raw"]) for x in cand if str(x["raw"]) in kept_set]

    path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    removed_total = remove_expired + remove_low_conf + remove_limit + remove_non_active
    return {
        "schema_version": "memory_prune_result_v1",
        "removed_total": removed_total,
        "removed_expired": remove_expired,
        "removed_low_confidence": remove_low_conf,
        "removed_over_limit": remove_limit,
        "removed_non_active": remove_non_active,
        "invalid_json_lines": invalid_json_lines,
        "removed_by_reason": by_reason,
        "kept_total": len(kept),
    }


def save_instincts(root: str | Path, instincts: Iterable[Instinct]) -> Path | None:
    """将一组 Instinct 以 Markdown 形式持久化.

    当前实现采用简单的追加文件策略, 方便后续在 system prompt 中引用。
    """

    out_dir = _default_memory_dir(root)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    target = out_dir / f"instincts-{ts}.md"
    lines: list[str] = ["# Instincts snapshot", f"- generated_at: {ts}", ""]
    for inst in instincts:
        lines.append(f"## {inst.title}")
        if inst.tags:
            lines.append(f"- tags: {', '.join(inst.tags)}")
        lines.append(f"- confidence: {inst.confidence:.2f}")
        lines.append("")
        lines.append(inst.body.strip())
        lines.append("")
    target.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return target


def extract_basic_instincts_from_session(session: dict[str, Any]) -> List[Instinct]:
    """从单个会话 JSON 中提取最小 Instinct 信息.

    目前只基于 goal/answer 概要生成一条通用 Instinct, 后续可以
    升级为调用 LLM 进行结构化总结。
    """

    goal = session.get("goal") or ""
    answer = session.get("answer") or ""
    if not isinstance(goal, str):
        goal = str(goal)
    if not isinstance(answer, str):
        answer = str(answer)
    title = goal.strip()[:60] or "general-instinct"
    body = (
        "## Goal\n"
        f"{goal.strip()}\n\n"
        "## Observed solution\n"
        f"{answer.strip()}\n"
    )
    tags = ["auto", "session"]
    return [Instinct(title=title, body=body, tags=tags, confidence=0.5)]


def _word_jaccard_similarity(a: str, b: str) -> float:
    """简单词袋 Jaccard，用于冲突检测（与 backlog 的 n-gram 重叠同级近似）。"""
    wa = set(re.findall(r"[\w\u4e00-\u9fff]+", (a or "").lower(), flags=re.UNICODE))
    wb = set(re.findall(r"[\w\u4e00-\u9fff]+", (b or "").lower(), flags=re.UNICODE))
    wa = {x for x in wa if len(x) >= 2}
    wb = {x for x in wb if len(x) >= 2}
    if not wa and not wb:
        return 1.0
    if not wa or not wb:
        return 0.0
    inter = len(wa & wb)
    union = len(wa | wb)
    return float(inter) / float(union) if union else 0.0


def compute_memory_freshness_metrics(
    entries: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    freshness_days: int = 14,
) -> dict[str, Any]:
    """S2-02：记忆条目新鲜度 = 最近 ``freshness_days`` 天内创建的条目 / 总有效条目数。"""
    now_dt = now or datetime.now(UTC)
    window = max(1, int(freshness_days))
    since = now_dt - timedelta(days=window)
    n = len(entries)
    fresh = 0
    for row in entries:
        ct = _parse_dt(row.get("created_at"))
        if ct is not None and ct >= since:
            fresh += 1
    ratio = (float(fresh) / float(n)) if n else 0.0
    return {
        "freshness": round(ratio, 4),
        "freshness_days": window,
        "since_freshness": since.isoformat(),
        "memory_entries": n,
        "fresh_entries": fresh,
    }


def compute_memory_conflict_pairs(
    entries: list[dict[str, Any]],
    *,
    threshold: float = 0.85,
    max_pairs_returned: int = 3,
    max_compare_entries: int = 400,
) -> tuple[float, list[dict[str, Any]], int, int]:
    """返回 ``(conflict_rate, conflict_pairs_sample, conflict_pair_count, compared_entry_count)``。

    - ``conflict_rate`` = 超过阈值的条目对数 / max(1, 条目总数)（与 backlog S2-03 一致）。
    - 为控制耗时，仅对按 ``created_at`` 最近的 ``max_compare_entries`` 条做全两两比较；
      若 ``n_total`` 大于该上限，**分母仍为全量条目数**，分子仅统计该子集内的冲突对
     （与「全库两两不可行」的工程折衷一致，并在 ``compared_entry_count`` 中可观测）。
    """
    n_total = len(entries)
    if n_total <= 1:
        return 0.0, [], 0, min(n_total, max(1, int(max_compare_entries)))

    def created_key(row: dict[str, Any]) -> float:
        return -_parse_created_at(row)

    indexed = sorted(range(len(entries)), key=lambda i: created_key(entries[i]))
    cap = max(1, int(max_compare_entries))
    use_idx = indexed[:cap]
    use_entries = [entries[i] for i in use_idx]
    compared_entry_count = len(use_entries)
    thr = max(0.0, min(1.0, float(threshold)))
    conflict_pair_count = 0
    sample: list[dict[str, Any]] = []
    m = len(use_entries)
    for i in range(m):
        ti = str(use_entries[i].get("text", ""))
        idi = str(use_entries[i].get("id", ""))
        for j in range(i + 1, m):
            tj = str(use_entries[j].get("text", ""))
            idj = str(use_entries[j].get("id", ""))
            sim = _word_jaccard_similarity(ti, tj)
            if sim >= thr:
                conflict_pair_count += 1
                if len(sample) < max_pairs_returned:
                    sample.append(
                        {
                            "id_a": idi,
                            "id_b": idj,
                            "similarity": round(sim, 4),
                        },
                    )
    rate = float(conflict_pair_count) / float(max(1, n_total))
    return rate, sample, conflict_pair_count, compared_entry_count


def build_memory_health_payload(
    root: str | Path,
    *,
    days: int = 30,
    freshness_days: int = 14,
    session_pattern: str = ".cai-session*.json",
    session_limit: int = 200,
    conflict_threshold: float = 0.85,
    max_conflict_compare_entries: int = 400,
    reference_now: datetime | None = None,
    session_mtime_start: datetime | None = None,
    session_mtime_end_exclusive: datetime | None = None,
) -> dict[str, Any]:
    """S2-01：综合记忆健康评分 JSON（schema_version 1.0）。

    可选 ``session_mtime_start`` / ``session_mtime_end_exclusive``（与 ``reference_now`` 联用）用于按 UTC 时间窗截取会话（例如跨域按日趋势）。
    """
    from cai_agent.session import list_session_files, load_session

    root_path = Path(root).expanduser().resolve()
    clock = reference_now if reference_now is not None else datetime.now(UTC)
    if session_mtime_start is not None and session_mtime_end_exclusive is not None:
        since_sessions = session_mtime_start
        mtime_end_exc: datetime | None = session_mtime_end_exclusive
    else:
        since_sessions = clock - timedelta(days=max(1, int(days)))
        mtime_end_exc = None

    entries, memory_warnings = load_memory_entries_validated(root_path)
    fresh_metrics = compute_memory_freshness_metrics(
        entries,
        now=clock,
        freshness_days=int(freshness_days),
    )
    n_entries = int(fresh_metrics["memory_entries"])
    fresh_count = int(fresh_metrics["fresh_entries"])
    freshness = float(fresh_metrics["freshness"])
    session_paths = list_session_files(
        cwd=str(root_path),
        pattern=str(session_pattern),
        limit=max(1, int(session_limit)),
    )
    recent_sessions: list[Path] = []
    for p in session_paths:
        try:
            ts = datetime.fromtimestamp(p.stat().st_mtime, UTC)
        except OSError:
            continue
        if ts < since_sessions:
            continue
        if mtime_end_exc is not None and ts >= mtime_end_exc:
            continue
        recent_sessions.append(p)

    covered = 0
    skipped_short_goal = 0
    skipped_parse = 0
    for sp in recent_sessions:
        try:
            sess = load_session(str(sp))
        except Exception:
            skipped_parse += 1
            continue
        g = sess.get("goal") or ""
        if not isinstance(g, str):
            g = str(g)
        gstrip = g.strip()
        if len(gstrip) < 8:
            skipped_short_goal += 1
            continue
        needle = gstrip[:120]
        for row in entries:
            if needle in str(row.get("text", "")):
                covered += 1
                break

    n_recent = len(recent_sessions)
    sessions_considered = max(0, n_recent - skipped_parse - skipped_short_goal)
    coverage = (float(covered) / float(sessions_considered)) if sessions_considered else 0.0

    conflict_rate, conflict_pairs, conflict_pair_count, conflict_compared_entries = (
        compute_memory_conflict_pairs(
            entries,
            threshold=float(conflict_threshold),
            max_compare_entries=int(max_conflict_compare_entries),
        )
    )

    warn_penalty = 0.0
    if memory_warnings:
        warn_penalty = min(0.35, 0.06 * len(memory_warnings))

    dedup_component = max(0.0, 1.0 - min(1.0, conflict_rate * 3.0))
    integrity_component = max(0.0, 1.0 - warn_penalty)

    health_score = (
        0.28 * freshness
        + 0.34 * coverage
        + 0.28 * dedup_component
        + 0.10 * integrity_component
    )
    health_score = max(0.0, min(1.0, float(health_score)))

    if n_entries == 0 and n_recent == 0:
        health_score = 0.0

    if health_score >= 0.8:
        grade = "A"
    elif health_score >= 0.65:
        grade = "B"
    elif health_score >= 0.45:
        grade = "C"
    else:
        grade = "D"

    actions: list[str] = []
    if n_entries == 0 and n_recent > 0:
        actions.append("近期有会话但尚无结构化记忆条目，建议执行 `cai-agent memory extract`")
    if freshness < 0.3 and n_entries > 0:
        actions.append("记忆条目偏旧，建议补充 extract 或检查是否需 prune 过期项")
    if coverage < 0.4 and n_recent > 0:
        actions.append("会话与记忆覆盖偏低，建议提高 extract 频率或检查条目是否与会话目标对齐")
    if conflict_rate > 0.05:
        actions.append("检测到可能重复或冲突的记忆文本，建议人工审阅并去重")
    if memory_warnings:
        actions.append("修复 memory/entries.jsonl 中的无效行以提升数据完整性")
    if not actions:
        actions.append("记忆健康度良好：保持定期 `memory extract` 与 `memory prune` 即可")

    return {
        "schema_version": "1.0",
        "generated_at": clock.isoformat(),
        "window": {
            "days": max(1, int(days)),
            "since_sessions": since_sessions.isoformat(),
            "freshness_days": int(fresh_metrics["freshness_days"]),
            "since_freshness": str(fresh_metrics["since_freshness"]),
            "session_pattern": session_pattern,
            "session_limit": max(1, int(session_limit)),
        },
        "counts": {
            "memory_entries": n_entries,
            "recent_sessions": n_recent,
            "fresh_entries": fresh_count,
            "sessions_with_memory_hit": covered,
            "sessions_considered_for_coverage": sessions_considered,
            "coverage_skipped_short_goal": skipped_short_goal,
            "coverage_skipped_session_parse_error": skipped_parse,
        },
        "coverage_window_days": max(1, int(days)),
        "freshness": round(freshness, 4),
        "coverage": round(coverage, 4),
        "conflict_rate": round(conflict_rate, 6),
        "conflict_pairs": conflict_pairs,
        "conflict_pair_count": int(conflict_pair_count),
        "conflict_compared_entries": int(conflict_compared_entries),
        "conflict_max_compare_entries": int(max(1, int(max_conflict_compare_entries))),
        "conflict_similarity_metric": "word_jaccard",
        "conflict_threshold": float(max(0.0, min(1.0, float(conflict_threshold)))),
        "memory_warnings": memory_warnings,
        "health_score": round(health_score, 4),
        "grade": grade,
        "actions": actions,
    }


def extract_memory_entries_from_session(
    root: str | Path,
    session: dict[str, Any],
) -> MemoryEntry | None:
    goal = session.get("goal") or ""
    answer = session.get("answer") or ""
    if not isinstance(goal, str):
        goal = str(goal)
    if not isinstance(answer, str):
        answer = str(answer)
    text = f"{goal.strip()}\n\n{answer.strip()}".strip()
    if not text:
        return None
    return append_memory_entry(
        root,
        category="session",
        text=text,
        confidence=0.5,
        expires_at=None,
    )


def extract_memory_entries_structured(
    root: str | Path,
    session: dict[str, Any],
    *,
    settings: Any | None = None,
) -> dict[str, Any]:
    """可选 LLM 结构化抽取：从会话 goal+answer 中提取结构化记忆条目。

    当 ``settings`` 为 None 或 ``settings.mock=True`` 时退化为基于规则的启发式抽取
    （避免在 mock 模式下触发真实 LLM 调用）。

    返回 ``memory_extract_structured_v1`` 格式。
    """
    goal = str(session.get("goal") or "").strip()
    answer = str(session.get("answer") or "").strip()
    text = f"{goal}\n\n{answer}".strip()
    if not text:
        return {
            "schema_version": "memory_extract_structured_v1",
            "method": "skipped",
            "entries_written": 0,
            "entries": [],
            "skipped_invalid": [],
        }

    is_mock = (
        settings is None
        or bool(getattr(settings, "mock", False))
        or not bool(getattr(settings, "api_key", ""))
    )

    if is_mock:
        # 启发式规则：按句子切分，保留含动词/名词的有意义片段
        import re as _re
        candidates: list[dict[str, Any]] = []
        for line in _re.split(r"[。\n]", text):
            ln = line.strip()
            if len(ln) < 12 or len(ln) > 300:
                continue
            if not any(kw in ln for kw in ["是", "了", "的", "为", "有", "能", "可", "应", "需"]):
                continue
            candidates.append({
                "category": "insight",
                "text": ln,
                "confidence": 0.45,
            })
        entries_written = 0
        written_entries: list[dict[str, Any]] = []
        skipped_invalid: list[dict[str, Any]] = []
        for c in candidates[:5]:
            try:
                e = append_memory_entry(
                    root,
                    category=str(c["category"]),
                    text=str(c["text"]),
                    confidence=float(c["confidence"]),
                    source="structured_extract",
                )
                written_entries.append({
                    "id": e.id,
                    "category": e.category,
                    "text": e.text[:120],
                    "confidence": e.confidence,
                })
                entries_written += 1
            except MemoryEntryInvalid as ex:
                skipped_invalid.append({
                    "reason": classify_memory_entry_skip_reason(str(ex)),
                    "detail": str(ex),
                    "text_preview": str(c.get("text", ""))[:120],
                })
            except Exception as ex:
                skipped_invalid.append({
                    "reason": "unexpected_error",
                    "detail": f"{type(ex).__name__}:{ex}",
                    "text_preview": str(c.get("text", ""))[:120],
                })
        return {
            "schema_version": "memory_extract_structured_v1",
            "method": "heuristic",
            "entries_written": entries_written,
            "entries": written_entries,
            "skipped_invalid": skipped_invalid,
        }

    # LLM 模式：调用 chat_completion_by_role 返回 JSON 格式的记忆条目
    try:
        from cai_agent.llm_factory import chat_completion_by_role as _chat
        from cai_agent.llm import extract_json_object as _exj

        prompt = (
            "下面是一条 AI 会话（goal + answer），请从中提取 3-5 条结构化记忆条目，"
            "以 JSON 数组返回：\n"
            "[{\"category\":\"...\",\"text\":\"...\",\"confidence\":0.7},...]\n"
            "category 取 insight/fact/pattern/warning 之一。\n\n"
            f"---会话内容---\n{text[:2000]}\n---"
        )
        messages = [
            {"role": "system", "content": "你是记忆治理助手，只输出 JSON 数组，不加任何说明。"},
            {"role": "user", "content": prompt},
        ]
        raw_response = _chat(settings, messages, role="active")
        parsed = _exj(raw_response)
        entries_list = parsed if isinstance(parsed, list) else []
        entries_written = 0
        written_entries = []
        skipped_invalid_llm: list[dict[str, Any]] = []
        for item in entries_list[:8]:
            if not isinstance(item, dict):
                continue
            cat = str(item.get("category") or "insight").strip()
            txt = str(item.get("text") or "").strip()
            conf = float(item.get("confidence") or 0.5)
            if not txt or len(txt) < 5:
                continue
            try:
                e = append_memory_entry(
                    root,
                    category=cat,
                    text=txt,
                    confidence=conf,
                    source="structured_extract",
                )
                written_entries.append({
                    "id": e.id,
                    "category": e.category,
                    "text": e.text[:120],
                    "confidence": e.confidence,
                })
                entries_written += 1
            except MemoryEntryInvalid as ex:
                skipped_invalid_llm.append(
                    {
                        "reason": classify_memory_entry_skip_reason(str(ex)),
                        "detail": str(ex),
                        "text_preview": txt[:120],
                    },
                )
            except Exception as ex:
                skipped_invalid_llm.append(
                    {
                        "reason": "unexpected_error",
                        "detail": f"{type(ex).__name__}:{ex}",
                        "text_preview": txt[:120],
                    },
                )
        return {
            "schema_version": "memory_extract_structured_v1",
            "method": "llm",
            "entries_written": entries_written,
            "entries": written_entries,
            "skipped_invalid": skipped_invalid_llm,
        }
    except Exception as ex:
        return {
            "schema_version": "memory_extract_structured_v1",
            "method": "llm_failed",
            "error": str(ex)[:500],
            "entries_written": 0,
            "entries": [],
            "skipped_invalid": [],
        }
