from __future__ import annotations

import tempfile
from pathlib import Path

from cai_agent.user_model_store import (
    export_store_payload,
    init_user_model_store,
    query_beliefs_by_text,
    upsert_belief,
)


def test_user_model_store_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        init_user_model_store(root)
        upsert_belief(root, text="prefers pytest", confidence=0.7, tags=["qa"])
        upsert_belief(root, text="prefers pytest", confidence=0.9, tags=["ci"])
        hits = query_beliefs_by_text(root, needle="pytest", limit=5)
        assert len(hits) == 1
        assert float(hits[0].get("confidence") or 0) >= 0.89
        snap = export_store_payload(root)
        assert snap.get("schema_version") == "user_model_store_snapshot_v1"
        assert len(snap.get("beliefs") or []) >= 1
