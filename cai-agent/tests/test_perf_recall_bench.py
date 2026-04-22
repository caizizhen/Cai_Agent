from __future__ import annotations

import io
import subprocess
import sys
import unittest
from pathlib import Path


class PerfRecallBenchTests(unittest.TestCase):
    def test_script_runs_and_emits_markdown(self) -> None:
        root = Path(__file__).resolve().parents[2]
        script = root / "scripts" / "perf_recall_bench.py"
        self.assertTrue(script.is_file())
        proc = subprocess.run(
            [
                sys.executable,
                str(script),
                "--sessions",
                "3",
                "--runs",
                "1",
                "--output",
                "-",
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = proc.stdout or ""
        self.assertIn("# Recall performance benchmark", out)
        self.assertIn("| 3 |", out)


if __name__ == "__main__":
    unittest.main()
