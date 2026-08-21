"""_supervisor_cli_parser — argparse wiring for the one-shot supervisor CLI.

The command handlers stay in :mod:`supervisor` because tests and operator-side
callers patch facade-local helpers such as ``_cli_colliding``. This module owns
only the mechanical parser construction: subcommand names, help text, and handler
registration.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Protocol

from _seams import SubcommandHandler

__all__: list[str] = ["ParserHandlers", "build_parser"]


class ParserConfigurer(Protocol):
    def __call__(self, *, parser: argparse.ArgumentParser) -> None: ...


@dataclass(frozen=True, kw_only=True)
class ParserHandlers:
    list_handler: SubcommandHandler
    adopt_handler: SubcommandHandler
    add_handler: SubcommandHandler
    remove_handler: SubcommandHandler
    start_handler: SubcommandHandler


def build_parser(
    *,
    handlers: ParserHandlers,
    add_track_args: ParserConfigurer,
    add_mapping_write_args: ParserConfigurer,
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="overseer", description="livespec overseer track-management CLI"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="print the current joined table once (read-only)")
    _ = p_list.add_argument(
        "--json",
        action="store_true",
        help=(
            "emit observation-only snapshot JSON instead of the table; acting remains "
            "disabled because freshness is unproved"
        ),
    )
    p_list.set_defaults(func=handlers.list_handler)

    p_adopt = sub.add_parser(
        "adopt", help="adopt existing worker sessions matching active plan topics"
    )
    p_adopt.set_defaults(func=handlers.adopt_handler)

    p_add = sub.add_parser("add", help="add a (repo, topic) mapping row")
    add_track_args(parser=p_add)
    add_mapping_write_args(parser=p_add)
    p_add.set_defaults(func=handlers.add_handler)

    p_remove = sub.add_parser("remove", help="remove a (repo, topic) mapping row")
    add_track_args(parser=p_remove)
    p_remove.set_defaults(func=handlers.remove_handler)

    # unassign is a synonym for remove: drop the mapping so the plan reverts to
    # `unassigned` (never force-kills the session — surface-only).
    p_unassign = sub.add_parser("unassign", help="detach a plan's mapping (revert to unassigned)")
    add_track_args(parser=p_unassign)
    p_unassign.set_defaults(func=handlers.remove_handler)

    p_start = sub.add_parser("start", help="surface-only: launch a session for a plan and map it")
    add_track_args(parser=p_start)
    _ = p_start.add_argument(
        "--force",
        action="store_true",
        help="respawn even if the session already runs a live Claude (kills it)",
    )
    p_start.set_defaults(func=handlers.start_handler)
    return parser
