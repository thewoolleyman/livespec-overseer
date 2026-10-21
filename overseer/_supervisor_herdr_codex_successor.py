"""Exact process-and-rollout proof plus guarded Codex continuation after Herdr launch."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

import _herdr_replacement_process
import _herdr_replacement_store
import _supervisor_herdr_codex_naming
import _supervisor_herdr_codex_retry
import _supervisor_herdr_completion
import _supervisor_launch
import registry
import signals
from _supervisor_codex_successor import rename_command

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["continue_codex_successor"]


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
        if not _supervisor_herdr_codex_naming.rollout_named(sup=sup, track=track, rollout=rollout):
            _, reason = _supervisor_herdr_codex_retry.retry_pending(
                sup=sup,
                target=target,
                current=current,
                record_path=record_path,
                key="rename",
            )
            sup.refresh_codex_sessions()
            if not _supervisor_herdr_codex_naming.rollout_named(
                sup=sup, track=track, rollout=rollout
            ):
                return reason
    else:
        capture = sup.tmux.capture_pane(session=target)
        if signals.is_structured_gate(capture_text=capture):
            return "fresh Codex successor is waiting at a structured gate"
        if not signals.is_codex_idle_input(capture_text=capture):
            return "fresh Codex successor input is not ready"
        current["rename"] = rename_command(topic=track.topic)
        current["phase"] = "rename-attempted"
        _herdr_replacement_store.durable_write(path=record_path, value=current)
        # The rename asks the runtime for no turn, so it is submitted WITHOUT holding a
        # per-pane attempt and proven by its own durable index record; holding it is what
        # suppressed every later payload to this pane, the resume line included.
        if not _supervisor_herdr_codex_naming.name_fresh_successor(
            sup=sup,
            track=track,
            target=target,
            text=current["rename"],
            rollout=rollout,
        ):
            return "fresh Codex successor was never named for this plan topic"
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
