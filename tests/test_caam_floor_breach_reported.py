"""The hold path must name a breached protection floor, not just the margin.

The defect: when a protected active account is being spent below its floor and no
candidate clears the relative-headroom margin, the pass holds and the operator sees
a line naming only the MARGIN, offering three causes -- "all similarly spent,
exhausted, or unverifiable" -- none of which is "the active account is protected and
below its floor". The one condition protection exists to make visible was the one
the hold line could not express.

This began as the OBSERVABILITY repair alone, filed while the breach itself was
still open: triggering rotation did not stop the spend, because the margin gated
selection and nothing waived it for a protection trigger.

overseer-54k2za.43 has since CLOSED that breach, by measuring the active account's
headroom net of its own floor. So the configuration this file was written around --
a protected active at 91 beside an unprotected candidate at 82 -- now rotates, and
pinning a hold there would pin the defect back into place. The scenario below is
therefore one where a hold is still CORRECT: the only other account is protected
and sitting on its own floor, so nothing is eligible to move to and the pass must
stay put and say why. What is being tested is unchanged -- that the hold line names
a breached floor, and only when one is configured.
"""

from __future__ import annotations

from pathlib import Path

from caam_anthropic_decide import DecisionSeams, decide
from caam_decision import ProfileUsage, UsageRecord, floor_breach
from caam_rendering import decision_hold_no_candidate, floor_breach_reason

# At the shipped defaults (reserve 10, margin 10). Active A at seven_day 91 is on
# its floor and triggers. The only other account, B, is itself protected and on ITS
# floor, so it is disqualified as a candidate outright and clears the reserve on its
# raw balance -- which keeps the reserve unreleased and the hold line free of a
# release note. Nothing is eligible, so holding is the correct outcome rather than
# the breach it once was.
_ACTIVE_SEVEN_DAY = 91.0
_FLOOR = 10.0
_OTHER_SEVEN_DAY = 75.0
_OTHER_FLOOR = 30.0


def _usage(*, seven_day: float, five_hour: float = 40.0) -> UsageRecord:
    return UsageRecord(
        five_hour=five_hour,
        seven_day=seven_day,
        five_hour_resets_at=None,
        seven_day_resets_at=None,
        fable=None,
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


def _floors(*, protect_active: bool) -> dict[str, float]:
    """Protection configuration differing ONLY in whether the ACTIVE account has a floor.

    B keeps its floor in both, which is what holds the candidate set empty on both
    sides so the two hold lines remain comparable. Dropping B's floor as well would
    make B eligible and the pass would switch, comparing two different outcomes.
    """
    floors = {"anthropic-b": _OTHER_FLOOR}
    return {"anthropic-a": _FLOOR, **floors} if protect_active else floors


def _run(*, tmp_path: Path, protection_floors: dict[str, float]) -> list[str]:
    """Drive a real decide() pass into the no-candidate hold and return its output."""
    context = _Context(home=tmp_path)
    current = _usage(seven_day=_ACTIVE_SEVEN_DAY)
    profiles = (
        ProfileUsage(name="anthropic-a", source="live", usage=current),
        ProfileUsage(name="anthropic-b", source="live", usage=_usage(seven_day=_OTHER_SEVEN_DAY)),
    )
    code = decide(
        context=context,
        profiles=profiles,
        active_name="anthropic-a",
        current=current,
        protection_floors=protection_floors,
        seams=DecisionSeams(
            fetcher=lambda **_: (None, "not used on the hold path"),
            save_state=lambda **_: None,
            switch_account=lambda **_: (_ for _ in ()).throw(
                AssertionError("must not switch: this case must HOLD")
            ),
        ),
    )
    assert code == 0
    return context.lines


def test_the_hold_line_names_the_floor_that_was_just_crossed(tmp_path: Path) -> None:
    lines = _run(tmp_path=tmp_path, protection_floors=_floors(protect_active=True))
    hold = [line for line in lines if line.startswith("hold:")]
    assert len(hold) == 1
    # The operator must be able to see WHY it held, not merely that a margin was unmet.
    assert "PROTECTED" in hold[0]
    assert "past its floor" in hold[0]
    assert "floor 10%" in hold[0]
    assert "9% weekly left" in hold[0]


def test_with_no_floor_configured_the_hold_line_is_byte_identical(tmp_path: Path) -> None:
    """THE DISCRIMINATING LEG.

    An implementation that appends floor prose unconditionally passes the test above
    and must fail this one. Same inputs, same trigger, same empty candidate set --
    only the protection configuration differs.
    """
    protected = _run(tmp_path=tmp_path, protection_floors=_floors(protect_active=True))
    unprotected = _run(tmp_path=tmp_path, protection_floors=_floors(protect_active=False))

    protected_hold = next(line for line in protected if line.startswith("hold:"))
    unprotected_hold = next(line for line in unprotected if line.startswith("hold:"))

    assert unprotected_hold == decision_hold_no_candidate(
        gain_needed=10.0, dimension="seven_day", active_name="anthropic-a"
    )
    assert "PROTECTED" not in unprotected_hold
    assert "floor" not in unprotected_hold
    assert protected_hold != unprotected_hold
    assert protected_hold.startswith(unprotected_hold)


def test_the_pass_holds_because_nothing_is_eligible_to_move_to(tmp_path: Path) -> None:
    """Holding here is the correct outcome, not the breach this file once pinned.

    The switch seam raises if called, so reaching the end proves no switch occurred
    in either configuration. Since overseer-54k2za.43 the reason is that the only
    other account is on its own floor and cannot be moved to -- NOT that a protected
    active is being spent through its floor, which now rotates. The distinction
    matters: a hold with a candidate available would be the defect returning.
    """
    for protect_active in (True, False):
        lines = _run(tmp_path=tmp_path, protection_floors=_floors(protect_active=protect_active))
        assert any(line.startswith("hold:") for line in lines)
        assert not any("would switch" in line or "switched" in line for line in lines)


def test_floor_breach_reports_only_an_account_at_or_past_its_floor() -> None:
    at_floor = _usage(seven_day=_ACTIVE_SEVEN_DAY)
    assert floor_breach(usage=at_floor, protection_floor=_FLOOR) == (9.0, 10.0)
    # exactly AT the floor counts: 90 spent leaves 10, which the floor consumes whole
    assert floor_breach(usage=_usage(seven_day=90.0), protection_floor=_FLOOR) == (10.0, 10.0)
    # comfortably above it does not
    assert floor_breach(usage=_usage(seven_day=50.0), protection_floor=_FLOOR) is None
    # no floor configured is never a breach, whatever the spend
    assert floor_breach(usage=at_floor, protection_floor=0.0) is None
    # an unreadable account is not reported as a breach
    assert floor_breach(usage=None, protection_floor=_FLOOR) is None


def test_the_renderer_appends_nothing_when_given_no_breach() -> None:
    plain = decision_hold_no_candidate(
        gain_needed=10.0, dimension="five_hour", active_name="active"
    )
    assert plain == (
        "hold: no candidate has >=10.00 points more five_hour headroom than active "
        "(all similarly spent, exhausted, or unverifiable)"
    )
    assert (
        decision_hold_no_candidate(
            gain_needed=10.0,
            dimension="five_hour",
            active_name="active",
            reasons=(),
        )
        == plain
    )
    # a breach that is not a breach contributes no reason, so nothing is appended
    assert floor_breach_reason(active_name="active", breached_floor=None) is None
