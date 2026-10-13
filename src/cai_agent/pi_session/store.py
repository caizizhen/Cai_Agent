from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cai_agent.paths import sessions_root
from cai_agent.pi_core.messages import AgentMessage


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or sessions_root()
        self.root.mkdir(parents=True, exist_ok=True)

    def list_ids(self) -> list[str]:
        if not self.root.is_dir():
            return []
        ids = [p.name for p in self.root.iterdir() if p.is_dir() and (p / "session.jsonl").is_file()]
        return sorted(ids, reverse=True)

    def dir_for(self, session_id: str) -> Path:
        d = self.root / session_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def path_for(self, session_id: str) -> Path:
        path = self.dir_for(session_id) / "session.jsonl"
        if not path.is_file():
            path.touch()
        return path

    def meta_path(self, session_id: str) -> Path:
        return self.dir_for(session_id) / "meta.json"

    def new_id(self) -> str:
        return uuid.uuid4().hex

    def load_meta(self, session_id: str) -> dict[str, Any]:
        path = self.meta_path(session_id)
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def save_meta(self, session_id: str, meta: dict[str, Any]) -> dict[str, Any]:
        path = self.meta_path(session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return meta

    def ensure_meta(self, session_id: str, *, workspace: str | None = None) -> dict[str, Any]:
        meta = self.load_meta(session_id)
        changed = False
        if "created_at" not in meta:
            meta["created_at"] = _now()
            changed = True
        if "updated_at" not in meta:
            meta["updated_at"] = meta["created_at"]
            changed = True
        if workspace and not meta.get("workspace"):
            meta["workspace"] = workspace
            changed = True
        if changed:
            self.save_meta(session_id, meta)
        return meta

    def touch(self, session_id: str, *, workspace: str | None = None) -> dict[str, Any]:
        meta = self.ensure_meta(session_id, workspace=workspace)
        meta["updated_at"] = _now()
        if workspace:
            meta["workspace"] = workspace
        return self.save_meta(session_id, meta)

    def _mtime_iso(self, session_id: str) -> str:
        path = self.path_for(session_id)
        if path.is_file():
            return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        return _now()

    def list_sessions(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for sid in self.list_ids():
            meta = self.ensure_meta(sid)
            updated = str(meta.get("updated_at") or self._mtime_iso(sid))
            items.append(
                {
                    "id": sid,
                    "preview": self.preview(sid),
                    "workspace": str(meta.get("workspace") or ""),
                    "updated_at": updated,
                    "created_at": str(meta.get("created_at") or updated),
                },
            )
        items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        return items

    def append(self, session_id: str, message: AgentMessage) -> dict[str, Any]:
        path = self.path_for(session_id)
        seq = 1
        if path.is_file():
            with path.open("r", encoding="utf-8") as f:
                seq = sum(1 for _ in f) + 1
        row: dict[str, Any] = {
            "v": 1,
            "seq": seq,
            "ts": _now(),
            "role": message.role,
            "content": message.content,
        }
        if message.tool_calls:
            row["tool_calls"] = message.tool_calls
        if message.tool_call_id:
            row["tool_call_id"] = message.tool_call_id
        if message.name:
            row["name"] = message.name
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        self.touch(session_id)
        return row

    def load_messages(self, session_id: str) -> list[AgentMessage]:
        path = self.path_for(session_id)
        if not path.is_file():
            return []
        out: list[AgentMessage] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            out.append(
                AgentMessage(
                    role=str(row.get("role") or "user"),
                    content=str(row.get("content") or ""),
                    tool_calls=list(row.get("tool_calls") or []),
                    tool_call_id=str(row.get("tool_call_id") or ""),
                    name=str(row.get("name") or ""),
                ),
            )
        return out

    def preview(self, session_id: str, max_len: int = 80) -> str:
        msgs = self.load_messages(session_id)
        for m in msgs:
            if m.role == "user" and m.content.strip():
                t = m.content.strip().replace("\n", " ")
                return t[:max_len]
        return session_id[:12]
