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
