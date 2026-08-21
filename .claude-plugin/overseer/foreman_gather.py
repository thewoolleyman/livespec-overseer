"""CLI facade for the deterministic Phase A foreman gatherer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PACKAGE_PARENT = _HERE.parent
_VENDOR = _HERE / "_vendor"
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
if str(_PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_PARENT))
if str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))

import streams  # noqa: E402
from _supervisor_snapshot import DEFAULT_STATUS_PATH  # noqa: E402
from foreman_gather_collect import (  # noqa: E402
    DOCUMENT_SCHEMA_VERSION,
    ValidationError,
    compose_document,
)
from foreman_gather_render import render_document  # noqa: E402

__all__: list[str] = [
    "DOCUMENT_SCHEMA_VERSION",
    "ValidationError",
    "compose_document",
    "main",
    "render_document",
]


def default_list_json_command() -> list[str]:
    return [sys.executable, str(_HERE / "supervisor.py"), "list", "--json"]


def main(*, argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="foreman-gather",
        description="compose deterministic foreman evidence from local primitive sources",
    )
    _ = parser.add_argument("--repo", default=str(Path.cwd()), help="repo to gather for")
    _ = parser.add_argument("--snapshot-path", default=str(DEFAULT_STATUS_PATH))
    _ = parser.add_argument("--no-list-json-fallback", action="store_true")
    _ = parser.add_argument("--journal-path", default=None)
    _ = parser.add_argument("--journal-limit", type=int, default=20)
    _ = parser.add_argument("--render", action="store_true", help="emit deterministic watch text")
    args = parser.parse_args(argv)
    fallback = None if args.no_list_json_fallback else default_list_json_command()
    try:
        document = compose_document(
            repo=args.repo,
            snapshot_path=args.snapshot_path,
            list_json_command=fallback,
            journal_path=args.journal_path,
            journal_limit=args.journal_limit,
        )
    except (TypeError, ValueError) as exc:
        streams.write_stderr(text=f"foreman-gather: {exc}\n")
        return 1
    if args.render:
        streams.write_stdout(text=render_document(document=document))
    else:
        streams.write_stdout(text=json.dumps(document, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
