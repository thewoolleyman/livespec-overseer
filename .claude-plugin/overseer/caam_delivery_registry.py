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
from _foreman_vendor_path import VENDOR_PATHS_INSTALLED

from overseer._vendor.returns.result import Failure, Result, Success

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "Entry",
    "Refusal",
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
class Refusal:
    """An expected refusal, carried on the Result failure track."""

    message: str


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


def _entry(*, row: object) -> Entry | None:
    fields = jsonio.as_object(value=row)
    if fields is None:
        return None
    label = fields.get("label")
    network_identity = fields.get("network_identity")
    credential_digest = fields.get("credential_digest")
    issued_at = fields.get("issued_at")
    revoked = fields.get("revoked")
    revoked_at = fields.get("revoked_at")
    if not (
        isinstance(label, str)
        and isinstance(network_identity, str)
        and isinstance(credential_digest, str)
        and isinstance(issued_at, str)
        and isinstance(revoked, bool)
        and (revoked_at is None or isinstance(revoked_at, str))
    ):
        return None
    return Entry(
        label=label,
        network_identity=network_identity,
        credential_digest=credential_digest,
        issued_at=issued_at,
        revoked=revoked,
        revoked_at=revoked_at,
    )


def load_entries(*, home: Path) -> Result[tuple[Entry, ...], Refusal]:
    """Read the registry, failing closed on a file this module did not write.

    A registry that does not parse is reported, never treated as empty: a writer
    that took a damaged file for an empty one would replace it and silently drop
    every enrolment it held, including the revocations.
    """
    path = registry_path(home=home)
    if not path.exists():
        return Success(())
    corrupt = Failure(Refusal(message=f"the enrolment registry is corrupt: {path}"))
    parsed = jsonio.parse_object(text=path.read_text(encoding="utf-8"))
    document = None if isinstance(parsed, Failure) else parsed.unwrap()
    rows = None if document is None else jsonio.as_list(value=document.get("entries"))
    if rows is None:
        return corrupt
    entries: list[Entry] = []
    for row in rows:
        entry = _entry(row=row)
        if entry is None:
            return corrupt
        entries.append(entry)
    return Success(tuple(entries))


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
