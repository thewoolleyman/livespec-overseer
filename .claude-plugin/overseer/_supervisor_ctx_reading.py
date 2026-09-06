"""_supervisor_ctx_reading — how current the daemon's headroom knowledge is.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. Context headroom is the input to wrap-up safety — the daemon injects an
escalating wrap-up at a threshold so a session preserves its handoff BEFORE it is
restarted or lost — so a row that reports nothing about headroom cannot be assessed
for that threshold at all.

THE DEFECT THIS CLOSES (`overseer-62mgxr`). Headroom is read from the statusline the
pane renders (``signals.parse_ctx_remaining``). An open picker's overlay displaces
that statusline out of the capture, so the live read returns None: measured
fleet-wide 2026-08-23, 0 of 8 picker-open rows carried a reading, no exceptions. The
instrument therefore failed closed on exactly the sessions that sit longest, can
least act for themselves, and hold the most unpreserved state.
``_supervisor_observe.effective_ctx`` did already carry the last known value
forward — but for ``CTX_STALE_AFTER`` (one hour) only, and WITHOUT SAYING SO, which
is two separate defects: a session parked four hours reported a bare dash, and one
parked ten minutes reported an hour-old number as though the pane had just rendered
it. An operator cannot tell "near exhaustion" from "most of the window left" through
either.

WHAT THIS MODULE DOES, AND WHAT IT DELIBERATELY DOES NOT. It projects a
:class:`_supervisor_records.CtxReading` — the value AND its provenance AND its age —
for the OPERATOR surfaces (the table's ``Ctx%`` cell and the daemon status
snapshot). It does NOT feed the decision cascade: ``Observation.eff_ctx`` keeps its
fail-closed one-hour window, so a stale reading still cannot cross a threshold, open
a round, or authorize anything. That separation is the whole design. REPORTING an
old number is safe as long as the report says it is old; ACTING on one is the
failure the window exists to prevent, and this module never widens it.

IT KEYS ON THE READ, NEVER ON ``picker_open``. The predicate is "the live parse
returned nothing", which is the failure itself rather than a state believed to cause
it. Keying on the picker would be wrong in BOTH directions. A picker-open pane whose
statusline is still visible — measured 2026-08-22, ``factory-host-storage-reclamation``
at ctx 64 — would have its REAL reading discarded and replaced with an unknown,
which is this item's own leg 2 pointed the other way. And roughly half the fleet's
NON-picker rows also read None, for reasons that have nothing to do with a picker; a
picker-keyed fix would leave every one of them exactly as blind as before.

AND IT NEVER INVENTS A VALUE. There is no default, no floor, and no neighbour's
number. A track this daemon has never managed to read reports
``CTX_SOURCE_UNREADABLE`` with a null value and stays distinguishable from every row
carrying one — which is what keeps the population table honest rather than merely
healthy-looking.

The in-memory retention this reads from (``InjectState.last_ctx``) is reset by a
daemon bounce, so a bounce returns a picker-parked track to ``unreadable`` until its
statusline is visible again. That is the truthful answer for that state, not a gap:
the daemon genuinely does not know, and says so.
"""

from __future__ import annotations

from _supervisor_config import CTX_STALE_AFTER
from _supervisor_records import (
    CTX_SOURCE_LIVE,
    CTX_SOURCE_RETAINED,
    CTX_SOURCE_UNREADABLE,
    CtxReading,
    InjectState,
)

__all__: list[str] = ["ctx_reading", "observed_stale_ctx_age"]


def ctx_reading(*, state: InjectState, current: int | None, now: float) -> CtxReading:
    """Project the track's headroom knowledge with the provenance that makes it judgeable.

    Three outcomes and no fourth: the pane rendered a statusline this tick (live); it
    did not, but this daemon has a reading of its own to carry (retained, stamped with
    that reading's age); or it did not and there is nothing to carry (unreadable).
    """
    if current is not None:
        return CtxReading(value=current, source=CTX_SOURCE_LIVE, age_seconds=None)
    if state.last_ctx is None or state.last_ctx_seen is None:
        return CtxReading(value=None, source=CTX_SOURCE_UNREADABLE, age_seconds=None)
    return CtxReading(
        value=state.last_ctx,
        source=CTX_SOURCE_RETAINED,
        age_seconds=max(0.0, now - state.last_ctx_seen),
    )


def observed_stale_ctx_age(
    *, state: InjectState, current: int | None, eff_ctx: int | None, now: float
) -> float | None:
    """Age of stale last-known ctx, or None while ctx knowledge is fresh/absent."""
    if current is not None or eff_ctx is not None or state.last_ctx_seen is None:
        return None
    age = max(0.0, now - state.last_ctx_seen)
    if age < CTX_STALE_AFTER:
        return None
    return age
