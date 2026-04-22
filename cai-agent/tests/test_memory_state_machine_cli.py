from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cai_agent.__main__ import main


class MemoryStateMachineCliTests(unittest.TestCase):
    def test_memory_list_includes_state_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem_dir = root / "memory"
            mem_dir.mkdir(parents=True, exist_ok=True)
            entries = mem_dir / "entries.jsonl"
            rows = [
                {
                    "id": "active-1",
                    "category": "session",
                    "text": "fresh and reliable",
                    "confidence": 0.9,
                    "expires_at": None,
                    "created_at": "2099-01-01T00:00:00+00:00",
                },
                {
                    "id": "stale-1",
                    "category": "session",
                    "text": "old and low confidence",
                    "confidence": 0.3,
                    "expires_at": None,
                    "created_at": "2020-01-01T00:00:00+00:00",
                },
            ]
            entries.write_text(
                "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["memory", "list", "--json", "--limit", "10"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "memory_list_v1")
            entries = payload.get("entries") or []
            self.assertEqual(len(entries), 2)
            by_id = {str(x.get("id")): x for x in entries if isinstance(x, dict)}
            self.assertEqual(by_id["active-1"].get("state"), "active")
            self.assertEqual(by_id["stale-1"].get("state"), "stale")
            self.assertIn("state_reason", by_id["active-1"])
            self.assertIn("state_reason", by_id["stale-1"])

    def test_memory_search_json_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem_dir = root / "memory"
            mem_dir.mkdir(parents=True, exist_ok=True)
            entries = mem_dir / "entries.jsonl"
            row = {
                "id": "s-1",
                "category": "session",
                "text": "needle for search",
                "confidence": 0.8,
                "expires_at": None,
                "created_at": "2099-01-01T00:00:00+00:00",
            }
            entries.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["memory", "search", "needle", "--json", "--limit", "5"])
            self.assertEqual(rc, 0)
            out = json.loads(buf.getvalue().strip())
            self.assertEqual(out.get("schema_version"), "memory_search_v1")
            self.assertEqual(out.get("query"), "needle")
            hits = out.get("hits") or []
            self.assertEqual(len(hits), 1)
            self.assertEqual(str((hits[0] or {}).get("id")), "s-1")

    def test_memory_instincts_json_envelope_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "memory" / "instincts").mkdir(parents=True, exist_ok=True)
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["memory", "instincts", "--json", "--limit", "5"])
            self.assertEqual(rc, 0)
            out = json.loads(buf.getvalue().strip())
            self.assertEqual(out.get("schema_version"), "memory_instincts_list_v1")
            self.assertEqual(out.get("paths"), [])

    def test_memory_extract_json_envelope_empty_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(["memory", "extract", "--limit", "5"])
            self.assertEqual(rc, 0)
            out = json.loads(buf.getvalue().strip())
            self.assertEqual(out.get("schema_version"), "memory_extract_v1")
            self.assertEqual(out.get("entries_appended"), 0)
            self.assertEqual(out.get("written"), [])

    def test_memory_prune_removes_non_active_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem_dir = root / "memory"
            mem_dir.mkdir(parents=True, exist_ok=True)
            entries = mem_dir / "entries.jsonl"
            rows = [
                {
                    "id": "keep-active",
                    "category": "session",
                    "text": "good",
                    "confidence": 0.8,
                    "expires_at": None,
                    "created_at": "2099-01-01T00:00:00+00:00",
                },
                {
                    "id": "drop-stale",
                    "category": "session",
                    "text": "old",
                    "confidence": 0.2,
                    "expires_at": None,
                    "created_at": "2020-01-01T00:00:00+00:00",
                },
            ]
            entries.write_text(
                "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                encoding="utf-8",
            )
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "memory",
                            "prune",
                            "--json",
                            "--drop-non-active",
                            "--state-stale-after-days",
                            "30",
                            "--state-min-active-confidence",
                            "0.4",
                        ],
                    )
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(int(payload.get("removed_non_active") or 0), 1)
            kept_lines = [
                ln
                for ln in entries.read_text(encoding="utf-8").splitlines()
                if ln.strip()
            ]
            self.assertEqual(len(kept_lines), 1)
            kept = json.loads(kept_lines[0])
            self.assertEqual(kept.get("id"), "keep-active")


if __name__ == "__main__":
    unittest.main()
