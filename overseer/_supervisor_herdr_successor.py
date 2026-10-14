"""Exact successor proof and guarded continuation for a Herdr replacement."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

import _herdr_replacement_process
import _herdr_replacement_store
import _supervisor_herdr_codex_successor
import _supervisor_herdr_completion
import _supervisor_launch
import _supervisor_observe
import registry
import signals
from _supervisor_config import SUBMIT_MAX_ENTERS, SUBMIT_POLL
from _supervisor_prompts import resume_for_track

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["resume_proven_successor"]


class PendingEnterRetry(Protocol):
    def __call__(
        self,
        *,
        session: str,
        text: str,
        sleep: Callable[[float], None],
    ) -> tuple[bool, bool]: ...


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
        if current.get("phase") == "resume-attempted":
            return _retry_recorded_resume(
                sup=sup,
                target=target,
                current=current,
                successor=successor,
                record_path=record_path,
            )
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


def _retry_recorded_resume(
    *,
    sup: Supervisor,
    target: str,
    current: dict[str, object],
    successor: _herdr_replacement_process.ProcessObservation,
    record_path: Path,
) -> str | None:
    recorded_successor = current.get("successor")
    resume = current.get("resume")
    attempts = current.get("resume_retry_attempts", 0)
    capture = sup.tmux.capture_pane(session=target)
    expected = resume.partition("\n")[0].strip() if isinstance(resume, str) else ""
    exact_pending = signals.input_box_text(capture_text=capture) == expected
    if recorded_successor != _herdr_replacement_process.process_record(process=successor):
        return "pending resume successor no longer matches the durable process identity"
    if signals.is_structured_gate(capture_text=capture) or not expected or not exact_pending:
        return "pending resume text is absent, gated, or differs from the durable payload"
    if not isinstance(attempts, int) or isinstance(attempts, bool) or attempts >= SUBMIT_MAX_ENTERS:
        return "pending resume Enter retry budget is exhausted or malformed"
    current["resume_retry_attempts"] = attempts + 1
    _herdr_replacement_store.durable_write(path=record_path, value=current)
    submitted, effect_unknown = _retry_enter(
        sup=sup,
        target=target,
        resume=cast(str, resume),
    )
    if submitted:
        current["phase"] = "completed"
        _herdr_replacement_store.durable_write(path=record_path, value=current)
        return None
    return (
        "pending resume Enter outcome is unknown"
        if effect_unknown
        else "pending resume Enter was not confirmed"
    )


def _retry_enter(*, sup: Supervisor, target: str, resume: str) -> tuple[bool, bool]:
    native = cast(
        PendingEnterRetry | None,
        getattr(sup.tmux, "retry_prompt_enter_once", None),
    )
    if native is not None:
        return native(session=target, text=resume, sleep=sup.sleep)
    sent = sup.tmux.send_keys(session=target, keys="Enter")
    sup.sleep(SUBMIT_POLL)
    submitted = sent and signals.input_box_ready(capture_text=sup.tmux.capture_pane(session=target))
    return submitted, sent and not submitted


def resume_proven_successor(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    transaction: dict[str, object],
) -> str | None:
    """Prove a distinct successor and submit its continuation at most once."""
    if transaction.get("runtime") == "codex":
        return _supervisor_herdr_codex_successor.continue_codex_successor(
            sup=sup,
            track=track,
            target=target,
            transaction=transaction,
        )
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
        reason = _supervisor_herdr_completion.complete_replacement_round(sup=sup, track=track)
    if reason is None:
        # The row still records the predecessor, and the recorded-identity pane gate
        # would refuse this successor on every later tick, so record the proven one.
        _ = registry.record_observed_session_identity(
            repo=track.repo,
            topic=track.topic,
            session_identity=cast(str, identity),
            store_path=sup.store_path,
        )
    return reason
