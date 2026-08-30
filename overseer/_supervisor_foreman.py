"""Foreman heartbeat observation for the daemon attention surface.

The foreman is an operator surface, not a tracked worker. Its heartbeat therefore
does not enter the session state machine and never authorizes a daemon act. The
daemon only observes one scratch file per watched repo and, when that PRESENT file is
stale, renders a synthetic report-only row through the same table, NEEDS YOU block,
window badge, and edge-triggered alert machinery every other attention member uses.
"""
# livespec-lloc-soft-band-owner: overseer-n1ai.1

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING

import _supervisor_evaluate
import _supervisor_foreman_dead
import _supervisor_foreman_heartbeat
import _supervisor_mapping_health
import foreman_runtime_identity
import foreman_stop_state
import registry
from _supervisor_config import track_key
from _supervisor_view import MAX_REASON_IN_ALERT, RowView, elide

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "FOREMAN_BLOCKING_PROMPT_STATUS",
    "FOREMAN_HEARTBEAT_DEAD_STATUS",
    "FOREMAN_HEARTBEAT_STALE_STATUS",
    "FOREMAN_TOPIC",
    "Heartbeat",
    "HeartbeatLapse",
    "foreman_evaluation_row",
    "foreman_row",
    "foreman_rows",
    "foreman_track",
    "heartbeat_lapse",
    "heartbeat_path",
    "read_heartbeat",
]

FOREMAN_TOPIC = _supervisor_foreman_heartbeat.FOREMAN_TOPIC
FOREMAN_BLOCKING_PROMPT_STATUS = "foreman-blocking-prompt"
FOREMAN_HEARTBEAT_DEAD_STATUS = _supervisor_foreman_dead.FOREMAN_HEARTBEAT_DEAD_STATUS
FOREMAN_HEARTBEAT_STALE_STATUS = _supervisor_foreman_dead.FOREMAN_HEARTBEAT_STALE_STATUS
FOREMAN_HEARTBEAT_HELD_STATUS = _supervisor_foreman_dead.FOREMAN_HEARTBEAT_HELD_STATUS
FOREMAN_HEARTBEAT_COMPLETED_STATUS = _supervisor_foreman_dead.FOREMAN_HEARTBEAT_COMPLETED_STATUS
_HEARTBEAT_ALERT_CONDITIONS = (
    FOREMAN_HEARTBEAT_STALE_STATUS,
    FOREMAN_HEARTBEAT_DEAD_STATUS,
)
_BLOCKING_PROMPT_CONDITION = "foreman-blocking-prompt"

Heartbeat = _supervisor_foreman_heartbeat.Heartbeat
HeartbeatLapse = _supervisor_foreman_heartbeat.HeartbeatLapse
heartbeat_path = _supervisor_foreman_heartbeat.heartbeat_path
read_heartbeat = _supervisor_foreman_heartbeat.read_heartbeat
heartbeat_lapse = _supervisor_foreman_heartbeat.heartbeat_lapse


def _age_seconds(*, heartbeat: Heartbeat, now: Callable[[], float]) -> float:
    return now() - heartbeat.written_at.timestamp()


def foreman_row(*, repo: str, now: Callable[[], float]) -> RowView | None:
    heartbeat = read_heartbeat(repo=repo)
    if heartbeat is None:
        return None
    age = _age_seconds(heartbeat=heartbeat, now=now)
    stale_after = _supervisor_foreman_heartbeat.stale_after(heartbeat=heartbeat)
    if age <= stale_after:
        return None
    stop_state = foreman_stop_state.read_foreman_stop_state(repo=repo)
    state = stop_state.state if stop_state is not None else foreman_stop_state.FOREMAN_STOP_DIED
    reason = stop_state.reason if stop_state is not None else "tick-deadline-lapsed"
    return _supervisor_foreman_dead.heartbeat_row(
        repo=repo,
        age_seconds=age,
        state=state,
        reason=reason,
        heartbeat=heartbeat,
        stale_after_seconds=stale_after,
    )


def foreman_track(
    *, repo: str, store_path: str | os.PathLike[str] | None = None
) -> registry.Track | None:
    topic = foreman_runtime_identity.canonical_session_name(repo=repo)
    repo_norm = registry.norm(repo=repo)
    for track in registry.read_valid_mapping(store_path=store_path):
        if registry.norm(repo=track.repo) == repo_norm and track.topic == topic:
            return track
    return None


def foreman_evaluation_row(
    *,
    sup: Supervisor,
    repo: str,
    act: bool,
    null_added_at_keys: frozenset[_supervisor_mapping_health.MappingKey] = frozenset(),
) -> RowView | None:
    track = foreman_track(repo=repo, store_path=sup.store_path)
    if track is None:
        return None
    row = _supervisor_evaluate.evaluate(sup=sup, track=track, act=act)
    if act:
        return row
    return _supervisor_mapping_health.apply_mapping_health(
        track=track, row=row, null_added_at_keys=null_added_at_keys
    )


def _blocking_prompt_row(*, row: RowView) -> RowView | None:
    if not row.picker_open:
        return None
    return RowView(
        topic=FOREMAN_TOPIC,
        repo=row.repo,
        tmux=row.tmux,
        ctx=row.ctx,
        status=FOREMAN_BLOCKING_PROMPT_STATUS,
        note=(
            "foreman blocking prompt open; an open prompt suppresses scheduled ticks; "
            "surface the decision through the foreman escalation file and return idle"
        ),
        runtime=row.runtime,
        human_wait=True,
        picker_open=row.picker_open,
        stall_seconds=row.stall_seconds,
    )


def _seat_heartbeat_row(*, evaluation_row: RowView | None, heartbeat_row: RowView) -> RowView:
    """The heartbeat row carrying the runtime the daemon OBSERVED for that same session.

    A heartbeat row is built from a FILE, so it knows no runtime, and
    `_supervisor_snapshot.session_identity` therefore falls through to its `tmux:` arm --
    publishing a live Claude seat under a second identity scheme while that seat's own
    evaluated row is published under `claude:`. One session then reads as two tracks.

    Inheriting is not a guess: the runtime is this tick's own observation of the SAME
    tmux session. When no evaluated row names that session there is nothing to inherit,
    and the row keeps the scheme a heartbeat file alone can justify.
    """
    if evaluation_row is None or evaluation_row.tmux != heartbeat_row.tmux:
        return heartbeat_row
    return replace(heartbeat_row, runtime=evaluation_row.runtime)


def _reconciled_row(*, prompt_row: RowView, heartbeat_row: RowView) -> RowView:
    """ONE row for one seat: the open prompt, carrying the heartbeat lapse it absorbed.

    The two rows are not independent facts about two tracks. An open prompt suppresses the
    scheduled tick, so the lapsed heartbeat is its CONSEQUENCE -- and published side by
    side the pair routes an operator two opposite ways: answer the prompt in that pane, or
    treat the loop as dead and restore it. The prompt survives because its remedy is the
    one that unblocks the loop; the heartbeat's own status and note are folded into the
    surviving note rather than dropped, and its edge-triggered alert is unchanged, so the
    stale heartbeat is still surfaced with coordinates.
    """
    return replace(
        prompt_row, note=f"{prompt_row.note}; {heartbeat_row.status}: {heartbeat_row.note}"
    )


def _clear_alert(*, sup: Supervisor, repo: str) -> None:
    for condition in _HEARTBEAT_ALERT_CONDITIONS:
        _ = sup.alerted.pop((*track_key(repo=repo, topic=FOREMAN_TOPIC), condition), None)


def _clear_blocking_prompt_alert(*, sup: Supervisor, repo: str) -> None:
    _ = sup.alerted.pop(
        (*track_key(repo=repo, topic=FOREMAN_TOPIC), _BLOCKING_PROMPT_CONDITION), None
    )


def _surface_alert(*, sup: Supervisor, row: RowView) -> None:
    note = row.note or "foreman heartbeat stale"
    sup.alert(
        repo=row.repo,
        topic=row.topic,
        session=row.tmux,
        pane=None,
        message=f"{note} — inspect that operator surface",
        condition=row.status,
    )


def _surface_blocking_prompt_alert(*, sup: Supervisor, row: RowView) -> None:
    note = elide(text=row.note or "foreman blocking prompt open", limit=MAX_REASON_IN_ALERT)
    sup.alert(
        repo=row.repo,
        topic=row.topic,
        session=row.tmux,
        pane=None,
        message=f"foreman blocking prompt open: {note} — inspect that operator surface",
        condition=_BLOCKING_PROMPT_CONDITION,
    )


def _repo_foreman_rows(
    *,
    sup: Supervisor,
    repo: str,
    act: bool,
    null_added_at_keys: frozenset[_supervisor_mapping_health.MappingKey],
) -> list[RowView]:
    """One repository's foreman rows, with one row per SESSION on the `foreman` topic.

    Two synthetic rows can arise for one repo -- an open blocking prompt on the mapped
    seat, and a lapsed heartbeat file -- and they are reconciled ONLY when they name the
    same tmux session. Rows naming different sessions are genuinely different seats and
    are both published, so this is not a collapse on (repo, topic).
    """
    rows: list[RowView] = []
    evaluation_row = foreman_evaluation_row(
        sup=sup, repo=repo, act=act, null_added_at_keys=null_added_at_keys
    )
    prompt_row = None if evaluation_row is None else _blocking_prompt_row(row=evaluation_row)
    if evaluation_row is not None:
        rows.append(evaluation_row)
    if prompt_row is None:
        _clear_blocking_prompt_alert(sup=sup, repo=repo)
    elif act:
        _surface_blocking_prompt_alert(sup=sup, row=prompt_row)
    heartbeat_row = foreman_row(repo=repo, now=sup.now)
    if heartbeat_row is None:
        _clear_alert(sup=sup, repo=repo)
        if prompt_row is not None:
            rows.append(prompt_row)
        return rows
    if act and heartbeat_row.status == FOREMAN_HEARTBEAT_STALE_STATUS:
        _surface_alert(sup=sup, row=heartbeat_row)
    else:
        _clear_alert(sup=sup, repo=repo)
    heartbeat_row = _seat_heartbeat_row(evaluation_row=evaluation_row, heartbeat_row=heartbeat_row)
    if prompt_row is None:
        rows.append(heartbeat_row)
    elif prompt_row.tmux == heartbeat_row.tmux:
        rows.append(_reconciled_row(prompt_row=prompt_row, heartbeat_row=heartbeat_row))
    else:
        rows.extend((prompt_row, heartbeat_row))
    return rows


def foreman_rows(
    *,
    sup: Supervisor,
    repos: list[str],
    act: bool,
    null_added_at_keys: frozenset[_supervisor_mapping_health.MappingKey] = frozenset(),
) -> list[RowView]:
    rows: list[RowView] = []
    for repo in repos:
        rows.extend(
            _repo_foreman_rows(sup=sup, repo=repo, act=act, null_added_at_keys=null_added_at_keys)
        )
    return rows
