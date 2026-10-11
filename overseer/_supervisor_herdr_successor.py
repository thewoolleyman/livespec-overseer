"""Exact successor proof and guarded continuation for a Herdr replacement."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import _herdr_replacement_process
import _herdr_replacement_store
import _supervisor_launch
import _supervisor_observe
import _supervisor_state
import registry
import signals
from _supervisor_prompts import resume_for_track

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["resume_proven_successor"]


def _ready_resume_text(
    *, sup: Supervisor, track: registry.Track, target: str
) -> tuple[str | None, str | None]:
    capture = sup.tmux.capture_pane(session=target)
    if signals.is_structured_gate(capture_text=capture):
        return None, "verified successor is waiting at a structured gate"
    if not signals.input_box_ready(capture_text=capture):
        return None, "verified successor input is not ready"
    resume = resume_for_track(track=track)
    if resume is None:
        return None, "recorded track has no certifiable resume continuation"
    return resume, None


def _continue_verified_successor(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    transaction: dict[str, object],
    identity: str,
) -> str | None:
    pane = cast(_herdr_replacement_process.ReplacementPane, sup.tmux)
    scratch = _herdr_replacement_store.scratch_path(track=track)
    record_path = scratch / _herdr_replacement_store.RECORD_NAME
    with _herdr_replacement_store.transaction_lock(
        path=scratch / _herdr_replacement_store.LOCK_NAME
    ):
        current = _herdr_replacement_store.read_transaction(path=record_path)
        if current != transaction:
            return "durable replacement changed during successor verification"
        current = cast(dict[str, object], current)
        snapshot = pane.herdr_replacement_snapshot(session=target)
        successor = _herdr_replacement_process.proven_successor(
            transaction=current, snapshot=snapshot, identity=identity
        )
        if successor is None:
            return "successor is not a fresh process generation in the retained shell"
        current["successor"] = _herdr_replacement_process.process_record(process=successor)
        current["phase"] = "successor-observed"
        _herdr_replacement_store.durable_write(path=record_path, value=current)
        resume, reason = _ready_resume_text(sup=sup, track=track, target=target)
        if reason is not None:
            return reason
        resume = cast(str, resume)
        current["resume"] = resume
        current["phase"] = "resume-attempted"
        _herdr_replacement_store.durable_write(path=record_path, value=current)
        if not _supervisor_launch.submit_prompt(sup=sup, target=target, text=resume):
            return "verified successor resume submission was not confirmed"
        current["phase"] = "completed"
        _herdr_replacement_store.durable_write(path=record_path, value=current)
    return None


def resume_proven_successor(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    transaction: dict[str, object],
) -> str | None:
    """Prove a distinct successor and submit its continuation at most once."""
    managed = _supervisor_observe.pane_is_managed_claude(
        sup=sup,
        target=target,
        repo=track.repo,
        topic=track.topic,
        session=_supervisor_launch.session_of(sup=sup, track=track),
    )
    identity = sup.claude_identity_by_session.get((target, track.topic))
    if not managed:
        reason: str | None = "observed process is not the recorded Claude runtime"
    elif identity is None:
        reason = "successor runtime identity is not yet observable"
    else:
        reason = None
    if reason is None:
        reason = _continue_verified_successor(
            sup=sup,
            track=track,
            target=target,
            transaction=transaction,
            identity=cast(str, identity),
        )
    if reason is None:
        _supervisor_state.clear_state(
            sup=sup,
            track=track,
            diagnostic_token=signals.STATE_RESTARTED,
            diagnostic_detail="Herdr replacement completed; consumed ready declaration",
        )
        sup.log(message=f"completed Herdr replacement for {track.repo}::{track.topic}")
    return reason
