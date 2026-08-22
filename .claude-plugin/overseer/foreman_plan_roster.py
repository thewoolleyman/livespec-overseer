"""Deterministic foreman roster rows for active plan directories."""
# livespec-lloc-soft-band-owner: overseer-2jblyq.5

from __future__ import annotations

from pathlib import Path

import jsonio
import tmuxio
from _supervisor_snapshot import read_status_snapshot
from foreman_plan_roster_state import mark_roster_tick
from foreman_plan_roster_work import (
    NO_WORK_IN_FLIGHT,
    WORK_IN_FLIGHT,
    WORK_STATES,
    work_states_by_plan,
)

__all__: list[str] = [
    "DONE_READY_TO_ARCHIVE",
    "INCOHERENT",
    "SESSION_STATES",
    "WORK_STATES",
    "active_plan_names",
    "compose_roster",
    "emoji_for_pair",
    "main",
    "mark_roster_tick",
    "tmuxio",
]

SCHEMA_VERSION = 1
NO_DAEMON_ROW = "no-daemon-row"
PLAN_WITHOUT_TMUX_SESSION = "plan_without_tmux_session"
TMUX_SESSION_WITHOUT_PLAN = "tmux_session_without_plan"
DAEMON_TMUX_NAME_MISMATCH = "daemon_tmux_name_mismatch"
OK = "ok"
INCOHERENT = "incoherent"
SESSION_WORKING = "working"
SESSION_IDLE = "idle"
SESSION_PICKER_PARKED = "picker-parked"
SESSION_NO_SESSION = "no-session"
DONE_READY_TO_ARCHIVE = "done-ready-to-archive"
SESSION_STATES = (
    SESSION_WORKING,
    SESSION_IDLE,
    SESSION_PICKER_PARKED,
    SESSION_NO_SESSION,
    DONE_READY_TO_ARCHIVE,
)
WORKING_STATUSES = frozenset({"working", "winding-down", "restarting", "settling"})
IDLE_STATUSES = frozenset(
    {
        "idle",
        "idle-with-context-left",
        "warned",
    }
)
PICKER_PARKED_STATUSES = frozenset(
    {
        "blocked:human",
        "parked-delivery",
        "picker-stalled",
    }
)
# The released foreman prose legend is the source of truth; this table is its
# deterministic helper rendering.
INCOHERENT_EMOJI = "❗"
PAIR_EMOJI = {
    (DONE_READY_TO_ARCHIVE, WORK_IN_FLIGHT): "🔵",
    (DONE_READY_TO_ARCHIVE, NO_WORK_IN_FLIGHT): "🔵",
    (SESSION_WORKING, WORK_IN_FLIGHT): "🟢",
    (SESSION_WORKING, NO_WORK_IN_FLIGHT): "🟢",
    (SESSION_IDLE, WORK_IN_FLIGHT): "⏳",
    (SESSION_IDLE, NO_WORK_IN_FLIGHT): "⚪",
    (SESSION_PICKER_PARKED, WORK_IN_FLIGHT): "🔴",
    (SESSION_PICKER_PARKED, NO_WORK_IN_FLIGHT): "🔴",
    (SESSION_NO_SESSION, WORK_IN_FLIGHT): "⏳",
    (SESSION_NO_SESSION, NO_WORK_IN_FLIGHT): "⚪",
}


def active_plan_names(*, repo: Path) -> list[str]:
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


def _daemon_status(*, daemon_row: dict[str, object] | None) -> str:
    if daemon_row is None:
        return NO_DAEMON_ROW
    status = daemon_row.get("status")
    if isinstance(status, str) and status:
        return status
    return "daemon-row-missing-status"


def _session_state(*, daemon_row: dict[str, object] | None) -> str:
    status = _daemon_status(daemon_row=daemon_row)
    if status in WORKING_STATUSES:
        return SESSION_WORKING
    if status in PICKER_PARKED_STATUSES:
        return SESSION_PICKER_PARKED
    if status in IDLE_STATUSES or status.startswith("blocked:"):
        return SESSION_IDLE
    return SESSION_NO_SESSION


def emoji_for_pair(*, session_state: str, work_state: str) -> str:
    return PAIR_EMOJI.get((session_state, work_state), INCOHERENT_EMOJI)


def _emoji_for_row(*, name_identity_verdict: str, session_state: str, work_state: str) -> str:
    if name_identity_verdict == DAEMON_TMUX_NAME_MISMATCH:
        return INCOHERENT_EMOJI
    return emoji_for_pair(session_state=session_state, work_state=work_state)


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
    work_state: str,
    unactioned_count: int | None,
) -> dict[str, object]:
    session_state = _session_state(daemon_row=daemon_row)
    name_identity_verdict = _name_identity_verdict(
        plan=plan,
        daemon_row=daemon_row,
        tmux_session_names=tmux_session_names,
    )
    daemon_topic = None if daemon_row is None else daemon_row.get("topic")
    row: dict[str, object] = {
        "plan": plan,
        "topic": plan,
        "tmux_session": plan if plan in tmux_session_names else None,
        "daemon_topic": daemon_topic if isinstance(daemon_topic, str) else None,
        "daemon_tmux": _daemon_tmux(daemon_row=daemon_row),
        "name_identity_verdict": name_identity_verdict,
        "session_state": session_state,
        "work_state": work_state,
        "emoji": _emoji_for_row(
            name_identity_verdict=name_identity_verdict,
            session_state=session_state,
            work_state=work_state,
        ),
    }
    if unactioned_count is not None:
        row["consecutive_unactioned_ticks"] = unactioned_count
    return row


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
    journal_path: Path | None = None,
    unactioned_counts: dict[str, int] | None = None,
) -> dict[str, object]:
    repo = repo.resolve()
    plan_names = active_plan_names(repo=repo)
    plan_name_set = set(plan_names)
    tmux_session_names = {session for session in tmux_sessions if session}
    daemon_rows = _snapshot_rows_by_topic(repo=repo, snapshot_path=snapshot_path)
    work_states = work_states_by_plan(repo=repo, plan_names=plan_names, journal_path=journal_path)
    rows = [
        _roster_row(
            plan=plan,
            daemon_row=daemon_rows.get(plan),
            tmux_session_names=tmux_session_names,
            work_state=work_states.get(plan, NO_WORK_IN_FLIGHT),
            unactioned_count=(
                None if unactioned_counts is None else unactioned_counts.get(plan, 0)
            ),
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


def main(*, argv: list[str] | None = None) -> int:
    from foreman_plan_roster_cli import main as cli_main

    return cli_main(argv=argv)
