"""Foreman heartbeat observation for the daemon attention surface.

The foreman is an operator surface, not a tracked worker. Its heartbeat therefore
does not enter the session state machine and never authorizes a daemon act. The
daemon only observes one scratch file per watched repo and, when that PRESENT file is
stale, renders a synthetic report-only row through the same table, NEEDS YOU block,
window badge, and edge-triggered alert machinery every other attention member uses.
"""
# livespec-lloc-soft-band-owner: overseer-lixhd3.1

from __future__ import annotations

import os
from collections.abc import Callable
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


def foreman_rows(
    *,
    sup: Supervisor,
    repos: list[str],
    act: bool,
    null_added_at_keys: frozenset[_supervisor_mapping_health.MappingKey] = frozenset(),
) -> list[RowView]:
    rows: list[RowView] = []
    for repo in repos:
        evaluation_row = foreman_evaluation_row(
            sup=sup,
            repo=repo,
            act=act,
            null_added_at_keys=null_added_at_keys,
        )
        if evaluation_row is not None:
            rows.append(evaluation_row)
            prompt_row = _blocking_prompt_row(row=evaluation_row)
            if prompt_row is not None:
                rows.append(prompt_row)
                if act:
                    _surface_blocking_prompt_alert(sup=sup, row=prompt_row)
            else:
                _clear_blocking_prompt_alert(sup=sup, repo=repo)
        else:
            _clear_blocking_prompt_alert(sup=sup, repo=repo)
        row = foreman_row(repo=repo, now=sup.now)
        if row is None:
            _clear_alert(sup=sup, repo=repo)
            continue
        rows.append(row)
        if act and row.status == FOREMAN_HEARTBEAT_STALE_STATUS:
            _surface_alert(sup=sup, row=row)
        else:
            _clear_alert(sup=sup, repo=repo)
    return rows
