"""Recall FTS5 索引（H1-M-04）：SQLite FTS5 虚拟表，可选替代 JSON 索引。"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from cai_agent.session import list_session_files, load_session

FTS5_DB_REL = ".cai-recall-fts5.sqlite"
META_REL = ".cai-recall-fts5.meta.json"


def fts5_db_path(cwd: str | Path) -> Path:
    return Path(cwd).expanduser().resolve() / FTS5_DB_REL


def fts5_meta_path(cwd: str | Path) -> Path:
    return Path(cwd).expanduser().resolve() / META_REL


def build_fts5_recall_index(
    *,
    cwd: str,
    pattern: str,
    limit: int,
    days: int,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    since = now - timedelta(days=max(days, 1))
    since_ts = since.timestamp()
    files = list_session_files(cwd=cwd, pattern=pattern, limit=limit)
    dbp = fts5_db_path(cwd)
    dbp.parent.mkdir(parents=True, exist_ok=True)
    if dbp.is_file():
        dbp.unlink()
    conn = sqlite3.connect(str(dbp))
    try:
        conn.execute("CREATE VIRTUAL TABLE recall_fts USING fts5(path UNINDEXED, mtime UNINDEXED, content)")
        parse_skipped = 0
        indexed = 0
        for p in files:
            if p.stat().st_mtime < since_ts:
                continue
            try:
                sess = load_session(str(p))
            except Exception:
                parse_skipped += 1
                continue
            fragments: list[str] = []
            ans = sess.get("answer")
            if isinstance(ans, str) and ans.strip():
                fragments.append(ans.strip())
            msgs = sess.get("messages")
            if isinstance(msgs, list):
                for msg in msgs:
                    if not isinstance(msg, dict):
                        continue
                    c = msg.get("content")
                    if isinstance(c, str) and c.strip():
                        fragments.append(c.strip())
            blob = "\n".join(fragments)
            if not blob.strip():
                continue
            conn.execute(
                "INSERT INTO recall_fts(path, mtime, content) VALUES (?,?,?)",
                (str(p), int(p.stat().st_mtime), blob),
            )
            indexed += 1
        conn.commit()
    finally:
        conn.close()
    meta = {
        "schema_version": "recall_fts5_meta_v1",
        "generated_at": now.isoformat(),
        "engine": "fts5",
        "db_file": str(dbp),
        "sessions_indexed": indexed,
        "parse_skipped": parse_skipped,
        "window_days": max(days, 1),
    }
    fts5_meta_path(cwd).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "schema_version": "recall_fts5_build_v1",
        "index_file": str(dbp),
        "meta_file": str(fts5_meta_path(cwd)),
        "sessions_indexed": indexed,
        "parse_skipped": parse_skipped,
        "engine": "fts5",
    }


def search_fts5_recall(
    *,
    cwd: str,
    query: str,
    limit: int,
    days: int,
    hits_per_session: int,
) -> list[dict[str, Any]]:
    """BM25 风格 FTS5 查询；返回与 ``_build_recall_payload`` 近似的 ``results`` 行结构。"""
    dbp = fts5_db_path(cwd)
    if not dbp.is_file():
        return []
    now = datetime.now(UTC)
    since_ts = (now - timedelta(days=max(days, 1))).timestamp()
    conn = sqlite3.connect(str(dbp))
    rows_out: list[dict[str, Any]] = []
    try:
        # sqlite FTS5: escape double quotes in query
        q = (query or "").strip().replace('"', '""')
        if not q:
            return []
        cur = conn.execute(
            "SELECT path, mtime, snippet(recall_fts, 2, '[', ']', '…', 32) AS snip "
            "FROM recall_fts WHERE recall_fts MATCH ? AND mtime >= ? "
            "ORDER BY bm25(recall_fts) LIMIT ?",
            (q, int(since_ts), max(1, limit * max(1, hits_per_session))),
        )
        for path, mtime, snip in cur.fetchall():
            rows_out.append(
                {
                    "path": path,
                    "mtime": int(mtime),
                    "model": None,
                    "task_id": None,
                    "answer_preview": "",
                    "hits": [{"snippet": snip or "", "message_index": 1}],
                    "hits_count": 1,
                    "score": 0.0,
                    "score_breakdown": {"engine": "fts5"},
                },
            )
    finally:
        conn.close()
    return rows_out[: max(1, limit)]


def fts5_index_age_seconds(cwd: str | Path) -> float | None:
    mp = fts5_meta_path(cwd)
    if not mp.is_file():
        return None
    try:
        doc = json.loads(mp.read_text(encoding="utf-8"))
        raw = doc.get("generated_at")
        if not isinstance(raw, str):
            return None
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return max(0.0, time.time() - dt.timestamp())
    except Exception:
        return None
