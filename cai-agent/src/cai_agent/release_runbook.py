from __future__ import annotations

from pathlib import Path
from typing import Any

from cai_agent.changelog_semantic import build_changelog_semantic_compare
from cai_agent.changelog_sync import check_changelog_bilingual
from cai_agent.feedback import feedback_stats


def default_release_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def resolve_release_repo_root(*candidates: str | Path | None) -> Path:
    for cand in candidates:
        if cand is None:
            continue
        root = Path(cand).expanduser().resolve()
        if (root / "CHANGELOG.md").is_file() and (root / "docs" / "qa" / "T7_RELEASE_GATE_CHECKLIST.zh-CN.md").is_file():
            return root
    return default_release_repo_root()


def _rel_doc_entry(repo_root: Path, rel_path: str, *, kind: str) -> dict[str, Any]:
    abs_path = repo_root / rel_path
    return {
        "kind": kind,
        "path": rel_path.replace("\\", "/"),
        "exists": abs_path.is_file(),
    }


def build_release_runbook_payload(
    *,
    repo_root: str | Path,
    workspace: str | Path,
) -> dict[str, Any]:
    root = resolve_release_repo_root(repo_root)
    workspace_path = Path(workspace).expanduser().resolve()
    docs = [
        _rel_doc_entry(root, "docs/CHANGELOG_SYNC.zh-CN.md", kind="changelog_sync"),
        _rel_doc_entry(root, "docs/qa/T7_RELEASE_GATE_CHECKLIST.zh-CN.md", kind="t7_checklist"),
        _rel_doc_entry(root, "docs/PRODUCT_PLAN.zh-CN.md", kind="product_plan"),
        _rel_doc_entry(root, "docs/PRODUCT_GAP_ANALYSIS.zh-CN.md", kind="product_gap_analysis"),
        _rel_doc_entry(root, "docs/PARITY_MATRIX.zh-CN.md", kind="parity_matrix"),
        _rel_doc_entry(root, "CHANGELOG.md", kind="changelog_en"),
        _rel_doc_entry(root, "CHANGELOG.zh-CN.md", kind="changelog_zh"),
    ]
    runbook_steps = [
        {
            "id": "doctor",
            "command": "cai-agent doctor --json",
            "purpose": "capture current health and config summary",
        },
        {
            "id": "release_changelog",
            "command": "cai-agent release-changelog --json --semantic",
            "purpose": "verify bilingual and structural changelog sync",
        },
        {
            "id": "smoke",
            "command": "python scripts/smoke_new_features.py",
            "purpose": "run repo smoke coverage before release",
        },
        {
            "id": "regression",
            "command": "QA_SKIP_LOG=1 python scripts/run_regression.py",
            "purpose": "run the heavier regression pass when the release scope needs it",
        },
        {
            "id": "feedback_export",
            "command": "cai-agent feedback export --dest dist/feedback-export.jsonl --json",
            "purpose": "archive recent user/operator feedback alongside the release notes",
        },
    ]
    writeback_targets = [
        _rel_doc_entry(root, "docs/PRODUCT_PLAN.zh-CN.md", kind="product_plan"),
        _rel_doc_entry(root, "docs/PRODUCT_GAP_ANALYSIS.zh-CN.md", kind="product_gap_analysis"),
        _rel_doc_entry(root, "docs/PARITY_MATRIX.zh-CN.md", kind="parity_matrix"),
        _rel_doc_entry(root, "CHANGELOG.md", kind="changelog_en"),
        _rel_doc_entry(root, "CHANGELOG.zh-CN.md", kind="changelog_zh"),
    ]
    bilingual = check_changelog_bilingual(repo_root=root)
    semantic = build_changelog_semantic_compare(repo_root=root)
    docs_ok = all(bool(row.get("exists")) for row in docs)
    release_state = "ok" if docs_ok and bool(bilingual.get("ok")) and bool(semantic.get("ok")) else "needs_attention"
    return {
        "schema_version": "release_runbook_v1",
        "repo_root": str(root),
        "workspace": str(workspace_path),
        "state": release_state,
        "docs": docs,
        "runbook_steps": runbook_steps,
        "writeback_targets": writeback_targets,
        "changelog": {
            "bilingual": bilingual,
            "semantic": semantic,
        },
        "feedback": feedback_stats(workspace_path),
    }
