"""Purpose-reservation validation for the manager configuration.

SPECIFICATION/contracts.md encodes `account_reservations` exactly
as ``{"<provider>":{"<account_id>":["<purpose>",...]}}``, every key non-empty and every
value a non-empty array of unique non-empty purposes. A matching account entry permits
ONLY the listed purposes; an account absent from its provider object is unreserved; and a
well-shaped key with no matching record is harmless and reserves nothing.

THE MULTI-PURPOSE RULE IS THE LOAD-BEARING ONE. If any single account's array contains
more than one purpose, `health_strategy` MUST be `remaining-percent` and every registered
credential-kind row for that provider MUST declare a shared-usage observer — so a shared
factory/interactive reservation cannot allocate the account without enforcing its
configured capacity floor. This is a CONFIGURATION-time refusal for every command, not a
selection-time one, because the harm it prevents is silent: under `none` the manager
applies no health-based exclusion at all, so a shared account would be handed to a second
purpose with no observation that the first has already consumed it.

`account_id` here is the credential RECORD field. It is not authority derived from the
separate caam published-selection record, and selection compares the two byte-for-byte.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_registry import UNSUPPORTED_SHARED_USAGE, rows_for_provider
from _lpm_results import ManagerError, invalid_request

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "REMAINING_PERCENT_STRATEGY",
    "AccountReservations",
    "reservations_from_object",
]

REMAINING_PERCENT_STRATEGY = "remaining-percent"

AccountReservations = Mapping[str, Mapping[str, tuple[str, ...]]]


def reservations_from_object(
    *, value: object, health_strategy: str
) -> Result[AccountReservations, ManagerError]:
    """Validate the `account_reservations` object against its shape and the registry."""
    if not isinstance(value, dict):
        return Failure(invalid_request(message="account_reservations must be an object"))
    providers = cast("dict[str, object]", value)
    reservations: dict[str, Mapping[str, tuple[str, ...]]] = {}
    for provider, accounts in providers.items():
        if provider == "":
            return Failure(
                invalid_request(message="account_reservations provider must be non-empty")
            )
        parsed = _accounts_for_provider(
            provider=provider, accounts=accounts, health_strategy=health_strategy
        )
        if isinstance(parsed, Failure):
            return parsed
        reservations[provider] = parsed.unwrap()
    return Success(reservations)


def _accounts_for_provider(
    *, provider: str, accounts: object, health_strategy: str
) -> Result[Mapping[str, tuple[str, ...]], ManagerError]:
    if not isinstance(accounts, dict):
        return Failure(
            invalid_request(message=f"account_reservations[{provider}] must be an object")
        )
    entries = cast("dict[str, object]", accounts)
    parsed: dict[str, tuple[str, ...]] = {}
    for account_id, purposes in entries.items():
        if account_id == "":
            return Failure(
                invalid_request(message=f"account_reservations[{provider}] key must be non-empty")
            )
        listed = _purposes(provider=provider, account_id=account_id, purposes=purposes)
        if isinstance(listed, Failure):
            return listed
        names = listed.unwrap()
        if len(names) > 1:
            refusal = _multi_purpose_prerequisites(
                provider=provider, account_id=account_id, health_strategy=health_strategy
            )
            if refusal is not None:
                return Failure(refusal)
        parsed[account_id] = names
    return Success(parsed)


def _purposes(
    *, provider: str, account_id: str, purposes: object
) -> Result[tuple[str, ...], ManagerError]:
    location = f"account_reservations[{provider}][{account_id}]"
    if not isinstance(purposes, list) or purposes == []:
        return Failure(invalid_request(message=f"{location} must be a non-empty array"))
    listed = cast("list[object]", purposes)
    names: list[str] = []
    for purpose in listed:
        if not isinstance(purpose, str) or purpose == "":
            return Failure(
                invalid_request(message=f"{location} purposes must be non-empty strings")
            )
        names.append(purpose)
    if len(set(names)) != len(names):
        return Failure(invalid_request(message=f"{location} purposes must be unique"))
    return Success(tuple(names))


def _multi_purpose_prerequisites(
    *, provider: str, account_id: str, health_strategy: str
) -> ManagerError | None:
    location = f"account_reservations[{provider}][{account_id}]"
    if health_strategy != REMAINING_PERCENT_STRATEGY:
        return invalid_request(
            message=f"{location} reserves several purposes, which requires "
            f"health_strategy {REMAINING_PERCENT_STRATEGY}"
        )
    unsupported = [
        row.kind
        for row in rows_for_provider(provider=provider)
        if row.shared_usage_observation == UNSUPPORTED_SHARED_USAGE
    ]
    if unsupported:
        return invalid_request(
            message=f"{location} reserves several purposes, but registered kind "
            f"{unsupported[0]} declares no shared-usage observer"
        )
    return None
