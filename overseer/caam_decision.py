"""Pure decision helpers for caam account rotation."""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import datetime
from math import inf

from caam_decision_models import ActiveAccount, EligibleProfiles, ProfileUsage, UsageRecord
from caam_decision_protection import (
    NO_PROTECTION_FLOORS,
    CandidatePolicy,
    can_serve_scoped_model,
    candidate_allowed,
    dimension_remaining,
    empty_release_note,
    floor_breach,
    is_eligible,
    protection_floor_for,
    raw_weekly_left,
    select_candidate_set,
    weekly_left,
)
from caam_rendering import (
    SwitchTargetSummary,
    current_cell,
    decision_dry_run,
    decision_forced,
    decision_hold_allowance,
    decision_hold_no_candidate,
    decision_hold_unsatisfiable_pin,
    decision_switched,
    decision_trigger,
    floor_breach_reason,
    fmt_duration,
    render_table,
    trigger_header,
    unsatisfiable_pin_reason,
    until,
)

__all__: list[str] = [
    "ActiveAccount",
    "EligibleProfiles",
    "ProfileUsage",
    "SwitchTargetSummary",
    "UsageRecord",
    "binding",
    "can_serve_scoped_model",
    "candidate_allowed",
    "current_cell",
    "decision_dry_run",
    "decision_forced",
    "decision_hold_allowance",
    "decision_hold_no_candidate",
    "decision_hold_unsatisfiable_pin",
    "decision_switched",
    "decision_trigger",
    "dimension_remaining",
    "eligible_profiles",
    "five_hour_remaining_floor",
    "five_hour_threshold",
    "floor_breach",
    "floor_breach_reason",
    "fmt_duration",
    "is_eligible",
    "min_headroom_gain",
    "rank_profiles",
    "render_table",
    "resets_at",
    "scoped_waiver_floor",
    "trigger_header",
    "triggered",
    "unsatisfiable_pin_reason",
    "until",
    "weekly_left",
    "weekly_reserve",
]


def binding(
    *,
    usage: UsageRecord,
    active_name: str | None = None,
    protection_floors: Mapping[str, float] = NO_PROTECTION_FLOORS,
) -> tuple[str, float, str]:
    protection_floor = protection_floor_for(name=active_name, protection_floors=protection_floors)
    if usage.five_hour_remaining <= five_hour_remaining_floor():
        return ("five_hour", usage.five_hour_remaining, "5-hour window")
    if protection_floor > 0 and raw_weekly_left(usage=usage) <= protection_floor:
        return (
            "seven_day",
            usage.seven_day_remaining,
            f"protection floor for {active_name} ({protection_floor:g}%)",
        )
    if weekly_left(usage=usage) < weekly_reserve():
        return ("seven_day", usage.seven_day_remaining, "weekly reserve")
    return ("five_hour", usage.five_hour_remaining, "5-hour window")


def triggered(
    *,
    usage: UsageRecord,
    active_name: str | None = None,
    protection_floors: Mapping[str, float] = NO_PROTECTION_FLOORS,
    scoped_pin: bool = False,
) -> bool:
    # The scoped leg sits ALONGSIDE the short-window threshold, the weekly
    # reserve and the protection floor rather than replacing any of them, and it
    # fires only while an operator pin names the scoped model: with no pin,
    # rotating on scoped exhaustion would be rotating in order to consume a
    # scoped allowance, which the same clause still forbids.
    protection_floor = protection_floor_for(name=active_name, protection_floors=protection_floors)
    return (
        usage.five_hour_remaining <= five_hour_remaining_floor()
        or weekly_left(usage=usage) < weekly_reserve()
        or (protection_floor > 0 and raw_weekly_left(usage=usage) <= protection_floor)
        or (scoped_pin and not can_serve_scoped_model(usage=usage))
    )


def scoped_waiver_floor(*, active: ActiveAccount) -> float | None:
    """The short-window balance a candidate must still have for the margin to be waived.

    The same bound the spent direction called a ceiling, read from the other end:
    "may have spent less than the rotation threshold" and "must still have more
    left than the rotation floor" name one line.

    None means no waiver, and it is the answer in the two cases the ratified
    clause draws a line between: no operator pin names the scoped model, or the
    ACTIVE account can still serve that pin. In the second case the pin is
    satisfiable where it already is, so no capability justifies relaxing a margin
    whose whole purpose is to make oscillation impossible.
    """
    if active.scoped_pin and not can_serve_scoped_model(usage=active.usage):
        return five_hour_remaining_floor()
    return None


def eligible_profiles(
    *,
    profiles: tuple[ProfileUsage, ...],
    active: ActiveAccount,
    force: bool,
    dimension: str,
    protection_floors: Mapping[str, float] = NO_PROTECTION_FLOORS,
) -> EligibleProfiles:
    reserve = weekly_reserve()

    def _select(*, enforce_reserve: bool) -> tuple[ProfileUsage, ...]:
        """The candidate set under one reserve stance, everything else held fixed.

        The two passes below differ in exactly that stance. Building both from
        one place is what keeps them from drifting apart -- a field added to the
        enforcing pass and forgotten on the releasing one would silently change
        who is admitted only once every account has fallen under the reserve,
        which is the least observed path in the whole selection.
        """
        return select_candidate_set(
            profiles=profiles,
            active_name=active.name,
            policy=CandidatePolicy(
                current=active.usage,
                gain_needed=0.01 if force else min_headroom_gain(),
                dimension=dimension,
                enforce_reserve=enforce_reserve,
                weekly_reserve=reserve,
                scoped_waiver_floor=scoped_waiver_floor(active=active),
                current_protection_floor=protection_floor_for(
                    name=active.name, protection_floors=protection_floors
                ),
            ),
            protection_floors=protection_floors,
        )

    eligible = _select(enforce_reserve=True)
    if eligible or not every_live_account_under_reserve(profiles=profiles):
        return EligibleProfiles(profiles=eligible, reserve_released=False, note=None)

    released = _select(enforce_reserve=False)
    if not released:
        return EligibleProfiles(
            profiles=(),
            reserve_released=False,
            note=empty_release_note(
                profiles=profiles,
                protection_floors=protection_floors,
                weekly_reserve=reserve,
                active_name=active.name,
            ),
        )
    note = empty_release_note(
        profiles=profiles,
        protection_floors=protection_floors,
        weekly_reserve=reserve,
        active_name=active.name,
    )
    return EligibleProfiles(profiles=released, reserve_released=bool(released), note=note)


def rank_profiles(
    *, profiles: tuple[ProfileUsage, ...], scoped_pin: bool = False
) -> tuple[ProfileUsage, ...]:
    # Serve-capability is a HIGHER-PRIORITY ordering than soonest weekly reset,
    # never a replacement for it: soonest reset remains the ordering among
    # candidates equal on that test. With no pin every candidate scores the same
    # on the leading key, and Python's stable sort leaves the pre-change order
    # byte-identical.
    return tuple(
        sorted(
            profiles,
            key=lambda profile: (
                0 if scoped_pin and can_serve_scoped_model(usage=profile.usage) else 1,
                resets_at(
                    timestamp=None if profile.usage is None else profile.usage.seven_day_resets_at
                ),
            ),
        )
    )


def resets_at(*, timestamp: str | None) -> float:
    if not timestamp:
        return inf
    normalized = timestamp.removesuffix("Z") + "+00:00" if timestamp.endswith("Z") else timestamp
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return inf
    return parsed.timestamp()


def five_hour_threshold() -> float:
    return float(os.environ.get("CAAM_ROTATE_FIVE_HOUR_THRESHOLD", "85"))


def five_hour_remaining_floor() -> float:
    """The short-window balance at or below which a pass rotates.

    THE BRIDGE, and the only complement left in the decision path. Every stored
    figure and every predicate now runs in the REMAINING direction, but the
    operator knob `CAAM_ROTATE_FIVE_HOUR_THRESHOLD` is still published as percent
    SPENT, so exactly one function turns it around and everything else -- the
    trigger, the binding allowance, the scoped waiver bound, the rendered trigger
    header -- compares against this. Its clean-break rename to a remaining-named
    knob is a change of its own; until that lands, this is where the two
    directions meet and the only place they are allowed to.
    """
    return 100.0 - five_hour_threshold()


def weekly_reserve() -> float:
    return float(os.environ.get("CAAM_ROTATE_WEEKLY_RESERVE", "10"))


def min_headroom_gain() -> float:
    return float(os.environ.get("CAAM_ROTATE_MIN_HEADROOM_GAIN", "10"))


def every_live_account_under_reserve(*, profiles: tuple[ProfileUsage, ...]) -> bool:
    live_usages = tuple(profile.usage for profile in profiles if profile.source == "live")
    return bool(live_usages) and all(
        usage is not None and weekly_left(usage=usage) < weekly_reserve() for usage in live_usages
    )
