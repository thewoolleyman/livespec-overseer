"""What a lapse leaves behind, so a settled refusal is never attributed afresh.

A transcript KEEPS its records. So the pass after a refusal lapses reads that
same refusal again, and meets every attribution condition it met the first time
-- which for a refusal that reported no reset is worse than merely re-arming the
hold. That hold ends on a comparison against the reset the named window carried
WHEN THE REFUSAL WAS ATTRIBUTED, so a re-attribution re-baselines the comparison
against the very reading that just ended the hold, and no later reading can end
it again short of another whole window roll. The hold would end for exactly one
pass and then stand: neither a hold nor a lapse.

What is remembered is ONE instant per account and window -- the latest at which
a refusal on that window was judged lapsed -- rather than a record per refusal.
That is the shape the ratified settling-claim rule already records for a claim
that cleared a window, and it is bounded by construction: a refusal recorded at
or before the floor names a window whose hold has been discharged, while one
recorded after it is a fresh refusal of that window, attributed on its own
terms. A floor only ever moves forward, because the refusals it settles stay
settled.

A floor nothing can read, and a floor a concurrent writer overwrote, both settle
nothing -- the refusal is attributed afresh and holds its account again, which is
what contracts.md bounds a lost refusal memory at, and the direction that cannot
strand the fleet on an account serving nothing.
"""

from __future__ import annotations

from typing import Final

import jsonio
from caam_refusal_store import RememberedRefusal

__all__: list[str] = [
    "attribution_floor",
    "remember_lapsed",
]

_LAPSED_REFUSALS: Final = "lapsed_refusals"


def attribution_floor(*, state: dict[str, object], account: str, window: str) -> float | None:
    """The instant at or before which this account's refusals on this window are settled."""
    return _floors(state=state).get((account, window))


def remember_lapsed(*, state: dict[str, object], lapsed: tuple[RememberedRefusal, ...]) -> None:
    """Record the floor the refusals just judged lapsed leave behind.

    A pass that judged nothing lapsed writes nothing, so it leaves the memory --
    and every decision downstream of it -- exactly as it found it.
    """
    if not lapsed:
        return
    floors = _floors(state=state)
    for entry in lapsed:
        key = (entry.account, entry.refusal.window)
        # The later of the two, so a refusal that lapses after an older one on
        # the same window cannot lower the floor that older one established.
        floors[key] = max(entry.refusal.recorded_at, floors.get(key, entry.refusal.recorded_at))
    state[_LAPSED_REFUSALS] = [
        {"account": account, "window": window, "recorded_at": at}
        for (account, window), at in sorted(floors.items())
    ]


def _floors(*, state: dict[str, object]) -> dict[tuple[str, str], float]:
    stored = jsonio.as_list(value=state.get(_LAPSED_REFUSALS)) or []
    return {
        key: at
        for value in stored
        for record in (jsonio.as_object(value=value) or {},)
        for key, at in _floor(record=record)
    }


def _floor(*, record: dict[str, object]) -> tuple[tuple[tuple[str, str], float], ...]:
    account = record.get("account")
    window = record.get("window")
    at = jsonio.as_float(value=record.get("recorded_at"))
    if not isinstance(account, str) or not isinstance(window, str) or at is None:
        return ()
    return (((account, window), at),)
