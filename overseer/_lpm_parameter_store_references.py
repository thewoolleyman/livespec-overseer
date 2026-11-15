"""Validated Parameter Store reference entries: where a value lives, never the value.

Proposed in SPECIFICATION/proposed_changes/lpm-parameter-store-reference-records.md
(the configuration-and-state contract in
SPECIFICATION/contracts.md). Under the `parameter-store-reference` backend
the manager stores no credential value at all. Each configured entry names one canonical
Parameter Store slot that only the fleet's dedicated writer writes, and the manager reads
that slot only at provision time through the host's declared reader route.

THIS MODULE ONLY VALIDATES THE SHAPE, and it is deliberately not yet wired into
`_lpm_config`. Accepting the backend name in configuration before the runtime can honour
it would let a configuration choose `parameter-store-reference` and then silently run the
1Password ports, which is worse than refusing. The backend is registered in the slice
that also gives the runtime its reference store.

THE ENTRY'S MEMBER SET IS CLOSED IN BOTH DIRECTIONS, for the same reason the provisioning
request's is. An extra member is refused rather than ignored. The one an operator is most
likely to add by mistake is the value itself, and accepting it silently would put a
credential into a configuration file that is supposed to hold only references.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_registry import provider_row
from _lpm_results import ManagerError, invalid_request

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "PARAMETER_STORE_REFERENCE_BACKEND",
    "REFERENCE_MEMBERS",
    "ParameterStoreReference",
    "references_from_object",
    "value_ref_for",
]

PARAMETER_STORE_REFERENCE_BACKEND: Final = "parameter-store-reference"
_KEY: Final = "parameter_store_references"
_ACCOUNT_ID: Final = re.compile(r"[0-9]{12}")

REFERENCE_MEMBERS: Final = (
    "provider",
    "account_id",
    "kind",
    "purpose",
    "source_account",
    "region",
    "parameter_name",
    "reader_manifest",
    "reader_consumer",
)


@dataclass(frozen=True, kw_only=True)
class ParameterStoreReference:
    """One accepted entry: a record identity and the slot that holds its value."""

    provider: str
    account_id: str
    kind: str
    purpose: str
    source_account: str
    region: str
    parameter_name: str
    reader_manifest: str
    reader_consumer: str

    def identity(self) -> tuple[str, str, str, str]:
        """The four fields that together name one credential record."""
        return (self.provider, self.account_id, self.kind, self.purpose)


def value_ref_for(*, reference: ParameterStoreReference) -> str:
    """The record's `value_ref`: the slot's location, never its contents."""
    return (
        f"parameter-store:{reference.source_account}:{reference.region}:"
        f"{reference.parameter_name}"
    )


def references_from_object(
    *, value: object, backend: str
) -> Result[tuple[ParameterStoreReference, ...], ManagerError]:
    """Validate the configured list, refusing at the first defect it finds."""
    if not isinstance(value, list):
        return Failure(invalid_request(message=f"{_KEY} must be an array"))
    entries = cast("list[object]", value)
    if entries and backend != PARAMETER_STORE_REFERENCE_BACKEND:
        return Failure(
            invalid_request(
                message=f"{_KEY} requires secret_store_backend "
                f"{PARAMETER_STORE_REFERENCE_BACKEND}"
            )
        )
    accepted: list[ParameterStoreReference] = []
    seen: set[tuple[str, str, str, str]] = set()
    for index, entry in enumerate(entries):
        reference = _reference_from_entry(entry=entry, label=f"{_KEY}[{index}]")
        if isinstance(reference, Failure):
            return reference
        identity = reference.unwrap().identity()
        if identity in seen:
            return Failure(
                invalid_request(
                    message=f"{_KEY}[{index}] duplicates the identity of an earlier entry"
                )
            )
        seen.add(identity)
        accepted.append(reference.unwrap())
    return Success(tuple(accepted))


def _reference_from_entry(
    *, entry: object, label: str
) -> Result[ParameterStoreReference, ManagerError]:
    if not isinstance(entry, dict):
        return Failure(invalid_request(message=f"{label} must be an object"))
    members = cast("dict[str, object]", entry)
    for name in REFERENCE_MEMBERS:
        if name not in members:
            return Failure(invalid_request(message=f"{label} is missing member: {name}"))
    unknown = sorted(set(members) - set(REFERENCE_MEMBERS))
    if unknown:
        return Failure(invalid_request(message=f"{label} has unknown member: {unknown[0]}"))
    for name in REFERENCE_MEMBERS:
        field = members[name]
        if not isinstance(field, str) or not field:
            return Failure(invalid_request(message=f"{label}.{name} must be a non-empty string"))
    fields = cast("dict[str, str]", members)
    refusal = _field_refusal(fields=fields, label=label)
    if refusal is not None:
        return Failure(refusal)
    return Success(ParameterStoreReference(**fields))


def _field_refusal(*, fields: dict[str, str], label: str) -> ManagerError | None:
    if _ACCOUNT_ID.fullmatch(fields["source_account"]) is None:
        return invalid_request(message=f"{label}.source_account must be a 12-digit AWS account id")
    for name in ("parameter_name", "reader_manifest"):
        if not fields[name].startswith("/"):
            return invalid_request(message=f"{label}.{name} must be absolute")
    if provider_row(provider=fields["provider"], kind=fields["kind"]) is None:
        return invalid_request(
            message=f"{label} names an unregistered provider and kind: "
            f"{fields['provider']} {fields['kind']}"
        )
    return None
