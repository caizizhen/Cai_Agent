"""SQLite-backed user model store (Honcho-lite): beliefs, events, tags under ``.cai/``."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator


USER_MODEL_STORE_REL = ".cai/user_model_store.sqlite3"


def user_model_store_path(cwd: str | Path) -> Path:
    return Path(cwd).expanduser().resolve() / USER_MODEL_STORE_REL


@contextmanager
def _connect(path: Path) -> Iterator[sqlite3.Connection]:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path), timeout=30.0)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
    finally:
        con.close()


def init_user_model_store(cwd: str | Path) -> Path:
    """Create tables if missing; returns store path."""
    p = user_model_store_path(cwd)
    with _connect(p) as con:
        con.executescript(
            """
            PRAGMA journal_mode=DELETE;
            CREATE TABLE IF NOT EXISTS beliefs (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.5,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                source TEXT
            );
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                payload_json TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tags (
                belief_id TEXT NOT NULL,
                tag TEXT NOT NULL,
                PRIMARY KEY (belief_id, tag)
            );
            CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);
            CREATE INDEX IF NOT EXISTS idx_beliefs_updated ON beliefs(updated_at);
            """,
        )
        con.commit()
    return p


def upsert_belief(
    cwd: str | Path,
    *,
    text: str,
    confidence: float = 0.5,
    tags: list[str] | None = None,
    source: str | None = "cli_learn",
) -> dict[str, Any]:
    """Insert or update a belief by normalized text key (exact text match)."""
    t = (text or "").strip()
    if not t:
        raise ValueError("belief text must be non-empty")
    c = max(0.0, min(1.0, float(confidence)))
    now = datetime.now(UTC).isoformat()
    p = user_model_store_path(cwd)
    init_user_model_store(cwd)
    bid = str(uuid.uuid4())
    with _connect(p) as con:
        cur = con.execute("SELECT id FROM beliefs WHERE text = ?", (t,))
        row = cur.fetchone()
        if row:
            bid = str(row["id"])
            con.execute(
                "UPDATE beliefs SET confidence = ?, updated_at = ?, source = COALESCE(?, source) WHERE id = ?",
                (c, now, source, bid),
            )
        else:
            con.execute(
                "INSERT INTO beliefs (id, text, confidence, created_at, updated_at, source) VALUES (?,?,?,?,?,?)",
                (bid, t, c, now, now, source),
            )
        con.execute("DELETE FROM tags WHERE belief_id = ?", (bid,))
        for tg in tags or []:
            tg2 = str(tg).strip()
            if tg2:
                con.execute(
                    "INSERT OR IGNORE INTO tags (belief_id, tag) VALUES (?, ?)",
                    (bid, tg2[:64]),
                )
        con.commit()
    return {"id": bid, "text": t, "confidence": c, "updated_at": now}


def append_event(
    cwd: str | Path,
    *,
    kind: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    eid = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    p = user_model_store_path(cwd)
    init_user_model_store(cwd)
    pj = json.dumps(payload or {}, ensure_ascii=False)
    with _connect(p) as con:
        con.execute(
            "INSERT INTO events (id, kind, payload_json, created_at) VALUES (?,?,?,?)",
            (eid, str(kind or "event")[:120], pj, now),
        )
        con.commit()
    return {"id": eid, "kind": kind, "created_at": now}


def list_recent_beliefs(cwd: str | Path, *, limit: int = 50) -> list[dict[str, Any]]:
    lim = max(1, min(500, int(limit)))
    p = user_model_store_path(cwd)
    if not p.is_file():
        return []
    with _connect(p) as con:
        rows = con.execute(
            "SELECT id, text, confidence, created_at, updated_at, source FROM beliefs ORDER BY updated_at DESC LIMIT ?",
            (lim,),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "text": r["text"],
                "confidence": float(r["confidence"] or 0.0),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "source": r["source"],
            },
        )
    return out


def query_beliefs_by_text(cwd: str | Path, *, needle: str, limit: int = 20) -> list[dict[str, Any]]:
    """Substring match on belief text (case-insensitive)."""
    n = (needle or "").strip().lower()
    lim = max(1, min(200, int(limit)))
    if not n:
        return []
    p = user_model_store_path(cwd)
    if not p.is_file():
        return []
    with _connect(p) as con:
        rows = con.execute(
            """
            SELECT b.id, b.text, b.confidence, b.updated_at,
                   GROUP_CONCAT(t.tag, ',') AS tags
            FROM beliefs b
            LEFT JOIN tags t ON t.belief_id = b.id
            WHERE lower(b.text) LIKE '%' || ? || '%'
            GROUP BY b.id
            ORDER BY b.updated_at DESC
            LIMIT ?
            """,
            (n, lim),
        ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        tags_raw = r["tags"] or ""
        tags = [x for x in str(tags_raw).split(",") if x.strip()]
        out.append(
            {
                "id": r["id"],
                "text": r["text"],
                "confidence": float(r["confidence"] or 0.0),
                "updated_at": r["updated_at"],
                "tags": tags,
            },
        )
    return out


def export_store_payload(cwd: str | Path, *, belief_limit: int = 100, event_limit: int = 50) -> dict[str, Any]:
    """Snapshot for embedding in ``memory_user_model_v3``."""
    p = user_model_store_path(cwd)
    if not p.is_file():
        return {
            "schema_version": "user_model_store_snapshot_v1",
            "store_path": str(p),
            "store_exists": False,
            "beliefs": [],
            "recent_events": [],
        }
    bl = max(1, min(500, int(belief_limit)))
    el = max(1, min(500, int(event_limit)))
    with _connect(p) as con:
        brows = con.execute(
            "SELECT id, text, confidence, created_at, updated_at, source FROM beliefs ORDER BY updated_at DESC LIMIT ?",
            (bl,),
        ).fetchall()
        erows = con.execute(
            "SELECT id, kind, payload_json, created_at FROM events ORDER BY created_at DESC LIMIT ?",
            (el,),
        ).fetchall()
    beliefs: list[dict[str, Any]] = []
    for r in brows:
        beliefs.append(
            {
                "id": r["id"],
                "text": (r["text"] or "")[:400],
                "confidence": float(r["confidence"] or 0.0),
                "updated_at": r["updated_at"],
            },
        )
    events: list[dict[str, Any]] = []
    for r in erows:
        try:
            payload = json.loads(r["payload_json"] or "{}")
        except json.JSONDecodeError:
            payload = {}
        events.append(
            {
                "id": r["id"],
                "kind": r["kind"],
                "created_at": r["created_at"],
                "payload": payload if isinstance(payload, dict) else {},
            },
        )
    return {
        "schema_version": "user_model_store_snapshot_v1",
        "store_path": str(p),
        "store_exists": True,
        "beliefs": beliefs,
        "recent_events": events,
    }
