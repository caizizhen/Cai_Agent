"""ECC-N02-D05: pack source ingest gate aligned with ``hook_runtime`` dangerous-command rules."""

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
        }

    for comp in _PACK_COMPONENTS:
        base = root / comp
        if not base.is_dir():
            continue
        for path in base.rglob("hooks.json"):
            if not path.is_file():
                continue
            hooks_files_scanned += 1
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
                continue
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
                continue
            if not isinstance(doc, dict):
                violations.append(
                    {
                        "kind": "invalid_hooks_document",
                        "path": str(path),
                        "reason": "root_not_object",
                    },
                )
                continue
            hooks = doc.get("hooks")
            if hooks is None:
                continue
            if not isinstance(hooks, list):
                violations.append(
                    {
                        "kind": "invalid_hooks_document",
                        "path": str(path),
                        "reason": "hooks_not_array",
                    },
                )
                continue
            for h in hooks:
                if not isinstance(h, dict):
                    continue
                hooks_entries_seen += 1
                hid = str(h.get("id") or "").strip() or None
                argv, reason = resolve_hook_argv_for_pack_scan(
                    h,
                    hooks_file=path,
                    project_root=root,
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

    return {
        "schema_version": "ecc_pack_ingest_gate_v1",
        "policy_mode": "deny_exec",
        "decision": decision,
        "allow": allow,
        "source_workspace": str(root),
        "checks": checks,
        "violations": violations,
        "blocked_patterns": blocked,
        "hooks_files_scanned": hooks_files_scanned,
        "hooks_entries_seen": hooks_entries_seen,
    }
