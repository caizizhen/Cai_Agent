from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from cai_agent.__main__ import main


class ReleaseGaCliTests(unittest.TestCase):
    def test_release_ga_pass(self) -> None:
        with (
            patch("cai_agent.__main__.run_quality_gate", return_value={"ok": True, "failed_count": 0}),
            patch("cai_agent.__main__.run_security_scan", return_value={"ok": True, "findings_count": 0}),
            patch("cai_agent.__main__.aggregate_sessions", return_value={"failure_rate": 0.0, "total_tokens": 10}),
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(
                    [
                        "release-ga",
                        "--json",
                        "--with-security-scan",
                        "--max-failure-rate",
                        "0.2",
                        "--max-tokens",
                        "100",
                    ],
                )
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue().strip())
        self.assertEqual(payload.get("ok"), True)
        self.assertEqual(payload.get("failed_checks"), [])

    def test_release_ga_fail_on_thresholds(self) -> None:
        with (
            patch("cai_agent.__main__.run_quality_gate", return_value={"ok": False, "failed_count": 2}),
            patch("cai_agent.__main__.run_security_scan", return_value={"ok": False, "findings_count": 3}),
            patch(
                "cai_agent.__main__.aggregate_sessions",
                return_value={"failure_rate": 0.8, "total_tokens": 9999},
            ),
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(
                    [
                        "release-ga",
                        "--json",
                        "--max-failure-rate",
                        "0.2",
                        "--max-tokens",
                        "100",
                        "--with-security-scan",
                    ],
                )
        self.assertEqual(rc, 2)
        payload = json.loads(buf.getvalue().strip())
        self.assertEqual(payload.get("ok"), False)
        failed = payload.get("failed_checks") or []
        self.assertIn("quality_gate", failed)
        self.assertIn("security_scan", failed)
        self.assertIn("session_failure_rate", failed)
        self.assertIn("token_budget", failed)


if __name__ == "__main__":
    unittest.main()
