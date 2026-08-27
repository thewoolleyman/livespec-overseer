"""A protected account's usable headroom is measured net of its floor in BOTH roles.

SPECIFICATION/spec.md:1518: "A protected account's usable headroom MUST be measured
net of its floor... A protected account MUST NOT be selected while any unprotected
account is eligible: protection is an ordering over which accounts are spent, not
merely a limit on how far. Where the active account is itself protected and has
reached its floor, that MUST trigger rotation on its own."

`is_eligible` has always accepted `current_protection_floor` and no caller ever
supplied it, so the ACTIVE account's floor did not participate in the comparison.
A protected active at 91 with a floor of 10 was judged as though its last 9 points
were spendable, an unprotected candidate at 82 missed the margin by one point, and
the pass held while the protected account was spent through its floor -- the breach
the v037 ratification record accepted the feature despite.

Wiring it does more than close that case, and the extra is the point rather than a
side effect: it makes each side of the comparison measure headroom net of the floor
that side is actually subject to. That symmetry is what forbids oscillation, and it
is pinned directly below rather than inferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from caam_anthropic_decide import DecisionSeams, decide
from caam_decision import ProfileUsage, UsageRecord, is_eligible

_RESERVE = 10.0
_MARGIN = 10.0


def _usage(*, seven_day: float, five_hour: float = 40.0) -> UsageRecord:
    return UsageRecord(
        five_hour=five_hour,
        seven_day=seven_day,
        five_hour_resets_at=None,
        seven_day_resets_at=None,
        fable=None,
        fable_resets_at=None,
    )


@dataclass(frozen=True, kw_only=True)
class _SwitchResult:
    lines: tuple[str, ...]
    exit_code: int
    # Mirrors the real SwitchResult: the decision path reads this to decide
    # whether a switch actually moved the credential. These fakes stand in for
    # one that did, so they report it.
    switched: bool = True


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


def _pass(
    *,
    tmp_path: Path,
    profiles: tuple[ProfileUsage, ...],
    active_name: str,
    protection_floors: dict[str, float],
) -> str | None:
    """Run one rotation pass; return the account switched to, or None if it held."""
    switched: list[str] = []
    context = _Context(home=tmp_path)

    def _switch(*, request: object) -> _SwitchResult:
        switched.append(request.target.name)  # type: ignore[attr-defined]
        return _SwitchResult(lines=("SWITCHED",), exit_code=0)

    current = next(p.usage for p in profiles if p.name == active_name)
    assert current is not None
    decide(
        context=context,
        profiles=profiles,
        active_name=active_name,
        current=current,
        protection_floors=protection_floors,
        seams=DecisionSeams(
            fetcher=lambda **_: (None, "not used"),
            save_state=lambda **_: None,
            switch_account=_switch,
        ),
    )
    return switched[0] if switched else None


def _profile(*, name: str, seven_day: float, five_hour: float = 40.0) -> ProfileUsage:
    return ProfileUsage(
        name=name, source="live", usage=_usage(seven_day=seven_day, five_hour=five_hour)
    )


def test_the_v037_breach_case_now_rotates_instead_of_spending_through_the_floor(
    tmp_path: Path,
) -> None:
    """THE RECORDED BREACH, end to end, on the shipped constants.

    Protected active at 91 with a floor of 10 has nothing left it may spend. The
    unprotected candidate at 82 misses the undiscounted margin by a single point,
    which is why the pass used to hold and keep spending the protected account.
    """
    profiles = (
        _profile(name="anthropic-a", seven_day=91.0),
        _profile(name="anthropic-b", seven_day=82.0),
    )
    switched = _pass(
        tmp_path=tmp_path,
        profiles=profiles,
        active_name="anthropic-a",
        protection_floors={"anthropic-a": _RESERVE},
    )
    assert switched == "anthropic-b", "must leave a protected account at its floor"


def test_a_second_pass_does_not_rotate_back_onto_the_account_it_just_left(
    tmp_path: Path,
) -> None:
    """NON-OSCILLATION, run as successive passes rather than argued.

    The second pass is genuinely triggered -- the new active is over the
    short-window threshold -- so the eligibility comparison really does run, and
    on the short-window dimension the account just vacated looks far cheaper.
    What holds the pass is that a protected account AT its floor has no usable
    headroom at all and is disqualified as a candidate outright.

    That mechanism is load-bearing rather than incidental: removing the
    `weekly_left(...) > 0` disqualifier makes this test rotate straight back onto
    an account that is already below its floor.
    """
    floors = {"anthropic-a": 20.0}
    first = _pass(
        tmp_path=tmp_path,
        profiles=(
            _profile(name="anthropic-a", seven_day=85.0),
            _profile(name="anthropic-b", seven_day=70.0),
        ),
        active_name="anthropic-a",
        protection_floors=floors,
    )
    assert first == "anthropic-b"

    back = _pass(
        tmp_path=tmp_path,
        profiles=(
            _profile(name="anthropic-a", seven_day=85.0),
            _profile(name="anthropic-b", seven_day=70.0, five_hour=90.0),
        ),
        active_name="anthropic-b",
        protection_floors=floors,
    )
    assert back is None, f"rotated back onto a protected account at its floor: {back}"


def test_the_margin_cannot_be_cleared_in_both_directions_at_once(tmp_path: Path) -> None:
    """THE PROPERTY THAT FORBIDS OSCILLATION, stated where it can actually fail.

    Two accounts equally spent, each protected with the same floor, is the shape
    that separates a symmetric comparison from an asymmetric one. Measured net of
    each account's own floor they are identical and neither clears the margin.
    Discount only the ACTIVE side -- the plausible half-wiring of this change --
    and each account appears a full floor's worth better than the other, so the
    pass would switch on every tick forever.

    This is a predicate-level test on purpose. Both accounts sit above their
    floors and below the thresholds, so no pass would be triggered to carry it,
    and a test routed through `decide` would hold for a reason that has nothing
    to do with the property being asserted.
    """
    del tmp_path
    a, b = _usage(seven_day=50.0), _usage(seven_day=50.0)
    floor = 40.0

    def clears(*, candidate: UsageRecord, active: UsageRecord) -> bool:
        return is_eligible(
            usage=candidate,
            current=active,
            gain_needed=_MARGIN,
            dimension="seven_day",
            protection_floor=floor,
            current_protection_floor=floor,
        )

    assert not (clears(candidate=b, active=a) and clears(candidate=a, active=b))
    assert not clears(candidate=b, active=a)


def test_an_unprotected_active_is_not_discounted_by_so_much_as_a_point(
    tmp_path: Path,
) -> None:
    """THE DISCRIMINATING LEG. The discount must apply only where a floor exists.

    This pass is triggered by the weekly reserve, and its candidate sits eight
    points ahead -- inside the ten-point margin, so it must be refused. Any
    discount leaking onto an unprotected active flips this to a switch, which is
    what makes the leg able to fail rather than merely able to pass.
    """
    switched = _pass(
        tmp_path=tmp_path,
        profiles=(
            _profile(name="anthropic-a", seven_day=92.0),
            _profile(name="anthropic-b", seven_day=84.0),
        ),
        active_name="anthropic-a",
        protection_floors={},
    )
    assert switched is None, "an unprotected active gets no floor it does not have"
