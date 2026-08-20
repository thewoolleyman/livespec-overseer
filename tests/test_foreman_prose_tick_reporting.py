"""The three tick-reporting rules must stay in the foreman prose.

Each rule below was added because its ABSENCE was measured in a live foreman
transcript: reports that re-argued a standing list every tick, escalations
raised without a routing attempt, and refusals that quoted the contract instead
of naming an actor. Removing any one of them makes exactly one of these
assertion groups fail, which is the point of asserting them separately.
"""

from __future__ import annotations

from pathlib import Path

FOREMAN_PROSE = Path(__file__).resolve().parents[1] / ".claude-plugin" / "prose" / "foreman.md"

__all__: list[str] = []


def prose() -> str:
    return FOREMAN_PROSE.read_text(encoding="utf-8")


def test_the_tick_reporting_section_exists():
    assert "### Tick reporting discipline" in prose()


def test_a_standing_item_is_named_once_by_id_and_not_re_argued():
    text = prose()

    assert "LIST A STANDING ITEM ONCE, BY ID, AND DO NOT RE-ARGUE IT." in text
    assert "named by its work-item or" in text
    assert "session id and nothing more" in text
    assert "grows monotonically while the" in text


def test_every_route_is_tried_before_anything_may_be_called_an_escalation():
    text = prose()

    assert "ROUTE BEFORE YOU ESCALATE." in text
    assert "the grooming skill" in text
    assert "a worker session" in text
    assert "the review panel" in text
    assert "a ledger action" in text
    assert "Only what survives all four routes may be" in text


def test_refusal_boilerplate_is_replaced_by_naming_the_actor():
    text = prose()

    assert "NAME WHO CAN ACT INSTEAD OF QUOTING YOUR OWN CONTRACT." in text
    assert "my contract does not permit it" in text
    assert "Replace it with the actor and the route" in text
    assert "only the maintainer can act" in text
