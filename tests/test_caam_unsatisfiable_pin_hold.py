"""A pin no candidate can serve MUST hold and say so, not rotate to no purpose.

SPECIFICATION/spec.md, the scoped-model selection clause: "Where rotation is
triggered by scoped unsatisfiability alone and no candidate can serve the pinned
model, the operation MUST hold and MUST report that the pin cannot currently be
satisfied, rather than rotating to no purpose."

The trigger leg that makes this reachable landed with overseer-gt6ne5: an active
account that cannot serve the pinned model triggers rotation ON ITS OWN. Nothing
then asked whether any CANDIDATE could serve it, so the pass fell through to the
ordinary headroom comparison and could switch onto another account that also
cannot serve the pin -- which is the rotation to no purpose the clause forbids.

Both halves of the clause's condition are load-bearing and each has its own leg
below: the trigger's PROVENANCE (scoped unsatisfiability ALONE, so an account
that is also over its short-window threshold still rotates for that reason), and
the CANDIDATE SET's capability (a candidate that can serve the pin is still the
whole point of the gt6ne5 trigger and must still be switched to).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from caam_anthropic_decide import DecisionSeams, decide
from caam_decision import ProfileUsage, UsageRecord
from caam_foreman_override import SCOPED_MODEL

_SPENT = 100.0
_SERVES = 10.0


def _usage(*, seven_day: float, five_hour: float, fable: float | None = _SPENT) -> UsageRecord:
    return UsageRecord(
        five_hour=five_hour,
        seven_day=seven_day,
        five_hour_resets_at=None,
        seven_day_resets_at=None,
        fable=fable,
        fable_resets_at=None,
    )


@dataclass(frozen=True, kw_only=True)
class _SwitchResult:
    lines: tuple[str, ...]
    exit_code: int


class _Flags:
    def __init__(self, *, force: bool = False, dry_run: bool = False) -> None:
        self.force = force
        self.dry_run = dry_run


class _Context:
    def __init__(self, *, home: Path, pinned: bool, flags: _Flags) -> None:
        self.flags = flags
        self.home = home
        self.now = 1_787_000_000.0
        self.state: dict[str, object] = {"foreman_model": SCOPED_MODEL} if pinned else {}
        self.state_path = home / "state.json"
        self.lines: list[str] = []

    def stdout(self, line: str) -> None:
        self.lines.append(line)


class _Outcome:
    def __init__(self) -> None:
        self.switched_to: str | None = None
        self.lines: list[str] = []

    @property
    def held(self) -> bool:
        return self.switched_to is None

    def hold_line(self) -> str:
        return next(line for line in self.lines if line.startswith("hold:"))


def _run(
    *,
    tmp_path: Path,
    active: UsageRecord,
    candidates: tuple[ProfileUsage, ...],
    pinned: bool = True,
    force: bool = False,
) -> _Outcome:
    outcome = _Outcome()
    context = _Context(home=tmp_path, pinned=pinned, flags=_Flags(force=force))

    def _switch(*, request: object) -> _SwitchResult:
        outcome.switched_to = request.target.name  # type: ignore[attr-defined]
        return _SwitchResult(lines=("SWITCHED",), exit_code=0)

    decide(
        context=context,
        profiles=(ProfileUsage(name="anthropic-a", source="live", usage=active), *candidates),
        active_name="anthropic-a",
        current=active,
        protection_floors={},
        seams=DecisionSeams(
            fetcher=lambda **_: (None, "not used"),
            save_state=lambda **_: None,
            switch_account=_switch,
        ),
    )
    outcome.lines = context.lines
    return outcome


def _quiet_active(*, fable: float | None = _SPENT) -> UsageRecord:
    """An active account no OTHER trigger leg fires for.

    Short window well under the rotation threshold, weekly well above the
    reserve, no protection floor configured. So when this account cannot serve
    the pin, scoped unsatisfiability is the sole reason the pass is leaving.
    """
    return _usage(seven_day=50.0, five_hour=40.0, fable=fable)


def _candidate(*, name: str, five_hour: float, fable: float | None = _SPENT) -> ProfileUsage:
    return ProfileUsage(
        name=name,
        source="live",
        usage=_usage(seven_day=40.0, five_hour=five_hour, fable=fable),
    )


def test_a_scoped_alone_pass_holds_when_no_candidate_can_serve_the_pin(
    tmp_path: Path,
) -> None:
    """THE CLAUSE ITSELF. The candidate clears the margin and would be switched to.

    It cannot serve the pin either, so switching achieves nothing the pin needs
    and the pass must stay put and report why.
    """
    outcome = _run(
        tmp_path=tmp_path,
        active=_quiet_active(),
        candidates=(_candidate(name="anthropic-b", five_hour=20.0),),
    )
    assert outcome.held, f"must not rotate to no purpose; switched to {outcome.switched_to}"
    assert "cannot currently be satisfied" in outcome.hold_line()
    assert SCOPED_MODEL in outcome.hold_line()


def test_an_ordinary_trigger_still_rotates_even_though_the_pin_is_unsatisfiable(
    tmp_path: Path,
) -> None:
    """DISCRIMINATING LEG A -- the leg an implementation ignoring PROVENANCE fails.

    The short-window threshold fires here on its own, so scoped unsatisfiability
    is NOT the sole reason for leaving. Holding would strand the account for a
    reason the clause does not license, and the account would keep burning the
    very window it is over.
    """
    outcome = _run(
        tmp_path=tmp_path,
        active=_usage(seven_day=50.0, five_hour=90.0),
        candidates=(_candidate(name="anthropic-b", five_hour=20.0),),
    )
    assert outcome.switched_to == "anthropic-b"
    assert not any("cannot currently be satisfied" in line for line in outcome.lines)


def test_a_scoped_alone_pass_still_switches_to_a_candidate_that_can_serve_the_pin(
    tmp_path: Path,
) -> None:
    """DISCRIMINATING LEG B -- the new branch must not swallow what gt6ne5 enabled.

    A candidate that CAN serve the pin is the entire reason the scoped trigger
    exists. The hold applies only where no candidate can serve it.
    """
    outcome = _run(
        tmp_path=tmp_path,
        active=_quiet_active(),
        candidates=(
            _candidate(name="anthropic-b", five_hour=20.0),
            _candidate(name="anthropic-c", five_hour=20.0, fable=_SERVES),
        ),
    )
    assert outcome.switched_to == "anthropic-c"


def test_the_reason_composes_onto_the_no_candidate_hold_rather_than_replacing_it(
    tmp_path: Path,
) -> None:
    """The two hold causes COMPOSE. Neither line may swallow the other's cause.

    Here no candidate clears the margin at all, so the pass was already holding.
    It must keep saying so AND gain the pin reason -- one line, both causes.
    """
    outcome = _run(
        tmp_path=tmp_path,
        active=_quiet_active(),
        candidates=(_candidate(name="anthropic-b", five_hour=45.0),),
    )
    assert outcome.held
    hold = outcome.hold_line()
    assert hold.startswith("hold: no candidate has")
    assert "cannot currently be satisfied" in hold


def test_a_forced_pass_rotates_because_force_is_a_reason_of_its_own(
    tmp_path: Path,
) -> None:
    """--force is the operator saying to move now; it is not scoped unsatisfiability."""
    outcome = _run(
        tmp_path=tmp_path,
        active=_quiet_active(),
        candidates=(_candidate(name="anthropic-b", five_hour=20.0),),
        force=True,
    )
    assert outcome.switched_to == "anthropic-b"


def test_with_no_pin_in_effect_an_exhausted_scoped_allowance_changes_nothing(
    tmp_path: Path,
) -> None:
    """LEG 4. With no operator pin the scoped allowance MUST NOT reach selection.

    Same accounts as the ordinary-trigger leg above, pin removed: the pass must
    rotate exactly as it always did and must not mention the pin at all.
    """
    outcome = _run(
        tmp_path=tmp_path,
        active=_usage(seven_day=50.0, five_hour=90.0),
        candidates=(_candidate(name="anthropic-b", five_hour=20.0),),
        pinned=False,
    )
    assert outcome.switched_to == "anthropic-b"
    assert not any("pin" in line for line in outcome.lines)


def test_with_no_pin_in_effect_a_quiet_account_still_holds_on_its_allowance(
    tmp_path: Path,
) -> None:
    """The untriggered hold line must not grow a clause it never had."""
    outcome = _run(
        tmp_path=tmp_path,
        active=_quiet_active(),
        candidates=(_candidate(name="anthropic-b", five_hour=20.0),),
        pinned=False,
    )
    assert outcome.held
    hold = outcome.hold_line()
    assert hold.startswith("hold: 5-hour window is the binding allowance")
    assert ";" not in hold
