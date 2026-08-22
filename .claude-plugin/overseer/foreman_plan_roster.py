"""Deterministic foreman roster rows for active plan directories."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import jsonio
import streams
import tmuxio
from _supervisor_snapshot import DEFAULT_STATUS_PATH, read_status_snapshot

__all__: list[str] = [
    "compose_roster",
    "main",
]

SCHEMA_VERSION = 1
NO_DAEMON_ROW = "no-daemon-row"
PLAN_WITHOUT_TMUX_SESSION = "plan_without_tmux_session"
TMUX_SESSION_WITHOUT_PLAN = "tmux_session_without_plan"
DAEMON_TMUX_NAME_MISMATCH = "daemon_tmux_name_mismatch"
OK = "ok"
GREEN_STATUSES = frozenset({"working", "winding-down", "restarting", "settling"})
YELLOW_STATUSES = frozenset(
    {
        "blocked:human",
        "idle",
        "idle-with-context-left",
        "parked-delivery",
        "picker-stalled",
        "warned",
    }
)


def _active_plan_names(*, repo: Path) -> list[str]:
    plan_dir = repo / "plan"
    if not plan_dir.is_dir():
        return []
    return sorted(
        child.name for child in plan_dir.iterdir() if child.is_dir() and child.name != "archive"
    )


def _snapshot_rows_by_topic(*, repo: Path, snapshot_path: Path) -> dict[str, dict[str, object]]:
    read = read_status_snapshot(path=snapshot_path)
    if read is None:
        return {}
    rows = jsonio.as_list(value=read.document.get("rows"))
    if rows is None:
        return {}
    repo_text = str(repo)
    by_topic: dict[str, dict[str, object]] = {}
    for raw in rows:
        row = jsonio.as_object(value=raw)
        if row is None or row.get("repo") != repo_text:
            continue
        topic = row.get("topic")
        if isinstance(topic, str) and topic:
            by_topic[topic] = row
    return by_topic


def _row_status(*, daemon_row: dict[str, object] | None) -> str:
    if daemon_row is None:
        return NO_DAEMON_ROW
    status = daemon_row.get("status")
    if isinstance(status, str) and status:
        return status
    return "daemon-row-missing-status"


def _status_emoji(*, status: str) -> str:
    if status in GREEN_STATUSES:
        return "🟢"
    if status in YELLOW_STATUSES or status.startswith("blocked:"):
        return "🟡"
    return "🔴"


def _daemon_tmux(*, daemon_row: dict[str, object] | None) -> str | None:
    if daemon_row is None:
        return None
    tmux = daemon_row.get("tmux")
    if isinstance(tmux, str) and tmux:
        return tmux
    return None


def _name_identity_verdict(
    *,
    plan: str,
    daemon_row: dict[str, object] | None,
    tmux_session_names: set[str],
) -> str:
    daemon_tmux = _daemon_tmux(daemon_row=daemon_row)
    if daemon_tmux is not None and daemon_tmux != plan:
        return DAEMON_TMUX_NAME_MISMATCH
    if plan not in tmux_session_names:
        return PLAN_WITHOUT_TMUX_SESSION
    return OK


def _roster_row(
    *,
    plan: str,
    daemon_row: dict[str, object] | None,
    tmux_session_names: set[str],
) -> dict[str, object]:
    status = _row_status(daemon_row=daemon_row)
    daemon_topic = None if daemon_row is None else daemon_row.get("topic")
    return {
        "plan": plan,
        "topic": plan,
        "tmux_session": plan if plan in tmux_session_names else None,
        "daemon_topic": daemon_topic if isinstance(daemon_topic, str) else None,
        "daemon_tmux": _daemon_tmux(daemon_row=daemon_row),
        "name_identity_verdict": _name_identity_verdict(
            plan=plan,
            daemon_row=daemon_row,
            tmux_session_names=tmux_session_names,
        ),
        "status": status,
        "status_emoji": _status_emoji(status=status),
    }


def _tmux_only_errors(
    *, plan_names: set[str], tmux_session_names: set[str]
) -> list[dict[str, str]]:
    return [
        {"kind": TMUX_SESSION_WITHOUT_PLAN, "tmux": session}
        for session in sorted(tmux_session_names - plan_names)
    ]


def _repo_scoped_tmux_session_names(
    *, daemon_rows: dict[str, dict[str, object]], tmux_session_names: set[str]
) -> set[str]:
    daemon_tmux_names = {
        tmux for row in daemon_rows.values() if (tmux := _daemon_tmux(daemon_row=row)) is not None
    }
    return tmux_session_names & daemon_tmux_names


def compose_roster(
    *,
    repo: Path,
    snapshot_path: Path,
    tmux_sessions: list[str],
) -> dict[str, object]:
    repo = repo.resolve()
    plan_names = _active_plan_names(repo=repo)
    plan_name_set = set(plan_names)
    tmux_session_names = {session for session in tmux_sessions if session}
    daemon_rows = _snapshot_rows_by_topic(repo=repo, snapshot_path=snapshot_path)
    rows = [
        _roster_row(
            plan=plan,
            daemon_row=daemon_rows.get(plan),
            tmux_session_names=tmux_session_names,
        )
        for plan in plan_names
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "repo": str(repo),
        "snapshot_path": str(snapshot_path),
        "rows": rows,
        "name_identity_errors": _tmux_only_errors(
            plan_names=plan_name_set,
            tmux_session_names=_repo_scoped_tmux_session_names(
                daemon_rows=daemon_rows,
                tmux_session_names=tmux_session_names,
            ),
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="foreman-plan-roster")
    _ = parser.add_argument("--repo", default=str(Path.cwd()))
    _ = parser.add_argument("--snapshot-path", default=str(DEFAULT_STATUS_PATH))
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
    roster = compose_roster(
        repo=Path(args.repo),
        snapshot_path=Path(args.snapshot_path),
        tmux_sessions=tmux_sessions,
    )
    streams.write_stdout(text=json.dumps(roster, sort_keys=True) + "\n")
    return 0
