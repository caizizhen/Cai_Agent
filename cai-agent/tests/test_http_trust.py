"""effective_http_trust_env：环回地址不走系统代理。"""
from __future__ import annotations

import unittest

from cai_agent.http_trust import effective_http_trust_env


class EffectiveHttpTrustEnvTests(unittest.TestCase):
    def test_trust_env_false_always_false(self) -> None:
        self.assertFalse(
            effective_http_trust_env(
                trust_env=False,
                request_url="https://api.openai.com/v1/chat/completions",
            ),
        )

    def test_loopback_never_trusts_proxy(self) -> None:
        for url in (
            "http://localhost:1234/v1/models",
            "http://127.0.0.1:8000/v1/chat/completions",
            "http://127.42.0.1:11434/v1",
        ):
            with self.subTest(url=url):
                self.assertFalse(effective_http_trust_env(trust_env=True, request_url=url))

    def test_public_host_respects_trust_env(self) -> None:
        self.assertTrue(
            effective_http_trust_env(
                trust_env=True,
                request_url="https://open.bigmodel.cn/api/paas/v4/chat/completions",
            ),
        )


if __name__ == "__main__":
    unittest.main()
