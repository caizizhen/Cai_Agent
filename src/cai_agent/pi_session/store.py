from __future__ import annotations

import base64
import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cai_agent.paths import sessions_root
from cai_agent.pi_core.messages import AgentMessage

ALLOWED_IMAGE_MIME = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGES_PER_MESSAGE = 6


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(name: str) -> str:
    base = Path(str(name or "image")).name
    base = re.sub(r"[^\w.\-]+", "_", base).strip("._") or "image"
    return base[:80]


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

    def attachments_dir(self, session_id: str) -> Path:
        d = self.dir_for(session_id) / "attachments"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_image_bytes(
        self,
        session_id: str,
        *,
        data: bytes,
        mime: str,
        name: str = "image",
    ) -> dict[str, Any]:
        mime_n = str(mime or "image/png").split(";")[0].strip().lower()
        if mime_n == "image/jpg":
            mime_n = "image/jpeg"
        if mime_n not in ALLOWED_IMAGE_MIME:
            raise ValueError(f"unsupported image type: {mime_n}")
        if not data:
            raise ValueError("empty image")
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError(f"image too large (max {MAX_IMAGE_BYTES // (1024 * 1024)}MB)")
        ext = ALLOWED_IMAGE_MIME[mime_n]
        fid = uuid.uuid4().hex
        filename = f"{fid}{ext}"
        path = self.attachments_dir(session_id) / filename
        path.write_bytes(data)
        return {
            "id": fid,
            "name": _safe_name(name) if name else f"image{ext}",
            "mime": mime_n,
            "file": filename,
            "size": len(data),
        }

    def save_image_b64(
        self,
        session_id: str,
        *,
        data_b64: str,
        mime: str,
        name: str = "image",
    ) -> dict[str, Any]:
        raw = str(data_b64 or "").strip()
        if raw.startswith("data:") and "," in raw:
            header, raw = raw.split(",", 1)
            if not mime:
                meta = header[5:] if header.startswith("data:") else header
                mime = meta.split(";", 1)[0] if meta else "image/png"
        try:
            data = base64.b64decode(raw, validate=False)
        except Exception as e:
            raise ValueError(f"invalid image data: {e}") from e
        return self.save_image_bytes(session_id, data=data, mime=mime or "image/png", name=name)

    def resolve_images_for_llm(self, session_id: str, images: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Load attachment files into in-memory base64 payloads for the LLM."""
        out: list[dict[str, Any]] = []
        for img in images or []:
            if not isinstance(img, dict):
                continue
            if img.get("data") or img.get("data_b64"):
                out.append(
                    {
                        "name": img.get("name") or "image",
                        "mime": img.get("mime") or "image/png",
                        "data": img.get("data") or img.get("data_b64"),
                    },
                )
                continue
            fname = str(img.get("file") or "").strip()
            if not fname or "/" in fname or "\\" in fname or ".." in fname:
                continue
            path = self.attachments_dir(session_id) / fname
            if not path.is_file():
                continue
            data = path.read_bytes()
            mime = str(img.get("mime") or "image/png")
            out.append(
                {
                    "name": img.get("name") or fname,
                    "mime": mime,
                    "data": base64.b64encode(data).decode("ascii"),
                },
            )
        return out

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
        if isinstance(message.meta, dict):
            if message.meta.get("usage"):
                row["usage"] = message.meta["usage"]
            if message.meta.get("feedback"):
                row["feedback"] = message.meta["feedback"]
            if message.meta.get("images"):
                # Persist file refs only (no inline base64 in jsonl).
                refs = []
                for img in message.meta["images"] or []:
                    if not isinstance(img, dict):
                        continue
                    refs.append(
                        {
                            "id": img.get("id") or "",
                            "name": img.get("name") or "image",
                            "mime": img.get("mime") or "image/png",
                            "file": img.get("file") or "",
                            "size": img.get("size") or 0,
                        },
                    )
                if refs:
                    row["images"] = refs
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        if isinstance(message.meta, dict) and isinstance(message.meta.get("usage"), dict):
            self.add_usage(session_id, message.meta["usage"])
        else:
            self.touch(session_id)
        return row

    def load_rows(self, session_id: str) -> list[dict[str, Any]]:
        path = self.path_for(session_id)
        if not path.is_file():
            return []
        out: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                out.append(row)
        return out

    def load_messages(self, session_id: str) -> list[AgentMessage]:
        out: list[AgentMessage] = []
        for row in self.load_rows(session_id):
            meta: dict[str, Any] = {}
            if row.get("usage"):
                meta["usage"] = row["usage"]
            if row.get("feedback"):
                meta["feedback"] = row["feedback"]
            if row.get("images"):
                # Hydrate for LLM (base64) while keeping file refs available.
                refs = [i for i in (row.get("images") or []) if isinstance(i, dict)]
                meta["images"] = self.resolve_images_for_llm(session_id, refs)
                meta["image_refs"] = refs
            out.append(
                AgentMessage(
                    role=str(row.get("role") or "user"),
                    content=str(row.get("content") or ""),
                    tool_calls=list(row.get("tool_calls") or []),
                    tool_call_id=str(row.get("tool_call_id") or ""),
                    name=str(row.get("name") or ""),
                    meta=meta,
                ),
            )
        return out

    def add_usage(self, session_id: str, usage: dict[str, Any]) -> dict[str, Any]:
        meta = self.ensure_meta(session_id)
        totals = meta.get("usage_total") if isinstance(meta.get("usage_total"), dict) else {}
        for k in (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "cache_read_tokens",
            "cache_write_tokens",
        ):
            totals[k] = int(totals.get(k) or 0) + int(usage.get(k) or 0)
        meta["usage_total"] = totals
        meta["updated_at"] = _now()
        return self.save_meta(session_id, meta)

    def add_run_metrics(self, session_id: str, metrics: dict[str, Any]) -> dict[str, Any]:
        """Accumulate per-run timing / step counters into session meta."""
        meta = self.ensure_meta(session_id)
        acc = meta.get("run_metrics") if isinstance(meta.get("run_metrics"), dict) else {}
        for k in ("rounds", "steps", "ttft_count"):
            acc[k] = int(acc.get(k) or 0) + int(metrics.get(k) or 0)
        for k in ("model_ms", "tool_ms", "ttft_sum_ms"):
            acc[k] = float(acc.get(k) or 0) + float(metrics.get(k) or 0)
        meta["run_metrics"] = acc
        meta["updated_at"] = _now()
        return self.save_meta(session_id, meta)

    def set_feedback(self, session_id: str, seq: int, vote: str) -> dict[str, Any]:
        vote = str(vote or "").strip().lower()
        if vote not in ("up", "down", ""):
            raise ValueError("vote must be up, down, or empty")
        rows = self.load_rows(session_id)
        found = False
        path = self.path_for(session_id)
        rewritten: list[dict[str, Any]] = []
        for row in rows:
            if int(row.get("seq") or 0) == int(seq):
                found = True
                if vote:
                    row["feedback"] = vote
                else:
                    row.pop("feedback", None)
            rewritten.append(row)
        if not found:
            raise ValueError("message not found")
        with path.open("w", encoding="utf-8") as f:
            for row in rewritten:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        meta = self.ensure_meta(session_id)
        fb = meta.get("feedback") if isinstance(meta.get("feedback"), dict) else {}
        key = str(seq)
        if vote:
            fb[key] = vote
        else:
            fb.pop(key, None)
        meta["feedback"] = fb
        meta["updated_at"] = _now()
        self.save_meta(session_id, meta)
        return {"session_id": session_id, "seq": seq, "feedback": vote or None}

    def branch(self, session_id: str, *, upto_seq: int | None = None) -> str:
        """Create a new session copying messages (optionally up to seq)."""
        rows = self.load_rows(session_id)
        if upto_seq is not None:
            rows = [r for r in rows if int(r.get("seq") or 0) <= int(upto_seq)]
        new_id = self.new_id()
        src_meta = self.load_meta(session_id)
        self.ensure_meta(new_id, workspace=str(src_meta.get("workspace") or ""))
        path = self.path_for(new_id)
        with path.open("w", encoding="utf-8") as f:
            for i, row in enumerate(rows, start=1):
                cloned = dict(row)
                cloned["seq"] = i
                cloned.pop("feedback", None)
                f.write(json.dumps(cloned, ensure_ascii=False) + "\n")
        src_att = self.dir_for(session_id) / "attachments"
        if src_att.is_dir():
            shutil.copytree(src_att, self.attachments_dir(new_id), dirs_exist_ok=True)
        self.touch(new_id, workspace=str(src_meta.get("workspace") or "") or None)
        return new_id

    def session_stats(self, session_id: str, *, context_window: int = 128_000) -> dict[str, Any]:
        rows = self.load_rows(session_id)
        meta = self.ensure_meta(session_id)
        totals = meta.get("usage_total") if isinstance(meta.get("usage_total"), dict) else {}
        prompt = int(totals.get("prompt_tokens") or 0)
        completion = int(totals.get("completion_tokens") or 0)
        total = int(totals.get("total_tokens") or (prompt + completion))
        cache_read = int(totals.get("cache_read_tokens") or 0)
        cache_write = int(totals.get("cache_write_tokens") or 0)
        uncached_input = max(0, prompt - cache_read)
        cache_denom = cache_read + uncached_input
        cache_hit_pct = round(100.0 * cache_read / cache_denom, 1) if cache_denom else 0.0
        window = max(1, int(context_window or 128_000))
        # estimate context = chars of retained messages / 4
        chars = sum(len(str(r.get("content") or "")) for r in rows)
        context_used = max(prompt or 0, (chars + 3) // 4) if rows else 0
        if not context_used and total:
            context_used = min(total, window)
        rm = meta.get("run_metrics") if isinstance(meta.get("run_metrics"), dict) else {}
        model_ms = float(rm.get("model_ms") or 0)
        tool_ms = float(rm.get("tool_ms") or 0)
        ttft_count = int(rm.get("ttft_count") or 0)
        ttft_avg_ms = (
            float(rm.get("ttft_sum_ms") or 0) / ttft_count if ttft_count else 0.0
        )
        tps = (completion / (model_ms / 1000.0)) if model_ms > 0 and completion else 0.0
        rounds = int(rm.get("rounds") or 0)
        if not rounds:
            rounds = sum(1 for r in rows if r.get("role") == "user")
        steps = int(rm.get("steps") or 0)
        if not steps:
            steps = sum(1 for r in rows if r.get("role") in ("assistant", "tool"))
        return {
            "session_id": session_id,
            "messages": len(rows),
            "rounds": rounds,
            "steps": steps,
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": total,
            "cache_read_tokens": cache_read,
            "cache_write_tokens": cache_write,
            "uncached_input_tokens": uncached_input,
            "cache_hit_pct": cache_hit_pct,
            "model_ms": model_ms,
            "tool_ms": tool_ms,
            "ttft_avg_ms": ttft_avg_ms,
            "tps": round(tps, 1),
            "context_used": context_used,
            "context_window": window,
            "context_pct": min(100.0, round(100.0 * context_used / window, 1)),
        }

    def preview(self, session_id: str, max_len: int = 80) -> str:
        msgs = self.load_messages(session_id)
        for m in msgs:
            if m.role == "user" and m.content.strip():
                t = m.content.strip().replace("\n", " ")
                return t[:max_len]
        return session_id[:12]

    def delete(self, session_id: str) -> bool:
        """Remove a session directory. Returns True if something was deleted."""
        sid = str(session_id or "").strip()
        if not sid or "/" in sid or "\\" in sid or sid in (".", ".."):
            raise ValueError("invalid session id")
        d = self.root / sid
        if not d.is_dir():
            return False
        shutil.rmtree(d)
        return True
