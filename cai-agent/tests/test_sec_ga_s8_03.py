"""Hermes S8-03: GA security gates (security-scan on src, no quoted long sk- literals)."""

from __future__ import annotations

import re
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from cai_agent.config import Settings
from cai_agent.security_scan import run_security_scan


def _cai_agent_src() -> Path:
    return Path(__file__).resolve().parents[1] / "src"


class SecGaS803Tests(unittest.TestCase):
    def test_security_scan_cai_agent_src_has_no_high_findings(self) -> None:
        src = _cai_agent_src()
        self.assertTrue(src.is_dir(), str(src))
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / "cai-agent.toml").write_text(
                '[llm]\nbase_url = "http://127.0.0.1:1/v1"\nmodel = "m"\napi_key = "k"\n',
                encoding="utf-8",
            )
            s = Settings.from_env(config_path=str(root / "cai-agent.toml"))
            s = replace(s, workspace=str(src))
            out = run_security_scan(s)
        self.assertEqual(out.get("schema_version"), "security_scan_result_v1")
        self.assertTrue(
            bool(out.get("ok")),
            f"security_scan ok=false: {out.get('findings')!r}",
        )

    def test_no_quoted_openai_like_key_literals_in_src(self) -> None:
        """SEC-GA-002 style: reject long sk-… strings inside quotes (not regex rule definitions)."""
        bad = re.compile(r"""['"]sk-[a-zA-Z0-9]{36,}['"]""")
        src = _cai_agent_src()
        hits: list[str] = []
        for path in sorted(src.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(text.splitlines(), start=1):
                if bad.search(line):
                    hits.append(f"{path.relative_to(src)}:{i}:{line.strip()[:120]}")
        self.assertEqual(
            hits,
            [],
            "Possible hardcoded API key pattern in src:\n" + "\n".join(hits),
        )
