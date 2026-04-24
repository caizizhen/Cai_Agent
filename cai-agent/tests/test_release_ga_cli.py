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
        self.assertEqual((payload.get("release_runbook") or {}).get("schema_version"), "release_runbook_v1")
        names = [c.get("name") for c in (payload.get("checks") or []) if isinstance(c, dict)]
        self.assertIn("changelog_bilingual", names)
        self.assertIn("changelog_semantic", names)

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
        failed_details = payload.get("failed_check_details") or []
        self.assertTrue(any(isinstance(row, dict) and row.get("name") == "quality_gate" for row in failed_details))

    def test_release_ga_includes_doctor_and_memory_nudge_gate(self) -> None:
        with (
            patch("cai_agent.__main__.run_quality_gate", return_value={"ok": True, "failed_count": 0}),
            patch("cai_agent.__main__.run_security_scan", return_value={"ok": True, "findings_count": 0}),
            patch("cai_agent.__main__.aggregate_sessions", return_value={"failure_rate": 0.0, "total_tokens": 10}),
            patch("cai_agent.__main__.run_doctor", return_value=2),
            patch("cai_agent.__main__._build_memory_nudge_payload", return_value={"severity": "high"}),
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(
                    [
                        "release-ga",
                        "--json",
                        "--with-security-scan",
                        "--with-doctor",
                        "--with-memory-nudge",
                        "--memory-max-severity",
                        "medium",
                        "--max-failure-rate",
                        "0.2",
                        "--max-tokens",
                        "100",
                    ],
                )
        self.assertEqual(rc, 2)
        payload = json.loads(buf.getvalue().strip())
        failed = payload.get("failed_checks") or []
        self.assertIn("doctor", failed)
        self.assertIn("memory_nudge", failed)

    def test_release_ga_memory_state_gate(self) -> None:
        with (
            patch("cai_agent.__main__.run_quality_gate", return_value={"ok": True, "failed_count": 0}),
            patch("cai_agent.__main__.aggregate_sessions", return_value={"failure_rate": 0.0, "total_tokens": 10}),
            patch(
                "cai_agent.__main__.evaluate_memory_entry_states",
                return_value={
                    "schema_version": "memory_state_eval_v1",
                    "rows": [{"id": "a"}, {"id": "b"}, {"id": "c"}, {"id": "d"}, {"id": "e"}],
                    "counts": {"active": 2, "stale": 3, "expired": 0},
                    "warnings": [],
                    "stale_after_days": 30,
                    "min_active_confidence": 0.4,
                },
            ),
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(
                    [
                        "release-ga",
                        "--json",
                        "--with-memory-state",
                        "--memory-max-stale-ratio",
                        "0.50",
                        "--memory-max-expired-ratio",
                        "0.10",
                        "--max-failure-rate",
                        "0.2",
                        "--max-tokens",
                        "100",
                    ],
                )
        self.assertEqual(rc, 2)
        payload = json.loads(buf.getvalue().strip())
        failed = payload.get("failed_checks") or []
        self.assertIn("memory_state", failed)

        checks = payload.get("checks") or []
        mcheck = next((c for c in checks if isinstance(c, dict) and c.get("name") == "memory_state"), None)
        self.assertIsInstance(mcheck, dict)
        actual = mcheck.get("actual") if isinstance(mcheck, dict) else {}
        if not isinstance(actual, dict):
            actual = {}
        self.assertEqual(actual.get("stale_rate"), 0.6)
        self.assertEqual(actual.get("expired_rate"), 0.0)

    def test_release_ga_text_output_prints_writeback_targets(self) -> None:
        with (
            patch("cai_agent.__main__.run_quality_gate", return_value={"ok": True, "failed_count": 0}),
            patch("cai_agent.__main__.aggregate_sessions", return_value={"failure_rate": 0.0, "total_tokens": 10}),
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(
                    [
                        "release-ga",
                        "--max-failure-rate",
                        "0.2",
                        "--max-tokens",
                        "100",
                    ],
                )
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("[release-ga] runbook:", out)
        self.assertIn("[release-ga] writeback targets:", out)
        self.assertIn("CHANGELOG.md", out)

    def test_release_ga_with_memory_policy_gate(self) -> None:
        with (
            patch("cai_agent.__main__.run_quality_gate", return_value={"ok": True, "failed_count": 0}),
            patch("cai_agent.__main__.aggregate_sessions", return_value={"failure_rate": 0.0, "total_tokens": 10}),
            patch(
                "cai_agent.memory.build_memory_entries_jsonl_validate_report",
                return_value={
                    "exists": True,
                    "ok": True,
                    "valid_lines": 3,
                    "invalid_lines": [],
                    "entries_file": "/tmp/x",
                },
            ),
        ):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main(
                    [
                        "release-ga",
                        "--json",
                        "--with-memory-policy",
                        "--max-failure-rate",
                        "0.2",
                        "--max-tokens",
                        "100",
                    ],
                )
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue().strip())
        names = [c.get("name") for c in (payload.get("checks") or []) if isinstance(c, dict)]
        self.assertIn("memory_policy_entries", names)


if __name__ == "__main__":
    unittest.main()
