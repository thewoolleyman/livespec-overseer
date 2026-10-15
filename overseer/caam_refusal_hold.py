"""Which accounts a refusal holds, and what the refusal trigger compares on.

An account is REFUSAL-HELD from the moment a refusal is attributed to it, and
the refusal trigger fires exactly while a refusal holds the ACTIVE account.
When it fires, candidates are compared on the dimension the refusal NAMES and
the active account's headroom on that dimension is taken as zero, since an
account that is refusing has none to offer whatever its reading says.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Final

from caam_decision import UsageRecord, binding
from caam_refusal_store import RememberedRefusal, remembered_refusals
from caam_refusals import WINDOW_FIVE_HOUR, window_label

__all__: list[str] = [
    "NO_REFUSALS",
    "RefusalState",
    "TriggerBinding",
    "refusal_state",
    "trigger_binding",
]

_NOTHING_LEFT: Final = 0.0


@dataclass(frozen=True, kw_only=True)
class RefusalState:
    """Which accounts are refusal-held, and the refusal governing the active one.

    ``active`` is the active account's own governing refusal, which is the most
    recently recorded of the ones still holding it, and None where no refusal
    holds it. The refusal trigger fires exactly while it is present.
    """

    held: frozenset[str]
    active: RememberedRefusal | None

    @property
    def holds_active(self) -> bool:
        return self.active is not None


NO_REFUSALS: Final = RefusalState(held=frozenset(), active=None)


@dataclass(frozen=True, kw_only=True)
class TriggerBinding:
    """The dimension this pass is leaving on, and the account's standing on it.

    Under the refusal trigger the dimension is the one the refusal NAMES and the
    active account's headroom on it is taken as zero, since an account that is
    refusing has none to offer whatever its reading says. ``usage`` carries that
    zero so every downstream comparison -- the margin, the candidate gate, the
    reserve release -- reads it without being told about refusals at all.
    """

    dimension: str
    remaining: float
    label: str
    usage: UsageRecord


def refusal_state(*, state: dict[str, object], active_name: str) -> RefusalState:
    """The refusal standing of every account the store remembers one against."""
    kept = remembered_refusals(state=state)
    return RefusalState(
        held=frozenset(remembered.account for remembered in kept),
        active=max(
            (remembered for remembered in kept if remembered.account == active_name),
            key=lambda remembered: remembered.refusal.recorded_at,
            default=None,
        ),
    )


def trigger_binding(
    *,
    refusal: RefusalState,
    current: UsageRecord,
    active_name: str,
    protection_floors: Mapping[str, float],
) -> TriggerBinding:
    """What this pass is leaving on: the refusal's dimension where one governs."""
    dimension, remaining, label = binding(
        usage=current, active_name=active_name, protection_floors=protection_floors
    )
    if refusal.active is None:
        return TriggerBinding(dimension=dimension, remaining=remaining, label=label, usage=current)
    window = refusal.active.refusal.window
    return TriggerBinding(
        dimension=window,
        remaining=_NOTHING_LEFT,
        label=f"usage-limit refusal on the {window_label(window=window)}",
        usage=_no_headroom(usage=current, window=window),
    )


def _no_headroom(*, usage: UsageRecord, window: str) -> UsageRecord:
    if window == WINDOW_FIVE_HOUR:
        return replace(usage, five_hour_remaining=_NOTHING_LEFT)
    return replace(usage, seven_day_remaining=_NOTHING_LEFT)
