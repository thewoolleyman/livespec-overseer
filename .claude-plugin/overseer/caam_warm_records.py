"""What the caam warm stage has to SAY about a pass, as two value objects.

`caam_warm` does the work -- refreshing idle snapshots and scheduling the next
wake. These are what it reports back, and they are declared apart from it for one
measured reason: `caam_warm` already sits in the LLOC soft band, and a record that
grows with the questions an operator asks does not belong inside a file that is
close to the ceiling. Keeping them here also lets the span module that shapes them
for the wire import the records WITHOUT importing the refresh machinery.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__: list[str] = [
    "WarmOutcome",
    "WarmSchedule",
]


@dataclass(frozen=True, kw_only=True)
class WarmOutcome:
    """What ONE `keep_warm` pass did to the idle snapshots it maintains.

    `maintained` is false exactly when the pass returned before looking at any
    profile at all -- warming switched off, a dry run, or no vault. Without it a
    disabled warm stage and a healthy one with nothing to do are the same record,
    which is the distinction an operator asking "why was nothing warmed" needs.

    `attempted` counts refreshes tried, `refreshed` the subset that worked. They
    differ whenever an account is persistently unrefreshable, which is the
    condition that eventually leaves rotation with nowhere to go.
    """

    maintained: bool
    attempted: int
    refreshed: int


@dataclass(frozen=True, kw_only=True)
class WarmSchedule:
    """When to next run warm maintenance, and which idle account that instant is for.

    Both fields are absent together: the wake IS the soonest FUTURE idle expiry
    plus a delay, so a pass with no such expiry has neither a wake to schedule nor
    a profile to name it after.
    """

    profile: str | None
    wake: float | None
