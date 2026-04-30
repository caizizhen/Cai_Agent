"""P4-4: gateway goal-prefix dangerous approval stripping."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from cai_agent.gateway_danger import (
    GATEWAY_DANGER_APPROVE_CONTRACT_SCHEMA_VERSION,
    apply_gateway_danger_grants,
    gateway_danger_approve_tokens,
    strip_gateway_danger_approve_lines,
)


class GatewayDangerContractTests(unittest.TestCase):
    def test_strip_default_tokens_case_insensitive(self) -> None:
        body, n = strip_gateway_danger_approve_lines("[Danger-Approve]\n\nhello")
        self.assertEqual(n, 1)
        self.assertEqual(body, "hello")

    def test_strip_multiple_skips_blank_between(self) -> None:
        raw = "[danger-approve]\n\n[danger-approve]\ntask"
        body, n = strip_gateway_danger_approve_lines(raw)
        self.assertEqual(n, 2)
        self.assertEqual(body, "task")

    def test_slash_token(self) -> None:
        body, n = strip_gateway_danger_approve_lines("/danger-approve\nx")
        self.assertEqual(n, 1)
        self.assertEqual(body, "x")

    def test_env_override_tokens(self) -> None:
        old = os.environ.get("CAI_GATEWAY_DANGER_APPROVE_TOKENS")
        try:
            os.environ["CAI_GATEWAY_DANGER_APPROVE_TOKENS"] = "[go],[ok]"
            toks = gateway_danger_approve_tokens()
            self.assertEqual(toks, ("[go]", "[ok]"))
            body, n = strip_gateway_danger_approve_lines("[go]\n[y]")
            self.assertEqual(n, 1)
            self.assertEqual(body, "[y]")
        finally:
            if old is None:
                os.environ.pop("CAI_GATEWAY_DANGER_APPROVE_TOKENS", None)
            else:
                os.environ["CAI_GATEWAY_DANGER_APPROVE_TOKENS"] = old

    def test_apply_gateway_danger_grants_calls_grant(self) -> None:
        with patch("cai_agent.tools.grant_dangerous_approval_once") as mock_grant:
            mock_grant.return_value = 1
            apply_gateway_danger_grants(None, 2)
        self.assertEqual(mock_grant.call_count, 2)


class GatewayDangerContractSchemaTests(unittest.TestCase):
    def test_schema_constant(self) -> None:
        self.assertEqual(GATEWAY_DANGER_APPROVE_CONTRACT_SCHEMA_VERSION, "danger_gateway_goal_prefix_contract_v1")


if __name__ == "__main__":
    unittest.main()
