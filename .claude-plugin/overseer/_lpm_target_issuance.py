"""Durable issuance records for the built-in isolated-run target adapter.

RESOLUTION IS A LOOKUP, NEVER A PARSE. ``target_ref`` is an opaque reference issued
through the manager's target command, so resolution compares it with a persisted issuance
record and returns that record's destination. Nothing here derives a path from reference
text. Unassigned references expire after 24 hours, while a bound recovery remains
resolvable after that instant.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_registry import REGISTERED_TARGET_ADAPTERS
from _lpm_results import ManagerError, internal_bug, invalid_request
from _lpm_time import add_seconds, is_at_or_after, is_canonical_timestamp

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "ISOLATED_RUN_ADAPTER",
    "ISSUANCE_MEMBERS",
    "ISSUANCE_SECONDS",
    "ISSUANCE_VERSION",
    "TargetIssuance",
    "issuance_from_object",
    "issuance_object",
    "new_issuance",
    "resolve_issuance",
]

ISSUANCE_VERSION: Final = 1
ISSUANCE_SECONDS: Final = 86400
ISOLATED_RUN_ADAPTER: Final = "isolated-run"
ISSUANCE_MEMBERS: Final = (
    "version",
    "target_ref",
    "consumer_run_id",
    "adapter",
    "isolated_root",
    "target_path",
    "issued_at",
    "expires_at",
)


@dataclass(frozen=True, kw_only=True)
class TargetIssuance:
    """One opaque reference, the single run it is bound to, and where it resolves."""

    reference: str
    consumer_run_id: str
    adapter: str
    isolated_root: str
    destination: str
    issued_at: str
    expires_at: str


def new_issuance(
    *,
    reference: str,
    consumer_run_id: str,
    adapter: str,
    isolated_root: str,
    destination: str,
    now: str,
) -> Result[TargetIssuance, ManagerError]:
    """Issue one reference bound to one run, expiring 24 hours from ``now``."""
    if adapter not in REGISTERED_TARGET_ADAPTERS:
        return Failure(invalid_request(message=f"{adapter} is not a registered target adapter"))
    for name, value in (
        ("target_ref", reference),
        ("consumer_run_id", consumer_run_id),
        ("isolated_root", isolated_root),
        ("target_path", destination),
    ):
        if value == "":
            return Failure(invalid_request(message=f"target {name} must be a non-empty string"))
    expires_at = add_seconds(timestamp=now, seconds=ISSUANCE_SECONDS)
    if expires_at is None:
        return Failure(internal_bug(message="issue time is not a UTC RFC 3339-second timestamp"))
    return Success(
        TargetIssuance(
            reference=reference,
            consumer_run_id=consumer_run_id,
            adapter=adapter,
            isolated_root=isolated_root,
            destination=destination,
            issued_at=now,
            expires_at=expires_at,
        )
    )


def issuance_object(*, issuance: TargetIssuance) -> dict[str, object]:
    """The exact eight-member issuance mapping used by installed target roles."""
    return {
        "version": ISSUANCE_VERSION,
        "target_ref": issuance.reference,
        "consumer_run_id": issuance.consumer_run_id,
        "adapter": issuance.adapter,
        "isolated_root": issuance.isolated_root,
        "target_path": issuance.destination,
        "issued_at": issuance.issued_at,
        "expires_at": issuance.expires_at,
    }


def issuance_from_object(*, parsed: object) -> Result[TargetIssuance, ManagerError]:
    """Validate one decoded issuance record; an unusable one is ``invalid-request``."""
    if not isinstance(parsed, dict):
        return Failure(invalid_request(message="target issuance must be a JSON object"))
    source = cast("dict[str, object]", parsed)
    if sorted(source) != sorted(ISSUANCE_MEMBERS):
        return Failure(
            invalid_request(
                message=f"target issuance carries exactly {', '.join(ISSUANCE_MEMBERS)}"
            )
        )
    version = source["version"]
    if isinstance(version, bool) or version != ISSUANCE_VERSION:
        return Failure(invalid_request(message="target issuance version must be the integer 1"))
    for member in ISSUANCE_MEMBERS[1:6]:
        value = source[member]
        if not isinstance(value, str) or value == "":
            return Failure(
                invalid_request(message=f"target issuance {member} must be a non-empty string")
            )
    return _issuance_with_times(source=source)


def resolve_issuance(
    *, issuance: TargetIssuance, target_ref: str, consumer_run_id: str, now: str, bound: bool
) -> Result[str, ManagerError]:
    """Resolve one persisted opaque reference without parsing caller-supplied text."""
    if issuance.reference != target_ref:
        return Failure(invalid_request(message="target_ref does not name this issuance"))
    if issuance.consumer_run_id != consumer_run_id:
        return Failure(invalid_request(message="target_ref is bound to a different consumer run"))
    if issuance.adapter not in REGISTERED_TARGET_ADAPTERS:
        return Failure(
            invalid_request(message=f"{issuance.adapter} is not a registered target adapter")
        )
    if not bound and is_at_or_after(moment=now, limit=issuance.expires_at) is not False:
        return Failure(invalid_request(message="target_ref issuance has expired unassigned"))
    return Success(issuance.destination)


def _issuance_with_times(*, source: dict[str, object]) -> Result[TargetIssuance, ManagerError]:
    for member in ("issued_at", "expires_at"):
        value = source[member]
        if not isinstance(value, str) or not is_canonical_timestamp(text=value):
            return Failure(
                invalid_request(
                    message=f"target issuance {member} is not a UTC RFC 3339-second timestamp"
                )
            )
    return Success(
        TargetIssuance(
            reference=str(source["target_ref"]),
            consumer_run_id=str(source["consumer_run_id"]),
            adapter=str(source["adapter"]),
            isolated_root=str(source["isolated_root"]),
            destination=str(source["target_path"]),
            issued_at=str(source["issued_at"]),
            expires_at=str(source["expires_at"]),
        )
    )
