"""The session-window trigger rotates early, never onto a protected account.

Work item overseer-xwfyxy. Maintainer direction (verbatim, recorded on
livespec-dev-tooling-6tgd2z): "Yes do that. Just get things working the way
they're supposed to so they rotate automatically to whatever is available and
manage it correctly". Incident: a protected account at a 100% floor went live
and ran out its 5-hour window, killing a seat.

Pinned here: the session floor defaults to 20% remaining; a pass triggered on
the 5-hour window never falls back onto the protected set; the dry-run names
the account it would select without switching; and the committed configuration
protects exactly one account, anthropic-0, which an explicit `none` still clears.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from caam_anthropic_decide import DecisionSeams, decide
from caam_decision import ProfileUsage, UsageRecord, five_hour_remaining_floor
from caam_decision_protection import CandidatePolicy, select_candidate_set
from caam_protected_accounts import (
    apply_protected_accounts,
    committed_protected_requests,
    requested_protected_accounts,
)


def _usage(*, five_hour_left: float, seven_day_left: float = 80.0) -> UsageRecord:
    return UsageRecord(
        five_hour_remaining=five_hour_left,
        seven_day_remaining=seven_day_left,
        five_hour_resets_at=None,
        seven_day_resets_at=None,
        fable_remaining=None,
        fable_resets_at=None,
    )


def _profile(*, name: str, five_hour_left: float, seven_day_left: float = 80.0) -> ProfileUsage:
    return ProfileUsage(
        name=name,
        source="live",
        usage=_usage(five_hour_left=five_hour_left, seven_day_left=seven_day_left),
    )


@dataclass(frozen=True, kw_only=True)
class _SwitchResult:
    lines: tuple[str, ...]
    exit_code: int
    switched: bool = True


class _Flags:
    force = False

    def __init__(self, *, dry_run: bool = False) -> None:
        self.dry_run = dry_run


class _Context:
    def __init__(self, *, home: Path, dry_run: bool) -> None:
        self.flags = _Flags(dry_run=dry_run)
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
    dry_run: bool = False,
) -> tuple[str | None, list[str]]:
    switched: list[str] = []
    context = _Context(home=tmp_path, dry_run=dry_run)

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
    return (switched[0] if switched else None), context.lines


def test_the_session_floor_defaults_to_twenty_percent_remaining(monkeypatch) -> None:
    monkeypatch.delenv("CAAM_ROTATE_FIVE_HOUR_REMAINING", raising=False)

    assert five_hour_remaining_floor() == 20.0


def test_a_pass_rotates_at_nineteen_percent_session_left_and_holds_at_twenty_five(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("CAAM_ROTATE_FIVE_HOUR_REMAINING", raising=False)
    spare = _profile(name="anthropic-b", five_hour_left=90.0)

    low, _ = _pass(
        tmp_path=tmp_path,
        profiles=(_profile(name="anthropic-a", five_hour_left=19.0), spare),
        active_name="anthropic-a",
        protection_floors={},
    )
    healthy, _ = _pass(
        tmp_path=tmp_path,
        profiles=(_profile(name="anthropic-a", five_hour_left=25.0), spare),
        active_name="anthropic-a",
        protection_floors={},
    )

    assert low == "anthropic-b"
    assert healthy is None


def test_the_session_trigger_never_falls_back_onto_a_protected_account(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("CAAM_ROTATE_FIVE_HOUR_REMAINING", raising=False)
    target, _ = _pass(
        tmp_path=tmp_path,
        profiles=(
            _profile(name="anthropic-a", five_hour_left=5.0),
            _profile(name="anthropic-0", five_hour_left=95.0),
        ),
        active_name="anthropic-a",
        protection_floors={"anthropic-0": 10.0},
    )

    assert target is None


def test_the_session_trigger_prefers_the_unprotected_account_with_headroom(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("CAAM_ROTATE_FIVE_HOUR_REMAINING", raising=False)
    target, _ = _pass(
        tmp_path=tmp_path,
        profiles=(
            _profile(name="anthropic-a", five_hour_left=5.0),
            _profile(name="anthropic-0", five_hour_left=95.0),
            _profile(name="anthropic-c", five_hour_left=60.0),
        ),
        active_name="anthropic-a",
        protection_floors={"anthropic-0": 10.0},
    )

    assert target == "anthropic-c"


def test_the_weekly_dimension_keeps_its_protected_fallback() -> None:
    """Only the session-window comparison lost the fallback; the weekly one is unchanged."""
    current = _usage(five_hour_left=90.0, seven_day_left=5.0)
    protected = (_profile(name="anthropic-0", five_hour_left=90.0, seven_day_left=90.0),)

    def candidates(*, dimension: str) -> tuple[ProfileUsage, ...]:
        return select_candidate_set(
            profiles=protected,
            active_name="anthropic-a",
            policy=CandidatePolicy(
                current=current,
                gain_needed=10.0,
                dimension=dimension,
                enforce_reserve=True,
                weekly_reserve=10.0,
            ),
            protection_floors={"anthropic-0": 10.0},
        )

    assert [p.name for p in candidates(dimension="seven_day")] == ["anthropic-0"]
    assert candidates(dimension="five_hour") == ()


def test_the_dry_run_names_the_account_it_would_select_without_switching(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("CAAM_ROTATE_FIVE_HOUR_REMAINING", raising=False)
    target, lines = _pass(
        tmp_path=tmp_path,
        profiles=(
            _profile(name="anthropic-a", five_hour_left=5.0),
            _profile(name="anthropic-0", five_hour_left=95.0),
            _profile(name="anthropic-c", five_hour_left=60.0),
        ),
        active_name="anthropic-a",
        protection_floors={"anthropic-0": 10.0},
        dry_run=True,
    )

    assert target is None
    text = "\n".join(lines)
    assert "anthropic-c" in text
    assert "anthropic-0" not in text.split("anthropic-c")[0]
    assert "5-hour window" in text


def test_the_committed_configuration_protects_only_anthropic_0() -> None:
    state: dict[str, object] = {}

    result = apply_protected_accounts(
        state=state, requested_accounts=committed_protected_requests()
    )

    assert tuple(result.values) == ("anthropic-0",)
    assert result.values["anthropic-0"] == 10.0


def test_an_explicit_flag_after_the_committed_set_can_still_clear_or_add() -> None:
    cleared = apply_protected_accounts(
        state={},
        requested_accounts=requested_protected_accounts(flagged=(("anthropic-0", "none"),)),
    )
    added = apply_protected_accounts(
        state={},
        requested_accounts=requested_protected_accounts(flagged=(("anthropic-9", "25"),)),
    )

    assert cleared.values == {}
    assert added.values == {"anthropic-0": 10.0, "anthropic-9": 25.0}


def test_a_stale_stored_mark_is_cleared_by_an_explicit_none() -> None:
    state: dict[str, object] = {"protected_accounts": {"anthropic-4": 100.0}}

    result = apply_protected_accounts(
        state=state,
        requested_accounts=requested_protected_accounts(flagged=(("anthropic-4", "none"),)),
    )

    assert tuple(result.values) == ("anthropic-0",)
