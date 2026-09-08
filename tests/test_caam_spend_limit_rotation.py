"""The 2026-09-08 pay-as-you-go spend-limit incident, reproduced through ``decide()``.

INCIDENT (work-item overseer-t04c). Every fleet session refused with "You've hit
your monthly spend limit" while the account-rotation table showed healthy
subscription percentages on the active account. The rotator was blind to the
DOLLAR meter: `/api/oauth/usage` reports `extra_usage.spend_limit_reached`
alongside the percentages, and the pass parsed the percentages and discarded the
meter. So caam rotated the whole interactive fleet onto an account that had hit
its OWN per-account dollar cap, and then could neither see it nor route around
it -- while three accounts that had never enabled extra usage at all still had
included quota to serve from.

An account at its extra-usage spend limit has exhausted its included quota AND
the paid path that was standing in for it, so it cannot serve a request
immediately -- which is the ratified selection clause this conformance sits
under. It is therefore disqualified as a candidate, and triggers rotation when
it is the account in use.

Every scenario here is written in the REMAINING direction the records store.
"""

from __future__ import annotations

import importlib
from pathlib import Path

from caam_anthropic_decide import DecisionSeams, decide
from caam_decision import ProfileUsage, UsageRecord

__all__: list[str] = []


CAPPED_BLOCK: dict[str, object] = {
    "is_enabled": False,
    "spend_limit_reached": True,
    "monthly_limit": 100.0,
    "used_credits": 107.37,
}
NEVER_ENABLED_BLOCK: dict[str, object] = {
    "is_enabled": False,
    "spend_limit_reached": False,
    "monthly_limit": None,
    "used_credits": None,
}

_SOON = "2026-09-09T00:00:00Z"
_LATER = "2026-09-12T00:00:00Z"


def meter(*, block: dict[str, object] | None) -> object:
    """A parsed dollar meter, gated on the reader module existing at all."""
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "caam_extra_usage.py"
    assert module_path.is_file()
    module = importlib.import_module("caam_extra_usage")
    body: dict[str, object] = {} if block is None else {"extra_usage": block}
    return module.extra_usage_from(body=body)


def usage(
    *,
    five_hour: float,
    seven_day: float,
    weekly_reset: str = _LATER,
    block: dict[str, object] | None = None,
) -> UsageRecord:
    return UsageRecord(
        five_hour_remaining=five_hour,
        seven_day_remaining=seven_day,
        five_hour_resets_at="2026-09-08T14:00:00Z",
        seven_day_resets_at=weekly_reset,
        fable_remaining=None,
        fable_resets_at=None,
        extra_usage=meter(block=block),
    )


class Flags:
    def __init__(self) -> None:
        self.force = False
        self.dry_run = False


class Context:
    def __init__(self, *, home: Path) -> None:
        self.flags = Flags()
        self.home = home
        self.now = 1_788_000_000.0
        self.state: dict[str, object] = {}
        self.state_path = home / "state.json"
        self.lines: list[str] = []

    def stdout(self, line: str) -> None:
        self.lines.append(line)


class SwitchResult:
    def __init__(self) -> None:
        self.lines = ("SWITCHED",)
        self.exit_code = 0
        self.switched = True
        self.reason = "test"


class Outcome:
    def __init__(self) -> None:
        self.switched_to: str | None = None
        self.lines: list[str] = []

    @property
    def held(self) -> bool:
        return self.switched_to is None


def run(*, tmp_path: Path, active: UsageRecord, candidates: tuple[ProfileUsage, ...]) -> Outcome:
    outcome = Outcome()
    context = Context(home=tmp_path)

    def switch(*, request: object) -> SwitchResult:
        outcome.switched_to = request.target.name  # type: ignore[attr-defined]
        return SwitchResult()

    decide(
        context=context,
        profiles=(ProfileUsage(name="active", source="live", usage=active), *candidates),
        active_name="active",
        current=active,
        protection_floors={},
        seams=DecisionSeams(
            fetcher=lambda **_: (None, "not used"),
            save_state=lambda **_: None,
            switch_account=switch,
        ),
    )
    outcome.lines = context.lines
    return outcome


def candidate(
    *,
    name: str,
    five_hour: float = 90.0,
    seven_day: float = 90.0,
    weekly_reset: str = _LATER,
    block: dict[str, object] | None = None,
) -> ProfileUsage:
    return ProfileUsage(
        name=name,
        source="live",
        usage=usage(
            five_hour=five_hour, seven_day=seven_day, weekly_reset=weekly_reset, block=block
        ),
    )


# ---------------------------------------------------------------------------
# (a) A spend-capped account is not selected while an included-quota one exists.
# ---------------------------------------------------------------------------


def test_a_spend_capped_candidate_is_never_selected_over_an_included_quota_account(
    tmp_path: Path,
) -> None:
    """The capped account WINS every ordinary test and must still lose.

    It has more short-window headroom and the sooner weekly reset, so both the
    margin and the ranking point at it. It cannot serve a request, so it is out.
    """
    outcome = run(
        tmp_path=tmp_path,
        active=usage(five_hour=5.0, seven_day=60.0),
        candidates=(
            candidate(name="capped", five_hour=99.0, weekly_reset=_SOON, block=CAPPED_BLOCK),
            candidate(name="included", five_hour=70.0, weekly_reset=_LATER),
        ),
    )

    assert outcome.switched_to == "included", (
        "a spend-capped account cannot serve a request and must never be selected "
        f"while an included-quota account exists; switched_to={outcome.switched_to}"
    )


def test_a_pass_whose_only_candidate_is_spend_capped_holds_rather_than_spilling(
    tmp_path: Path,
) -> None:
    outcome = run(
        tmp_path=tmp_path,
        active=usage(five_hour=5.0, seven_day=60.0),
        candidates=(candidate(name="capped", weekly_reset=_SOON, block=CAPPED_BLOCK),),
    )

    assert outcome.held


# ---------------------------------------------------------------------------
# (b) A spend_limit_reached ACTIVE account triggers rotation to a clean one.
# ---------------------------------------------------------------------------


def test_a_spend_capped_active_account_rotates_to_an_included_quota_account(
    tmp_path: Path,
) -> None:
    """THE INCIDENT. Healthy percentages everywhere, and the account cannot serve.

    The destination has LESS short-window headroom than the account being left,
    so the ordinary relative-headroom margin would refuse the move. That margin
    measures headroom the capped account is not permitted to spend, so it is
    waived rather than measured -- otherwise the fleet stays stranded exactly
    where it stranded.
    """
    outcome = run(
        tmp_path=tmp_path,
        active=usage(five_hour=80.0, seven_day=83.0, block=CAPPED_BLOCK),
        candidates=(candidate(name="included", five_hour=40.0, seven_day=40.0),),
    )

    assert outcome.switched_to == "included", (
        "a spend_limit_reached ACTIVE account must trigger rotation; "
        f"held={outcome.held} lines={outcome.lines}"
    )
    assert any("spend limit" in line for line in outcome.lines), outcome.lines


def test_the_same_healthy_active_holds_when_its_meter_reports_no_cap(tmp_path: Path) -> None:
    """The control for the scenario above: the CAP is what moved it, nothing else."""
    outcome = run(
        tmp_path=tmp_path,
        active=usage(five_hour=80.0, seven_day=83.0, block=NEVER_ENABLED_BLOCK),
        candidates=(candidate(name="included", five_hour=40.0, seven_day=40.0),),
    )

    assert outcome.held


# ---------------------------------------------------------------------------
# (c) No behavior change when extra usage is disabled everywhere.
# ---------------------------------------------------------------------------


def test_meters_reporting_no_spend_decide_exactly_as_a_fleet_with_no_meter_at_all(
    tmp_path: Path,
) -> None:
    """Byte-for-byte, both directions: the added dimension is inert while unused."""
    without = run(
        tmp_path=tmp_path,
        active=usage(five_hour=5.0, seven_day=60.0),
        candidates=(
            candidate(name="one", five_hour=99.0, weekly_reset=_SOON),
            candidate(name="two", five_hour=70.0),
        ),
    )
    with_meters = run(
        tmp_path=tmp_path,
        active=usage(five_hour=5.0, seven_day=60.0, block=NEVER_ENABLED_BLOCK),
        candidates=(
            candidate(name="one", five_hour=99.0, weekly_reset=_SOON, block=NEVER_ENABLED_BLOCK),
            candidate(name="two", five_hour=70.0, block=NEVER_ENABLED_BLOCK),
        ),
    )

    assert without.switched_to == "one"
    assert with_meters.switched_to == without.switched_to
    assert with_meters.lines == without.lines


def test_a_quiet_fleet_with_no_meter_anywhere_still_holds(tmp_path: Path) -> None:
    outcome = run(
        tmp_path=tmp_path,
        active=usage(five_hour=80.0, seven_day=83.0),
        candidates=(candidate(name="included"),),
    )

    assert outcome.held
