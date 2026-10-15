"""Which accounts a refusal still holds, and what the refusal trigger compares on.

An account is REFUSAL-HELD from the moment a refusal is attributed to it until
that refusal has LAPSED, and a held account MUST NOT be selected as a candidate
whatever its readings report. That last clause is what keeps the trigger from
oscillating: the account this pass is leaving is exactly the one whose lagging
reading would otherwise attract a return to it on the next pass.

A refusal lapses by whichever of two rules its own record allows:

  * it reported a reset, and that reset has passed; or
  * it reported none, and a later reading of the named window shows that window
    fully replenished, or shows a reset more than the one-minute tolerance later
    than the reset the window carried when the refusal was attributed.

The tolerance is not a setting. The provider reports a nominal reset with
sub-second jitter that can straddle a minute boundary, so one minute is a
property of the reading noise, exactly as it is for the expiring-quota drain.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Final

from caam_decision import ProfileUsage, UsageRecord, binding, resets_at
from caam_refusal_lapse import remember_lapsed
from caam_refusal_store import RememberedRefusal, keep_refusals, remembered_refusals
from caam_refusals import WINDOW_FIVE_HOUR, window_label

__all__: list[str] = [
    "NO_REFUSALS",
    "RefusalState",
    "TriggerBinding",
    "refusal_state",
    "selectable_profiles",
    "trigger_binding",
]

_RESET_TOLERANCE_S: Final = 60.0
_FULLY_REPLENISHED: Final = 100.0
_NOTHING_LEFT: Final = 0.0


@dataclass(frozen=True, kw_only=True)
class RefusalState:
    """Which accounts are refusal-held, and the refusal governing the active one.

    ``holding`` is every refusal that still holds its account, carried whole
    rather than reduced to the names it covers: a hold has to be REPORTED as
    well as applied, and the report states when each refusal was recorded.
    ``held`` is derived from it so the set selection prunes by and the set the
    report names cannot drift apart.

    ``active`` is the active account's own governing refusal, which is the most
    recently recorded of the ones still holding it, and None where no refusal
    holds it. The refusal trigger fires exactly while it is present.
    """

    holding: tuple[RememberedRefusal, ...]
    active: RememberedRefusal | None

    @property
    def held(self) -> frozenset[str]:
        return frozenset(remembered.account for remembered in self.holding)

    @property
    def holds_active(self) -> bool:
        return self.active is not None


NO_REFUSALS: Final = RefusalState(holding=(), active=None)


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


def refusal_state(
    *,
    state: dict[str, object],
    profiles: tuple[ProfileUsage, ...],
    active_name: str,
    now: float,
) -> RefusalState:
    """The refusal standing of every account, dropping the refusals that lapsed.

    Lapsed refusals are dropped from the durable store as they are read, so that
    a settled refusal neither holds its account nor returns on a later pass. The
    drop is a write to the state this pass will persist; nothing else prunes it.

    Dropping one is not enough on its own, because the transcript the refusal was
    read from still carries the record: the lapse is ALSO remembered, as the
    attribution floor `caam_refusal_lapse` keeps, or the next pass would attribute
    the same refusal afresh and -- for a refusal that reported no reset -- do it
    against a baseline that makes the hold unendable.
    """
    judged = tuple(
        (
            remembered,
            _lapsed(
                remembered=remembered,
                reading=_reading(profiles=profiles, account=remembered.account),
                now=now,
            ),
        )
        for remembered in remembered_refusals(state=state)
    )
    kept = tuple(remembered for remembered, lapsed in judged if not lapsed)
    remember_lapsed(state=state, lapsed=tuple(r for r, lapsed in judged if lapsed))
    keep_refusals(state=state, remembered=kept)
    return RefusalState(
        holding=kept,
        active=max(
            (remembered for remembered in kept if remembered.account == active_name),
            key=lambda remembered: remembered.refusal.recorded_at,
            default=None,
        ),
    )


def selectable_profiles(
    *, profiles: tuple[ProfileUsage, ...], refusal: RefusalState
) -> tuple[ProfileUsage, ...]:
    """The rows selection may choose from: every account no refusal holds.

    The refusal-held ACTIVE account leaves the set too, which is also how the
    weekly reserve's release stops counting it as an account above the reserve.
    """
    return tuple(profile for profile in profiles if profile.name not in refusal.held)


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


def _reading(*, profiles: tuple[ProfileUsage, ...], account: str) -> UsageRecord | None:
    return next(
        (profile.usage for profile in profiles if profile.name == account and profile.usage),
        None,
    )


def _lapsed(*, remembered: RememberedRefusal, reading: UsageRecord | None, now: float) -> bool:
    reported = remembered.refusal.resets_at
    if reported is not None:
        return now >= reported
    if reading is None:
        return False
    window = remembered.refusal.window
    if _window_remaining(reading=reading, window=window) >= _FULLY_REPLENISHED:
        return True
    later = resets_at(timestamp=_window_reset(reading=reading, window=window))
    baseline = remembered.window_reset_at
    if baseline is None or later == float("inf"):
        return False
    return later > baseline + _RESET_TOLERANCE_S


def _window_remaining(*, reading: UsageRecord, window: str) -> float:
    if window == WINDOW_FIVE_HOUR:
        return reading.five_hour_remaining
    return reading.seven_day_remaining


def _window_reset(*, reading: UsageRecord, window: str) -> str | None:
    if window == WINDOW_FIVE_HOUR:
        return reading.five_hour_resets_at
    return reading.seven_day_resets_at
