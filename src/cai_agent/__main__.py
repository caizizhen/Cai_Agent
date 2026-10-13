"""CAI CLI entry — Harness-style flags, layered engine."""

from __future__ import annotations

import argparse
import json
import os
import sys

from cai_agent import __version__
from cai_agent.config import Settings
from cai_agent.runtime import dump_info, run_sync


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cai-agent",
        description="CAI — Pi engine + DeepSeek Harness–inspired UI (layered)",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--config",
        default=None,
        help="Path to YAML/JSON config (or set CAI_CONFIG)",
    )
    parser.add_argument("--model", default=None, help="Override LLM model id")
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        dest="max_steps",
        help="Max agent turns / tool rounds",
    )
    parser.add_argument(
        "--stream",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Stream assistant tokens to the terminal (default: on)",
    )
    parser.add_argument(
        "--debug",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Print extra finish/debug metadata",
    )
    parser.add_argument(
        "--dump-config",
        action="store_true",
        help="Print resolved settings and exit",
    )

    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Headless / Harness-rendered one-shot")
    run_p.add_argument("goal", nargs="+", help="Task description")
    run_p.add_argument("-w", "--workspace", default=None)
    run_p.add_argument("--session", default=None, help="Resume session id")
    run_p.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Print only the final assistant reply",
    )
    run_p.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON result envelope instead of Harness chrome",
    )

    ui_p = sub.add_parser("ui", help="Interactive Harness-style REPL")
    ui_p.add_argument("-w", "--workspace", default=None)

    web_p = sub.add_parser("web", help="Local Web UI + SSE (same EventBus kinds)")
    web_p.add_argument("--host", default="127.0.0.1")
    web_p.add_argument("--port", type=int, default=8765)
    web_p.add_argument("-w", "--workspace", default=None)

    return parser


def _resolve_settings(args: argparse.Namespace) -> Settings:
    settings = Settings.from_env(config_path=getattr(args, "config", None))
    workspace = getattr(args, "workspace", None)
    return settings.with_overrides(
        model=getattr(args, "model", None),
        max_steps=getattr(args, "max_steps", None),
        stream=getattr(args, "stream", None),
        debug=getattr(args, "debug", None),
        workspace=workspace,
    )


def main(argv: list[str] | None = None) -> int:
    """Parse argv and dispatch to run / ui / web."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    workspace = getattr(args, "workspace", None)
    if workspace:
        os.environ["CAI_WORKSPACE"] = os.path.abspath(workspace)

    settings = _resolve_settings(args)

    if args.dump_config:
        print(json.dumps(dump_info(settings), ensure_ascii=False, indent=2))
        return 0

    if args.command is None:
        parser.print_help()
        return 2

    if args.command == "run":
        goal = " ".join(args.goal).strip()
        if not goal:
            print("goal 不能为空", file=sys.stderr)
            return 2
        result = run_sync(
            goal,
            settings=settings,
            session_id=args.session,
            quiet=bool(args.quiet or args.json),
            render=not args.json and not args.quiet,
        )
        if args.quiet:
            print(result.get("reply") or "")
        elif args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            # Harness renderer already painted the stream; print session footer.
            print(f"\nsession={result.get('session_id')}", file=sys.stderr)
        return 0

    if args.command == "ui":
        from cai_agent.ui.tui import run_tui_sync

        return run_tui_sync(settings)

    if args.command == "web":
        from cai_agent.surfaces.web import run_web

        run_web(host=args.host, port=args.port, settings=settings)
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
