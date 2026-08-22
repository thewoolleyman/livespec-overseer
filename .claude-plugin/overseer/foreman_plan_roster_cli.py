"""CLI entry point for the deterministic foreman plan roster helper."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import streams
import tmuxio
from _supervisor_snapshot import DEFAULT_STATUS_PATH
from foreman_plan_roster import active_plan_names, compose_roster, mark_roster_tick

__all__: list[str] = ["main"]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="foreman-plan-roster")
    _ = parser.add_argument("--repo", default=str(Path.cwd()))
    _ = parser.add_argument("--snapshot-path", default=str(DEFAULT_STATUS_PATH))
    _ = parser.add_argument("--journal-path", default=None)
    _ = parser.add_argument("--tick-identity", default=None)
    _ = parser.add_argument("--actioned-plan", default=None)
    _ = parser.add_argument(
        "--tmux-session",
        action="append",
        default=None,
        help="test seam: supply tmux session names instead of querying tmux",
    )
    return parser


def main(*, argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    tmux_sessions = args.tmux_session
    if tmux_sessions is None:
        tmux_sessions = tmuxio.TmuxIO().list_sessions()
    repo = Path(args.repo).resolve()
    plan_names = active_plan_names(repo=repo)
    unactioned_counts = None
    if args.tick_identity is not None:
        unactioned_counts = mark_roster_tick(
            repo=repo,
            plan_names=plan_names,
            tick_identity=args.tick_identity,
            actioned_plan=args.actioned_plan,
        )
        if unactioned_counts is None:
            return 0
    roster = compose_roster(
        repo=repo,
        snapshot_path=Path(args.snapshot_path),
        tmux_sessions=tmux_sessions,
        journal_path=Path(args.journal_path) if args.journal_path is not None else None,
        unactioned_counts=unactioned_counts,
    )
    if args.tick_identity is not None:
        roster["tick_identity"] = args.tick_identity
    streams.write_stdout(text=json.dumps(roster, sort_keys=True) + "\n")
    return 0
