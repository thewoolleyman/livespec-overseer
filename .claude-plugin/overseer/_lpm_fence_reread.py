"""The authoritative reread that decides a fenced conditional-set, against the real store.

SPECIFICATION/contracts.md requires that after a deadline, interruption, unavailable transport or
malformed adapter result the manager BYPASS EVERY CACHE and authoritatively reread the complete
metadata revision chain before deciding the effect: an exact desired next revision CARRYING THAT
`effect_id` proves the logical effect committed and advances it without another adapter call,
while the exact expected predecessor or expected absence proves only that no desired revision was
visible by that reread.

"CARRYING THAT EFFECT_ID" IS WHY THE TITLE IS COMPARED AND NOT ONLY THE BYTES. Two different
effects can desire byte-identical records — a lifecycle transition retried under a new operation
desires the same `suspect` record its predecessor did — so matching record bytes alone would let
one effect claim another's revision as proof of its own commit. The fence's `item_title` already
encodes record id, revision and effect id, so comparing it IS the contract's test.

AN UNAVAILABLE OR INVALID CHAIN IS `unreadable`, NOT `absent`. This is the one classification that
must not be collapsed: absence is a defined ANSWER that can prove expected-absence still holds,
while a backend that did not answer proves nothing at all. Mapping the second onto the first would
let a reread that failed authorize a create.

A STORE STATUS OF `unavailable` MAPS TO THE CONTRACT'S `unknown`, and so does any status this
module does not recognize. The contract's unknown bucket is "deadline, interruption, unavailable
transport or malformed adapter result" — all the ways nobody can say what happened — and an
unrecognized status is exactly that, so the conservative mapping is the correct one rather than a
defensive one.

THE RETRY MAY ISSUE ONLY THE BYTE-IDENTICAL REVISION, which is why the request is built FROM THE
FENCE rather than from whatever the caller still holds in memory. The fence is what survives the
crash; building the request from anything else is how a retry comes to append a revision nobody
authorized.
"""

from __future__ import annotations

from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_canonical import canonical_json_text
from _lpm_fence import MetadataFence
from _lpm_fence_recovery import DESIRED_REVISION, FenceDecision, reconcile_conditional_set
from _lpm_results import ManagerError, internal_bug
from _lpm_store import ConditionalSet, SecretStore

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "ADAPTER_OUTCOME_BY_STATUS",
    "apply_fenced_set",
    "authoritative_reread",
    "conditional_set_request",
]

_EXPECTED: Final = "expected"
_ABSENT: Final = "absent"
_DIFFERENT: Final = "different"
_UNREADABLE: Final = "unreadable"

_UNKNOWN_OUTCOME: Final = "unknown"
ADAPTER_OUTCOME_BY_STATUS: Final[dict[str, str]] = {
    "committed": "committed",
    "condition-failed": "condition-failed",
    "uncommitted": "uncommitted",
    "unavailable": _UNKNOWN_OUTCOME,
}


def conditional_set_request(*, fence: MetadataFence) -> Result[ConditionalSet, ManagerError]:
    """The one request `fence` authorizes, built from the fence's own stored records."""
    desired = canonical_json_text(value=fence.desired_record)
    if isinstance(desired, Failure):
        return Failure(internal_bug(message="a fenced desired record is not encodable"))
    expected = _expected_text(fence=fence)
    if isinstance(expected, Failure):
        return expected
    return Success(
        ConditionalSet(
            record_id=fence.record_id,
            effect_id=fence.effect_id,
            expected_record=expected.unwrap(),
            desired_record=desired.unwrap(),
        )
    )


def authoritative_reread(*, store: SecretStore, fence: MetadataFence) -> str:
    """Classify the record's current authoritative revision against `fence`.

    Every cache is bypassed by construction: this asks the store itself, and the three answers
    that matter — the desired revision, the expected predecessor, something else — are
    distinguished before any decision is taken.
    """
    result = store.metadata_get(record_id=fence.record_id)
    if result.get("status") != "ok":
        return _UNREADABLE
    item = result.get("item")
    if item is None:
        return _ABSENT if fence.expected_record is None else _DIFFERENT
    if not isinstance(item, dict):
        return _UNREADABLE
    envelope = cast("dict[str, object]", item)
    return _classified(fence=fence, envelope=envelope)


def apply_fenced_set(
    *, store: SecretStore, fence: MetadataFence, created_from_absence: bool
) -> Result[FenceDecision, ManagerError]:
    """Issue `fence`'s one authorized revision, then decide it from an authoritative reread.

    The reread happens on EVERY path, not only after an unknown result. A definitive
    `condition-failed` from a call that inherited the fence is inconclusive, and a `committed`
    acknowledgement is still only an acknowledgement — so the decision is always taken against
    what the store can be read to hold, never against what it said.
    """
    request = conditional_set_request(fence=fence)
    if isinstance(request, Failure):
        return request
    status = store.credential_conditional_set(request=request.unwrap()).get("status")
    outcome = ADAPTER_OUTCOME_BY_STATUS.get(str(status), _UNKNOWN_OUTCOME)
    return reconcile_conditional_set(
        adapter_outcome=outcome,
        created_from_absence=created_from_absence,
        reread=authoritative_reread(store=store, fence=fence),
    )


def _classified(*, fence: MetadataFence, envelope: dict[str, object]) -> str:
    desired = canonical_json_text(value=fence.desired_record)
    if isinstance(desired, Failure):
        return _UNREADABLE
    if envelope.get("item_id") == fence.item_title and envelope.get("record") == desired.unwrap():
        return DESIRED_REVISION
    expected = _expected_text(fence=fence)
    if isinstance(expected, Failure):
        return _UNREADABLE
    stored = expected.unwrap()
    if stored is not None and envelope.get("record") == stored:
        return _EXPECTED
    return _DIFFERENT


def _expected_text(*, fence: MetadataFence) -> Result[str | None, ManagerError]:
    if fence.expected_record is None:
        return Success(None)
    encoded = canonical_json_text(value=fence.expected_record)
    if isinstance(encoded, Failure):
        return Failure(internal_bug(message="a fenced expected record is not encodable"))
    return Success(encoded.unwrap())
