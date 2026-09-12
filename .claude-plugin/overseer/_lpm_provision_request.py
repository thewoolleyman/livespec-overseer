"""The exact provisioning request, and the normalized form request identity is judged on.

SPECIFICATION/contracts.md fixes the request as exactly `version` (the integer `1`), non-empty
`provider`, `kind`, `purpose`, `consumer_run_id` and `target_ref`, an optional `strategy`
(`consume-first` or `spread`, default `consume-first`) and an optional integer
`lease_seconds` (default `21600`, minimum `60`, maximum `86400`). The NORMALIZED request is
that exact object after materializing both optional defaults, and `identical`, `same logical
request` and `exact request` all mean field-for-field equality of normalized requests.

NORMALIZATION IS WHY THIS IS A SEPARATE CONCERN FROM THE COMMAND. Idempotent replay, the
tombstone reuse refusal and the pending-operation refusal are all stated in terms of whether
two requests are the same LOGICAL request — a question about the request object alone, asked
before any store, lease or target is touched. Keeping the answer here means the boundary next
door never has to re-derive it, and means the equality that gates replay is defined in one
place rather than spelled out at each refusal.

THE MEMBER SET IS CLOSED IN BOTH DIRECTIONS. A missing required member and an unrecognized
extra member are the same refusal, because the contract says the request contains ONLY those
members: a consumer that sends an extra field is sending a request this version cannot
honour, and accepting it silently would mean honouring something other than what was asked.

`lease_seconds` IS RANGE-CHECKED HERE, NOT CLAMPED. The contract puts that range inside exact
provisioning-object validation, refused with `invalid-request` BEFORE recovery, target
validation, selection or lease acquisition. Clamping would hand the consumer a lease it never
asked for and report success.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_leases import lease_seconds_field
from _lpm_results import ManagerError, invalid_request
from _lpm_strategy import strategy_field

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "PROVISION_OPTIONAL_MEMBERS",
    "PROVISION_REQUIRED_MEMBERS",
    "PROVISION_VERSION",
    "ProvisionRequest",
    "provision_request_from_object",
    "provision_request_object",
]

PROVISION_VERSION: Final = 1

PROVISION_REQUIRED_MEMBERS: Final = (
    "version",
    "provider",
    "kind",
    "purpose",
    "consumer_run_id",
    "target_ref",
)
PROVISION_OPTIONAL_MEMBERS: Final = ("strategy", "lease_seconds")


@dataclass(frozen=True, kw_only=True)
class ProvisionRequest:
    """One normalized provisioning request: both optional members already materialized."""

    provider: str
    kind: str
    purpose: str
    consumer_run_id: str
    target_ref: str
    strategy: str
    lease_seconds: int


def provision_request_from_object(*, parsed: object) -> Result[ProvisionRequest, ManagerError]:
    """Validate and normalize one decoded provisioning request."""
    if not isinstance(parsed, dict):
        return Failure(invalid_request(message="provisioning request must be a JSON object"))
    source = cast("dict[str, object]", parsed)
    permitted = set(PROVISION_REQUIRED_MEMBERS) | set(PROVISION_OPTIONAL_MEMBERS)
    if not set(PROVISION_REQUIRED_MEMBERS) <= set(source) or not set(source) <= permitted:
        return Failure(
            invalid_request(
                message=(
                    f"provisioning request carries {', '.join(PROVISION_REQUIRED_MEMBERS)} "
                    f"and optionally {', '.join(PROVISION_OPTIONAL_MEMBERS)}"
                )
            )
        )
    version = source["version"]
    if isinstance(version, bool) or version != PROVISION_VERSION:
        return Failure(
            invalid_request(message="provisioning request version must be the integer 1")
        )
    for member in PROVISION_REQUIRED_MEMBERS[1:]:
        value = source[member]
        if not isinstance(value, str) or value == "":
            return Failure(
                invalid_request(message=f"provisioning request {member} must be a non-empty string")
            )
    return _normalized(source=source)


def provision_request_object(*, request: ProvisionRequest) -> dict[str, object]:
    """The normalized request as an object: field-for-field equality is request identity."""
    values: dict[str, object] = {"version": PROVISION_VERSION}
    for member in PROVISION_REQUIRED_MEMBERS[1:] + PROVISION_OPTIONAL_MEMBERS:
        values[member] = getattr(request, member)
    return values


def _normalized(*, source: dict[str, object]) -> Result[ProvisionRequest, ManagerError]:
    strategy = strategy_field(value=source.get("strategy"))
    if isinstance(strategy, Failure):
        return Failure(strategy.failure())
    seconds = lease_seconds_field(value=source.get("lease_seconds"))
    if isinstance(seconds, Failure):
        return Failure(seconds.failure())
    return Success(
        ProvisionRequest(
            provider=str(source["provider"]),
            kind=str(source["kind"]),
            purpose=str(source["purpose"]),
            consumer_run_id=str(source["consumer_run_id"]),
            target_ref=str(source["target_ref"]),
            strategy=strategy.unwrap(),
            lease_seconds=seconds.unwrap(),
        )
    )
