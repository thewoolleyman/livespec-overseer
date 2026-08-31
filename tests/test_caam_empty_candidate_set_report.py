"""A pass with an empty candidate set must not report a comparison that never ran.

Observed 2026-08-28, and `_table_2026_08_28` below reproduces the rows verbatim:

    PROFILE       CURRENT   5H    WEEK   SOURCE
    anthropic-0             -     -      dark: token expired 93.0h ago
    anthropic-1             100%  100%   cached 0.6h
    anthropic-2             100%  62%    cached 0.6h
    anthropic-3             100%  100%   cached 0.6h
    anthropic-4   active    82%   9%     live

    hold: no candidate has >=0.01 points more seven_day headroom than anthropic-4
    (all similarly spent, exhausted, or unverifiable); note: every account is under
    the 10% weekly reserve -- releasing it

Three claims in that output are false, and each is pinned here.

The hold line asserted a headroom margin, but `candidate_allowed` requires a LIVE
source and anthropic-4 was the only live row -- excluded as the active account --
so the candidate set was empty and no comparison ran at all. The release note said
"every account" while `every_live_account_under_reserve` filters to live rows, a
set of exactly one here, so three accounts at 100%, 62% and 100% weekly were never
consulted. And the not-considered note named only the dark row, leaving the three
cached rows silently excluded with their stale figures still rendered as usable.

SPECIFICATION/spec.md: "The operator-facing report MUST NOT assert figures it
cannot know", whose stated rationale is that the machine is already protected by
the live-verification rule, so the only consumer left to mislead is the human
deciding whether to intervene.

Reporting only. The last test in this file is the control: selection, ranking,
eligibility and the reserve predicate must be untouched by any of it.
"""

from __future__ import annotations

from pathlib import Path

from _caam_pass_span import PassSpan
from caam_anthropic_decide import DecisionSeams, decide
from caam_anthropic_status import unverified_note, write_status
from caam_decision import ActiveAccount, ProfileUsage, UsageRecord, eligible_profiles
from caam_switch import SwitchRequest, SwitchResult

_ACTIVE = "anthropic-4"


def _usage(*, five_hour: float, seven_day: float) -> UsageRecord:
    return UsageRecord(
        five_hour=five_hour,
        seven_day=seven_day,
        five_hour_resets_at=None,
        seven_day_resets_at=None,
        fable=None,
        fable_resets_at=None,
    )


def _cached(*, name: str, five_hour: float, seven_day: float) -> ProfileUsage:
    return ProfileUsage(
        name=name, source="cached 0.6h", usage=_usage(five_hour=five_hour, seven_day=seven_day)
    )


def _table_2026_08_28() -> tuple[tuple[ProfileUsage, ...], UsageRecord]:
    """The five rows exactly as the operator saw them, in the order they rendered."""
    active = _usage(five_hour=18.0, seven_day=91.0)
    return (
        (
            ProfileUsage(name="anthropic-0", source="dark: token expired 93.0h ago", usage=None),
            _cached(name="anthropic-1", five_hour=0.0, seven_day=0.0),
            _cached(name="anthropic-2", five_hour=0.0, seven_day=38.0),
            _cached(name="anthropic-3", five_hour=0.0, seven_day=0.0),
            ProfileUsage(name=_ACTIVE, source="live", usage=active),
        ),
        active,
    )


class _Flags:
    force = False
    dry_run = False
    no_models = False
    foreman_model: str | None = None
    session_models: tuple[tuple[str, str], ...] = ()
    protected_accounts: tuple[tuple[str, str], ...] = ()


class _Context:
    def __init__(self, *, home: Path) -> None:
        self.flags = _Flags()
        self.home = home
        self.now = 1_787_000_000.0
        self.state: dict[str, object] = {}
        self.state_path = home / "state.json"
        self.lines: list[str] = []
        # This file drives `write_status` directly rather than through a rotation
        # pass, so there is no open pass span and enforcement reports no facts.
        self.span: PassSpan | None = None

    def stdout(self, line: str) -> None:
        self.lines.append(line)


def _decide(
    *,
    tmp_path: Path,
    profiles: tuple[ProfileUsage, ...],
    current: UsageRecord,
    active_name: str = _ACTIVE,
    switched: list[str] | None = None,
) -> list[str]:
    context = _Context(home=tmp_path)

    def _switch(*, request: SwitchRequest) -> SwitchResult:
        name = request.target.name
        if switched is None:
            raise AssertionError(f"must not switch: this case must HOLD (target {name})")
        switched.append(name)
        return SwitchResult(
            exit_code=0, reason="switched", lines=(f"SWITCHED -> {name}",), switched=True
        )

    decide(
        context=context,
        profiles=profiles,
        active_name=active_name,
        current=current,
        protection_floors={},
        seams=DecisionSeams(
            fetcher=lambda **_: (None, "not used"),
            save_state=lambda **_: None,
            switch_account=_switch,
        ),
    )
    return context.lines


def _hold_line(*, lines: list[str]) -> str:
    return next(line for line in lines if line.startswith("hold:"))


def test_the_hold_line_reports_the_empty_set_and_names_live_verification_as_the_cause(
    *, tmp_path: Path
) -> None:
    """THE DEFECT. The pass measured nothing, so it must not describe a margin."""
    profiles, current = _table_2026_08_28()
    hold = _hold_line(lines=_decide(tmp_path=tmp_path, profiles=profiles, current=current))

    assert hold == (
        "hold: the candidate set was empty -- no account other than anthropic-4 could "
        "be verified live this pass (anthropic-0, anthropic-1, anthropic-2, "
        "anthropic-3), so no seven_day headroom comparison was made; "
        "note: every live-verified account is under the 10% weekly reserve -- releasing it"
    )
    # The old line's LEADING cause is what a reader with 100% weekly figures in
    # front of them acted on, and it is the one thing this pass cannot claim.
    assert "similarly spent" not in hold
    assert "points more" not in hold


def test_the_reserve_release_note_claims_only_the_scope_it_measured() -> None:
    """`every_live_account_under_reserve` filters to live rows; the words must too."""
    profiles, current = _table_2026_08_28()
    released = eligible_profiles(
        profiles=profiles,
        active=ActiveAccount(name=_ACTIVE, usage=current),
        force=False,
        dimension="seven_day",
    )

    assert released.profiles == ()
    assert released.note == (
        "note: every live-verified account is under the 10% weekly reserve -- releasing it"
    )
    # One live account was measured. Three cached rows above the reserve were not,
    # and the wording must not sweep them in -- that is the direction that makes a
    # healthy fleet read as exhausted.
    assert not released.note.startswith("note: every account")


def test_the_not_considered_note_names_the_cached_rows_and_not_the_active_one() -> None:
    """Cached rows were excluded for exactly the reason the dark one was."""
    profiles, _ = _table_2026_08_28()

    assert unverified_note(profiles=profiles, active_name=_ACTIVE) == (
        "note: anthropic-0, anthropic-1, anthropic-2, anthropic-3 could not be verified "
        "live and were not considered. Revive with: caam activate claude <name>; "
        "claude -p ok; caam backup claude <name>"
    )


def test_the_not_considered_note_reaches_the_operator_from_the_status_writer(
    *, tmp_path: Path
) -> None:
    """The note is the operator's only record of what the table's figures are worth."""
    profiles, current = _table_2026_08_28()
    context = _Context(home=tmp_path)

    write_status(
        context=context,
        profiles=profiles,
        active_name=_ACTIVE,
        current=current,
        enforce_models=lambda **_: [],
    )

    note = next(line for line in context.lines if "could not be verified live" in line)
    for name in ("anthropic-0", "anthropic-1", "anthropic-2", "anthropic-3"):
        assert name in note
    assert _ACTIVE not in note


def test_a_vault_holding_only_the_active_account_says_so(*, tmp_path: Path) -> None:
    """A distinct cause with a distinct sentence: there was nothing to compare TO."""
    _, current = _table_2026_08_28()
    profiles = (ProfileUsage(name=_ACTIVE, source="live", usage=current),)
    hold = _hold_line(lines=_decide(tmp_path=tmp_path, profiles=profiles, current=current))

    assert hold.startswith(
        "hold: the candidate set was empty -- anthropic-4 is the only account in the "
        "vault, so no seven_day headroom comparison was made"
    )


def test_live_candidates_with_nothing_left_are_reported_as_exhausted(*, tmp_path: Path) -> None:
    """Verified live, reached by the comparison, and out of allowance -- a third cause."""
    _, current = _table_2026_08_28()
    profiles = (
        ProfileUsage(name=_ACTIVE, source="live", usage=current),
        ProfileUsage(
            name="anthropic-5", source="live", usage=_usage(five_hour=10.0, seven_day=100.0)
        ),
    )
    hold = _hold_line(lines=_decide(tmp_path=tmp_path, profiles=profiles, current=current))

    assert hold.startswith(
        "hold: the candidate set was empty -- every live-verified candidate is "
        "exhausted (anthropic-5)"
    )


def test_live_candidates_that_were_compared_and_fell_short_still_name_the_margin(
    *, tmp_path: Path
) -> None:
    """The margin claim is legitimate ONLY over candidates the margin was applied to."""
    current = _usage(five_hour=95.0, seven_day=50.0)
    profiles = (
        ProfileUsage(name="anthropic-a", source="live", usage=current),
        ProfileUsage(
            name="anthropic-b", source="live", usage=_usage(five_hour=94.0, seven_day=48.0)
        ),
    )
    hold = _hold_line(
        lines=_decide(
            tmp_path=tmp_path, profiles=profiles, current=current, active_name="anthropic-a"
        )
    )

    assert hold == (
        "hold: the candidate set was empty -- none of the live-verified candidates "
        "(anthropic-b) clears the >=10.00 point five_hour headroom margin over "
        "anthropic-a within the weekly reserve"
    )


def test_selection_is_untouched_by_the_reporting_change(*, tmp_path: Path) -> None:
    """THE CONTROL. Reporting only: the chosen target must be byte-identical.

    The 2026-08-28 rows are kept exactly as they were and ONE live account is added,
    so the fixture still carries both a dark row and three cached rows. Two of those
    cached rows hold far more weekly headroom than the added candidate, so an
    implementation that let the reporting fix leak into eligibility -- by admitting
    a row it can now name -- ranks a cached account first here and fails.
    """
    rows, current = _table_2026_08_28()
    candidate = ProfileUsage(
        name="anthropic-5", source="live", usage=_usage(five_hour=20.0, seven_day=60.0)
    )
    profiles = (*rows, candidate)

    eligible = eligible_profiles(
        profiles=profiles,
        active=ActiveAccount(name=_ACTIVE, usage=current),
        force=False,
        dimension="seven_day",
    )
    assert [profile.name for profile in eligible.profiles] == ["anthropic-5"]
    assert eligible.note is None

    switched: list[str] = []
    lines = _decide(tmp_path=tmp_path, profiles=profiles, current=current, switched=switched)
    assert switched == ["anthropic-5"]
    assert not any(line.startswith("hold:") for line in lines)
