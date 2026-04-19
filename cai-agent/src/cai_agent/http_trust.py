"""是否让 httpx 读取环境代理（HTTP_PROXY 等）的派生规则。"""

from __future__ import annotations

from urllib.parse import urlparse


def effective_http_trust_env(*, trust_env: bool, request_url: str) -> bool:
    """在 ``trust_env`` 为真时，对环回地址仍返回 ``False``。

    用户常把 ``http_trust_env`` 设为 ``true`` 以便访问外网 API 时走系统代理；
    但同一开关会让 ``localhost`` / ``127.0.0.1`` 的请求也走代理，企业代理往往
    无法转发环回目标，表现为 **HTTP 503** 或连接失败，本地 LM Studio / Ollama
    即使用户已启动也无法 ping / chat。
    """
    if not trust_env:
        return False
    raw = (request_url or "").strip()
    if not raw:
        return True
    if "://" not in raw:
        raw = "http://" + raw
    try:
        parsed = urlparse(raw)
        host = (parsed.hostname or "").lower().strip()
    except ValueError:
        return True
    if not host:
        return True
    if host in ("localhost", "127.0.0.1", "::1"):
        return False
    if host.startswith("127."):
        return False
    return True
