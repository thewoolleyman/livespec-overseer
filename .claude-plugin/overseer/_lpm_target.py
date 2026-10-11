"""The `isolated-run` ProvisioningTarget adapter: one reference, one run, one atomic write.

SPECIFICATION/contracts.md requires a conforming adapter to bind each reference IMMUTABLY to
exactly one consumer-run identity, never reassign it, validate that binding WITHOUT receiving
credential bytes, make a successful write atomic and durable, and leave an existing
destination BYTE-IDENTICAL whenever it returns failure — including after process
interruption. It fixes commit status at exactly `in-progress`, `committed` or `uncommitted`
plus a nullable `committed_at` that is non-null exactly for `committed`, requires the final
lease-fence check IMMEDIATELY before atomic replacement, and requires an abort without
changing prior target bytes when that sample is at or after `lease_expires_at`. For this
built-in adapter the destination must end up owned by the manager's effective user, mode no
broader than `0600`, beneath parent directories no broader than `0700`. An unassigned
reference expires 24 hours after issue.

RESOLUTION IS A LOOKUP, NEVER A PARSE. The contract is explicit that `target_ref` is an
opaque reference issued through the manager's own target command rather than an arbitrary
path supplied to it, and that the manager must resolve it from the PERSISTED ISSUANCE RECORD
rather than parse it for a destination. So `resolve_issuance` compares a caller-supplied
reference against a record it was handed and returns that record's destination; nothing here
derives a filesystem path from reference text. A reference that could be read as a path is a
reference a consumer could forge into one.

THE FENCE IS SAMPLED ONCE AND THAT SAMPLE BECOMES `committed_at`. The contract requires
`committed_at` to EQUAL the adapter's final lease-fence sample at the commit boundary, which
is why `commit_credential` takes the sample as an argument rather than reading a clock twice.
Two reads would let the value reported to the consumer differ from the value the fence was
actually judged against, and every overlap proof downstream is built on that instant.

THE ORDER OF THE TWO REFUSALS BELOW IS LOAD-BEARING. The fence is checked before the write
is attempted, so an expired lease leaves the destination untouched by construction rather
than by a cleanup that might not run. Everything after it delegates the atomicity itself to
the local-record writer, which stages beside the destination and renames — so a failure
anywhere in that path leaves the prior bytes exactly as they were.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_localstate import write_local_bytes
from _lpm_locks import release_lock, take_lock
from _lpm_registry import REGISTERED_TARGET_ADAPTERS as REGISTERED_TARGET_ADAPTERS
from _lpm_target_issuance import (
    ISOLATED_RUN_ADAPTER,
    ISSUANCE_MEMBERS,
    ISSUANCE_SECONDS,
    ISSUANCE_VERSION,
    TargetIssuance,
    issuance_from_object,
    issuance_object,
    new_issuance,
    resolve_issuance,
)
from _lpm_time import is_at_or_after

from overseer._vendor.returns.result import Failure

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "COMMITTED",
    "COMMIT_STATUSES",
    "IN_PROGRESS",
    "ISOLATED_RUN_ADAPTER",
    "ISSUANCE_MEMBERS",
    "ISSUANCE_SECONDS",
    "ISSUANCE_VERSION",
    "REGISTERED_TARGET_ADAPTERS",
    "UNCOMMITTED",
    "CommitOutcome",
    "TargetIssuance",
    "TargetLock",
    "commit_credential",
    "issuance_from_object",
    "issuance_object",
    "new_issuance",
    "resolve_issuance",
]

COMMITTED: Final = "committed"
UNCOMMITTED: Final = "uncommitted"
IN_PROGRESS: Final = "in-progress"

COMMIT_STATUSES: Final = (IN_PROGRESS, COMMITTED, UNCOMMITTED)


@dataclass(frozen=True, kw_only=True)
class CommitOutcome:
    """The adapter's commit status and, for a commit, the fence sample it landed at."""

    status: str
    committed_at: str | None


@dataclass(frozen=True, kw_only=True)
class TargetLock:
    """The per-reference lock that serializes every write to one target.

    The clock and the sleep are injected for the same reason the lock module injects them:
    a bounded wait must be exercisable without a test actually waiting out the budget.
    """

    path: Path
    timeout_seconds: float
    monotonic: Callable[[], float]
    sleep: Callable[[float], None]


def commit_credential(
    *,
    destination: str,
    value: bytes,
    owner_uid: int,
    fence_now: str,
    lease_expires_at: str,
    lock: TargetLock,
) -> CommitOutcome:
    """Serialize on the reference, fence, then atomically replace the target with `value`.

    The three statuses are returned rather than raised or rail-failed because they are the
    adapter's ANSWER, not its failure: the contract asks for commit status and the manager
    decides what each one means. That is also why this returns a bare `CommitOutcome` — a
    `Result` here would invite a caller to treat `uncommitted` as an error rail and skip
    the cleanup the contract requires for it.

    FAILING TO TAKE THE PER-REFERENCE LOCK IS `in-progress`, NEVER `uncommitted`. The
    contract says so explicitly, and the reason is that a timed-out or parent-orphaned
    target child may still own that lock and still be writing: reporting `uncommitted`
    would assert the destination is unchanged at the exact moment nobody can know that.

    A fence sample at or after `lease_expires_at` aborts BEFORE the write is attempted, so
    the prior bytes are untouched by construction rather than by a cleanup that might not
    run. A write that definitively fails reports `uncommitted`, and the local-record writer
    stages beside the destination and renames, so the prior bytes survive that too.
    """
    held = take_lock(
        path=lock.path,
        owner_uid=owner_uid,
        timeout_seconds=lock.timeout_seconds,
        monotonic=lock.monotonic,
        sleep=lock.sleep,
    )
    if isinstance(held, Failure):
        return CommitOutcome(status=IN_PROGRESS, committed_at=None)
    try:
        return _fenced_write(
            destination=destination,
            value=value,
            owner_uid=owner_uid,
            fence_now=fence_now,
            lease_expires_at=lease_expires_at,
        )
    finally:
        release_lock(held=held.unwrap())


def _fenced_write(
    *, destination: str, value: bytes, owner_uid: int, fence_now: str, lease_expires_at: str
) -> CommitOutcome:
    if is_at_or_after(moment=fence_now, limit=lease_expires_at) is not False:
        return CommitOutcome(status=UNCOMMITTED, committed_at=None)
    written = write_local_bytes(path=Path(destination), payload=value, owner_uid=owner_uid)
    if isinstance(written, Failure):
        return CommitOutcome(status=UNCOMMITTED, committed_at=None)
    return CommitOutcome(status=COMMITTED, committed_at=fence_now)
