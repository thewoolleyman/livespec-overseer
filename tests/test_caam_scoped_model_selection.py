"""The scoped-model allowance in rotation target selection (SPECIFICATION v036).

The clause this pins is narrow, and the narrowing is the point. A scoped-model
allowance still MUST NOT influence selection as capacity; it influences selection
only WHILE AN OPERATOR PIN NAMES IT, and only in the three ways below. Every
figure here is a SPENT percentage, matching what the durable state stores: a
scoped value of 100.0 is ZERO remaining, and the five-hour floor written as
"below the rotation threshold" means `five_hour < 85` spent. A reader who assumes
remaining inverts the floor and selects exactly the nearly-spent accounts it
exists to exclude.
"""

from __future__ import annotations

import caam_decision_protection as protection
import pytest
from caam_decision import (
    ActiveAccount,
    ProfileUsage,
    UsageRecord,
    binding,
    can_serve_scoped_model,
    eligible_profiles,
    rank_profiles,
    triggered,
)
from caam_foreman_override import apply_foreman_model_override, scoped_model_pinned

__all__: list[str] = []

_SOON = "2026-08-22T12:00:00Z"
_LATER = "2026-08-24T12:00:00Z"


def usage(
    *,
    five_hour: float,
    seven_day: float = 20.0,
    scoped: float | None = 0.0,
    seven_day_resets_at: str = _SOON,
) -> UsageRecord:
    """A usage record in the stored SPENT convention; `scoped` is the Fable allowance."""
    return UsageRecord(
        five_hour_remaining=100.0 - five_hour,
        seven_day_remaining=100.0 - seven_day,
        five_hour_resets_at="2026-08-21T12:00:00Z",
        seven_day_resets_at=seven_day_resets_at,
        fable_remaining=None if scoped is None else 100.0 - scoped,
        fable_resets_at="2026-08-23T12:00:00Z",
    )


def live(*, name: str, record: UsageRecord | None) -> ProfileUsage:
    return ProfileUsage(name=name, source="live", usage=record)


def selected(
    *,
    profiles: tuple[ProfileUsage, ...],
    active: ActiveAccount,
    dimension: str = "five_hour",
) -> list[str]:
    return [
        profile.name
        for profile in eligible_profiles(
            profiles=profiles,
            active=active,
            force=False,
            dimension=dimension,
        ).profiles
    ]


# ---------------------------------------------------------------------------
# LEG 1 -- the trigger.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scoped", [100.0, None])
def test_an_active_that_cannot_serve_the_pinned_model_triggers_rotation_on_its_own(
    *, scoped: float | None
):
    """Fully spent AND absent altogether both count as "cannot serve"."""
    active = usage(five_hour=40.0, scoped=scoped)

    assert not triggered(usage=active)
    assert triggered(usage=active, scoped_pin=True)


def test_the_scoped_trigger_sits_alongside_the_thresholds_it_does_not_replace():
    unsatisfiable = usage(five_hour=40.0, scoped=100.0)
    short_window = usage(five_hour=90.0, scoped=0.0)
    weekly = usage(five_hour=40.0, seven_day=95.0, scoped=0.0)
    floors = {"active": 12.0}

    assert triggered(usage=unsatisfiable, scoped_pin=True)
    assert triggered(usage=short_window, scoped_pin=True)
    assert triggered(usage=weekly, scoped_pin=True)
    assert triggered(
        usage=usage(five_hour=40.0, seven_day=89.0, scoped=0.0),
        active_name="active",
        protection_floors=floors,
        scoped_pin=True,
    )


def test_an_active_that_can_still_serve_the_pinned_model_does_not_trigger_on_scoped_grounds():
    assert not triggered(usage=usage(five_hour=40.0, scoped=20.0), scoped_pin=True)


# ---------------------------------------------------------------------------
# LEG 2 -- eligibility, bounded. The measured 2026-08-26T08:17Z selection.
# ---------------------------------------------------------------------------


def test_a_candidate_that_can_serve_the_pin_is_selected_without_clearing_the_margin():
    """The active holds ZERO scoped allowance; the candidate carries some and is above the floor.

    The candidate is deliberately WORSE off on five-hour headroom than the active
    (60 spent against 40), so nothing about the relative-headroom margin admits
    it. Only the scoped waiver can, and only while the pin is in effect.
    """
    active = usage(five_hour=40.0, scoped=100.0)
    candidate = live(name="candidate", record=usage(five_hour=60.0, scoped=10.0))

    assert selected(
        profiles=(candidate,),
        active=ActiveAccount(name="active", usage=active, scoped_pin=True),
    ) == ["candidate"]


# ---------------------------------------------------------------------------
# LEG 3 -- the converse. Where the active CAN serve the pin, the margin is unwaived.
# ---------------------------------------------------------------------------


def test_the_margin_applies_unwaived_where_the_active_can_still_serve_the_pin():
    """The same candidate that wins under the waiver loses when the pin is satisfiable.

    Without this the waiver would be available on ANY trigger while a pin exists,
    which review demonstrated as a two-account ping-pong: each account can serve
    the pin, so each is admissible onto the other with no strict improvement, and
    the margin's anti-oscillation guarantee is gone in the ordinary steady state.
    """
    candidate = live(name="candidate", record=usage(five_hour=60.0, scoped=10.0))
    cannot_serve = ActiveAccount(
        name="active", usage=usage(five_hour=40.0, scoped=100.0), scoped_pin=True
    )
    can_serve = ActiveAccount(
        name="active", usage=usage(five_hour=40.0, scoped=30.0), scoped_pin=True
    )

    assert selected(profiles=(candidate,), active=cannot_serve) == ["candidate"]
    assert selected(profiles=(candidate,), active=can_serve) == []


# ---------------------------------------------------------------------------
# LEG 4 -- the pin gate. The discriminating control for the whole narrowing.
# ---------------------------------------------------------------------------


def test_with_no_pin_in_effect_the_scoped_allowance_selects_nothing():
    """An implementation that ignores the pin condition passes LEGS 1 and 2 and fails here.

    A suite without this leg cannot tell the ratified rule from the rejected
    unconditioned form, in which scoped exhaustion alone rotates -- which IS
    rotating in order to consume a scoped allowance, still forbidden.
    """
    active = usage(five_hour=40.0, scoped=100.0)
    candidate = live(name="candidate", record=usage(five_hour=60.0, scoped=10.0))
    unpinned = ActiveAccount(name="active", usage=active)

    assert not triggered(usage=active)
    assert selected(profiles=(candidate,), active=unpinned) == []


def test_with_no_pin_in_effect_ranking_stays_on_soonest_weekly_reset_alone():
    spent_but_soonest = live(
        name="soonest", record=usage(five_hour=10.0, scoped=100.0, seven_day_resets_at=_SOON)
    )
    scoped_but_later = live(
        name="later", record=usage(five_hour=10.0, scoped=0.0, seven_day_resets_at=_LATER)
    )
    profiles = (spent_but_soonest, scoped_but_later)

    assert [profile.name for profile in rank_profiles(profiles=profiles)] == ["soonest", "later"]
    assert [profile.name for profile in rank_profiles(profiles=profiles, scoped_pin=True)] == [
        "later",
        "soonest",
    ]


# ---------------------------------------------------------------------------
# LEG 5 -- no scoped comparison dimension.
# ---------------------------------------------------------------------------


def test_no_scoped_dimension_ever_reaches_the_comparison_helpers(*, monkeypatch):
    """`dimension_remaining` answers negative infinity outside five_hour/seven_day and
    `is_eligible` gates on that same set, so a "scoped" dimension would make EVERY candidate
    ineligible -- rotation frozen, the exact opposite of this rule's purpose. An earlier spec
    draft specified it before review caught it, so the absence is pinned rather than assumed.
    """
    seen: list[str] = []
    real_dimension_remaining = protection.dimension_remaining
    real_is_eligible = protection.is_eligible

    def recording_dimension_remaining(
        *, usage: UsageRecord, dimension: str, protection_floor: float = 0.0
    ) -> float:
        seen.append(dimension)
        return real_dimension_remaining(
            usage=usage, dimension=dimension, protection_floor=protection_floor
        )

    def recording_is_eligible(**kwargs: object) -> bool:
        seen.append(str(kwargs["dimension"]))
        return real_is_eligible(**kwargs)  # pyright: ignore[reportArgumentType]

    monkeypatch.setattr(protection, "dimension_remaining", recording_dimension_remaining)
    monkeypatch.setattr(protection, "is_eligible", recording_is_eligible)

    active = usage(five_hour=40.0, scoped=100.0)
    dimension, _remaining, _label = binding(usage=active)
    assert dimension == "five_hour"

    assert selected(
        profiles=(live(name="candidate", record=usage(five_hour=60.0, scoped=10.0)),),
        active=ActiveAccount(name="active", usage=active, scoped_pin=True),
        dimension=dimension,
    ) == ["candidate"]

    assert seen
    assert set(seen) == {"five_hour"}


# ---------------------------------------------------------------------------
# LEG 6 -- the floor.
# ---------------------------------------------------------------------------


def test_a_scoped_rich_candidate_below_the_rotation_threshold_does_not_win():
    """92 spent is past the 85 threshold, so this account would trigger the moment it arrived.

    Without the floor the rule silently becomes "scoped availability always wins"
    and reintroduces exactly the flapping the threshold reuse was chosen to avoid.
    Selection falls back to the ordinary headroom comparison, which here picks the
    roomy account even though it cannot serve the pin at all.
    """
    active = ActiveAccount(
        name="active", usage=usage(five_hour=40.0, scoped=100.0), scoped_pin=True
    )
    nearly_spent = live(name="nearly-spent", record=usage(five_hour=92.0, scoped=0.0))
    roomy = live(name="roomy", record=usage(five_hour=10.0, scoped=100.0))

    assert selected(profiles=(nearly_spent,), active=active) == []
    assert selected(profiles=(nearly_spent, roomy), active=active) == ["roomy"]


# ---------------------------------------------------------------------------
# LEG 7 -- preserved exclusions.
# ---------------------------------------------------------------------------


def test_the_weekly_reserve_still_excludes_a_scoped_rich_candidate():
    active = ActiveAccount(
        name="active", usage=usage(five_hour=40.0, scoped=100.0), scoped_pin=True
    )
    below_reserve = live(name="below", record=usage(five_hour=50.0, seven_day=95.0, scoped=0.0))
    roomy = live(name="roomy", record=usage(five_hour=10.0, scoped=100.0))

    assert selected(profiles=(below_reserve, roomy), active=active) == ["roomy"]


def test_the_zero_weekly_disqualifier_still_excludes_a_scoped_rich_candidate():
    """Even on the released path, where the reserve protects nothing, zero weekly excludes."""
    active = ActiveAccount(
        name="active", usage=usage(five_hour=40.0, seven_day=95.0, scoped=100.0), scoped_pin=True
    )
    exhausted = live(name="exhausted", record=usage(five_hour=50.0, seven_day=100.0, scoped=0.0))

    assert selected(profiles=(exhausted,), active=active) == []


def test_a_candidate_that_is_not_live_verified_is_never_selected_on_scoped_grounds():
    active = ActiveAccount(
        name="active", usage=usage(five_hour=40.0, scoped=100.0), scoped_pin=True
    )
    cached = ProfileUsage(
        name="cached", source="cached 2.0h", usage=usage(five_hour=50.0, scoped=0.0)
    )

    assert selected(profiles=(cached,), active=active) == []


def test_a_per_account_protection_floor_still_excludes_a_scoped_rich_candidate():
    active = ActiveAccount(
        name="active", usage=usage(five_hour=40.0, scoped=100.0), scoped_pin=True
    )
    at_its_floor = live(name="protected", record=usage(five_hour=50.0, seven_day=90.0, scoped=0.0))

    assert (
        eligible_profiles(
            profiles=(at_its_floor,),
            active=active,
            force=False,
            dimension="five_hour",
            protection_floors={"protected": 10.0},
        ).profiles
        == ()
    )


# ---------------------------------------------------------------------------
# LEG 8 -- ranking fail-closed.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "record"),
    [
        ("unreadable", usage(five_hour=10.0, scoped=None, seven_day_resets_at=_SOON)),
        ("no-usage", None),
        ("spent", usage(five_hour=10.0, scoped=100.0, seven_day_resets_at=_SOON)),
    ],
)
def test_ranking_treats_an_unreadable_scoped_allowance_as_unable_to_serve(
    *, name: str, record: UsageRecord | None
):
    """Each of these sorts BEHIND a server despite holding the soonest weekly reset."""
    cannot_serve = live(name=name, record=record)
    server = live(
        name="server", record=usage(five_hour=10.0, scoped=0.0, seven_day_resets_at=_LATER)
    )

    assert [
        profile.name for profile in rank_profiles(profiles=(cannot_serve, server), scoped_pin=True)
    ] == ["server", name]


def test_soonest_weekly_reset_remains_the_ordering_among_candidates_equal_on_serve_capability():
    soonest = live(
        name="soonest", record=usage(five_hour=10.0, scoped=5.0, seven_day_resets_at=_SOON)
    )
    later = live(name="later", record=usage(five_hour=10.0, scoped=5.0, seven_day_resets_at=_LATER))

    assert [
        profile.name for profile in rank_profiles(profiles=(later, soonest), scoped_pin=True)
    ] == ["soonest", "later"]


# ---------------------------------------------------------------------------
# The predicate and the pin surface.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("record", "expected"),
    [
        (usage(five_hour=10.0, scoped=0.0), True),
        (usage(five_hour=10.0, scoped=99.9), True),
        (usage(five_hour=10.0, scoped=100.0), False),
        (usage(five_hour=10.0, scoped=None), False),
        (None, False),
    ],
)
def test_serve_capability_is_read_from_the_scoped_balance_alone(
    *, record: UsageRecord | None, expected: bool
):
    assert can_serve_scoped_model(usage=record) is expected


def test_only_a_pin_naming_the_scoped_model_puts_the_clause_in_effect():
    """The general-model pin is an operator pin too, and it does NOT arm this clause."""
    state: dict[str, object] = {}

    assert not scoped_model_pinned(state=state)

    _ = apply_foreman_model_override(
        state=state, requested_model="opus", default_model="opus", fable_left=False
    )
    assert not scoped_model_pinned(state=state)

    _ = apply_foreman_model_override(
        state=state, requested_model="fable", default_model="opus", fable_left=False
    )
    assert scoped_model_pinned(state=state)

    _ = apply_foreman_model_override(
        state=state, requested_model="auto", default_model="opus", fable_left=False
    )
    assert not scoped_model_pinned(state=state)


# ---------------------------------------------------------------------------
# A PER-SESSION pin arms the same clause as the global pin (SPEC v040).
# ---------------------------------------------------------------------------


def test_a_per_session_pin_naming_the_scoped_model_arms_the_clause():
    """A `session_models` entry equal to the scoped model is an operator pin too."""
    state: dict[str, object] = {"session_models": {"livespec-overseer-foreman": "fable"}}

    assert scoped_model_pinned(state=state)


def test_a_per_session_pin_arms_the_clause_even_when_the_global_pin_is_not_scoped():
    """The per-session pin arms selection though `foreman_model` is opus, not fable."""
    state: dict[str, object] = {
        "foreman_model": "opus",
        "session_models": {"homelab-foreman": "fable"},
    }

    assert scoped_model_pinned(state=state)


def test_a_per_session_pin_naming_the_general_model_does_not_arm_the_clause():
    """A per-session opus pin is an operator pin, but it does NOT arm this clause."""
    state: dict[str, object] = {"session_models": {"livespec-overseer-foreman": "opus"}}

    assert not scoped_model_pinned(state=state)


def test_a_per_session_scoped_pin_under_the_legacy_state_key_also_arms_the_clause():
    """State not yet migrated off the legacy `session-models` key still arms selection."""
    state: dict[str, object] = {"session-models": {"livespec-overseer-foreman": "fable"}}

    assert scoped_model_pinned(state=state)


def test_with_neither_a_global_nor_a_per_session_scoped_pin_the_clause_stays_off():
    """The global-only path is unchanged: no pin of either kind leaves selection unarmed."""
    assert not scoped_model_pinned(state={})
    assert not scoped_model_pinned(state={"session_models": {}})
    assert not scoped_model_pinned(
        state={"foreman_model": "opus", "session_models": {"a-foreman": "opus"}}
    )


def test_a_per_session_fable_pin_does_not_breach_a_protected_floor():
    """The per-session pin waives the relative-headroom margin only, never a protection floor."""
    state: dict[str, object] = {"session_models": {"livespec-overseer-foreman": "fable"}}
    scoped_pin = scoped_model_pinned(state=state)
    active = ActiveAccount(
        name="active", usage=usage(five_hour=40.0, scoped=100.0), scoped_pin=scoped_pin
    )
    at_its_floor = live(name="protected", record=usage(five_hour=50.0, seven_day=90.0, scoped=0.0))

    assert (
        eligible_profiles(
            profiles=(at_its_floor,),
            active=active,
            force=False,
            dimension="five_hour",
            protection_floors={"protected": 10.0},
        ).profiles
        == ()
    )
