"""Durable replay interlock for uncertain terminal bootstrap mutations.

The public bootstrap writes one exact-instance intent BEFORE asking a backend to
split.  A process that dies, or a native request whose reply is lost after the
write boundary, therefore leaves a durable reason not to repeat the mutation.
The record is scoped by backend, socket, live server generation and invoking
pane; an old server generation cannot hold a replacement generation hostage.

This journal authorizes no terminal action and contains no cleanup verb.  It can
only block a mutation, retain the known created-pane identity after an uncertain
reply, or remove its own record after the backend has freshly proved a live
daemon or a mutation has settled with a known result.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import terminal_ownership

__all__: list[str] = [
    "BootstrapMutationJournal",
    "MutationJournal",
    "NoMutationJournal",
    "default_journal_root",
]

_STATE_DIR = ".local/state/livespec-overseer/bootstrap"


class MutationJournal(Protocol):
    """Durable replay interlock surrounding one terminal layout mutation."""

    def pending_error(self, *, claim: terminal_ownership.OwnershipClaim) -> str: ...

    def prepare(self, *, claim: terminal_ownership.OwnershipClaim) -> None: ...

    def retain(self, *, claim: terminal_ownership.OwnershipClaim, pane_id: str) -> None: ...

    def resolve(self, *, claim: terminal_ownership.OwnershipClaim) -> None: ...


@dataclass(frozen=True, kw_only=True)
class NoMutationJournal:
    """No-op journal retained for direct library callers and deterministic tests."""

    def pending_error(self, *, claim: terminal_ownership.OwnershipClaim) -> str:
        _ = claim
        return ""

    def prepare(self, *, claim: terminal_ownership.OwnershipClaim) -> None:
        _ = claim

    def retain(self, *, claim: terminal_ownership.OwnershipClaim, pane_id: str) -> None:
        _ = claim, pane_id

    def resolve(self, *, claim: terminal_ownership.OwnershipClaim) -> None:
        _ = claim


def default_journal_root(*, home: Path | None = None) -> Path:
    """Per-user directory holding exact-target bootstrap uncertainty records."""
    return (Path.home() if home is None else home) / _STATE_DIR


def _identity(*, claim: terminal_ownership.OwnershipClaim) -> dict[str, object]:
    return {
        "backend": claim.backend,
        "socket_path": claim.socket_path,
        "server_pid": claim.server_pid,
        "server_starttime": claim.server_starttime,
        "invoking_pane_id": claim.pane_id,
    }


def _record(*, claim: terminal_ownership.OwnershipClaim, pane_id: str) -> str:
    value = _identity(claim=claim)
    value["known_created_pane_id"] = pane_id
    return json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"


@dataclass(frozen=True, kw_only=True)
class BootstrapMutationJournal:
    """Filesystem implementation of :class:`bootstrap.MutationJournal`.

    Exclusive creation serializes two public bootstrap processes racing for the
    same exact target.  A truncated or malformed record fails closed: it means a
    prior process crossed the prepare boundary and did not establish a settled
    result, regardless of how many bytes reached disk.
    """

    root: Path = field(default_factory=default_journal_root)

    def pending_error(self, *, claim: terminal_ownership.OwnershipClaim) -> str:
        """Why this exact target still has an unresolved mutation, or ``""``."""
        path = self._path(claim=claim)
        if not path.exists():
            return ""
        return self._unresolved(path=path)

    def prepare(self, *, claim: terminal_ownership.OwnershipClaim) -> None:
        """Exclusively persist intent before the first terminal mutation."""
        path = self._path(claim=claim)
        self.root.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            _ = handle.write(_record(claim=claim, pane_id=""))
            handle.flush()
            os.fsync(handle.fileno())

    def retain(self, *, claim: terminal_ownership.OwnershipClaim, pane_id: str) -> None:
        """Retain an uncertain effect, adding its created pane when known."""
        path = self._path(claim=claim)
        self.root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=self.root, delete=False
        ) as handle:
            temporary = Path(handle.name)
            _ = handle.write(_record(claim=claim, pane_id=pane_id))
            handle.flush()
            os.fsync(handle.fileno())
        _ = temporary.replace(path)

    def resolve(self, *, claim: terminal_ownership.OwnershipClaim) -> None:
        """Remove only this target's journal record after a settled observation."""
        path = self._path(claim=claim)
        path.unlink(missing_ok=True)

    def _path(self, *, claim: terminal_ownership.OwnershipClaim) -> Path:
        encoded = json.dumps(_identity(claim=claim), sort_keys=True).encode()
        return self.root / f"{hashlib.sha256(encoded).hexdigest()}.json"

    @staticmethod
    def _unresolved(*, path: Path) -> str:
        return (
            f"a previous terminal mutation remains unresolved at {path}; "
            "refusing to repeat it — further action requires fresh exact-instance, "
            "pane and process evidence"
        )
