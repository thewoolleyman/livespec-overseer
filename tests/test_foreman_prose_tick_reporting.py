"""The three tick-reporting rules must stay in the foreman prose.

Each rule below was added because its ABSENCE was measured in a live foreman
transcript: reports that re-argued a standing list every tick, escalations
raised without a routing attempt, and refusals that quoted the contract instead
of naming an actor. Removing any one of them makes exactly one of these
assertion groups fail, which is the point of asserting them separately.
"""

from __future__ import annotations

import re
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


def test_plan_roster_is_the_narrow_list_once_exemption():
    text = prose()
    tick_section = text.split("### Tick reporting discipline", maxsplit=1)[1].split(
        "### Operational lessons",
        maxsplit=1,
    )[0]

    assert "THE PLAN ROSTER IS THE ONLY LIST-ONCE EXEMPTION." in tick_section
    assert "The prose half of the tick report is not exempt" in tick_section
    assert "must not repeat what the roster already carries" in tick_section


def test_plan_roster_contract_splits_session_and_work_state():
    text = prose()
    normalized = " ".join(text.split())

    assert (
        "exactly six columns: name, session state, work state, action needed, "
        "why-not-acting, and emoji"
    ) in normalized
    assert "Session state is the pane's own state" in text
    assert "Work state is whether factory runs are in flight" in normalized
    assert "The daemon's status field describes the pane, not the work" in normalized
    assert "session state and work state are orthogonal" in normalized
    assert "Idle with runs in flight is healthy" in text
    assert "idle with nothing in flight is the attention case" in normalized
    assert "Column budgets are hard limits" in text
    assert "session state 10 words" in normalized
    assert "work state 6 words" in normalized
    assert "action needed 20 words" in normalized
    assert "why-not-acting 20 words" in normalized


def test_plan_roster_emoji_is_derived_total_and_discriminates_idle_controls():
    text = prose()
    normalized = " ".join(text.split())

    assert "The emoji is derived, never authored" in text
    assert "total closed mapping" in text
    assert "every session and work combination resolves to exactly one emoji" in normalized
    assert "Precedence is 🔵, then 🔴, then 🟢, then ⏳, then ⚪" in text
    assert "❗ overrides everything" in text
    assert "session idle and work runs in flight yields ⏳, not 🟢" in normalized
    assert "session idle and no runs in flight yields ⚪, distinct from ⏳" in normalized

    legend_match = re.search(r"The legend is one line and names every symbol:\n([^\n]+)", text)
    assert legend_match is not None
    legend = legend_match.group(1)
    for symbol in ("🔵", "🔴", "🟢", "⏳", "⚪", "❗"):
        assert symbol in legend


def test_plan_roster_placement_and_handoff_exclusion_are_declared():
    text = prose()
    normalized = " ".join(text.split())

    assert "Emit the plan roster for this runtime tick" in text
    assert "before any `AskUserQuestion`" in text
    assert "missed occurrences are dropped rather than backfilled" in normalized
    assert "Emit the plan roster before `overseer-declare ready`" in text
    assert "successor session most needs" in text
    assert "Do not write roster state into the handoff entry" in text
    assert "at most once per tick identity" in normalized


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
