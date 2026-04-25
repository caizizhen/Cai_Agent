"""[models.routing] parse + match + CLI routing-test."""
from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from cai_agent.__main__ import main
from cai_agent.config import Settings
from cai_agent.model_routing import (
    first_matching_routing_rule,
    model_routing_enabled,
    parse_model_routing_section,
)

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "cai_agent"
    / "schemas"
    / "models_routing_test_v1.schema.json"
)
_FALLBACK_CANDIDATES_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "cai_agent"
    / "schemas"
    / "model_fallback_candidates_v1.schema.json"
)
_ROUTING_EXPLAIN_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "cai_agent"
    / "schemas"
    / "routing_explain_v1.schema.json"
)


class ModelRoutingParseTests(unittest.TestCase):
    def test_models_routing_test_v1_schema_file(self) -> None:
        raw = _SCHEMA_PATH.read_text(encoding="utf-8")
        sch = json.loads(raw)
        self.assertEqual(sch["properties"]["schema_version"]["const"], "models_routing_test_v1")
        self.assertIn("matched_rule", sch.get("required", []))

    def test_model_fallback_candidates_v1_schema_file(self) -> None:
        sch = json.loads(_FALLBACK_CANDIDATES_SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            sch["properties"]["schema_version"]["const"],
            "model_fallback_candidates_v1",
        )
        self.assertFalse(sch["properties"]["auto_switch"]["const"])
        self.assertIn("candidates", sch.get("required", []))

    def test_routing_explain_v1_schema_file(self) -> None:
        sch = json.loads(_ROUTING_EXPLAIN_SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertEqual(sch["properties"]["schema_version"]["const"], "routing_explain_v1")
        self.assertIn("decision", sch.get("required", []))

    def test_parse_rules_and_enabled(self) -> None:
        data = {
            "models": {
                "active": "fast",
                "routing": {
                    "enabled": True,
                    "version": 1,
                    "rules": [
                        {
                            "roles": ["planner"],
                            "goal_regex": "(?i)security",
                            "profile": "review",
                        },
                        {
                            "roles": ["active"],
                            "goal_substring": "翻译",
                            "profile": "review",
                        },
                    ],
                },
            },
        }
        self.assertTrue(model_routing_enabled(data))
        rules = parse_model_routing_section(data)
        self.assertEqual(len(rules), 2)
        self.assertEqual(rules[0].profile_id, "review")

    def test_first_match_planner_regex(self) -> None:
        data = {
            "models": {
                "routing": {
                    "rules": [
                        {
                            "roles": ["planner"],
                            "goal_regex": "(?i)audit",
                            "profile": "review",
                        },
                    ],
                },
            },
        }
        rules = parse_model_routing_section(data)
        hit = first_matching_routing_rule(rules, role="planner", goal="Please AUDIT the code")
        self.assertIsNotNone(hit)
        self.assertEqual(hit.profile_id, "review")
        self.assertIsNone(
            first_matching_routing_rule(rules, role="active", goal="Please AUDIT the code"),
        )

    def test_disabled_routing_flag(self) -> None:
        data = {"models": {"routing": {"enabled": False, "rules": []}}}
        self.assertFalse(model_routing_enabled(data))

    def test_parse_cost_only_rule(self) -> None:
        data = {
            "models": {
                "routing": {
                    "rules": [
                        {
                            "roles": ["active"],
                            "cost_budget_remaining_tokens_below": 500,
                            "profile": "tiny",
                        },
                    ],
                },
            },
        }
        rules = parse_model_routing_section(data)
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0].cost_budget_remaining_tokens_below, 500)
        self.assertIsNone(rules[0].goal_substring)

    def test_cost_condition_requires_remaining_below_threshold(self) -> None:
        rules = parse_model_routing_section(
            {
                "models": {
                    "routing": {
                        "rules": [
                            {
                                "cost_budget_remaining_tokens_below": 1000,
                                "profile": "p",
                            },
                        ],
                    },
                },
            },
        )
        self.assertIsNone(
            first_matching_routing_rule(
                rules,
                role="active",
                goal="",
                cost_budget_max_tokens=10_000,
                total_tokens_used=8000,
            ),
        )
        hit = first_matching_routing_rule(
            rules,
            role="active",
            goal="",
            cost_budget_max_tokens=10_000,
            total_tokens_used=9200,
        )
        self.assertIsNotNone(hit)
        self.assertEqual(hit.profile_id, "p")


class ModelRoutingCliTests(unittest.TestCase):
    def test_routing_test_json_hit(self) -> None:
        toml = "\n".join(
            [
                "[llm]",
                'provider = "openai_compatible"',
                'base_url = "http://127.0.0.1:9/v1"',
                'model = "m"',
                'api_key = "k"',
                "",
                "[agent]",
                "mock = true",
                "",
                "[models]",
                'active = "fast"',
                "",
                "[[models.profile]]",
                'id = "fast"',
                'provider = "openai_compatible"',
                'base_url = "http://127.0.0.1:9/v1"',
                'model = "m-fast"',
                'api_key = "k"',
                "",
                "[[models.profile]]",
                'id = "review"',
                'provider = "openai_compatible"',
                'base_url = "http://127.0.0.1:9/v1"',
                'model = "m-review"',
                'api_key = "k"',
                "",
                "[models.routing]",
                "version = 1",
                "",
                "[[models.routing.rules]]",
                'roles = ["planner"]',
                'goal_regex = "(?i)plan"',
                'profile = "review"',
                "",
            ],
        )
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = root / "cai-agent.toml"
            cfg.write_text(toml, encoding="utf-8")
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "models",
                            "--config",
                            str(cfg),
                            "routing-test",
                            "--goal",
                            "PLAN the migration",
                            "--role",
                            "planner",
                            "--json",
                        ],
                    )
            self.assertEqual(rc, 0)
            o = json.loads(buf.getvalue().strip())
            self.assertEqual(o.get("schema_version"), "models_routing_test_v1")
            self.assertEqual(o.get("base_profile_id"), "fast")
            self.assertEqual(o.get("effective_profile_id"), "review")
            self.assertIsNotNone(o.get("matched_rule"))
            self.assertIn("cost_budget_max_tokens", o)
            self.assertIn("cost_budget_remaining", o)
            ex = o.get("explain")
            self.assertIsInstance(ex, dict)
            self.assertEqual(ex.get("schema_version"), "routing_explain_v1")
            self.assertEqual(ex.get("decision"), "matched_rule")
            fb = o.get("fallback_candidates")
            self.assertIsInstance(fb, dict)
            self.assertEqual(fb.get("schema_version"), "model_fallback_candidates_v1")
            self.assertFalse(fb.get("auto_switch"))
            candidates = fb.get("candidates") or []
            self.assertTrue(candidates)
            self.assertEqual(candidates[0].get("profile_id"), "fast")
            self.assertIn("capabilities", candidates[0])

    def test_routing_test_text_summary(self) -> None:
        toml = "\n".join(
            [
                "[llm]",
                'provider = "openai_compatible"',
                'base_url = "http://127.0.0.1:9/v1"',
                'model = "m"',
                'api_key = "k"',
                "",
                "[agent]",
                "mock = true",
                "",
                "[models]",
                'active = "fast"',
                "",
                "[[models.profile]]",
                'id = "fast"',
                'provider = "openai_compatible"',
                'base_url = "http://127.0.0.1:9/v1"',
                'model = "m-fast"',
                'api_key = "k"',
                "",
                "[[models.profile]]",
                'id = "local"',
                'provider = "openai_compatible"',
                'base_url = "http://127.0.0.1:1234/v1"',
                'model = "qwen3-coder"',
                'api_key = "local"',
                "",
                "[models.routing]",
                "enabled = false",
                "",
            ],
        )
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = root / "cai-agent.toml"
            cfg.write_text(toml, encoding="utf-8")
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "models",
                            "--config",
                            str(cfg),
                            "routing-test",
                            "--role",
                            "active",
                            "--goal",
                            "hello",
                        ],
                    )
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            self.assertIn("effective_profile_id=fast", out)
            self.assertIn("已关闭", out)
            self.assertIn("fallback_candidate", out)

    def test_routing_test_cost_simulation(self) -> None:
        toml = "\n".join(
            [
                "[llm]",
                'provider = "openai_compatible"',
                'base_url = "http://127.0.0.1:9/v1"',
                'model = "m"',
                'api_key = "k"',
                "",
                "[agent]",
                "mock = true",
                "",
                "[cost]",
                "budget_max_tokens = 10000",
                "",
                "[models]",
                'active = "fast"',
                "",
                "[[models.profile]]",
                'id = "fast"',
                'provider = "openai_compatible"',
                'base_url = "http://127.0.0.1:9/v1"',
                'model = "m-fast"',
                'api_key = "k"',
                "",
                "[[models.profile]]",
                'id = "review"',
                'provider = "openai_compatible"',
                'base_url = "http://127.0.0.1:9/v1"',
                'model = "m-review"',
                'api_key = "k"',
                "",
                "[models.routing]",
                "",
                "[[models.routing.rules]]",
                "roles = [\"active\"]",
                "cost_budget_remaining_tokens_below = 2000",
                'profile = "review"',
                "",
            ],
        )
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cfg = root / "cai-agent.toml"
            cfg.write_text(toml, encoding="utf-8")
            buf = io.StringIO()
            with patch("cai_agent.__main__.os.getcwd", return_value=str(root)):
                with redirect_stdout(buf):
                    rc = main(
                        [
                            "models",
                            "--config",
                            str(cfg),
                            "routing-test",
                            "--role",
                            "active",
                            "--total-tokens-used",
                            "9200",
                            "--json",
                        ],
                    )
            self.assertEqual(rc, 0)
            o = json.loads(buf.getvalue().strip())
            self.assertEqual(o.get("effective_profile_id"), "review")
            self.assertEqual(o.get("cost_budget_max_tokens"), 10_000)
            self.assertEqual(o.get("total_tokens_used"), 9200)
            self.assertEqual(o.get("cost_budget_remaining"), 800)
            mr = o.get("matched_rule")
            self.assertIsNotNone(mr)
            self.assertEqual(mr.get("cost_budget_remaining_tokens_below"), 2000)
            sch = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
            for key in sch.get("required", ()):
                self.assertIn(key, o)


class ModelRoutingSettingsIntegrationTests(unittest.TestCase):
    def test_settings_loads_rules(self) -> None:
        toml = "\n".join(
            [
                "[llm]",
                'provider = "openai_compatible"',
                'base_url = "http://127.0.0.1:9/v1"',
                'model = "m"',
                'api_key = "k"',
                "",
                "[agent]",
                "mock = true",
                "",
                "[models]",
                'active = "fast"',
                "",
                "[[models.profile]]",
                'id = "fast"',
                'provider = "openai_compatible"',
                'base_url = "http://127.0.0.1:9/v1"',
                'model = "m-fast"',
                'api_key = "k"',
                "",
                "[[models.profile]]",
                'id = "review"',
                'provider = "openai_compatible"',
                'base_url = "http://127.0.0.1:9/v1"',
                'model = "m-review"',
                'api_key = "k"',
                "",
                "[models.routing]",
                "",
                "[[models.routing.rules]]",
                'goal_substring = "hello"',
                'profile = "review"',
                "",
            ],
        )
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "cai-agent.toml"
            p.write_text(toml, encoding="utf-8")
            s = Settings.from_env(config_path=str(p), workspace_hint=str(td))
            self.assertTrue(s.model_routing_enabled)
            self.assertEqual(len(s.model_routing_rules), 1)
            self.assertEqual(s.model_routing_rules[0].profile_id, "review")
