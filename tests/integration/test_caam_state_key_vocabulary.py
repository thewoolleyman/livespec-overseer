"""Every state key the program writes is named in the key vocabulary docstring.

`caam_profile_state`'s module docstring carries a STATE FILE KEY VOCABULARY, and
it exists because a key the vocabulary does not name fails SILENTLY in the one
direction nobody checks: an unrecognised key is loaded and saved back untouched,
so the file goes on APPEARING to carry it while nothing ever reads it. That is
not a hypothetical -- the docstring records `session_models` shipping hyphenated
once, which stopped both maintainer model pins applying without any surface
saying so.

A prose list of that kind is exactly the artifact that rots: it is maintained by
whoever remembers it exists, and the cost of forgetting is paid much later by
someone reading the file to find out what is in it. So the list is measured
against the PROGRAM rather than reviewed -- this drives the shipped rotation pass
and asserts that every top-level key the run actually wrote is named.

It asserts one direction only, deliberately. A key the program writes and the
vocabulary omits is the silent failure above; a key the vocabulary names and this
particular run does not write is just a path this run did not take -- the
`warm`, `models` and `last_switch` keys among them -- and asserting the converse
would make the test a restatement of the docstring it is supposed to check.
"""

from __future__ import annotations

from pathlib import Path

import caam_profile_state
import pytest
from test_caam_fast_drain import (
    LARGE_PLAN,
    NOW,
    PASS_INTERVAL,
    SMALL_PLAN,
    RotationHarness,
    usage,
)

__all__: list[str] = []

pytestmark = pytest.mark.integration

DAY = 86_400.0


def vocabulary_keys() -> frozenset[str]:
    """The keys the module docstring's vocabulary block names.

    Each entry is `<key> <defining module> -- <what it holds>`, so an entry is
    recognised by its SECOND column naming a `caam_` module rather than by its
    position in the docstring: the prose around the block mentions key names
    too, and a substring search over the whole docstring would accept one of
    those as an entry and pass a key that was never listed.
    """
    entries: set[str] = set()
    for line in (caam_profile_state.__doc__ or "").splitlines():
        columns = line.split()
        if len(columns) >= 2 and columns[1].startswith("caam_"):
            entries.add(columns[0])
    return frozenset(entries)


def test_every_state_key_the_program_writes_is_in_the_key_vocabulary(*, tmp_path: Path) -> None:
    """A two-pass run, so the keys only a MEASURING pass writes are reached.

    One pass cannot write the burn-rate state at all: a baseline is written on
    every pass, but the fleet load is recorded only where a rate was measured,
    and a rate needs two readings of one short window at known, different
    instants. A single-pass version of this test would therefore pass while the
    very keys this work added went unnamed.
    """
    harness = RotationHarness(
        home=tmp_path,
        active="big",
        usages={
            "big": usage(five_hour_remaining=30.0, seven_day_reset_s=DAY),
            "small-plan": usage(five_hour_remaining=50.0, seven_day_reset_s=2 * DAY),
        },
        live_plans={"big": LARGE_PLAN, "small-plan": SMALL_PLAN},
    )

    first_code, _first_lines = harness.run(at=NOW)
    harness.read(name="big", record=usage(five_hour_remaining=20.0, seven_day_reset_s=DAY))
    second_code, _second_lines = harness.run(at=NOW + PASS_INTERVAL)

    assert first_code == second_code == 0
    written = frozenset(harness.read_state())
    # The premise: a run that wrote neither the baseline nor the load would
    # satisfy the assertion below while measuring nothing about this work.
    assert {"fleet_load", "short_window_baseline"} <= written
    assert sorted(written - vocabulary_keys()) == []
