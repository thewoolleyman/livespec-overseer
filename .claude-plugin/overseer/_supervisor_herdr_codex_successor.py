"""Exact process-and-rollout proof plus guarded Codex continuation after Herdr launch."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

import _herdr_replacement_process
import _herdr_replacement_store
import _supervisor_herdr_codex_retry
import _supervisor_herdr_completion
import _supervisor_launch
import codex_sessions
import registry
import signals
from _supervisor_codex_successor import rename_command
from _supervisor_config import RESTART_POLL_INTERVAL, RESTART_POLL_MAX

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["continue_codex_successor"]

# SPECIFICATION v064: an unnamed successor is the rename's own failure path, stated as
# such. The rename is proven by its session-index record and never by a turn start, so
# "the submission was not observed" is no longer a fact this phase can report — the
# payload went in and nothing named the successor, which is what the operator needs told.
_UNNAMED_SUCCESSOR = "fresh Codex successor is not named in the session index"


def _rollout_named(*, sup: Supervisor, track: registry.Track, rollout: str) -> bool:
    indexed = codex_sessions.latest_session_for_thread_name(
        thread_name=track.topic, codex_home=sup.codex_home
    )
    return indexed == rollout


def _named_within_bound(*, sup: Supervisor, track: registry.Track, rollout: str) -> bool:
    """Wait, bounded, for the rename's OWN evidence: its durable session-index record.

    The rename starts no turn, so there is nothing in the pane to wait on; Codex
    appends the record a few seconds later, and v064 admits no other proof. The tmux
    arm polls the same record over the same budget
    (:func:`_supervisor_codex_fresh._named`), which is what this phase mirrors.

    A miss is not terminal: the next tick re-reads the record at the top of the
    ``rename-attempted`` phase before retrying anything, so this bound only decides how
    long ONE tick waits before keeping the ready declaration and surfacing an unnamed
    successor.
    """
    for attempt in range(RESTART_POLL_MAX):
        sup.refresh_codex_sessions()
        if _rollout_named(sup=sup, track=track, rollout=rollout):
            return True
        if attempt + 1 < RESTART_POLL_MAX:
            sup.sleep(RESTART_POLL_INTERVAL)
    return False


def _prove_successor(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    current: dict[str, object],
) -> tuple[_herdr_replacement_process.ProcessObservation | None, str | None, str | None]:
    session = _supervisor_launch.session_of(sup=sup, track=track)
    sup.refresh_codex_sessions()
    live = sup.live_codex.get((session, track.topic))
    prior = current.get("predecessor_rollout")
    if (
        live is None
        or live.session_id == prior
        or _supervisor_launch.canonical_codex_session_id(value=live.session_id) is None
        or not signals.path_in_repo(pane_current_path=live.cwd, repo=track.repo)
    ):
        return None, None, "fresh Codex rollout is not yet observable in the original pane"
    starttime = sup.starttime_of(pid=live.pid)
    if starttime is None:
        return None, None, "fresh Codex process generation is not readable"
    pane = cast(_herdr_replacement_process.ReplacementPane, sup.tmux)
    snapshot = pane.herdr_replacement_snapshot(session=target)
    identity = f"codex:{live.pid}:{starttime}:{track.topic}"
    successor = _herdr_replacement_process.proven_successor(
        transaction=current, snapshot=snapshot, identity=identity
    )
    if successor is None:
        return None, None, "Codex successor is not a fresh process in the retained shell"
    return successor, live.session_id, None


def _rename_successor(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    current: dict[str, object],
    record_path: Path,
    rollout: str,
) -> str | None:
    if current.get("phase") == "rename-attempted":
        if not _rollout_named(sup=sup, track=track, rollout=rollout):
            submitted, reason = _supervisor_herdr_codex_retry.retry_pending(
                sup=sup,
                target=target,
                current=current,
                record_path=record_path,
                key="rename",
            )
            sup.refresh_codex_sessions()
            if not _rollout_named(sup=sup, track=track, rollout=rollout):
                # The Enter is worth reporting only when IT is what failed. A rename
                # that did go in and still named nothing is an unnamed successor, not a
                # submission problem — and the old code returned the retry's EMPTY
                # success string there, a reason with nothing in it.
                return _UNNAMED_SUCCESSOR if submitted else reason
    else:
        capture = sup.tmux.capture_pane(session=target)
        if signals.is_structured_gate(capture_text=capture):
            return "fresh Codex successor is waiting at a structured gate"
        if not signals.is_codex_idle_input(capture_text=capture):
            return "fresh Codex successor input is not ready"
        current["rename"] = rename_command(topic=track.topic)
        current["phase"] = "rename-attempted"
        _herdr_replacement_store.durable_write(path=record_path, value=current)
        # v064: a slash command asks Codex for nothing, so this delivery can never be
        # confirmed by a turn start and is never HELD as an unconfirmed attempt — which
        # is what used to answer the resume request below from the stale rename and
        # leave the replacement's resume line unpasted. The index record is its proof.
        _ = _supervisor_launch.submit_prompt(
            sup=sup,
            target=target,
            text=current["rename"],
            expect_codex=True,
            expects_no_turn=True,
        )
        if not _named_within_bound(sup=sup, track=track, rollout=rollout):
            return _UNNAMED_SUCCESSOR
    current["phase"] = "successor-observed"
    _herdr_replacement_store.durable_write(path=record_path, value=current)
    return None


def _resume_successor(
    *,
    sup: Supervisor,
    target: str,
    current: dict[str, object],
    record_path: Path,
) -> str | None:
    if current.get("phase") == "resume-attempted":
        submitted, reason = _supervisor_herdr_codex_retry.retry_pending(
            sup=sup,
            target=target,
            current=current,
            record_path=record_path,
            key="resume",
        )
        if not submitted:
            return reason
    else:
        resume = current.get("resume")
        capture = sup.tmux.capture_pane(session=target)
        if not isinstance(resume, str) or not resume:
            return "recorded track has no durable resume continuation"
        if signals.is_structured_gate(capture_text=capture):
            return "named Codex successor is waiting at a structured gate"
        if not signals.is_codex_idle_input(capture_text=capture):
            return "named Codex successor input is not ready"
        current["phase"] = "resume-attempted"
        _herdr_replacement_store.durable_write(path=record_path, value=current)
        if not _supervisor_launch.submit_prompt(
            sup=sup, target=target, text=resume, expect_codex=True
        ):
            return "verified Codex successor resume submission was not confirmed"
    current["phase"] = "completed"
    _herdr_replacement_store.durable_write(path=record_path, value=current)
    return None


def continue_codex_successor(
    *,
    sup: Supervisor,
    track: registry.Track,
    target: str,
    transaction: dict[str, object],
) -> str | None:
    """Prove process and rollout, then name and resume without replaying either paste."""
    scratch = _herdr_replacement_store.scratch_path(track=track)
    record_path = scratch / _herdr_replacement_store.RECORD_NAME
    with _herdr_replacement_store.transaction_lock(
        path=scratch / _herdr_replacement_store.LOCK_NAME
    ):
        current = _herdr_replacement_store.read_transaction(path=record_path)
        if current != transaction:
            return "durable replacement changed during Codex successor verification"
        current = cast(dict[str, object], current)
        successor, rollout, reason = _prove_successor(
            sup=sup, track=track, target=target, current=current
        )
        if successor is None or rollout is None:
            return reason
        recorded = current.get("successor")
        process_record = _herdr_replacement_process.process_record(process=successor)
        if recorded is not None and recorded != process_record:
            return "Codex successor no longer matches its durable process generation"
        current["successor"] = process_record
        current["successor_rollout"] = rollout
        if current.get("phase") in {"launch-attempted", "rename-attempted"}:
            reason = _rename_successor(
                sup=sup,
                track=track,
                target=target,
                current=current,
                record_path=record_path,
                rollout=rollout,
            )
        if reason is None and current.get("phase") in {"successor-observed", "resume-attempted"}:
            reason = _resume_successor(
                sup=sup, target=target, current=current, record_path=record_path
            )
    if reason is None:
        reason = _supervisor_herdr_completion.complete_replacement_round(sup=sup, track=track)
    return reason
