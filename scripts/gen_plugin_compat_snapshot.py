"""Generate/check the plugin compatibility matrix CI snapshot (ECC-03c)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "cai-agent" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cai_agent.plugin_registry import (  # noqa: E402
    build_plugin_compat_matrix,
    build_plugin_compat_matrix_check_v1,
)

DEFAULT_OUTPUT = ROOT / "docs" / "schema" / "plugin_compat_matrix_v1.snapshot.json"


def build_snapshot() -> dict[str, Any]:
    matrix = build_plugin_compat_matrix()
    check = build_plugin_compat_matrix_check_v1()
    return {
        "schema_version": "plugin_compat_matrix_snapshot_v1",
        "matrix_schema_version": matrix.get("schema_version"),
        "check_schema_version": check.get("schema_version"),
        "ok": bool(check.get("ok")),
        "matrix": matrix,
        "compat_check": check,
    }


def _normalized(obj: dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Snapshot path (default: docs/schema/plugin_compat_matrix_v1.snapshot.json)",
    )
    parser.add_argument("--check", action="store_true", help="Fail if the snapshot file is stale")
    args = parser.parse_args(argv)

    output = Path(str(args.output)).expanduser()
    if not output.is_absolute():
        output = (ROOT / output).resolve()
    snapshot = build_snapshot()
    rendered = _normalized(snapshot)

    if args.check:
        if not output.is_file():
            print(f"snapshot missing: {output}", file=sys.stderr)
            return 2
        current = output.read_text(encoding="utf-8")
        if current != rendered:
            print(f"snapshot stale: {output}", file=sys.stderr)
            return 2
        print(f"plugin compat snapshot OK: {output}")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"wrote plugin compat snapshot: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
