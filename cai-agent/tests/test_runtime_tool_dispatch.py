from __future__ import annotations

import tempfile
import textwrap
from pathlib import Path
from unittest.mock import patch

from cai_agent.config import Settings
from cai_agent.runtime.base import ExecResult, RuntimeBackend
from cai_agent.tools import tool_run_command


class _FakeRemoteRuntime(RuntimeBackend):
    name = "fake_remote"

    def __init__(self) -> None:
        self.called: list[tuple[str, str]] = []

    def exists(self) -> bool:
        return True

    def exec(
        self,
        cmd: str | list[str],
        *,
        cwd: str,
        env=None,
        timeout_sec: float | None = None,
    ) -> ExecResult:
        self.called.append((str(cmd), str(cwd)))
        return ExecResult("hello\n", "", 0, None, self.name)


def test_run_command_dispatches_to_runtime_backend() -> None:
    root = Path(tempfile.mkdtemp()).resolve()
    cfg = ""
    try:
        toml = textwrap.dedent(
            f"""
            [llm]
            base_url = "http://localhost:1/v1"
            model = "m"
            api_key = "k"
            [agent]
            workspace = "{root.as_posix()}"
            [permissions]
            run_command = "allow"
            run_command_approval_mode = "allow_all"
            [runtime]
            backend = "docker"
            [runtime.docker]
            container_name = "noop"
            """,
        )
        with tempfile.NamedTemporaryFile(
            "w",
            suffix=".toml",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(toml)
            cfg = f.name
        s = Settings.from_env(config_path=cfg)
        fake = _FakeRemoteRuntime()
        with patch("cai_agent.tools.get_runtime_backend", return_value=fake):
            out = tool_run_command(
                s,
                {"argv": ["python", "-c", "print(1)"], "cwd": "."},
            )
        assert "backend=fake_remote" in out
        assert "hello" in out
        assert fake.called and "python" in fake.called[0][0]
    finally:
        import os

        if cfg:
            try:
                os.unlink(cfg)
            except OSError:
                pass


def test_run_command_stays_local_when_backend_local() -> None:
    root = Path(tempfile.mkdtemp()).resolve()
    toml = textwrap.dedent(
        f"""
        [llm]
        base_url = "http://localhost:1/v1"
        model = "m"
        api_key = "k"
        [agent]
        workspace = "{root.as_posix()}"
        [permissions]
        run_command = "allow"
        run_command_approval_mode = "allow_all"
        [runtime]
        backend = "local"
        """,
    )
    with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False, encoding="utf-8") as f:
        f.write(toml)
        cfg = f.name
    try:
        s = Settings.from_env(config_path=cfg)
        out = tool_run_command(s, {"argv": ["python", "-c", "print('x')"], "cwd": "."})
        assert "exit=0" in out
        assert "backend=local" in out
    finally:
        import os

        os.unlink(cfg)
