from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from cai_agent.__main__ import main
from cai_agent.session import save_session


class ObserveReportCliTests(unittest.TestCase):
    def test_observe_report_json_alerts_and_state(self) -> None:
        with TemporaryDirectory() as td:
            root = Path(td)
            save_session(
                str(root / ".cai-session-a.json"),
                {
                    "version": 2,
                    "elapsed_ms": 15,
                    "total_tokens": 500,
                    "prompt_tokens": 300,
                    "completion_tokens": 200,
                    "error_count": 1,
                    "events": [{"event": "run.started"}, {"event": "run.finished"}],
                },
            )
            save_session(
                str(root / ".cai-session-b.json"),
                {
                    "version": 2,
                    "elapsed_ms": 10,
                    "total_tokens": 600,
                    "prompt_tokens": 350,
                    "completion_tokens": 250,
                    "error_count": 0,
                    "events": [{"event": "run.started"}],
                },
            )

            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "observe-report",
                            "--json",
                            "--fail-failure-rate",
                            "0.2",
                            "--fail-token-budget",
                            "1000",
                        ],
                    )
            self.assertEqual(rc, 2)
            payload = json.loads(buf.getvalue().strip())
            self.assertEqual(payload.get("schema_version"), "observe_report_v1")
            self.assertEqual(payload.get("state"), "fail")
            alerts = payload.get("alerts") or []
            names = [str(a.get("metric")) for a in alerts if isinstance(a, dict)]
            self.assertIn("failure_rate", names)
            self.assertIn("total_tokens", names)


if __name__ == "__main__":
    unittest.main()
