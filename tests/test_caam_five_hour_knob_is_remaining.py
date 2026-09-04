"""The five-hour rotation knob says REMAINING too, and the spent-direction name is gone.

`plan/quota-percentages-say-remaining/research/used-versus-remaining.md` records the
maintainer ruling that these percentages must say REMAINING in labels AND in keys.
The representation flip that preceded this change left exactly one knob still
published in the spent direction -- `CAAM_ROTATE_FIVE_HOUR_THRESHOLD`, default 85 --
and exactly one bridge complementing it, so that the two directions still met
somewhere. This file pins the clean break the maintainer ruled for on 2026-09-04:
the knob is renamed to `CAAM_ROTATE_FIVE_HOUR_REMAINING`, its default transforms to
15, and there is NO backward-compatible alias.

THE ABSENT ALIAS IS THE ASSERTION THAT MATTERS, and it is the one an outcome test
cannot make. A silently-honoured old name would keep both directions in circulation
under one number, which is the defect the whole thread exists to remove -- and it
would be invisible at the default, where 85 spent and 15 remaining describe the same
account. So the retired name is pinned to have NO effect at a value where the two
readings disagree loudly, rather than at the default where they agree.

The migration note is pinned here too. A clean break with no alias is a silent
behaviour change for any operator who customised the old knob: their export stops
being read, and the default quietly takes over. That makes the documented rename and
value transform part of the deliverable rather than a courtesy, so it is gated like
one.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

__all__: list[str] = []

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "overseer"
CARRIER = ROOT / ".claude-plugin" / "overseer"
PROSE = ROOT / ".claude-plugin" / "prose" / "caam-anthropic-loop.md"

REMAINING_ENV = "CAAM_ROTATE_FIVE_HOUR_REMAINING"
RETIRED_ENV = "CAAM_ROTATE_FIVE_HOUR_THRESHOLD"
DEFAULT_REMAINING_FLOOR = 15.0


def decision_module() -> ModuleType:
    return importlib.import_module("caam_decision")


def test_the_five_hour_knob_is_read_from_the_remaining_named_variable(*, monkeypatch):
    monkeypatch.delenv(RETIRED_ENV, raising=False)
    monkeypatch.setenv(REMAINING_ENV, "20")

    assert decision_module().five_hour_remaining_floor() == 20.0


def test_the_unset_knob_falls_back_to_the_transformed_default(*, monkeypatch):
    monkeypatch.delenv(RETIRED_ENV, raising=False)
    monkeypatch.delenv(REMAINING_ENV, raising=False)

    assert decision_module().five_hour_remaining_floor() == DEFAULT_REMAINING_FLOOR


def test_the_retired_spent_direction_variable_is_not_honoured_as_an_alias(*, monkeypatch):
    """50 spent and 50 remaining are opposite accounts, so an alias cannot hide here."""
    monkeypatch.delenv(REMAINING_ENV, raising=False)
    monkeypatch.setenv(RETIRED_ENV, "50")

    assert decision_module().five_hour_remaining_floor() == DEFAULT_REMAINING_FLOOR


def test_no_spent_direction_threshold_helper_survives_the_break():
    module = decision_module()

    assert not hasattr(module, "five_hour_threshold")
    assert "five_hour_threshold" not in module.__all__


def test_the_retired_name_appears_nowhere_in_either_shipped_package():
    """Both trees, because the carrier is what an installed plugin actually runs."""
    carrying = [
        path.name
        for root in (PACKAGE, CARRIER)
        for path in sorted(root.glob("*.py"))
        if RETIRED_ENV in path.read_text(encoding="utf-8")
    ]

    assert carrying == []


def test_the_operator_prose_documents_the_rename_and_the_value_transform():
    prose = PROSE.read_text(encoding="utf-8")

    assert f"`{REMAINING_ENV}`, default `15`" in prose
    assert f"replaces `{RETIRED_ENV}`" in prose
    assert "no backward-compatible alias" in prose
    assert "subtracting it from 100" in prose
    assert "spent becomes `15` remaining" in prose
