"""The reason a pass could not use the released reserve must reach the operator.

Two defects, one deliverable. empty_release_note computed a perfectly good
explanation and its value was DISCARDED at the only production call site, so it
could never reach anyone. And its protected-floor branch was judged over every live
account -- the ACTIVE one included -- while the ratified clause is about every
remaining CANDIDATE, so the branch stayed silent in exactly the ordinary case where
an unprotected active account sits beside candidates that are all at their floors.

SPECIFICATION/spec.md: "Where every remaining candidate is protected and at or below
its floor, the operation MUST hold and MUST report which accounts are protected and
at what floor, rather than breaching a floor silently or stalling without a reason."
A report that cannot vary with the condition it reports does not satisfy that.
"""

from __future__ import annotations

from pathlib import Path

from caam_anthropic_decide import DecisionSeams, decide
from caam_decision import ProfileUsage, UsageRecord

_RESERVE = 10.0
_FLOOR = 10.0


def _usage(*, seven_day: float, five_hour: float = 40.0) -> UsageRecord:
    return UsageRecord(
        five_hour_remaining=100.0 - five_hour,
        seven_day_remaining=100.0 - seven_day,
        five_hour_resets_at=None,
        seven_day_resets_at=None,
        fable_remaining=None,
        fable_resets_at=None,
    )


class _Flags:
    force = False
    dry_run = False


class _Context:
    def __init__(self, *, home: Path) -> None:
        self.flags = _Flags()
        self.home = home
        self.now = 1_787_000_000.0
        self.state: dict[str, object] = {}
        self.state_path = home / "state.json"
        self.lines: list[str] = []

    def stdout(self, line: str) -> None:
        self.lines.append(line)


def _run(
    *,
    tmp_path: Path,
    profiles: tuple[ProfileUsage, ...],
    current: UsageRecord,
    protection_floors: dict[str, float],
    allow_switch: bool = False,
) -> list[str]:
    context = _Context(home=tmp_path)

    def _no_switch(**_: object) -> object:
        raise AssertionError("must not switch: this case must HOLD")

    decide(
        context=context,
        profiles=profiles,
        active_name="anthropic-a",
        current=current,
        protection_floors=protection_floors,
        seams=DecisionSeams(
            fetcher=lambda **_: (None, "not used"),
            save_state=lambda **_: None,
            switch_account=_no_switch if not allow_switch else (lambda **_: None),
        ),
    )
    return context.lines


def _all_under_reserve_with_protected_candidates() -> (
    tuple[tuple[ProfileUsage, ...], UsageRecord, dict[str, float]]
):
    """Active UNPROTECTED; every candidate protected and at its floor.

    Every live account is under the weekly reserve, so the reserve is released and
    the protected-floor branch is the one that must speak.
    """
    active = _usage(seven_day=95.0)
    profiles = (
        ProfileUsage(name="anthropic-a", source="live", usage=active),
        ProfileUsage(name="anthropic-b", source="live", usage=_usage(seven_day=92.0)),
        ProfileUsage(name="anthropic-c", source="live", usage=_usage(seven_day=93.0)),
    )
    floors = {"anthropic-b": _FLOOR, "anthropic-c": _FLOOR}
    return profiles, active, floors


def test_an_unprotected_active_beside_candidates_at_their_floors_is_reported(
    tmp_path: Path,
) -> None:
    """THE DISCRIMINATING LEG -- the case the shipped guard got wrong.

    Judged over every live account, the ACTIVE one is not protected, so the count
    never matches and the protected-floor branch stays silent. Judged over the
    CANDIDATES, which is what the ratified clause says, it fires. An implementation
    that only wires the value through without fixing the population passes every
    other test on this item and fails this one.
    """
    profiles, active, floors = _all_under_reserve_with_protected_candidates()
    lines = _run(tmp_path=tmp_path, profiles=profiles, current=active, protection_floors=floors)
    hold = next(line for line in lines if line.startswith("hold:"))
    assert "protected account floors reached" in hold
    assert "anthropic-b" in hold
    assert "anthropic-c" in hold
    assert "floor 10%" in hold
    # the active account is NOT protected, so it must not be named as one
    assert "anthropic-a at" not in hold


def test_the_reason_reaches_the_operator_at_all(tmp_path: Path) -> None:
    """The value was computed and discarded; a note that no one reads is not a report."""
    profiles, active, floors = _all_under_reserve_with_protected_candidates()
    lines = _run(tmp_path=tmp_path, profiles=profiles, current=active, protection_floors=floors)
    assert any("protected account floors reached" in line for line in lines)


def test_with_no_protection_configured_the_reserve_release_is_reported_instead(
    tmp_path: Path,
) -> None:
    """The OTHER branch is a distinct condition and must not be lost in the move."""
    profiles, active, _ = _all_under_reserve_with_protected_candidates()
    lines = _run(tmp_path=tmp_path, profiles=profiles, current=active, protection_floors={})
    hold = next(line for line in lines if line.startswith("hold:"))
    assert "weekly reserve" in hold
    assert "releasing it" in hold
    assert "protected account floors reached" not in hold


def test_the_hold_line_is_byte_identical_when_there_is_no_reason_to_give(
    tmp_path: Path,
) -> None:
    """No reserve release, no protection: the line must not grow a trailing clause.

    Candidates are above the reserve, so eligible_profiles returns early with no
    note at all -- the path that predates every reason added to this line.
    """
    active = _usage(seven_day=50.0, five_hour=95.0)
    profiles = (
        ProfileUsage(name="anthropic-a", source="live", usage=active),
        ProfileUsage(
            name="anthropic-b", source="live", usage=_usage(seven_day=48.0, five_hour=94.0)
        ),
    )
    lines = _run(tmp_path=tmp_path, profiles=profiles, current=active, protection_floors={})
    hold = next(line for line in lines if line.startswith("hold:"))
    assert hold == (
        "hold: the candidate set was empty -- none of the live-verified candidates "
        "(anthropic-b) clears the >=10.00 point five_hour headroom margin over "
        "anthropic-a within the weekly reserve"
    )
    assert ";" not in hold
