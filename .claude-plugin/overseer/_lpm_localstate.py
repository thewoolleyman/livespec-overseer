"""Owner-only, no-symlink, atomic persistence for every manager-local record.

SPECIFICATION/contracts.md requires that every filesystem-backed local store and audit
file be mode `0600` beneath a mode-`0700` manager state directory, that creation REFUSE a
pre-existing path with broader permissions rather than expose data, and that a malformed,
non-regular, symlinked, incorrectly owned or more broadly accessible record return
`store-unavailable` with exit `4` while NEITHER RESETTING NOR MUTATING the unsafe path.

The no-reset half is the one that is easy to get wrong and impossible to undo. The
tempting repair for an unreadable state file is to rewrite it with a fresh empty one —
and that is precisely the forbidden move: a corrupt lease, assignment or fence file is
EVIDENCE of state this manager may still be bound by, and replacing it with initial state
silently converts "I cannot tell what is running" into "nothing is running". So a defect
reports and stops; the file is left exactly as found.

ABSENCE IS AN ANSWER, NOT A DEFECT. The contract defines an absent issuance, lease,
assignment, tombstone, operation or fence file to MEAN that entity does not exist. A read
therefore distinguishes three outcomes — absent, safe-and-parsed, unsafe — and never
collapses the first into either of the others.

THE EFFECTIVE UID IS PASSED IN rather than read here. The manager's identity comes from
the operating-system account database and belongs to the caller's resolved namespace; a
module that consults the process uid on its own would be untestable for the mismatch case
and would also hide which identity a given read was actually checked against.
"""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path
from typing import Final

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_canonical import canonical_json_text, parse_canonical_json
from _lpm_results import ManagerError, internal_bug, store_unavailable

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "LOCAL_FILE_MODE",
    "STATE_DIRECTORY_MODE",
    "ensure_state_directory",
    "read_local_record",
    "read_local_text",
    "write_local_bytes",
    "write_local_record",
    "write_local_text",
]

STATE_DIRECTORY_MODE: Final = 0o700
LOCAL_FILE_MODE: Final = 0o600

_BROADER_THAN_OWNER = 0o077


def read_local_text(*, path: Path, owner_uid: int) -> Result[str | None, ManagerError]:
    """Read one local file as UTF-8 text: `Success(None)` when absent, `Failure` when unsafe.

    A symlink is refused before it is followed, so a record path can never be redirected
    at content outside the manager's own state directory.
    """
    defect = _file_defect(path=path, owner_uid=owner_uid)
    if defect is not None:
        return Failure(store_unavailable(message=defect))
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return Success(None)
    except OSError as failure:
        reason = _named(failure=failure)
        return Failure(store_unavailable(message=f"{path.name} is unreadable: {reason}"))
    try:
        return Success(raw.decode("utf-8"))
    except ValueError:
        return Failure(store_unavailable(message=f"{path.name} is not valid UTF-8"))


def read_local_record(*, path: Path, owner_uid: int) -> Result[object | None, ManagerError]:
    """Read one canonical-JSON local record; an absent file means the entity does not exist."""
    text = read_local_text(path=path, owner_uid=owner_uid)
    if isinstance(text, Failure):
        return text
    stored = text.unwrap()
    if stored is None:
        return Success(None)
    parsed = parse_canonical_json(text=stored)
    if isinstance(parsed, Failure):
        return Failure(store_unavailable(message=f"{path.name} is {parsed.failure().reason}"))
    return Success(parsed.unwrap())


def write_local_bytes(*, path: Path, payload: bytes, owner_uid: int) -> Result[None, ManagerError]:
    """Atomically replace one local file with exactly `payload`.

    The replacement is staged in the destination's own directory and renamed over it, so
    a crash leaves either the prior bytes or the whole new content — never a torn suffix.
    The staged file is created mode `0600`; an EXISTING destination with broader
    permissions is refused rather than rewritten, because rewriting it would expose the
    new content through the very permissions that made the old one unsafe.

    THE BYTES ARE WRITTEN VERBATIM. SPECIFICATION/contracts.md requires a provisioned
    credential to reach its target with NO added encoding, framing or trailing newline, so
    the payload crosses this boundary as bytes rather than as text something downstream
    might re-encode or line-terminate on its behalf.
    """
    directory = ensure_state_directory(path=path.parent, owner_uid=owner_uid)
    if isinstance(directory, Failure):
        return directory
    defect = _file_defect(path=path, owner_uid=owner_uid)
    if defect is not None:
        return Failure(store_unavailable(message=defect))
    return _atomic_replace(path=path, payload=payload)


def write_local_text(*, path: Path, text: str, owner_uid: int) -> Result[None, ManagerError]:
    """Atomically replace one local file with the UTF-8 encoding of `text`."""
    return write_local_bytes(path=path, payload=text.encode("utf-8"), owner_uid=owner_uid)


def write_local_record(*, path: Path, value: object, owner_uid: int) -> Result[None, ManagerError]:
    """Atomically replace one local record with the canonical encoding of `value`."""
    encoded = canonical_json_text(value=value)
    if isinstance(encoded, Failure):
        return Failure(internal_bug(message=f"record is {encoded.failure().reason}"))
    return write_local_text(path=path, text=encoded.unwrap(), owner_uid=owner_uid)


def ensure_state_directory(*, path: Path, owner_uid: int) -> Result[None, ManagerError]:
    """Create or validate one manager-owned mode-`0700` non-symlink directory."""
    if path.is_symlink():
        return Failure(store_unavailable(message=f"{path.name} is a symlink"))
    try:
        path.mkdir(mode=STATE_DIRECTORY_MODE, parents=True, exist_ok=True)
        status = path.stat()
    except OSError as failure:
        return Failure(
            store_unavailable(message=f"{path.name} is unusable: {_named(failure=failure)}")
        )
    if status.st_uid != owner_uid:
        return Failure(store_unavailable(message=f"{path.name} is not owned by the manager"))
    if status.st_mode & _BROADER_THAN_OWNER:
        return Failure(store_unavailable(message=f"{path.name} is more broadly accessible"))
    return Success(None)


def _file_defect(*, path: Path, owner_uid: int) -> str | None:
    if path.is_symlink():
        return f"{path.name} is a symlink"
    try:
        status = path.stat()
    except FileNotFoundError:
        return None
    except OSError as failure:
        return f"{path.name} is unreadable: {_named(failure=failure)}"
    return _status_defect(name=path.name, status=status, owner_uid=owner_uid)


def _status_defect(*, name: str, status: os.stat_result, owner_uid: int) -> str | None:
    if not stat.S_ISREG(status.st_mode):
        return f"{name} is not a regular file"
    if status.st_uid != owner_uid:
        return f"{name} is not owned by the manager"
    if status.st_mode & _BROADER_THAN_OWNER:
        return f"{name} is more broadly accessible"
    return None


def _atomic_replace(*, path: Path, payload: bytes) -> Result[None, ManagerError]:
    handle, staged = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(handle, "wb") as staged_file:
            _ = staged_file.write(payload)
            staged_file.flush()
            os.fsync(staged_file.fileno())
        Path(staged).chmod(LOCAL_FILE_MODE)
        _ = Path(staged).replace(path)
        _sync_directory(path=path.parent)
    except OSError as failure:
        Path(staged).unlink(missing_ok=True)
        reason = _named(failure=failure)
        return Failure(store_unavailable(message=f"{path.name} was not replaced: {reason}"))
    return Success(None)


def _sync_directory(*, path: Path) -> None:
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _named(*, failure: OSError) -> str:
    return failure.__class__.__name__
