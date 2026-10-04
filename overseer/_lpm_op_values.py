"""Final provisioning's value read: the bytes exist here, go to the target, and stop.

SPECIFICATION/contracts.md makes the final provisioning boundary the ONE place in this
operation that legitimately holds a provisionable credential, and then closes every edge of
it: "only after validation may it validate the values-vault namespace item, resolve the exact
`value_ref`, keep the raw bytes confined there and pass them directly to the target adapter's
write call. It MUST return either the target adapter's secret-free commit-status shape or
exactly `{"version":1,"status":"store-unavailable"}` and MUST destroy its in-memory byte
buffer when the call ends; raw bytes MUST NOT cross its input or output boundary."

THE TARGET IS A PORT, which is what makes "pass them directly" checkable. The write is the
only thing this module hands the value to, and it is an argument rather than an import, so
there is no second consumer a refactor could add without changing this signature. Nothing
here logs, returns, re-encodes or stores the bytes.

THE BUFFER THIS MODULE OWNS IS DESTROYED. A `bytearray` is zeroed in a `finally`, so the
copy this process made is gone whether the target committed, refused or raised. The `bytes`
handed across the port is the target's to hold for its own write — Python gives no way to
overwrite an immutable object, and inventing one would be theatre rather than a control.

THE REFERENCE IS JUDGED BEFORE THE VAULT IS OPENED. "`value_ref` MUST be exactly
`op://llm-provider-manager-token-values/<record_id>-<value_generation>/credential` ... The
adapters MUST reject any other reference shape." Both halves are checked: the registered
SHAPE, and that the shape names THIS record and generation. A reference with the right syntax
pointing at another generation would otherwise resolve real bytes for the wrong credential.

AN ABSENT ITEM IS NOT AN EMPTY VALUE AND A DUPLICATE IS NOT CHOSEN BETWEEN. "a values-vault
outage, missing or malformed value, refused permission or SecretStore deadline MUST return
that `store-unavailable` shape before invoking the target adapter's write call." All of those
are one answer to the manager, and this module's job is to make sure none of them can reach
the target as a write.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_launcher import pre_exec_failure_object
from _lpm_onepassword import VALUES_VAULT, value_ref, value_ref_is_registered, values_item_title
from _lpm_op_vault import VaultAccess, namespace_bound_summaries
from _lpm_store import STORE_VERSION
from _lpm_target import CommitOutcome

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "CREDENTIAL_FIELD_LABEL",
    "TargetWrite",
    "ValueReference",
    "commit_status_result",
    "provisioned_credential_result",
]

# "whose only application field is concealed non-empty `credential`". Only, and non-empty:
# an item with a second field is not a generation item this backend wrote, and an empty
# credential is a malformed value rather than a short one.
CREDENTIAL_FIELD_LABEL: Final = "credential"


class TargetWrite(Protocol):
    """The registered `ProvisioningTarget`'s write, called exactly once with the raw bytes."""

    def __call__(self, *, value: bytes) -> CommitOutcome:
        """Atomically write `value` to this reference's destination and report commit status."""
        ...


@dataclass(frozen=True, kw_only=True)
class ValueReference:
    """The three members of this role's input that name one credential generation.

    All three, even though the reference is derivable from the other two. The contract passes
    the boundary a `value_ref` the MANAGER resolved, and comparing it against the derivation
    is the check — a boundary that rebuilt the reference from the pair would agree with itself
    and prove nothing about what it was asked to read.
    """

    record_id: str
    value_generation: str
    value_ref: str


def commit_status_result(*, outcome: CommitOutcome) -> dict[str, object]:
    """The target adapter's secret-free commit-status shape, passed through unchanged.

    `committed_at` rides on ALL THREE statuses because the contract fixes it as "a nullable
    `committed_at` that is non-null exactly for `committed`" — so a definitive no-change is
    `uncommitted` WITH a null commit time, not a shape missing a member.
    """
    return {
        "version": STORE_VERSION,
        "status": outcome.status,
        "committed_at": outcome.committed_at,
    }


def provisioned_credential_result(
    *,
    access: VaultAccess,
    namespace: Mapping[str, str],
    reference: ValueReference,
    write: TargetWrite,
) -> dict[str, object]:
    """Resolve `reference` inside this child and hand its bytes to the target, once."""
    unusable = _reference_defect(reference=reference)
    if unusable is not None:
        return _role_failure(access=access)
    resolved = _resolved_value(access=access, namespace=namespace, reference=reference)
    if isinstance(resolved, Failure):
        return _role_failure(access=access)
    buffer = bytearray(resolved.unwrap().encode("utf-8"))
    try:
        return commit_status_result(outcome=write(value=bytes(buffer)))
    finally:
        # The copy this process owns, destroyed as soon as the call that needed it has
        # ended — whether the target committed, refused or failed.
        buffer[:] = bytes(len(buffer))


def _role_failure(*, access: VaultAccess) -> dict[str, object]:
    """This role's one closed failure object, asked of the module that defines it.

    It is deliberately the SAME object the launcher emits on a pre-exec refusal: the contract
    gives each role exactly one secret-free failure shape, and the distinction between a
    pre-exec and a post-exec `store-unavailable` is carried by whether a child ever existed,
    not by the object. Building a second spelling here would be one more thing to keep equal.
    """
    return pre_exec_failure_object(role_name=access.role.name)


def _reference_defect(*, reference: ValueReference) -> str | None:
    """Why `reference` is not this record's registered generation reference, or None."""
    if not value_ref_is_registered(reference=reference.value_ref):
        return "the value reference does not have the one registered shape"
    expected = value_ref(record_id=reference.record_id, value_generation=reference.value_generation)
    if reference.value_ref != expected:
        return "the value reference names another record or generation"
    return None


def _resolved_value(
    *, access: VaultAccess, namespace: Mapping[str, str], reference: ValueReference
) -> Result[str, str]:
    """The referenced generation's credential, or the shape-only reason there is none.

    The enumeration is what makes the get addressable at all — a get is by ITEM ID, and the
    contract forbids relying on title uniqueness — and it is the same enumeration that proved
    the namespace binding. The role's whole values-vault scope is "`item list`, namespace-item
    `item get` and exact referenced-value `item get` only", which is exactly these three.
    """
    listing = namespace_bound_summaries(access=access, vault=VALUES_VAULT, expected=namespace)
    if isinstance(listing, Failure):
        return listing
    title = values_item_title(
        record_id=reference.record_id, value_generation=reference.value_generation
    )
    matching = [summary for summary in listing.unwrap() if summary.title == title]
    if not matching:
        return Failure("the referenced generation item is absent from the values vault")
    if len(matching) > 1:
        return Failure("the referenced generation item is duplicated in the values vault")
    stored = access.fields(vault=VALUES_VAULT, item_id=matching[0].item_id)
    if isinstance(stored, Failure):
        return stored
    fields = stored.unwrap()
    if sorted(fields) != [CREDENTIAL_FIELD_LABEL] or fields[CREDENTIAL_FIELD_LABEL] == "":
        return Failure("the referenced generation item is not one non-empty credential field")
    return Success(fields[CREDENTIAL_FIELD_LABEL])
