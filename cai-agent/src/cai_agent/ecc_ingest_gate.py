"""ECC-N02-D05/ECC-N02-D07: pack / skills-hub ingest gate aligned with ``hook_runtime`` dangerous-command rules."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cai_agent.hook_runtime import (
    hook_argv_matches_ingest_denylist,
    list_hook_argv_danger_matches,
    resolve_hook_argv_for_pack_scan,
)

_PACK_COMPONENTS = ("rules", "skills", "agents", "commands")
_TRUST_ORDER = {
    "unknown": 0,
    "community": 1,
    "publisher_verified": 1,
    "reviewed": 2,
    "local_reviewed": 2,
}
_TRUST_ORDER_MIN_REVIEWED = 2
_REGISTRY_CANDIDATES = (
    "ecc-asset-registry.json",
    ".cai/ecc-asset-registry.json",
    "cai-asset-registry.json",
    ".cai/cai-asset-registry.json",
)


def _trust_rank(level: str) -> int:
    return _TRUST_ORDER.get(str(level or "").strip().lower(), 0)


def _load_asset_registry(root: Path) -> tuple[dict[str, Any] | None, str | None, str | None]:
    for rel in _REGISTRY_CANDIDATES:
        p = root / rel
        if not p.is_file():
            continue
        try:
            obj = json.loads(p.read_text(encoding="utf-8-sig"))
        except Exception as e:
            return None, str(p), f"registry_unparseable:{e}"
        if not isinstance(obj, dict):
            return None, str(p), "registry_not_object"
        if obj.get("schema_version") != "ecc_asset_registry_v1":
            return None, str(p), "registry_schema_mismatch"
        return obj, str(p), None
    return None, None, "registry_missing"


def build_ecc_ingest_trust_decision_v1(
    source_workspace: str | Path,
    *,
    sanitizer_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Conservative provenance/trust gate for pack/import/install flows."""
    root = Path(source_workspace).expanduser().resolve()
    gate = sanitizer_gate if isinstance(sanitizer_gate, dict) else build_ecc_pack_ingest_gate_v1(root)
    sanitizer_decision = str(gate.get("decision") or "unknown")
    if not bool(gate.get("allow", False)):
        return {
            "schema_version": "ecc_ingest_trust_decision_v1",
            "policy_status": "enforced_metadata_gate",
            "source_workspace": str(root),
            "registry_path": None,
            "sanitizer_decision": sanitizer_decision,
            "trust_level": "unknown",
            "signature_scheme": "unknown",
            "signature_verified": False,
            "combined_decision": "reject",
            "allow_apply": False,
            "reason": "Sanitizer rejected this source before provenance/trust evaluation.",
            "checks": [
                {"id": "sanitizer", "status": "fail", "reason": sanitizer_decision},
            ],
        }

    registry, registry_path, registry_error = _load_asset_registry(root)
    checks: list[dict[str, Any]] = [
        {"id": "sanitizer", "status": "pass", "reason": sanitizer_decision},
    ]
    if registry is None:
        checks.append({"id": "registry", "status": "fail", "reason": registry_error or "registry_missing"})
        return {
            "schema_version": "ecc_ingest_trust_decision_v1",
            "policy_status": "enforced_metadata_gate",
            "source_workspace": str(root),
            "registry_path": registry_path,
            "sanitizer_decision": sanitizer_decision,
            "trust_level": "unknown",
            "signature_scheme": "none",
            "signature_verified": False,
            "combined_decision": "review",
            "allow_apply": False,
            "reason": "Source has no valid ecc_asset_registry_v1 provenance metadata; apply is blocked by default.",
            "checks": checks,
        }

    assets = registry.get("assets") if isinstance(registry.get("assets"), list) else []
    if not assets:
        checks.append({"id": "registry.assets", "status": "fail", "reason": "assets_empty"})
        min_level = "unknown"
    else:
        checks.append({"id": "registry.assets", "status": "pass", "reason": f"assets_count={len(assets)}"})
        levels: list[str] = []
        missing_required: list[str] = []
        signature_verified = False
        signature_scheme = "none"
        for idx, asset in enumerate(assets):
            if not isinstance(asset, dict):
                continue
            trust = asset.get("trust") if isinstance(asset.get("trust"), dict) else {}
            source = asset.get("source") if isinstance(asset.get("source"), dict) else {}
            integrity = asset.get("integrity") if isinstance(asset.get("integrity"), dict) else {}
            signature = asset.get("signature") if isinstance(asset.get("signature"), dict) else {}
            levels.append(str(trust.get("level") or "unknown").strip().lower() or "unknown")
            if not str(source.get("kind") or "").strip():
                missing_required.append(f"assets[{idx}].source.kind")
            if not str(source.get("origin") or "").strip():
                missing_required.append(f"assets[{idx}].source.origin")
            if not str(integrity.get("hash_algo") or "").strip():
                missing_required.append(f"assets[{idx}].integrity.hash_algo")
            if not str(integrity.get("hash_value") or "").strip():
                missing_required.append(f"assets[{idx}].integrity.hash_value")
            if bool(signature.get("verified")):
                signature_verified = True
            if str(signature.get("scheme") or "").strip():
                signature_scheme = str(signature.get("scheme")).strip()
        min_level = min(levels or ["unknown"], key=_trust_rank)
        if missing_required:
            checks.append({"id": "provenance.minimum_fields", "status": "fail", "missing": missing_required})
        else:
            checks.append({"id": "provenance.minimum_fields", "status": "pass", "reason": "all_present"})

    missing = next((c for c in checks if c.get("id") == "provenance.minimum_fields" and c.get("status") == "fail"), None)
    trust_ok = _trust_rank(min_level) >= _TRUST_ORDER_MIN_REVIEWED
    combined = "allow_metadata_only" if trust_ok and missing is None else "review"
    reason = (
        "Sanitizer passed and all assets declare reviewed-or-better provenance metadata."
        if combined == "allow_metadata_only"
        else "Sanitizer passed, but trust is below reviewed or provenance metadata is incomplete."
    )
    return {
        "schema_version": "ecc_ingest_trust_decision_v1",
        "policy_status": "enforced_metadata_gate",
        "source_workspace": str(root),
        "registry_path": registry_path,
        "sanitizer_decision": sanitizer_decision,
        "trust_level": min_level,
        "signature_scheme": locals().get("signature_scheme", "none"),
        "signature_verified": bool(locals().get("signature_verified", False)),
        "combined_decision": combined,
        "allow_apply": combined == "allow_metadata_only",
        "reason": reason,
        "checks": checks,
    }


def _scan_hooks_json_at(path: Path, project_root: Path, violations: list[dict[str, Any]]) -> int:
    """Parse one ``hooks.json`` and append violations. Returns hook entry count processed."""
    hooks_entries_seen = 0
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        violations.append(
            {
                "kind": "hooks_json_unreadable",
                "path": str(path),
                "detail": str(e),
            },
        )
        return 0
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError as e:
        violations.append(
            {
                "kind": "hooks_json_unparseable",
                "path": str(path),
                "detail": str(e),
            },
        )
        return 0
    if not isinstance(doc, dict):
        violations.append(
            {
                "kind": "invalid_hooks_document",
                "path": str(path),
                "reason": "root_not_object",
            },
        )
        return 0
    hooks = doc.get("hooks")
    if hooks is None:
        return 0
    if not isinstance(hooks, list):
        violations.append(
            {
                "kind": "invalid_hooks_document",
                "path": str(path),
                "reason": "hooks_not_array",
            },
        )
        return 0
    for h in hooks:
        if not isinstance(h, dict):
            continue
        hooks_entries_seen += 1
        hid = str(h.get("id") or "").strip() or None
        argv, reason = resolve_hook_argv_for_pack_scan(
            h,
            hooks_file=path,
            project_root=project_root,
        )
        if reason == "script_outside_workspace":
            violations.append(
                {
                    "kind": "script_outside_workspace",
                    "path": str(path),
                    "hook_id": hid,
                },
            )
            continue
        if argv is None:
            continue
        if hook_argv_matches_ingest_denylist(argv, strict=False):
            hits = list_hook_argv_danger_matches(argv, strict=False)
            violations.append(
                {
                    "kind": "dangerous_command_pattern",
                    "path": str(path),
                    "hook_id": hid,
                    "matched_fragments": hits,
                },
            )
    return hooks_entries_seen


def _finalize_gate_payload(
    *,
    source_workspace: Path,
    violations: list[dict[str, Any]],
    hooks_files_scanned: int,
    hooks_entries_seen: int,
    ingest_scan_kind: str,
    explicit_scanned_paths: list[str] | None = None,
) -> dict[str, Any]:
    allow = len(violations) == 0
    decision = "allow_metadata_only" if allow else "reject"
    blocked: list[str] = []
    seen: set[str] = set()
    for v in violations:
        for frag in v.get("matched_fragments") or []:
            s = str(frag)
            if s and s not in seen:
                seen.add(s)
                blocked.append(s)

    checks: list[dict[str, str]] = [
        {
            "id": "pack.hooks_json_scan",
            "status": "pass" if allow else "fail",
            "reason": "no_violations" if allow else "violations_present",
        },
    ]

    out: dict[str, Any] = {
        "schema_version": "ecc_pack_ingest_gate_v1",
        "policy_mode": "deny_exec",
        "decision": decision,
        "allow": allow,
        "source_workspace": str(source_workspace),
        "checks": checks,
        "violations": violations,
        "blocked_patterns": blocked,
        "hooks_files_scanned": hooks_files_scanned,
        "hooks_entries_seen": hooks_entries_seen,
        "ingest_scan_kind": ingest_scan_kind,
    }
    if explicit_scanned_paths is not None:
        out["explicit_scanned_paths"] = explicit_scanned_paths
    return out


def build_ecc_pack_ingest_gate_for_explicit_hooks_v1(
    project_root: str | Path,
    hook_paths: list[Path | str],
) -> dict[str, Any]:
    """Scan only the given ``hooks.json`` paths (deduped), each must live under *project_root*.

    Used by **skills hub install** when the manifest copies ``hooks.json`` entries.
    """
    root = Path(project_root).expanduser().resolve()
    violations: list[dict[str, Any]] = []
    hooks_files_scanned = 0
    hooks_entries_seen = 0
    scanned_list: list[str] = []
    seen: set[str] = set()

    if not root.is_dir():
        return {
            "schema_version": "ecc_pack_ingest_gate_v1",
            "policy_mode": "deny_exec",
            "decision": "reject",
            "allow": False,
            "source_workspace": str(root),
            "checks": [
                {
                    "id": "pack.source_workspace_exists",
                    "status": "fail",
                    "reason": "source_workspace_missing",
                },
            ],
            "violations": [
                {
                    "kind": "source_workspace_missing",
                    "path": str(root),
                },
            ],
            "blocked_patterns": [],
            "hooks_files_scanned": 0,
            "hooks_entries_seen": 0,
            "ingest_scan_kind": "explicit_hooks",
            "explicit_scanned_paths": [],
        }

    for raw in hook_paths:
        p = Path(raw).expanduser().resolve()
        sp = str(p)
        if sp in seen:
            continue
        seen.add(sp)
        if p.name != "hooks.json":
            continue
        try:
            p.relative_to(root)
        except ValueError:
            violations.append(
                {
                    "kind": "hooks_path_outside_workspace",
                    "path": sp,
                },
            )
            continue
        if not p.is_file():
            violations.append(
                {
                    "kind": "hooks_json_missing",
                    "path": sp,
                },
            )
            continue
        hooks_files_scanned += 1
        scanned_list.append(sp)
        hooks_entries_seen += _scan_hooks_json_at(p, root, violations)

    return _finalize_gate_payload(
        source_workspace=root,
        violations=violations,
        hooks_files_scanned=hooks_files_scanned,
        hooks_entries_seen=hooks_entries_seen,
        ingest_scan_kind="explicit_hooks",
        explicit_scanned_paths=list(scanned_list),
    )


def build_ecc_pack_ingest_gate_v1(source_workspace: str | Path) -> dict[str, Any]:
    """Scan ``rules|skills|agents|commands`` under *source_workspace* for ``hooks.json`` execution vectors.

    Uses the same dangerous-command substring set as ``hook_runtime`` (standard / non-strict profile).
    """
    root = Path(source_workspace).expanduser().resolve()
    violations: list[dict[str, Any]] = []
    hooks_files_scanned = 0
    hooks_entries_seen = 0

    if not root.is_dir():
        return {
            "schema_version": "ecc_pack_ingest_gate_v1",
            "policy_mode": "deny_exec",
            "decision": "reject",
            "allow": False,
            "source_workspace": str(root),
            "checks": [
                {
                    "id": "pack.source_workspace_exists",
                    "status": "fail",
                    "reason": "source_workspace_missing",
                },
            ],
            "violations": [
                {
                    "kind": "source_workspace_missing",
                    "path": str(root),
                },
            ],
            "blocked_patterns": [],
            "hooks_files_scanned": 0,
            "hooks_entries_seen": 0,
            "ingest_scan_kind": "workspace_components",
        }

    for comp in _PACK_COMPONENTS:
        base = root / comp
        if not base.is_dir():
            continue
        for path in base.rglob("hooks.json"):
            if not path.is_file():
                continue
            hooks_files_scanned += 1
            hooks_entries_seen += _scan_hooks_json_at(path, root, violations)

    return _finalize_gate_payload(
        source_workspace=root,
        violations=violations,
        hooks_files_scanned=hooks_files_scanned,
        hooks_entries_seen=hooks_entries_seen,
        ingest_scan_kind="workspace_components",
    )
