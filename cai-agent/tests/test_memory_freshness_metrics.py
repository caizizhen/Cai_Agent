from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from cai_agent.memory import compute_memory_freshness_metrics


class MemoryFreshnessMetricsTests(unittest.TestCase):
    def test_half_recent_in_window(self) -> None:
        now = datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC)
        old = (now - timedelta(days=40)).isoformat()
        new = (now - timedelta(days=3)).isoformat()
        entries = [
            {"id": "a", "category": "x", "text": "t", "confidence": 0.5, "expires_at": None, "created_at": old},
            {"id": "b", "category": "x", "text": "u", "confidence": 0.5, "expires_at": None, "created_at": new},
        ]
        m = compute_memory_freshness_metrics(entries, now=now, freshness_days=14)
        self.assertEqual(m["freshness"], 0.5)
        self.assertEqual(m["fresh_entries"], 1)
        self.assertEqual(m["memory_entries"], 2)


if __name__ == "__main__":
    unittest.main()
