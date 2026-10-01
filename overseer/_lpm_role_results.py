"""Each role's closed RESULT shapes: its status vocabulary and each status's exact members.

SPECIFICATION/contracts.md requires every direct SecretStore role result crossing the
credential-role launcher boundary to be "exactly one UTF-8 JSON object with no extra
fields", and then enumerates the permitted shapes per role and mode. This module is the
READING side of that enumeration; `_lpm_store` and `_lpm_target` are the writing side, and
the vocabularies here are deliberately the same words those producers emit.

"NO EXTRA FIELDS" IS A LEAK CONTROL, NOT TIDINESS. A parent that accepted any object with a
recognized `version` and `status` would pass every unrecognized member through to its
caller — including one holding a credential value. The role process is the ONE place in
this operation that legitimately holds a token, so the boundary it writes across is exactly
where an unexpected member has to be refused rather than forwarded.

THE ENVELOPE CLOSES HERE; THE RECORD DOES NOT. Which statuses a role may answer with, and
precisely which members each status carries, are decided here. The contents of a `record`
or an invalid-chain descriptor are NOT: the contract places those after this boundary —
"the manager applies the credential-record field and invariant checks only after receiving
that envelope" — and duplicating them here would put the same rule in two places that can
disagree.

A ROLE THIS SLICE DOES NOT IMPLEMENT IS NOT CLOSED, and reports no defect rather than
rejecting everything. An always-failing role would be a worse answer than an unvalidated
one, and each remaining role's shapes arrive with the operation that uses them.
`CLOSED_ROLE_RESULTS` is pinned by its beside-test so that gap stays visible.

NO DIAGNOSTIC QUOTES A CHILD'S BYTES. A rogue child controls both its status and its member
NAMES, so a reason echoing either would let a token placed in a member name be logged by the
very check that rejected the result. A status is named only once it has been found in this
module's own table, at which point the word is the manager's rather than the child's.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_target import COMMIT_STATUSES, COMMITTED

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "CLOSED_ROLE_RESULTS",
    "ENVELOPE_MEMBERS",
    "ClosedResult",
    "closed_result_defect",
]

# Present on every result and therefore never part of a shape's distinguishing members.
ENVELOPE_MEMBERS: Final = frozenset({"version", "status"})

_STORE_UNAVAILABLE: Final = "store-unavailable"
_UNAVAILABLE: Final = "unavailable"


@dataclass(frozen=True, kw_only=True)
class ClosedResult:
    """One permitted result: its status and the EXACT additional member names it carries.

    `members` is exact in both directions — a missing member and an extra one are the same
    defect, because a shape is the whole object rather than a minimum.
    """

    status: str
    members: frozenset[str]


def _shape(*, status: str, members: tuple[str, ...] = ()) -> ClosedResult:
    return ClosedResult(status=status, members=frozenset(members))


# A commit status plus `store-unavailable`, shared by final provisioning and the tokenless
# `target-status` role because the contract gives them the same answer vocabulary: the
# target adapter's secret-free commit-status shape, or that one closed failure. The
# `committed_at` member rides `committed` ALONE — the contract makes it non-null exactly
# there, so an `in-progress` carrying it is not a shape this boundary recognizes.
_COMMIT_RESULTS: Final = (
    *(
        _shape(status=status, members=("committed_at",) if status == COMMITTED else ())
        for status in COMMIT_STATUSES
    ),
    _shape(status=_STORE_UNAVAILABLE),
)

# A conditional set's four closed words. `condition-failed` is distinct from `uncommitted`
# on purpose and both are distinct from `unavailable`; the three mean definitively-no-change
# for a stated reason, definitively-no-change, and outcome-unknown.
_CONDITIONAL_SET_RESULTS: Final = tuple(
    _shape(status=status)
    for status in ("committed", "uncommitted", "condition-failed", _UNAVAILABLE)
)

CLOSED_ROLE_RESULTS: Final[dict[tuple[str, str | None], tuple[ClosedResult, ...]]] = {
    ("metadata-reader", "get"): (
        _shape(status="ok", members=("item",)),
        _shape(status="invalid", members=("invalid",)),
        _shape(status=_UNAVAILABLE),
    ),
    ("metadata-reader", "list"): (
        _shape(status="ok", members=("items", "invalid")),
        _shape(status=_UNAVAILABLE),
    ),
    ("lifecycle-writer", None): _CONDITIONAL_SET_RESULTS,
    ("report-writer", None): _CONDITIONAL_SET_RESULTS,
    ("recovery-writer", None): _CONDITIONAL_SET_RESULTS,
    ("final-provisioning", None): _COMMIT_RESULTS,
    ("target-status", None): _COMMIT_RESULTS,
}


def closed_result_defect(
    *, role_name: str, mode: str | None, members: Mapping[str, object]
) -> str | None:
    """Why `members` is not exactly one of this role's closed results, or None when it is.

    The returned phrase is role-free so the caller can name the role once; it is built only
    from this module's own words plus, at most, a status already found in the table.
    """
    shapes = CLOSED_ROLE_RESULTS.get((role_name, mode))
    if shapes is None:
        return None
    status = members.get("status")
    present = frozenset(members) - ENVELOPE_MEMBERS
    recognized = tuple(shape for shape in shapes if shape.status == status)
    if not recognized:
        return "a status outside its closed vocabulary"
    if not any(shape.members == present for shape in recognized):
        # `status` is quoted only HERE, after the table recognized it: by this point the
        # word came from `CLOSED_ROLE_RESULTS`, not from the child.
        return (
            f"a result with status {recognized[0].status} whose members "
            "are not that shape's exact members"
        )
    return None
