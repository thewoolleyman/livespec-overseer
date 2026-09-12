"""_supervisor_compaction — recognising an in-place context compaction, and latching it.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. This module owns ONE transition and decides nothing else: given what the store
remembers about a track's context generation, the identity of the session live in its
pane RIGHT NOW, and the percentage that pane is rendering, it says what the store
should remember next — and whether this observation is the one that caught a
compaction.

THE DEFECT THIS CLOSES (`overseer-nb7ok7`, maintainer ruling 2026-09-12). A session
that never goes idle can cross its wind-down threshold with no injection window, be
compacted in place by its own runtime, and come back ABOVE the threshold under the
same session id. Every surface downstream then reads healthy: the percentage is high,
so the below-threshold branch is not entered, the starvation episode closes, and
``_supervisor_round_recovery`` treats the replenished reading as proof the round is no
longer current. `llm-provider-manager` walked that exact path repeatedly on
2026-09-11. The daemon was not wrong about any single fact; it had no way to say that
the healthy number belonged to a DIFFERENT, summarized context generation than the one
it had been winding down.

The maintainer's ruling is that such a generation is EXHAUSTED, not recovered: its
summarized state is not acceptable as clean continuation. So a detected compaction
creates a durable restart-required obligation for either runtime, and that obligation
stands however healthy the percentage later reads, until the ordinary cooperative
protocol obtains a fresh `winding-down`, a certifiable `ready`, and a successor.

WHY A RISE IS THE SIGNAL, AND WHY IDENTITY IS THE DISCRIMINATOR. Remaining context
falls monotonically inside one generation — every turn consumes window and none
returns it — so a rise cannot be ordinary progress. It has exactly two causes: the
generation was replaced in place (a compaction), or the SESSION was replaced (a
restart). Those are opposite situations and the reading alone cannot tell them apart,
which is why this keys on the session identity the reading was taken under. Same
identity plus a rise is the failure; a new identity plus a rise is the successor of a
completed restart and RESETS the record, latch included.

IT KEYS ON THE LIVE IDENTITY, NEVER THE SYNTHESIZED ONE. ``_supervisor_ready`` hands
the certification cascade a fallback ``claude:<session>:<topic>`` when a Claude
session cannot be resolved in the registry, and that fallback is CONSTANT across a
real restart in the same tmux session. Feeding it here would read a genuine successor
as a compaction of its own predecessor — and, worse, would never clear, because the
identity that must change to clear the latch could not change. So the caller passes
the LIVE identity (``_supervisor_ready.live_session_identity``), which is None exactly
when the daemon cannot prove which process it is looking at, and a None identity
changes nothing at all. Fail-closed: an unprovable observation neither latches nor
clears.

AND IT NEVER AUTHORIZES A RESTART. The latch is an OBLIGATION — it decides that the
wind-down is still owed and that the round is still current. The cardinal rule is
untouched: only the session's own fresh, certifiable `ready` reaches the restart act
surface, and a latched track that is busy or undeclared is left alone exactly as any
other is.

It imports no supervisor sibling, deliberately: every input is a plain value, so the
transition is a pure function the beside-tests drive directly, and
:mod:`_supervisor_records` can carry the result without an import cycle.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import registry

__all__: list[str] = [
    "COMPACTION_CTX_RISE",
    "NO_COMPACTION_TRANSITION",
    "CompactionTransition",
    "compaction_evidence",
    "compaction_note",
    "injection_ctx",
    "observe_compaction",
    "wind_down_owed",
]

# How far a remaining-context reading must RISE, under an unchanged live session
# identity, before it is read as a compaction rather than as instrument noise.
#
# The physical claim is that a rise of any size is impossible inside one generation, so
# in principle a single point would do. The tolerance is here because the two
# statuslines this is parsed from carry the runtimes' OWN rounded integers, recomputed
# per render, and a one- or two-point wobble across a redraw says nothing about the
# window. A real compaction replenishes tens of points — the measured 2026-09-11 case
# crossed from below 50% to above it — so this band sits far below anything it must
# catch and far above anything it must ignore.
COMPACTION_CTX_RISE = 5


@dataclass(frozen=True, kw_only=True)
class CompactionTransition:
    """What one observation says the durable record should become, and why."""

    record: registry.ContextCompaction
    # This observation is the one that CAUGHT a compaction: the record was unlatched
    # and is now latched. True on exactly one observation per compaction, so it is an
    # edge an alert can hang off rather than a state re-reported every tick.
    detected: bool
    # This observation is looking at a DIFFERENT session than the record was opened
    # against — the successor of a completed restart. The record is reopened against
    # it, which is what clears a latch the predecessor was carrying.
    successor: bool

    @property
    def restart_required(self) -> bool:
        """Whether a detected compaction still owes a fresh-session restart."""
        return self.record.restart_required


# The transition for a track nothing has been observed about. The default on
# :class:`_supervisor_records.Observation`, and it claims nothing: no latch to act on,
# no edge to report.
NO_COMPACTION_TRANSITION = CompactionTransition(
    record=registry.NO_CONTEXT_COMPACTION, detected=False, successor=False
)


def observe_compaction(
    *,
    stored: registry.ContextCompaction | None,
    session_identity: str | None,
    current_ctx: int | None,
    now: float,
) -> CompactionTransition:
    """Fold one live reading into the track's durable context-generation record."""
    held = stored if stored is not None else registry.NO_CONTEXT_COMPACTION
    if session_identity is None or current_ctx is None:
        # Nothing was proven this observation: no identity to own a record, or no
        # percentage to compare against one. Carry the record untouched rather than
        # guessing in either direction.
        return CompactionTransition(record=held, detected=False, successor=False)
    if held.session_identity != session_identity:
        return CompactionTransition(
            record=registry.ContextCompaction(
                session_identity=session_identity, watermark_ctx=current_ctx
            ),
            detected=False,
            # A record that never had an owner is being opened for the first time,
            # which is not a restart having completed — only a change FROM a known
            # predecessor is.
            successor=held.session_identity is not None,
        )
    watermark = held.watermark_ctx
    if watermark is not None and current_ctx - watermark > COMPACTION_CTX_RISE:
        return CompactionTransition(
            record=registry.ContextCompaction(
                session_identity=session_identity,
                # Re-floored to the post-compaction reading, so a SECOND compaction in
                # the same session is still visible as a rise.
                watermark_ctx=current_ctx,
                # The evidence kept is the FIRST compaction's, not the latest: the
                # obligation is already owed, and re-dating it on every later
                # compaction would keep moving the failure an operator is reading.
                latched_at=held.latched_at if held.restart_required else now,
                from_ctx=held.from_ctx if held.restart_required else watermark,
                to_ctx=held.to_ctx if held.restart_required else current_ctx,
            ),
            detected=not held.restart_required,
            successor=False,
        )
    return CompactionTransition(
        record=dataclasses.replace(
            held,
            watermark_ctx=current_ctx if watermark is None else min(watermark, current_ctx),
        ),
        detected=False,
        successor=False,
    )


def wind_down_owed(
    *, compaction: CompactionTransition, eff_ctx: int | None, threshold: int
) -> bool:
    """Whether this track still owes the escalating wind-down.

    The ordinary trigger is a below-threshold reading. A latched track owes it too, at
    ANY percentage — that is the whole point of the latch: the generation the daemon
    was winding down is gone, and the number now on the statusline describes a
    different one.
    """
    return compaction.restart_required or (eff_ctx is not None and eff_ctx <= threshold)


def injection_ctx(*, compaction: CompactionTransition, eff_ctx: int, threshold: int) -> int:
    """The remaining-context figure the escalation bands are selected by.

    A latched track is floored to its threshold so the FIRST band fires: its
    post-compaction percentage says nothing about the generation being wound down, and
    left unfloored it would select no band at all and inject nothing. The floor is a
    ``min``, never an assignment — a latched track that is ALSO genuinely low keeps its
    real, lower figure and its sharper escalation band.
    """
    if not compaction.restart_required:
        return eff_ctx
    return min(eff_ctx, threshold)


def compaction_note(*, compaction: CompactionTransition) -> str | None:
    """The row note that tells an ordinary threshold warning from a latched failure."""
    record = compaction.record
    if not compaction.restart_required:
        return None
    return f"context compaction {record.from_ctx}%->{record.to_ctx}%; restart required"


def compaction_evidence(*, record: registry.ContextCompaction) -> str:
    """The identity + context-transition evidence a history line carries."""
    return (
        f"session {record.session_identity} context compacted "
        f"{record.from_ctx}% -> {record.to_ctx}%"
    )
