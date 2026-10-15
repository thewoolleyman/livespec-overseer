"""Retire a ``ready`` declaration that stands with no delivered round (spec v058).

Measured 2026-10-14 on gitops-fleet-capacity-monitoring: a wrap-up paste failed, the
daemon un-opened the round as spec.md requires of a failed opening paste, and the
session then wrote ``ready``. That declaration had no round to certify against, and
because the paste predicate never keystrokes over a standing ``ready``, no fresh round
could open either — the restart sat held for ~15h until an operator deleted the file.

spec.md (fail-soft posture) now closes that dead end: once the track OWES a wind-down
(known context at or below its threshold, or a context-compaction latch) and the
declaration has outlived the two-minute declaration grace, the supervising loop DELETES
the state file — guarded on the very same token and modification time it judged — and
records an edge-triggered alert. It never restarts, keystrokes or opens a round in the
same act; the ordinary wrap-up predicate opens the fresh round on that or a later
observation, and a ``ready`` written in answer certifies normally. The un-rounded
``ready`` held no authorization, so removing it takes nothing the cardinal rule protects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_compaction
import registry
import signals
from _supervisor_config import MARKER_VOID_GRACE
from _supervisor_liveness_time import threshold_for

if TYPE_CHECKING:
    from _supervisor_core import Supervisor
    from _supervisor_records import Observation

__all__: list[str] = [
    "UNROUNDED_READY_DELETE_FAILED_CONDITION",
    "UNROUNDED_READY_RETIRED_CONDITION",
    "retire_unrounded_ready",
]

UNROUNDED_READY_RETIRED_CONDITION = "unrounded-ready-retired"
UNROUNDED_READY_DELETE_FAILED_CONDITION = "unrounded-ready-delete-failed"


def _unrounded(*, record: registry.RoundRecord) -> bool:
    """No delivered round: no round-open timestamp and no recorded expiry."""
    return record.at is None and record.expired_at is None


def _guarded_delete(*, repo: str, topic: str, judged: signals.TrackState) -> bool | None:
    """Delete the state file only if it still holds the judged ``ready``.

    Returns True when deleted, None when the file changed under us (a newer write is
    never clobbered), and False when the delete itself failed.
    """
    current = signals.read_state(repo=repo, topic=topic)
    if current is None or (current.token, current.mtime) != (judged.token, judged.mtime):
        return None
    try:
        signals.state_path(repo=repo, topic=topic).unlink()
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return True


def retire_unrounded_ready(
    *,
    sup: Supervisor,
    track: registry.Track,
    obs: Observation,
    session: str,
    pane: str,
    act: bool,
) -> bool:
    """Retire an un-rounded ``ready`` once the track owes a wind-down; True if retired."""
    declared = obs.declared
    if (
        not act
        or declared is None
        or declared.token != signals.STATE_READY
        or not _unrounded(record=obs.round_record)
        or not _supervisor_compaction.wind_down_owed(
            compaction=obs.compaction,
            eff_ctx=obs.eff_ctx,
            threshold=threshold_for(sup=sup, track=track),
        )
    ):
        return False
    age = sup.now() - declared.mtime
    if age <= MARKER_VOID_GRACE:
        return False
    deleted = _guarded_delete(repo=track.repo, topic=track.topic, judged=declared)
    if deleted is None:
        return False
    if not deleted:
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=session,
            pane=pane,
            message="could not retire a ready declaration with no delivered round; "
            "the state file delete failed and will be retried",
            condition=UNROUNDED_READY_DELETE_FAILED_CONDITION,
        )
        return False
    sup.alert(
        repo=track.repo,
        topic=track.topic,
        session=session,
        pane=pane,
        message=f"retired a ready declaration with no delivered round (age {age:.0f}s); "
        "a fresh wrap-up round follows",
        condition=UNROUNDED_READY_RETIRED_CONDITION,
    )
    return True
