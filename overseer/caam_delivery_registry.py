"""Enrolled-host delivery: the enrolment registry's host state.

The registry lives in the account-rotation operation's host state directory,
beside the cache and the published selection record, as contracts.md requires of
the enrolled-host delivery service stores. It is created owner-only
and written atomically, so a concurrent reader observes either the previous
registry or the new one and never a partial file.

Every writer holds the REGISTRY LOCK across its read-modify-write. A lock on a
file of its own, rather than on the registry, survives the atomic replace that
swaps the registry's inode.

Nothing here stores or returns a credential: an entry holds only the one-way
digest of the enrolment credential it was issued with.
"""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

import jsonio

__all__: list[str] = [
    "Entry",
    "append_audit",
    "load_entries",
    "registry_lock",
    "registry_path",
    "save_entries",
]

STATE_DIR_REL: Final = Path(".local/state/caam-usage-rotate")
_REGISTRY_NAME: Final = "enrolment-registry.json"
_LOCK_NAME: Final = "enrolment-registry.lock"
_AUDIT_NAME: Final = "delivery-audit.log"


@dataclass(frozen=True, kw_only=True)
class Entry:
    label: str
    network_identity: str
    credential_digest: str
    issued_at: str
    revoked: bool
    revoked_at: str | None


def registry_path(*, home: Path) -> Path:
    return home / STATE_DIR_REL / _REGISTRY_NAME


@contextmanager
def registry_lock(*, home: Path) -> Iterator[None]:
    lock_path = home / STATE_DIR_REL / _LOCK_NAME
    lock_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def _entry(*, row: object) -> Entry:
    fields = jsonio.as_object(value=row) or {}
    revoked_at = fields.get("revoked_at")
    return Entry(
        label=str(fields["label"]),
        network_identity=str(fields["network_identity"]),
        credential_digest=str(fields["credential_digest"]),
        issued_at=str(fields["issued_at"]),
        revoked=fields["revoked"] is True,
        revoked_at=None if revoked_at is None else str(revoked_at),
    )


def load_entries(*, home: Path) -> tuple[Entry, ...]:
    path = registry_path(home=home)
    if not path.exists():
        return ()
    document = jsonio.parse_object(text=path.read_text(encoding="utf-8")).unwrap() or {}
    rows = jsonio.as_list(value=document.get("entries")) or []
    return tuple(_entry(row=row) for row in rows)


def save_entries(*, home: Path, entries: tuple[Entry, ...]) -> None:
    path = registry_path(home=home)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    text = json.dumps({"entries": [asdict(entry) for entry in entries]}, indent=1, sort_keys=True)
    temporary = path.with_name(path.name + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        _ = handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    _ = temporary.replace(path)


def append_audit(*, home: Path, event: str, host_label: str, at: str) -> None:
    """Append one record to the append-only audit log.

    The record names the event, the host label and the time, and nothing else, so
    it cannot carry credential material. The line goes out in a single write on an
    append-mode descriptor, so concurrent appenders never interleave inside a record.
    """
    path = home / STATE_DIR_REL / _AUDIT_NAME
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    record = {"event": event, "host_label": host_label, "time": at}
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
        _ = handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
