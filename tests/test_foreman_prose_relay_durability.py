"""Two relay rules that govern whether a relayed decision SURVIVES.

The ratified relay discipline governs what a relay must CARRY. These two govern
what happens to it afterwards, and both were added from measured 2026-08-20
incidents: a ruling relayed by message alone that left no trace on its item, and
a fenced claim repeated without its fence and then acted on.
"""

from __future__ import annotations

from pathlib import Path

FOREMAN_PROSE = Path(__file__).resolve().parents[1] / ".claude-plugin" / "prose" / "foreman.md"

__all__: list[str] = []


def prose() -> str:
    return FOREMAN_PROSE.read_text(encoding="utf-8")


def test_a_relayed_decision_must_land_in_a_durable_addressable_record():
    text = prose()

    assert "A RELAY THAT LIVES ONLY IN A MESSAGE IS NOT RECORDED." in text
    assert "durable addressable record" in text
    assert "the governed ledger item, or the plan anchor" in text
    assert "the only evidence it was ever made" in text
    assert "unverifiable by construction" in text
    assert "CHECKABLE BY SOMEONE WHO WAS NOT IN THE ROOM" in text


def test_a_repeated_claim_carries_its_hedge_or_is_re_measured():
    text = prose()

    assert "CARRY A CLAIM'S HEDGE OR RE-MEASURE IT." in text
    assert "does not become measured by being repeated" in text
    assert "and dropping the fence is not a summary" in text
    assert "measure it yourself first and say so" in text


def test_operational_holds_name_their_carrier_owner_and_lift_condition():
    text = prose()
    normalized = " ".join(text.split())

    assert "A HOLD OVER A SEAT IS NOT A HOLD OVER THE DRAIN LOOP." in text
    assert "owner who may lift it" in text
    assert "condition under which that owner may lift it" in text
    assert "repo-wide hold over unattended draining" in text
    assert "dispatcher.wip_cap == 0" in text
    assert "targeted `dispatch --item` override" in text
    assert "per-item hold" in text
    assert "lane other than `ready`" in text
    assert "per-factory loop hold" in text
    assert "no carrier exists" in text
    assert "The drain loop selected from the ready set exactly as designed" in normalized
