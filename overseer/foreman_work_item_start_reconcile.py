"""Reconciling a work-item start attempt with the outcome of its spawn.

A work-item start writes two durable things before it spawns: the surface's own
start-intent record, and the per-work-item ``claim.json`` that every later reader
consults to decide whether the track is being worked. Both must be squared with
what the spawn actually did, and the two failure cases named by
SPECIFICATION/spec.md square differently.

A spawn that fails and RESOLVES leaves a surviving surface: it amends the intent
record with the error and releases the claim, so nothing it wrote is left reading
as live work. A spawn that does NOT return leaves nobody to write anything — the
record stands outcome-less and the claim stands beside it — so the reconciliation
happens LATER, at the next start, where an outcome-less record is read as the
attempt it was and its stale claim is released then.
"""

from __future__ import annotations

from pathlib import Path

from foreman_start_intent import amend_start_intent, start_intent_reads_attempted_and_failed
from foreman_work_item_session_store import append_event, state_dir

__all__: list[str] = ["reconcile_spawn", "released_stale_claim"]

_STALE_CLAIM_REASON = "start_intent_attempted_and_failed"


def released_stale_claim(*, repo: Path, action_id: str, work_item_id: str) -> bool:
    """Release a claim whose own start-intent reads attempted-and-failed.

    Such a claim was written moments before a spawn that never resolved, so it
    names a dead attempt rather than live work. Anything the reader cannot
    place — no record, an unreadable one, or one already carrying an outcome —
    leaves the claim exactly as it was: this fails CLOSED, because reading
    silence as permission is how a reconciliation becomes a second session
    against a live one.
    """
    if not start_intent_reads_attempted_and_failed(
        repo=repo, action_id=action_id, target=work_item_id
    ):
        return False
    _release_claim(repo=repo, work_item_id=work_item_id, reason=_STALE_CLAIM_REASON)
    return True


def reconcile_spawn(*, repo: Path, action_id: str, work_item_id: str, code: int) -> str | None:
    """Square the intent record and the claim with a spawn that RESOLVED.

    Returns the failure reason, or None when the spawn started. Reaching this at
    all proves the surface survived its own spawn, which is precisely what makes
    an UNAMENDED record mean that it did not.
    """
    error = None if code == 0 else f"command_exit_{code}"
    amend_start_intent(repo=repo, action_id=action_id, target=work_item_id, error=error)
    if error is not None:
        _release_claim(repo=repo, work_item_id=work_item_id, reason=error)
    return error


def _release_claim(*, repo: Path, work_item_id: str, reason: str) -> None:
    """Drop a claim that no longer names live work, recording why beside it.

    Unlinking it silently would trade one loss for another: the journalled reason
    is what lets a later reader tell a reconciled attempt from one that was never
    made at all.
    """
    directory = state_dir(repo=repo, work_item_id=work_item_id)
    (directory / "claim.json").unlink(missing_ok=True)
    append_event(
        directory=directory,
        record={"event": "claim_released", "reason": reason, "work_item_id": work_item_id},
    )
