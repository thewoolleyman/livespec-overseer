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

A MEMBER NAME DOES NOT DETERMINE ITS NESTED SHAPE — the role, mode and status do. `invalid`
is ONE descriptor object on a metadata get and an ARRAY of them on a list; `item` is
nullable because null asserts authoritative absence, while an element of `items` is not,
because a list of records has nothing to be absent. Each nested expectation therefore hangs
off the specific `ClosedResult` rather than off the name, which is the only arrangement in
which those three distinctions can be stated at all.

THE ENVELOPE CLOSES HERE; THE RECORD DOES NOT. Which statuses a role may answer with,
precisely which members each status carries, and what KIND each of those members must be
are decided here. The contents of a `record` are NOT: the contract places those after this
boundary — "the manager applies the credential-record field and invariant checks only after
receiving that envelope" — and duplicating them here would put one rule in two places that
can disagree.

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
from dataclasses import dataclass, field
from typing import Final, Protocol

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_record import is_uuid4
from _lpm_revisions import INVALID_CHAIN_REASONS
from _lpm_target import COMMIT_STATUSES, COMMITTED
from _lpm_time import is_canonical_timestamp

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

_ITEM_ENVELOPE_MEMBERS: Final = frozenset({"item_id", "record"})
_DESCRIPTOR_MEMBERS: Final = frozenset({"record_id", "reason"})

# The nested KINDS a shape may require of one of its members. Named rather than inferred,
# because the same member name means a different kind in a different shape.
_NULLABLE_ENVELOPE: Final = "nullable-envelope"
_ENVELOPE_ARRAY: Final = "envelope-array"
_DESCRIPTOR: Final = "descriptor"
_DESCRIPTOR_ARRAY: Final = "descriptor-array"
_COMMIT_TIME: Final = "commit-time"
_ABSENT_VALUE: Final = "absent-value"


@dataclass(frozen=True, kw_only=True)
class ClosedResult:
    """One permitted result: its status, its EXACT members, and each member's nested kind.

    `members` is exact in both directions — a missing member and an extra one are the same
    defect, because a shape is the whole object rather than a minimum.

    `nested` maps a member to the kind its value must be. It lives here rather than beside
    the member name because the name does not determine the kind: `invalid` is one
    descriptor on a get and an array of them on a list, and `item` is nullable while an
    element of `items` is not.
    """

    status: str
    members: frozenset[str]
    nested: Mapping[str, str] = field(default_factory=dict)


def _shape(
    *, status: str, members: tuple[str, ...] = (), nested: Mapping[str, str] | None = None
) -> ClosedResult:
    return ClosedResult(
        status=status, members=frozenset(members), nested={} if nested is None else nested
    )


# A commit status plus `store-unavailable`, shared by final provisioning and the tokenless
# `target-status` role because the contract gives them the same answer vocabulary: the
# target adapter's secret-free commit-status shape, or that one closed failure.
#
# `committed_at` is a member of ALL THREE commit shapes, not just `committed`. The contract
# fixes it as "a nullable `committed_at` that is non-null exactly for `committed`", and
# `_lpm_target.CommitOutcome` carries it unconditionally as `str | None` — so the shape a
# real adapter produces for a definitive no-change is `uncommitted` WITH `committed_at:
# null`. Which VALUE each status may carry is the nested kind rather than the member set: a
# commit must be dated by a canonical timestamp, every other status by nothing at all.
_COMMIT_RESULTS: Final = (
    *(
        _shape(
            status=status,
            members=("committed_at",),
            nested={"committed_at": _COMMIT_TIME if status == COMMITTED else _ABSENT_VALUE},
        )
        for status in COMMIT_STATUSES
    ),
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
        _shape(status="ok", members=("item",), nested={"item": _NULLABLE_ENVELOPE}),
        _shape(status="invalid", members=("invalid",), nested={"invalid": _DESCRIPTOR}),
        _shape(status=_UNAVAILABLE),
    ),
    ("metadata-reader", "list"): (
        _shape(
            status="ok",
            members=("items", "invalid"),
            nested={"items": _ENVELOPE_ARRAY, "invalid": _DESCRIPTOR_ARRAY},
        ),
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


class _NestedChecker(Protocol):
    """One nested-kind checker: a secret-free reason, or None when the value is that kind."""

    def __call__(self, *, value: object) -> str | None: ...


def _envelope_defect(*, value: object) -> str | None:
    """Whether `value` is exactly a non-empty `item_id` plus a `record`.

    Deliberately NOT nullable. Null is meaningful only for the single `item` member, where
    it asserts authoritative absence; an element of `items` has nothing to be absent, so
    reusing a nullable checker for array elements let `items: [null]` pass as a record.
    """
    if not isinstance(value, dict):
        return "an item envelope that is not an object"
    members: dict[str, object] = value
    if frozenset(members) != _ITEM_ENVELOPE_MEMBERS:
        return "an item envelope whose members are not exactly item_id and record"
    item_id = members["item_id"]
    if not isinstance(item_id, str) or not item_id:
        return "an item envelope whose item_id is not a non-empty string"
    return None


def _nullable_envelope_defect(*, value: object) -> str | None:
    """The single `item` member: authoritative absence, or exactly one envelope."""
    return None if value is None else _envelope_defect(value=value)


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


def _array_defect(*, value: object, element: _NestedChecker, named: str) -> str | None:
    """Whether `value` is an array whose every element satisfies `element`.

    An EMPTY array is legal — a list result with nothing to report is still a list result.
    What is never legal is a non-array, which is how a bare descriptor object came to pass
    for a member the list shape requires to be an array.
    """
    if not isinstance(value, list):
        return f"a {named} member that is not an array"
    elements: list[object] = value
    for member in elements:
        defect = element(value=member)
        if defect is not None:
            return defect
    return None


def _envelope_array_defect(*, value: object) -> str | None:
    """The `items` member: an array of envelopes, with no element absent."""
    return _array_defect(value=value, element=_envelope_defect, named="items")


def _descriptor_array_defect(*, value: object) -> str | None:
    """A list result's `invalid` member: an array of descriptors, never a bare one."""
    return _array_defect(value=value, element=_descriptor_defect, named="invalid")


def _commit_time_defect(*, value: object) -> str | None:
    """Whether a commit's `committed_at` is a canonical UTC RFC 3339-second timestamp.

    Non-null alone is not enough. The contract requires this value to EQUAL the adapter's
    final lease-fence sample, which a later reconciler compares against stored timestamps,
    so `123` or `"nope"` dates a commit nobody can verify. The canonical spelling is asked
    of `_lpm_time`, whose own `capture_manager_time` produces it, rather than re-derived.

    ABSENT and MALFORMED stay separate findings. Null says the adapter reported no fence
    sample at all; a present-but-uncanonical value says it reported one that nothing can
    compare. Both refuse, but a reader chasing an unverifiable commit needs to know which.
    """
    if value is None:
        return "a committed result with no commit time"
    if not isinstance(value, str) or not is_canonical_timestamp(text=value):
        return "a committed result whose commit time is not a canonical UTC timestamp"
    return None


def _absent_value_defect(*, value: object) -> str | None:
    """Whether a member this shape requires to be null actually is."""
    return None if value is None else "a non-committed result carrying a commit time"


_NESTED_CHECKERS: Final[dict[str, _NestedChecker]] = {
    _NULLABLE_ENVELOPE: _nullable_envelope_defect,
    _ENVELOPE_ARRAY: _envelope_array_defect,
    _DESCRIPTOR: _descriptor_defect,
    _DESCRIPTOR_ARRAY: _descriptor_array_defect,
    _COMMIT_TIME: _commit_time_defect,
    _ABSENT_VALUE: _absent_value_defect,
}


def _nested_shapes_defect(*, shape: ClosedResult, members: Mapping[str, object]) -> str | None:
    """The first nested defect in the shape that MATCHED, or None.

    Reached only after the member set matched exactly, so every name in `shape.nested` is
    present in `members` and no lookup here can miss.
    """
    for name, kind in shape.nested.items():
        defect = _NESTED_CHECKERS[kind](value=members[name])
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

    Status, then members, then each member's nested kind — because each answer is only
    meaningful once the previous one holds. There is no "exact members for this status"
    until the status is one this role has, and no envelope to close until the member
    carrying it is one this shape expects.
    """
    status = members.get("status")
    recognized = tuple(shape for shape in shapes if shape.status == status)
    if not recognized:
        return "a status outside its closed vocabulary"
    present = frozenset(members) - ENVELOPE_MEMBERS
    matched = tuple(shape for shape in recognized if shape.members == present)
    if not matched:
        # `status` is quoted only HERE, after the table recognized it: by this point the
        # word came from `CLOSED_ROLE_RESULTS`, not from the child.
        return (
            f"a result with status {recognized[0].status} whose members "
            "are not that shape's exact members"
        )
    return _nested_shapes_defect(shape=matched[0], members=members)
