"""One conditional revision, appended by `op item create` alone — or definitively not.

SPECIFICATION/contracts.md makes every conditional write an APPEND to the logical-revision
chain: "A conditional-set whose current logical record equals the desired record in the
exact next revision carrying that effect_id is already committed; an exact expected
predecessor or expected absence permits `op item create` of that one revision; any other
current logical record is `condition-failed`."

APPEND-ONLY IS WHAT MAKES THE CONDITION ENFORCEABLE AT ALL. A mutable item update has no way
to express "replace this only if it still holds exactly what I read", and no backend here may
rely on 1Password item-title uniqueness — so the predecessor digest carries the comparison
instead, and a stale writer's create simply cannot be the next revision. There is therefore
no `edit` anywhere in this module's reach, and none is needed.

THE FOUR ANSWERS ARE FOUR DIFFERENT FACTS, and the order they are asked in is what keeps
them apart. Already-committed first, because a fenced retry must not be mistaken for a
competitor. Then the predecessor comparison, whose failure is `condition-failed` — a
definitive no-change FOR A STATED REASON. Then what this role is permitted to write at all,
whose refusal is `uncommitted` — a definitive no-change, nothing attempted. Only a create
that was attempted and did not report success is `unavailable`, which is the one answer that
means nobody knows and requires authoritative reconciliation.

THE LIFECYCLE FIELD BOUNDARY CAN ONLY LIVE HERE. "A lifecycle-role request that changes any
field other than `status` or `last_validated` MUST be refused, enforcing the externally
observable field boundary independently of 1Password vault permissions." The three lifecycle
roles share one metadata-writer token that CAN write any field in that vault, so a vault
permission cannot express this rule and the adapter's own behaviour has to.

A GENESIS CREATE IS NOT A LIFECYCLE WRITE. Read from the other end, the same rule refuses it:
a record that does not exist yet has no `status` to transition, so "changes no field other
than `status` or `last_validated`" is not something an absent predecessor can satisfy.
Publishing the first metadata revision for a record belongs to the acquisition writer, which
"MUST then conditionally publish matching metadata" after creating its generation item.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_canonical import canonical_json_bytes, parse_canonical_json
from _lpm_onepassword import METADATA_VAULT
from _lpm_op_items import item_create_template
from _lpm_op_metadata import REVISION_FIELD_LABELS, metadata_chains
from _lpm_op_vault import VaultAccess
from _lpm_record import (
    RECORD_MEMBERS,
    CredentialRecord,
    credential_record_from_object,
    record_object,
)
from _lpm_revisions import (
    FIRST_REVISION,
    ChainResolution,
    predecessor_digest,
    resolve_chain,
    revision_title,
)
from _lpm_roles import LIFECYCLE_ROLES, CredentialRole
from _lpm_store import ConditionalSet, already_committed, set_result

from overseer._vendor.returns.result import Failure

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "LIFECYCLE_MUTABLE_FIELDS",
    "conditional_set_answer",
    "lifecycle_boundary_defect",
]

LIFECYCLE_MUTABLE_FIELDS: Final = ("status", "last_validated")


def conditional_set_answer(
    *, access: VaultAccess, namespace: Mapping[str, str], request: ConditionalSet
) -> dict[str, object]:
    """Append `request`'s one revision, or report which of the four facts holds instead.

    The chain is re-read here rather than taken from the caller, because the comparison has
    to be against what the backend holds NOW: "Every metadata record read-modify-write MUST
    serialize through the owner-only per-record lock, re-read the complete logical chain
    after taking the lock and append only the next revision." An INVALID chain refuses every
    mutation for that record — "a mutation targeting it MUST return `store-unavailable`" —
    rather than being repaired by appending over it.
    """
    chains = metadata_chains(access=access, namespace=namespace, record_id=request.record_id)
    if isinstance(chains, Failure):
        return set_result(status="unavailable")
    resolved = resolve_chain(
        record_id=request.record_id, items=chains.unwrap().items.get(request.record_id, [])
    )
    if resolved.reason is not None:
        return set_result(status="unavailable")
    return _appended(access=access, request=request, resolved=resolved)


def lifecycle_boundary_defect(
    *, role: CredentialRole, current: str | None, desired: str
) -> str | None:
    """Why this role may not replace `current` with `desired`, or None when it may.

    Only a lifecycle role is bounded. The acquisition writer publishes whole records, and a
    non-writer role never reaches a mutation at all, so a check that applied to everything
    would be refusing writes the contract grants.

    The reason NAMES THE FIELD, and that name comes from `RECORD_MEMBERS` rather than from
    the request: a record is secret-free by construction, but its reason reaches a manager
    log, and a diagnostic built only from manager-owned words cannot carry anything else.
    """
    if role.name not in LIFECYCLE_ROLES:
        return None
    if current is None:
        return f"{role.name} may not create a record that does not exist yet"
    before = _parsed_record(text=current)
    after = _parsed_record(text=desired)
    if before is None or after is None:
        return f"{role.name} must write two complete credential records"
    outside = [
        member
        for member in RECORD_MEMBERS
        if member not in LIFECYCLE_MUTABLE_FIELDS
        and record_object(record=before)[member] != record_object(record=after)[member]
    ]
    if outside:
        return f"{role.name} may not change {outside[0]}"
    return None


def _appended(
    *, access: VaultAccess, request: ConditionalSet, resolved: ChainResolution
) -> dict[str, object]:
    """Decide this write against the chain just read, and create the one revision it permits."""
    current_item = resolved.item
    current = None if current_item is None else current_item.record
    if current_item is not None and already_committed(
        item=current_item, revision=resolved.revision or FIRST_REVISION, request=request
    ):
        # The desired record IS the current logical revision, in the exact revision carrying
        # this effect id. A fenced retry lands here and appends nothing.
        return set_result(status="committed")
    if current != request.expected_record:
        return set_result(status="condition-failed")
    bounded = lifecycle_boundary_defect(
        role=access.role, current=current, desired=request.desired_record
    )
    if bounded is not None:
        return set_result(status="uncommitted")
    body = canonical_json_bytes(
        value=item_create_template(
            title=revision_title(
                record_id=request.record_id,
                revision=FIRST_REVISION if resolved.revision is None else resolved.revision + 1,
                effect_id=request.effect_id,
            ),
            fields={
                REVISION_FIELD_LABELS[0]: predecessor_digest(record=current),
                REVISION_FIELD_LABELS[1]: request.desired_record,
            },
        )
    )
    if isinstance(body, Failure):
        # A desired record no encoder can reproduce — a lone surrogate has no UTF-8 encoding
        # at all — was never streamable, so nothing was attempted and the no-change is
        # DEFINITIVE. Reporting it unknown would send a reconciler after a create that never
        # reached a child.
        return set_result(status="uncommitted")
    unfinished = access.create(vault=METADATA_VAULT, template_bytes=body.unwrap())
    if unfinished is not None:
        return set_result(status="unavailable")
    return set_result(status="committed")


def _parsed_record(*, text: str) -> CredentialRecord | None:
    """One canonical record text as a complete credential record, or None when it is not one.

    The two ways it can fail are collapsed deliberately: this function exists only to answer
    "can these two be compared field by field", and both answers to that are no. Where the
    DISTINCTION matters — a stored record that will not parse versus one that parses and
    violates an invariant — it is drawn by the reader that owns the record, not here.
    """
    parsed = parse_canonical_json(text=text)
    if isinstance(parsed, Failure):
        return None
    record = credential_record_from_object(parsed=parsed.unwrap())
    if isinstance(record, Failure):
        return None
    return record.unwrap()
