"""Atomic target replacement and authoritative target-byte inspection."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

from _lpm_results import ManagerError, store_unavailable

from overseer._vendor.returns.result import Failure, Result, Success

__all__: list[str] = [
    "replace_staged_target",
    "target_matches_evidence",
]

_MATCHED = True
_NOT_MATCHED = False


def replace_staged_target(*, staged: Path, destination: Path) -> Result[None, ManagerError]:
    """Atomically replace the target and make its containing directory durable."""
    try:
        _ = staged.replace(destination)
        descriptor = os.open(str(destination.parent), os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError as failure:
        return Failure(
            store_unavailable(
                message=f"target replacement was not durable: {failure.__class__.__name__}"
            )
        )
    return Success(None)


def target_matches_evidence(
    *, destination: Path, owner_uid: int, target_sha256: str
) -> Result[bool, ManagerError]:
    """Prove regular owner-only target bytes match the armed evidence digest."""
    try:
        status = destination.lstat()
    except FileNotFoundError:
        return Success(_NOT_MATCHED)
    except OSError as failure:
        return Failure(
            store_unavailable(message=f"target is unreadable: {failure.__class__.__name__}")
        )
    mode = stat.S_IMODE(status.st_mode)
    if not stat.S_ISREG(status.st_mode) or status.st_uid != owner_uid or mode & ~0o600:
        return Success(_NOT_MATCHED)
    try:
        payload = destination.read_bytes()
    except OSError as failure:
        return Failure(
            store_unavailable(message=f"target is unreadable: {failure.__class__.__name__}")
        )
    matches = hashlib.sha256(payload).hexdigest() == target_sha256
    return Success(_MATCHED if matches else _NOT_MATCHED)
