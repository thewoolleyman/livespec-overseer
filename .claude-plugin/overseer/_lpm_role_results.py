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
from _lpm_record import is_uuid4
from _lpm_revisions import INVALID_CHAIN_REASONS
from _lpm_target import COMMIT_STATUSES, COMMITTED

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "CLOSED_ROLE_RESULTS",
    "CONDITIONAL_SET_MODE",
    "COVERED_ROLE_NAMES",
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
# target adapter's secret-free commit-status shape, or that one closed failure.
#
# `committed_at` is a member of ALL THREE commit shapes, not just `committed`. The contract
# fixes it as "a nullable `committed_at` that is non-null exactly for `committed`", and
# `_lpm_target.CommitOutcome` carries it unconditionally as `str | None` — so the shape a
# real adapter produces for a definitive no-change is `uncommitted` WITH `committed_at:
# null`. Giving the member to `committed` alone rejected exactly that, collapsing the
# distinction the three words exist to draw. Whether the value may be null is a separate
# rule, enforced below rather than by the member set.
_COMMIT_RESULTS: Final = (
    *(_shape(status=status, members=("committed_at",)) for status in COMMIT_STATUSES),
    _shape(status=_STORE_UNAVAILABLE),
)

# The one mode each lifecycle writer's request carries. The contract has those three roles
# receive "exactly the latter conditional-set object", whose `mode` is this, so their results
# are keyed on it. Keying them on NO mode made every valid writer request miss the table
# entirely and go unvalidated.
CONDITIONAL_SET_MODE: Final = "credential-conditional-set"

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
    ("lifecycle-writer", CONDITIONAL_SET_MODE): _CONDITIONAL_SET_RESULTS,
    ("report-writer", CONDITIONAL_SET_MODE): _CONDITIONAL_SET_RESULTS,
    ("recovery-writer", CONDITIONAL_SET_MODE): _CONDITIONAL_SET_RESULTS,
    # Modeless by contract: the final-provisioning and `target-status` inputs are the exact
    # objects their own paragraphs define, and neither carries a `mode` member.
    ("final-provisioning", None): _COMMIT_RESULTS,
    ("target-status", None): _COMMIT_RESULTS,
}


COVERED_ROLE_NAMES: Final = frozenset(name for name, _ in CLOSED_ROLE_RESULTS)


def _commit_dating_defect(*, status: object, members: Mapping[str, object]) -> str | None:
    """Whether `committed_at` is non-null exactly for `committed`, or None when not applicable.

    A `committed` with a null stamp claims a commit while withholding the fence sample that
    dates it; a non-null stamp on any other status dates a commit that did not happen. The
    member being PRESENT is a shape question and lives in the table; whether it may hold a
    value is this rule, because the same member name is legal either way.
    """
    if "committed_at" not in members or status not in COMMIT_STATUSES:
        return None
    committed = status == COMMITTED
    if committed and members["committed_at"] is None:
        return "a committed result with no commit time"
    if not committed and members["committed_at"] is not None:
        return "a non-committed result carrying a commit time"
    return None


_ITEM_ENVELOPE_MEMBERS: Final = frozenset({"item_id", "record"})
_DESCRIPTOR_MEMBERS: Final = frozenset({"record_id", "reason"})

# Which members carry a nested shape, and the checker that closes it. `record` is NOT in
# here: the contract has the manager apply the credential-record field and invariant checks
# only after receiving the envelope, so closing it twice would put one rule in two places.
_NESTED_MEMBERS: Final = ("item", "invalid", "items")


def _item_envelope_defect(*, value: object) -> str | None:
    """Whether `value` is exactly a non-empty `item_id` plus a `record`, or null absence."""
    if value is None:
        return None
    if not isinstance(value, dict):
        return "an item that is not an object"
    members: dict[str, object] = value
    if frozenset(members) != _ITEM_ENVELOPE_MEMBERS:
        return "an item envelope whose members are not exactly item_id and record"
    item_id = members["item_id"]
    if not isinstance(item_id, str) or not item_id:
        return "an item envelope whose item_id is not a non-empty string"
    return None


def _descriptor_defect(*, value: object) -> str | None:
    """Whether `value` is exactly a lowercase UUIDv4 `record_id` plus a registered `reason`."""
    if not isinstance(value, dict):
        return "an invalid-chain descriptor that is not an object"
    members: dict[str, object] = value
    if frozenset(members) != _DESCRIPTOR_MEMBERS:
        return "an invalid-chain descriptor whose members are not exactly record_id and reason"
    record_id = members["record_id"]
    if not isinstance(record_id, str) or not is_uuid4(value=record_id):
        return "an invalid-chain descriptor whose record_id is not a lowercase UUIDv4"
    if members["reason"] not in INVALID_CHAIN_REASONS:
        return "an invalid-chain descriptor whose reason is not a registered one"
    return None


def _nested_defect(*, name: str, value: object) -> str | None:
    """Close whichever nested shape `name` carries, including every element of a list."""
    if name == "item":
        return _item_envelope_defect(value=value)
    if name == "invalid" and not isinstance(value, list):
        # `invalid` carries ONE descriptor on a get result and a LIST of them on a list
        # result, so the member name alone does not say which; the list check does.
        return _descriptor_defect(value=value)
    if not isinstance(value, list):
        return f"a {name} member that is not a list"
    elements: list[object] = value
    for element in elements:
        defect = (
            _item_envelope_defect(value=element)
            if name == "items"
            else _descriptor_defect(value=element)
        )
        if defect is not None:
            return defect
    return None


def _nested_shapes_defect(*, members: Mapping[str, object]) -> str | None:
    """The first nested-shape defect among the members that carry one, or None."""
    for name in _NESTED_MEMBERS:
        if name in members:
            defect = _nested_defect(name=name, value=members[name])
            if defect is not None:
                return defect
    return None


def closed_result_defect(
    *, role_name: str, mode: str | None, members: Mapping[str, object]
) -> str | None:
    """Why `members` is not exactly one of this role's closed results, or None when it is.

    The returned phrase is role-free so the caller can name the role once; it is built only
    from this module's own words plus, at most, a status already found in the table.
    """
    shapes = CLOSED_ROLE_RESULTS.get((role_name, mode))
    if shapes is not None:
        return _result_defect(shapes=shapes, members=members)
    if role_name in COVERED_ROLE_NAMES:
        # The not-covered answer below is right for a role this slice does not implement,
        # where refusing everything would be worse than not validating. It is exactly WRONG
        # for an unrecognized mode of a role that IS covered: that would make the role whose
        # results are closed the one whose results are waved through, turning a guard against
        # over-refusing into one that under-refuses.
        return "a mode outside its closed inputs"
    return None


def _result_defect(
    *, shapes: tuple[ClosedResult, ...], members: Mapping[str, object]
) -> str | None:
    """The first way `members` departs from `shapes`, checked outermost-first.

    Status before members before nested shapes, because each answer is only meaningful once
    the previous one holds: there is no "exact members for this status" until the status is
    one this role has, and no envelope to close until the member carrying it is expected.
    """
    status = members.get("status")
    recognized = tuple(shape for shape in shapes if shape.status == status)
    if not recognized:
        return "a status outside its closed vocabulary"
    dated = _commit_dating_defect(status=status, members=members)
    if dated is not None:
        return dated
    if not any(shape.members == frozenset(members) - ENVELOPE_MEMBERS for shape in recognized):
        # `status` is quoted only HERE, after the table recognized it: by this point the
        # word came from `CLOSED_ROLE_RESULTS`, not from the child.
        return (
            f"a result with status {recognized[0].status} whose members "
            "are not that shape's exact members"
        )
    return _nested_shapes_defect(members=members)
