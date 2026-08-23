"""The held-claim surface invariant, kept beside the core invariant module.

This invariant answers a different question from the rest of the suite. Every
other check in `grooming_conformance_invariants` measures a property of the
scanned rows and reports the rows that breach it. This one reports the SHAPE of
the claim surface itself: it has no breach branch at all, because a terminal
assignee is provenance rather than a held claim, and the distinction is decided
by status rather than by the assignee field it reads.

It lives here so that `grooming_conformance_invariants` stays what its own name
says it is -- row-measured invariants -- and so that module stays under the LLOC
soft ceiling without an owner marker, which
`tests/test_grooming_conformance_external_refactor.py` enforces.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from grooming_conformance_types import InvariantCheck
from grooming_conformance_values import assignee, is_open

__all__: list[str] = [
    "held_claim_surface_check",
    "held_claim_surface_scope",
]


def held_claim_surface_check(*, items: Sequence[Mapping[str, object]]) -> InvariantCheck:
    assigned_items = tuple(item for item in items if assignee(item=item) is not None)
    terminal_count = sum(1 for item in assigned_items if not is_open(item=item))
    held_count = len(assigned_items) - terminal_count
    return InvariantCheck(
        key="held-claim-surface",
        title="Assignee scans are status-first",
        status="structurally-guaranteed",
        breaching_item_ids=(),
        scanned_item_count=held_count,
        scope=held_claim_surface_scope(
            held_count=held_count,
            terminal_count=terminal_count,
        ),
        reason=(
            "chosen route (b): terminal assignees are kept as provenance; only "
            "non-terminal assigned rows are held-claim candidates"
        ),
    )


def held_claim_surface_scope(*, held_count: int, terminal_count: int) -> str:
    held_row_word = "row" if held_count == 1 else "rows"
    terminal_row_word = "row" if terminal_count == 1 else "rows"
    terminal_be = "is" if terminal_count == 1 else "are"
    return (
        f"{held_count} non-terminal assigned {held_row_word} are held-claim candidates; "
        f"{terminal_count} terminal assigned {terminal_row_word} {terminal_be} provenance, "
        "not a held claim"
    )
