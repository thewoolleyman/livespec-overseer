"""The parameter-store-reference backend's owner-only local METADATA store.

Proposed in SPECIFICATION/proposed_changes/lpm-parameter-store-reference-records.md. Under
this backend the manager holds no credential value: the value stays in its canonical
Parameter Store slot. What remains to persist is metadata, meaning each record's lifecycle
and its reference, and that is all this store holds.

IT REUSES THE IN-MEMORY BACKEND'S PROTOCOL RATHER THAN RE-SPELLING IT. `InMemorySecretStore`
already implements the append-only chain, the already-committed recognition of a fenced
retry, and the committed / condition-failed / unavailable distinctions. This module only
loads the chains from disk, hands them to that implementation, and writes them back when a
conditional set committed a NEW revision. A second implementation of the comparison would
be a second place for it to be wrong.

THE LOCK SPANS READ, COMPARE AND WRITE. Every manager invocation is a separate process, so
two concurrent conditional sets must not both read the same predecessor and both append.
Reads take no lock: the file is replaced atomically, so a reader sees one whole revision
set or the other.

AN UNSAFE FILE IS REPORTED, NEVER REPAIRED. `_lpm_localstate` refuses a symlinked,
foreign-owned or broader-permission path, and this module refuses a file whose shape it
cannot read. Each such defect returns `unavailable` and leaves the file exactly as found,
because replacing it would erase history the manager may still be bound by.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from _foreman_vendor_path import VENDOR_PATHS_INSTALLED
from _lpm_localstate import read_local_record, write_local_record
from _lpm_locks import release_lock, take_lock
from _lpm_results import ManagerError
from _lpm_revisions import RevisionItem
from _lpm_store import (
    ConditionalSet,
    InMemorySecretStore,
    metadata_get_result,
    metadata_list_result,
    set_result,
)

from overseer._vendor.returns.result import Failure, Result

_ = VENDOR_PATHS_INSTALLED

__all__: list[str] = [
    "REFERENCE_STORE_DIRECTORY",
    "LocalReferenceMetadataStore",
]

REFERENCE_STORE_DIRECTORY: Final = "parameter-store-reference"
_METADATA_FILE: Final = "metadata.json"
_LOCK_FILE: Final = "metadata.lock"
_FILE_VERSION: Final = 1
_ITEM_MEMBERS: Final = frozenset({"title", "predecessor_sha256", "record"})

_Chains = dict[str, list[RevisionItem]]


@dataclass(frozen=True, kw_only=True)
class LocalReferenceMetadataStore:
    """A SecretStore whose append-only chains persist in one owner-only local file."""

    state_dir: Path
    owner_uid: int
    lock_timeout_seconds: float
    write_record: Callable[..., Result[None, ManagerError]] = write_local_record

    def metadata_get(self, *, record_id: str) -> dict[str, object]:
        """The closed metadata-get result for one record."""
        chains = self._load()
        if chains is None:
            return metadata_get_result(status="unavailable")
        return InMemorySecretStore(items=chains).metadata_get(record_id=record_id)

    def metadata_list(self) -> dict[str, object]:
        """Every chain's current revision, plus every invalid-chain descriptor."""
        chains = self._load()
        if chains is None:
            return metadata_list_result(status="unavailable")
        return InMemorySecretStore(items=chains).metadata_list()

    def credential_conditional_set(self, *, request: ConditionalSet) -> dict[str, object]:
        """Append `request`'s revision under the store lock, or report why it did not."""
        locked = take_lock(
            path=self._directory() / _LOCK_FILE,
            owner_uid=self.owner_uid,
            timeout_seconds=self.lock_timeout_seconds,
            monotonic=time.monotonic,
            sleep=time.sleep,
        )
        if isinstance(locked, Failure):
            return set_result(status="unavailable")
        held = locked.unwrap()
        try:
            return self._set_locked(request=request)
        finally:
            release_lock(held=held)

    def _set_locked(self, *, request: ConditionalSet) -> dict[str, object]:
        chains = self._load()
        if chains is None:
            return set_result(status="unavailable")
        before = len(chains.get(request.record_id, []))
        backend = InMemorySecretStore(items=chains)
        outcome = backend.credential_conditional_set(request=request)
        if len(backend.items.get(request.record_id, [])) == before:
            return outcome
        written = self.write_record(
            path=self._directory() / _METADATA_FILE,
            value=_encoded(chains=backend.items),
            owner_uid=self.owner_uid,
        )
        if isinstance(written, Failure):
            return set_result(status="unavailable")
        return outcome

    def _load(self) -> _Chains | None:
        stored = read_local_record(
            path=self._directory() / _METADATA_FILE, owner_uid=self.owner_uid
        )
        if isinstance(stored, Failure):
            return None
        value = stored.unwrap()
        if value is None:
            return {}
        return _decoded(value=value)

    def _directory(self) -> Path:
        return self.state_dir / REFERENCE_STORE_DIRECTORY


def _encoded(*, chains: _Chains) -> dict[str, object]:
    return {
        "version": _FILE_VERSION,
        "chains": {
            record_id: [
                {
                    "title": item.title,
                    "predecessor_sha256": item.predecessor_sha256,
                    "record": item.record,
                }
                for item in items
            ]
            for record_id, items in chains.items()
        },
    }


def _decoded(*, value: object) -> _Chains | None:
    if not isinstance(value, dict):
        return None
    envelope = cast("dict[str, object]", value)
    if set(envelope) != {"version", "chains"} or envelope["version"] != _FILE_VERSION:
        return None
    raw_chains = envelope["chains"]
    if not isinstance(raw_chains, dict):
        return None
    chains: _Chains = {}
    for record_id, raw_items in cast("dict[str, object]", raw_chains).items():
        items = _decoded_items(raw_items=raw_items)
        if items is None:
            return None
        chains[record_id] = items
    return chains


def _decoded_items(*, raw_items: object) -> list[RevisionItem] | None:
    if not isinstance(raw_items, list):
        return None
    items: list[RevisionItem] = []
    for raw in cast("list[object]", raw_items):
        if not isinstance(raw, dict) or frozenset(cast("dict[str, object]", raw)) != _ITEM_MEMBERS:
            return None
        fields = cast("dict[str, object]", raw)
        if not all(isinstance(fields[name], str) for name in _ITEM_MEMBERS):
            return None
        typed = cast("dict[str, str]", fields)
        items.append(
            RevisionItem(
                title=typed["title"],
                predecessor_sha256=typed["predecessor_sha256"],
                record=typed["record"],
            )
        )
    return items
