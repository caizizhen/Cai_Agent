from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cai_agent.__main__ import main


class MemoryPrunePolicyCliTests(unittest.TestCase):
    def test_prune_by_confidence_and_keep_limit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mem_dir = root / "memory"
            mem_dir.mkdir(parents=True, exist_ok=True)
            entries = mem_dir / "entries.jsonl"
            rows = [
                {
                    "id": "a",
                    "category": "session",
                    "text": "alpha",
                    "confidence": 0.20,
                    "expires_at": None,
                    "created_at": "2024-01-01T00:00:00+00:00",
                },
                {
                    "id": "b",
                    "category": "session",
                    "text": "beta",
                    "confidence": 0.90,
                    "expires_at": None,
                    "created_at": "2024-01-02T00:00:00+00:00",
                },
                {
                    "id": "c",
                    "category": "session",
                    "text": "gamma",
                    "confidence": 0.80,
                    "expires_at": None,
                    "created_at": "2024-01-03T00:00:00+00:00",
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
                            "--min-confidence",
                            "0.5",
                            "--max-entries",
                            "1",
                        ],
                    )
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("removed_total"), 2)
            self.assertEqual(payload.get("removed_low_confidence"), 1)
            self.assertEqual(payload.get("removed_over_limit"), 1)
            kept_lines = [
                ln
                for ln in entries.read_text(encoding="utf-8").splitlines()
                if ln.strip()
            ]
            self.assertEqual(len(kept_lines), 1)
            kept = json.loads(kept_lines[0])
            self.assertEqual(kept.get("id"), "c")


if __name__ == "__main__":
    unittest.main()
