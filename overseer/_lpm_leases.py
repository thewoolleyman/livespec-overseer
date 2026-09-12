"""Non-blocking, run-bound per-account leases: the interlock against half-assignment.

SPECIFICATION/contracts.md makes a lease live only while its record exists AND the current time is
STRICTLY EARLIER than `lease_expires_at`; requires selection to acquire a NON-BLOCKING per-account
lease bound to `consumer_run_id` before the authoritative read; requires `lease-create` to create
an absent lease or replace one only after proving the stored lease expired; requires every release
— including cleanup and expiry — to condition deletion on the file still naming the CLOSING
`consumer_run_id` and `record_id`; makes release idempotent; and requires an expired lease to be
treated as ABSENT before selecting, so an account becomes eligible again without a crashed
consumer's cooperation.

NON-BLOCKING IS THE POINT, AND IT IS WHY CONTENTION IS `retryable-exhaustion`. A blocking
acquire would hold a second run inside selection while a first run writes a credential to
its target, and the two would then both believe they own the account. Refusing immediately
with a typed retryable result keeps the losing run's target byte-identical and its run
identity unconsumed, which is exactly the state a retry needs.

THE RELEASE CONDITION IS NOT AN OPTIMIZATION. A cleanup path that unlinked whatever lease
file it found would delete the lease a LATER run took after this one's expired — the
classic delete-by-path race — and that later run would then discover its own account free
and hand the same credential to a third. Naming both the run and the record in the
condition makes "release my lease" unable to mean "release the lease that is there now".

EXPIRY IS READ, NEVER WRITTEN. Nothing here rewrites or deletes an expired lease as a
repair: `lease_is_live` simply answers False, and `acquire_lease` then replaces the record
wholesale. An unsafe or malformed lease file is a different thing entirely and returns
`store-unavailable` through the local-record reader, which never resets the path.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_localstate import read_local_record, write_local_record
from _lpm_record import is_uuid4
from _lpm_results import (
    ManagerError,
    internal_bug,
    invalid_request,
    retryable_exhaustion,
    store_unavailable,
)
from _lpm_time import add_seconds, is_at_or_after, is_canonical_timestamp

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "DEFAULT_LEASE_SECONDS",
    "LEASE_ABSENT",
    "LEASE_FOREIGN",
    "LEASE_MEMBERS",
    "LEASE_RELEASED",
    "LEASE_RELEASE_OUTCOMES",
    "LEASE_VERSION",
    "MAXIMUM_LEASE_SECONDS",
    "MINIMUM_LEASE_SECONDS",
    "AccountLease",
    "acquire_lease",
    "lease_from_object",
    "lease_is_live",
    "lease_object",
    "lease_seconds_field",
    "new_lease",
    "read_lease",
    "release_lease",
]

LEASE_VERSION: Final = 1

LEASE_RELEASED: Final = "released"
LEASE_ABSENT: Final = "absent"
LEASE_FOREIGN: Final = "foreign"

LEASE_RELEASE_OUTCOMES: Final = (LEASE_RELEASED, LEASE_ABSENT, LEASE_FOREIGN)

DEFAULT_LEASE_SECONDS: Final = 21600
MINIMUM_LEASE_SECONDS: Final = 60
MAXIMUM_LEASE_SECONDS: Final = 86400

LEASE_MEMBERS: Final = (
    "version",
    "provider",
    "account_id",
    "record_id",
    "consumer_run_id",
    "lease_started_at",
    "lease_expires_at",
)


@dataclass(frozen=True, kw_only=True)
class AccountLease:
    """One run's live claim on one provider account, and the instant it lapses."""

    provider: str
    account_id: str
    record_id: str
    consumer_run_id: str
    lease_started_at: str
    lease_expires_at: str


def lease_seconds_field(*, value: object) -> Result[int, ManagerError]:
    """Accept an optional `lease_seconds`, materializing the default for an absent value.

    This is part of EXACT provisioning-object validation, so an out-of-range value is
    refused with `invalid-request` before recovery, target validation, selection or lease
    acquisition — never clamped into range, which would silently provision a lease the
    consumer did not ask for.
    """
    if value is None:
        return Success(DEFAULT_LEASE_SECONDS)
    if isinstance(value, bool) or not isinstance(value, int):
        return Failure(invalid_request(message="lease_seconds must be an integer"))
    if value < MINIMUM_LEASE_SECONDS or value > MAXIMUM_LEASE_SECONDS:
        return Failure(
            invalid_request(
                message=(
                    f"lease_seconds must be from {MINIMUM_LEASE_SECONDS} "
                    f"through {MAXIMUM_LEASE_SECONDS}"
                )
            )
        )
    return Success(value)


def new_lease(
    *,
    provider: str,
    account_id: str,
    record_id: str,
    consumer_run_id: str,
    now: str,
    lease_seconds: int,
) -> Result[AccountLease, ManagerError]:
    """Build the lease one run would take on one account at `now`."""
    expires_at = add_seconds(timestamp=now, seconds=lease_seconds)
    if expires_at is None:
        return Failure(internal_bug(message="lease start is not a UTC RFC 3339-second timestamp"))
    return Success(
        AccountLease(
            provider=provider,
            account_id=account_id,
            record_id=record_id,
            consumer_run_id=consumer_run_id,
            lease_started_at=now,
            lease_expires_at=expires_at,
        )
    )


def lease_object(*, lease: AccountLease) -> dict[str, object]:
    """The exact seven-member lease mapping, built from the declared member list."""
    values: dict[str, object] = {"version": LEASE_VERSION}
    for member in LEASE_MEMBERS[1:]:
        values[member] = getattr(lease, member)
    return values


def lease_from_object(*, parsed: object) -> Result[AccountLease, ManagerError]:
    """Validate one decoded lease record; anything unsafe is `store-unavailable`."""
    if not isinstance(parsed, dict):
        return Failure(store_unavailable(message="lease must be a JSON object"))
    source = cast("dict[str, object]", parsed)
    refusal = _lease_refusal(source=source)
    if refusal is not None:
        return Failure(refusal)
    return Success(
        AccountLease(
            provider=str(source["provider"]),
            account_id=str(source["account_id"]),
            record_id=str(source["record_id"]),
            consumer_run_id=str(source["consumer_run_id"]),
            lease_started_at=str(source["lease_started_at"]),
            lease_expires_at=str(source["lease_expires_at"]),
        )
    )


def _lease_refusal(*, source: dict[str, object]) -> ManagerError | None:
    if sorted(source) != sorted(LEASE_MEMBERS):
        return store_unavailable(message=f"lease carries exactly {', '.join(LEASE_MEMBERS)}")
    version = source["version"]
    if isinstance(version, bool) or version != LEASE_VERSION:
        return store_unavailable(message="lease version must be the integer 1")
    for member in ("provider", "account_id", "consumer_run_id"):
        value = source[member]
        if not isinstance(value, str) or value == "":
            return store_unavailable(message=f"lease {member} must be a non-empty string")
    record_id = source["record_id"]
    if not isinstance(record_id, str) or not is_uuid4(value=record_id):
        return store_unavailable(message="lease record_id must be a lowercase UUIDv4")
    for member in ("lease_started_at", "lease_expires_at"):
        value = source[member]
        if not isinstance(value, str) or not is_canonical_timestamp(text=value):
            return store_unavailable(
                message=f"lease {member} is not a UTC RFC 3339-second timestamp"
            )
    return None


def read_lease(*, path: Path, owner_uid: int) -> Result[AccountLease | None, ManagerError]:
    """Read one account's lease; an ABSENT file means no run holds that account."""
    stored = read_local_record(path=path, owner_uid=owner_uid)
    if isinstance(stored, Failure):
        return Failure(stored.failure())
    value = stored.unwrap()
    if value is None:
        return Success(None)
    parsed = lease_from_object(parsed=value)
    if isinstance(parsed, Failure):
        return Failure(parsed.failure())
    return Success(parsed.unwrap())


def lease_is_live(*, lease: AccountLease, now: str) -> bool:
    """Whether `now` is STRICTLY earlier than `lease_expires_at`; equality is expired."""
    return is_at_or_after(moment=now, limit=lease.lease_expires_at) is False


def acquire_lease(
    *, path: Path, lease: AccountLease, owner_uid: int, now: str
) -> Result[AccountLease, ManagerError]:
    """Take `lease` without waiting, or refuse with typed retryable exhaustion.

    A stored lease that is still live belongs to another in-flight run and is left exactly
    as it is. Only an ABSENT or already-expired record is replaced, which is what lets an
    account recover from a crashed consumer with no cooperation from it.
    """
    stored = read_lease(path=path, owner_uid=owner_uid)
    if isinstance(stored, Failure):
        return Failure(stored.failure())
    current = stored.unwrap()
    if current is not None and lease_is_live(lease=current, now=now):
        if current.consumer_run_id == lease.consumer_run_id:
            return Success(current)
        return Failure(
            retryable_exhaustion(
                message=(
                    "the selected account is leased to another run until "
                    f"{current.lease_expires_at}"
                )
            )
        )
    written = write_local_record(path=path, value=lease_object(lease=lease), owner_uid=owner_uid)
    if isinstance(written, Failure):
        return Failure(written.failure())
    return Success(lease)


def release_lease(
    *, path: Path, consumer_run_id: str, record_id: str, owner_uid: int
) -> Result[str, ManagerError]:
    """Release this run's lease on this record; idempotent, and never another run's.

    The outcome is one of the three closed words rather than a Boolean, because the two
    non-releasing answers mean different things to a caller: `absent` says there is nothing
    to release, while `foreign` says a DIFFERENT run's lease is standing here and was left
    alone. A Boolean collapses those into "no", which is exactly the distinction a cleanup
    path needs in order to know it has not silently skipped its own lease.
    """
    stored = read_lease(path=path, owner_uid=owner_uid)
    if isinstance(stored, Failure):
        return Failure(stored.failure())
    current = stored.unwrap()
    if current is None:
        return Success(LEASE_ABSENT)
    if current.consumer_run_id != consumer_run_id or current.record_id != record_id:
        return Success(LEASE_FOREIGN)
    return _unlinked(path=path)


def _unlinked(*, path: Path) -> Result[str, ManagerError]:
    try:
        path.unlink()
    except FileNotFoundError:
        return Success(LEASE_ABSENT)
    except OSError as failure:
        reason = failure.__class__.__name__
        return Failure(store_unavailable(message=f"{path.name} was not released: {reason}"))
    return Success(LEASE_RELEASED)
