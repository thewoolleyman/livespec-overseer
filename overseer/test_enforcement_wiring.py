"""Wiring tests for SPECIFICATION/non-functional-requirements.md.

The NFR file states CONTRIBUTOR-facing requirements — how this repository is
developed, tested, and gated. Their real enforcement is a `just check` TARGET,
while `tests/heading-coverage.json` maps headings to pytest node ids. That
mismatch is why three of these rows sat at `test: "TODO"` with no candidate.

What these tests assert is the WIRING, not the gate's verdict. Re-running each
gate from inside the suite would be near-tautological — `just check` already runs
them, and it runs this suite too. The failure these rows actually need protection
from is a gate being DROPPED from the aggregate, at which point the requirement
silently stops being enforced while everything stays green. That is the same
"reports but cannot fail" shape this repo has hit twice already (the unarmed
heading-coverage lever, and the 705 Phase-0 ROP warnings).

Each test parses the `check` recipe's `targets=(...)` array out of the justfile.
"""

from __future__ import annotations

import pathlib
import re

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_JUSTFILE = _REPO_ROOT / "justfile"


def _aggregate_targets() -> frozenset[str]:
    """Every target name listed in the `check` aggregate recipe.

    The recipe header is the bare `check:` that the fleet's own
    wiring-completeness checks parse for, so this reads the same anchor they do.
    """
    source = _JUSTFILE.read_text(encoding="utf-8")
    recipe = re.search(r"^check:\n(.*?)^\S", source, re.MULTILINE | re.DOTALL)
    assert recipe is not None, "the `check` aggregate recipe is missing from the justfile"
    array = re.search(r"targets=\((.*?)\n\s*\)", recipe.group(1), re.DOTALL)
    assert array is not None, "the `check` recipe no longer carries a `targets=(...)` array"
    return frozenset(line.strip() for line in array.group(1).splitlines() if line.strip())


def test_the_beside_test_and_red_green_discipline_are_wired_into_the_aggregate():
    """The "Spec" section of SPECIFICATION/non-functional-requirements.md: tests
    "live BESIDE the supervision modules", every protocol behavior "is pinned by a
    deterministic beside-test", and "product Python changes land through the fleet's
    red-green commit ritual".

    `check-tests-mirror-pairing` is what makes the beside-placement rule enforceable;
    `check-red-green-replay` is the ritual's no-arg commit-range validator.

    SABOTAGE-VERIFIED 2026-07-26: deleting `check-tests-mirror-pairing` from the
    aggregate turns this red naming it; reverted to a zero diff.
    """
    targets = _aggregate_targets()
    missing = sorted({"check-tests-mirror-pairing", "check-red-green-replay"} - targets)

    assert missing == [], f"NFR Spec gates dropped from the `just check` aggregate: {missing}"


def test_the_hundred_percent_coverage_gates_are_wired_into_the_aggregate():
    """The "Constraints" section of SPECIFICATION/non-functional-requirements.md: the
    package "holds one hundred percent statement AND branch coverage", and "the
    aggregate check target is the single local, pre-push, and CI entry point".

    Both coverage gates are asserted, not just one: `check-coverage` is the whole-package
    total and `check-per-file-coverage` is the per-module floor. Keeping only the total
    would let a fully-uncovered module hide behind the rest of the package.

    SABOTAGE-VERIFIED 2026-07-26: deleting `check-per-file-coverage` from the aggregate
    turns this red naming it; reverted to a zero diff.
    """
    targets = _aggregate_targets()
    missing = sorted({"check-coverage", "check-per-file-coverage"} - targets)

    assert (
        missing == []
    ), f"NFR Constraints gates dropped from the `just check` aggregate: {missing}"


def test_the_scenario_tier_rule_is_wired_into_the_aggregate():
    """The "Scenarios" section of SPECIFICATION/non-functional-requirements.md: "every
    scenario heading in `scenarios.md` maps to test evidence through the repository's
    heading-coverage registry; a scenario's evidence is integration-tier or better,
    never a unit-tier test."

    That rule IS `check-heading-coverage` direction 4, so this row's evidence is the gate
    being wired — pleasingly circular, and the circularity is the point: the registry row
    for this heading is itself validated by the check this test pins.

    SABOTAGE-VERIFIED 2026-07-26: deleting `check-heading-coverage` from the aggregate
    turns this red naming it; reverted to a zero diff.
    """
    targets = _aggregate_targets()

    assert (
        "check-heading-coverage" in targets
    ), "NFR Scenarios gate `check-heading-coverage` dropped from the `just check` aggregate"
