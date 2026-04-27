from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cai_agent.profiles import ProfilesError, clone_profile_home_tree


class ProfileHomeIsolationTests(unittest.TestCase):
    def test_clone_profile_home_tree_rejects_illegal_destination_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            ws = Path(td)
            src_sessions = ws / ".cai" / "profiles" / "src" / "sessions"
            src_sessions.mkdir(parents=True)
            (src_sessions / "marker.txt").write_text("ok", encoding="utf-8")
            with self.assertRaises(ProfilesError):
                clone_profile_home_tree(ws, "src", "../escape")


if __name__ == "__main__":
    unittest.main()
