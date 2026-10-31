"""Observation-side helpers for the supervisor evaluation cascade."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_channel
import _supervisor_channel_hold
import _supervisor_codex_late_adoption
import _supervisor_compaction
import _supervisor_nudge_marker
import _supervisor_observe
import _supervisor_rejected_state
import registry
import signals
from _supervisor_records import Observation

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "COMPACTION_LATCHED_CONDITION",
    "RecordObservationRequest",
    "reconcile_and_observe",
    "record_tick_observations",
]

# The edge-triggered condition a caught compaction alerts under. It names the FAILURE,
# not the warning that follows from it: an operator reading the history must be able to
# tell "this track crossed its threshold" from "this track's context generation was
# thrown away and summarized", and both produce the same `warned` row.
COMPACTION_LATCHED_CONDITION = "context-compaction-latched"


@dataclass(frozen=True, kw_only=True)
class RecordObservationRequest:
    sup: Supervisor
    track: registry.Track
    obs: Observation
    session: str
    pane: str
    act: bool


def reconcile_and_observe(
    *,
    sup: Supervisor,
    track: registry.Track,
    session: str,
    pane: str,
    key: tuple[str, str],
    act: bool,
) -> Observation:
    """Bring durable per-track state into agreement with this tick, then observe it.

    The evaluation's whole PROLOGUE, as one named step, so the cascade that follows is
    the only thing left in :mod:`_supervisor_evaluate` and still reads top-to-bottom in
    one pass. Three reconciliations and one observation, and the ORDER is the design:

    1. A fresh-Codex restart whose bounded live-adoption proof ran out is completed if
       discovery now reports the successor it recorded launching. It must precede the
       observation: the cascade decides on the facts gathered below, so a declaration
       consumed afterwards would still read as armed and could drive a second respawn
       that kills the very successor this just proved.
    2. The observation itself — every fact the cascade decides on, gathered in one
       place.
    3. What the tick observed is persisted (the live identity a later dead-track
       recovery reads; the context-generation record a bounced daemon reads).
    4. A HELD channel delivery (v060) whose end the daemon can now read is released.
       It withholds every later daemon message to its session, so a hold released
       after the cascade had already read it would withhold a message that is owed for
       one more tick. It comes LAST because, alone among the four, it decides on the
       observation — and a release that lands a keep-going nudge writes that nudge's
       marker, so it returns step 2's observation with the declaration re-read.

    All four are the same KIND of work — make durable state agree with what was just
    observed, before anything decides on it — which is why they belong in one step
    rather than scattered through the cascade as legs that return nothing.
    """
    _ = _supervisor_codex_late_adoption.reconcile_late_codex_successor(
        sup=sup, track=track, session=session, target=pane, act=act
    )
    obs = _supervisor_observe.observe(sup=sup, track=track, session=session, target=pane, key=key)
    obs = _supervisor_rejected_state.reject_malformed_state(
        sup=sup, track=track, obs=obs, session=session, pane=pane, act=act
    )
    record_tick_observations(
        request=RecordObservationRequest(
            sup=sup, track=track, obs=obs, session=session, pane=pane, act=act
        )
    )
    return _release_resolved_hold(sup=sup, track=track, obs=obs) if act else obs


def _release_resolved_hold(
    *, sup: Supervisor, track: registry.Track, obs: Observation
) -> Observation:
    """Free a held delivery, deciding the nudge's episode from more than `idle`.

    A held NUDGE is bounded by the idle episode it answered, and that episode is NOT
    the pane's ``idle`` capture: a session that declares ``blocked`` keeps rendering an
    idle prompt while having plainly left the episode — which is exactly why the busy
    and blocked branches of the cascade both clear the nudge marker to re-arm a later
    one. The same composite bounds the hold.

    Both ENDS of the nudge's episode are wired here for that reason. A release that
    makes the nudge DELIVERED owes the episode the same `idle-with-context-left`
    marker a landed paste writes; the hold itself cannot write it, because the marker
    is the nudge act's bookkeeping rather than the round's.

    Returning a REFRESHED observation is what makes that marker count. It is written
    after step 2 has already read this tick's declaration, so the cascade would still
    see an un-nudged episode and send again — re-sending the very message the channel
    just confirmed the session accepted. Only ``declared`` can have moved: the write
    is guarded to a track that has declared nothing of its own, and the token it
    writes is the daemon's own, so ``malformed`` / ``blocked`` / ``acked`` / ``ready``
    all keep the values the observation derived.
    """
    delivered = _supervisor_channel_hold.release_resolved_hold(
        sup=sup,
        track=track,
        is_codex=obs.is_codex,
        pane_busy=obs.busy,
        idle=obs.idle and not obs.busy and not obs.gate and not obs.blocked,
    )
    if delivered != _supervisor_channel.NUDGE_MESSAGE:
        return obs
    _supervisor_nudge_marker.record_nudge_episode_answered(sup=sup, track=track)
    return dataclasses.replace(obs, declared=signals.read_state(repo=track.repo, topic=track.topic))


def record_tick_observations(*, request: RecordObservationRequest) -> None:
    """Persist what this tick OBSERVED about the track, and report what it caught.

    Both writes are gated on ``act`` for the same reason: the read-only ``list`` path
    must classify without mutating the store. Both are idempotent, so a steady-state
    tick — same identity, watermark already at the lowest reading — rewrites nothing.

    They sit together because they are the same kind of fact and carry the same
    durability requirement. The observed identity is what a dead-track recovery later
    reads to know which runtime it is reviving; the context-generation record is what a
    bounced daemon reads to know a restart is still owed. An in-memory version of
    either would be discarded by exactly the event it exists to survive.
    """
    if not request.act:
        return
    obs = request.obs
    if obs.session_identity is not None:
        _ = registry.record_observed_session_identity(
            repo=request.track.repo,
            topic=request.track.topic,
            session_identity=obs.session_identity,
            store_path=request.sup.store_path,
        )
    # `done` freezes the delivered round exactly where the session finished it. In
    # particular, later idle statusline readings must not lower a standing compaction
    # latch's watermark or re-report one of its edges. If resumed generation voids the
    # declaration, the next ordinary tick records observations again.
    if obs.declared is not None and obs.declared.token == signals.STATE_DONE:
        return
    _ = registry.record_context_compaction(
        repo=request.track.repo,
        topic=request.track.topic,
        record=obs.compaction.record,
        store_path=request.sup.store_path,
    )
    _report_compaction_edges(request=request)


def _report_compaction_edges(*, request: RecordObservationRequest) -> None:
    """Say what the fold caught, once per edge.

    A caught compaction ALERTS with its session identity and its context transition,
    because the row it goes on to produce is an ordinary `warned` and nothing else on
    that row says why. A cleared latch LOGS, because "the successor was adopted and the
    obligation is discharged" is the outcome an operator who saw that alert is waiting
    for, and an obligation that vanishes silently cannot be told from one that was
    dropped.
    """
    obs = request.obs
    if obs.compaction.detected:
        request.sup.alert(
            repo=request.track.repo,
            topic=request.track.topic,
            session=request.session,
            pane=request.pane,
            message=(
                "CONTEXT COMPACTION detected — "
                f"{_supervisor_compaction.compaction_evidence(record=obs.compaction.record)}; "
                "the compacted generation is exhausted, so a cooperative wind-down and a "
                "fresh-session restart stay REQUIRED at any later context percentage"
            ),
            condition=COMPACTION_LATCHED_CONDITION,
        )
    elif obs.compaction.successor:
        request.sup.log(
            message=(
                f"context-compaction latch cleared for {request.track.repo}::"
                f"{request.track.topic} after fresh session "
                f"{obs.compaction.record.session_identity} was adopted"
            )
        )
