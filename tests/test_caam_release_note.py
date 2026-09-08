"""Tests for the note explaining why a released weekly reserve went unused.

The note is REPORTING and nothing reads it back, which is exactly why it is worth
pinning directly: a line that is only ever printed can go wrong for a long time
without anything failing. Both defects it has already had were of that shape --
naming a scope it never consulted, and judging the floor branch over a
population that included the account being left.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

__all__: list[str] = []

_RESERVE = 10.0


def release_note_module() -> ModuleType:
    """The note's own module, asserted present before anything imports it."""
    module_path = Path(__file__).resolve().parents[1] / "overseer" / "caam_release_note.py"
    assert module_path.is_file()
    return importlib.import_module("caam_release_note")


def profile(*, name: str, weekly: float, source: str = "live") -> object:
    models = importlib.import_module("caam_decision_models")
    return models.ProfileUsage(
        name=name,
        source=source,
        usage=models.UsageRecord(
            five_hour_remaining=50.0,
            seven_day_remaining=weekly,
            five_hour_resets_at=None,
            seven_day_resets_at=None,
            fable_remaining=None,
            fable_resets_at=None,
        ),
    )


def dark(*, name: str) -> object:
    models = importlib.import_module("caam_decision_models")
    return models.ProfileUsage(name=name, source="dark: no token", usage=None)


def test_the_note_names_the_protected_floors_when_every_candidate_is_at_one() -> None:
    module = release_note_module()

    note = module.empty_release_note(
        profiles=(
            profile(name="active", weekly=4.0),
            profile(name="held", weekly=5.0),
        ),
        protection_floors={"held": 5.0},
        weekly_reserve=_RESERVE,
        active_name="active",
    )

    assert note == "hold: protected account floors reached: held at 5% left (floor 5%)"


def test_the_active_account_is_not_counted_among_the_candidates_at_their_floor() -> None:
    """The clause is about the CANDIDATES; including the active one is stricter."""
    module = release_note_module()

    note = module.empty_release_note(
        profiles=(
            profile(name="active", weekly=90.0),
            profile(name="held", weekly=5.0),
        ),
        protection_floors={"held": 5.0},
        weekly_reserve=_RESERVE,
        active_name="active",
    )

    assert "held at 5% left" in note


def test_one_candidate_still_above_its_floor_takes_the_release_branch() -> None:
    module = release_note_module()

    note = module.empty_release_note(
        profiles=(
            profile(name="held", weekly=5.0),
            profile(name="free", weekly=80.0),
        ),
        protection_floors={"held": 5.0},
        weekly_reserve=_RESERVE,
        active_name="active",
    )

    assert (
        note == "note: every live-verified account is under the 10% weekly reserve -- releasing it"
    )


def test_the_release_branch_speaks_only_of_live_verified_accounts() -> None:
    """A dark row was never asked, so it cannot be part of what the note claims."""
    module = release_note_module()

    note = module.empty_release_note(
        profiles=(dark(name="unreachable"),),
        protection_floors={},
        weekly_reserve=_RESERVE,
    )

    assert "live-verified" in note


def test_an_unreachable_protected_account_is_not_reported_as_being_at_its_floor() -> None:
    module = release_note_module()

    assert (
        module.protected_accounts_at_floor(
            profiles=(dark(name="held"), profile(name="cached", weekly=0.0, source="cached 1.0h")),
            protection_floors={"held": 5.0, "cached": 5.0},
        )
        == ()
    )


def test_a_protected_account_above_its_floor_is_not_reported_as_being_at_it() -> None:
    module = release_note_module()

    assert (
        module.protected_accounts_at_floor(
            profiles=(profile(name="held", weekly=40.0),),
            protection_floors={"held": 5.0},
        )
        == ()
    )
