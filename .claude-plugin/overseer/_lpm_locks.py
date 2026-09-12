"""Owner-only kernel lock files with a bounded, mutation-free wait.

SPECIFICATION/contracts.md serializes this operation on kernel lock files: a provider
account, a credential record, a target reference, a consumer run and the audit log each
have one, and a TIMEOUT acquiring a lock is `store-unavailable` rather than a reason to
proceed unserialized.

KERNEL LOCKS ARE USED PRECISELY BECAUSE THEY RELEASE WHEN THEIR HOLDER ENDS. A manager
worker can be killed at any point — a deadline, a revocation, a crash — and an advisory
`flock` held on an open file description is dropped by the kernel when that description
closes, so a dead holder cannot wedge the account it was serializing. A lock implemented
as "a file exists" would need its own crash-recovery protocol, and that protocol would
itself need serializing.

THE WAIT IS BOUNDED AND PERFORMS NO MUTATION. A caller that cannot take the lock within
its budget must return `store-unavailable` having changed nothing — not proceed, not
"steal" the lock, not remove the file. The lock FILE is therefore never deleted here:
deleting it would let a second holder open a fresh file, take a lock on a different
description, and believe it was serialized against the first.

The clock and the sleep are injected so a bounded wait can be exercised deterministically
rather than by making a test actually wait.
"""

from __future__ import annotations

import fcntl
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_localstate import LOCAL_FILE_MODE, ensure_state_directory
from _lpm_results import ManagerError, store_unavailable

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "LOCK_FILE_MODE",
    "LOCK_POLL_SECONDS",
    "HeldLock",
    "release_lock",
    "take_lock",
]

LOCK_POLL_SECONDS: Final = 0.05
LOCK_FILE_MODE: Final = LOCAL_FILE_MODE


@dataclass(frozen=True, kw_only=True)
class HeldLock:
    """One held advisory lock, named by the open file description holding it."""

    path: Path
    descriptor: int


def take_lock(
    *,
    path: Path,
    owner_uid: int,
    timeout_seconds: float,
    monotonic: Callable[[], float],
    sleep: Callable[[float], None],
) -> Result[HeldLock, ManagerError]:
    """Take the owner-only exclusive lock at `path`, waiting no longer than the budget."""
    directory = ensure_state_directory(path=path.parent, owner_uid=owner_uid)
    if isinstance(directory, Failure):
        return directory
    if path.is_symlink():
        return Failure(store_unavailable(message=f"{path.name} is a symlink"))
    try:
        descriptor = os.open(str(path), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, LOCK_FILE_MODE)
    except OSError as failure:
        return Failure(
            store_unavailable(message=f"{path.name} is unusable: {failure.__class__.__name__}")
        )
    deadline = monotonic() + timeout_seconds
    while True:
        taken = _try_lock(descriptor=descriptor)
        if taken:
            return Success(HeldLock(path=path, descriptor=descriptor))
        if monotonic() >= deadline:
            os.close(descriptor)
            return Failure(store_unavailable(message=f"{path.name} was held past the wait budget"))
        sleep(LOCK_POLL_SECONDS)


def release_lock(*, held: HeldLock) -> None:
    """Drop the lock by closing its description; the lock FILE deliberately remains."""
    os.close(held.descriptor)


def _try_lock(*, descriptor: int) -> bool:
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True
