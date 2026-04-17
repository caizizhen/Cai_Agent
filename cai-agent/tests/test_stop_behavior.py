from __future__ import annotations

import unittest

from cai_agent.config import Settings
from cai_agent.graph import build_app, initial_state


def _settings() -> Settings:
    return Settings.from_env(config_path=None)


class StopBehaviorTests(unittest.TestCase):
    def test_graph_stops_immediately_when_requested(self) -> None:
        settings = _settings()
        app = build_app(settings, should_stop=lambda: True)
        state = initial_state(settings, "任意任务")
        final = app.invoke(state)
        self.assertTrue(bool(final.get("finished")))
        self.assertIn("已手动停止", str(final.get("answer", "")))


if __name__ == "__main__":
    unittest.main()
