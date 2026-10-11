"""Strict lock and durable JSON storage for a per-track Herdr replacement."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import cast

import registry

__all__: list[str] = [
    "LOCK_NAME",
    "RECORD_NAME",
    "durable_write",
    "read_transaction",
    "scratch_path",
    "transaction_lock",
]

RECORD_NAME = ".herdr-replacement.json"
LOCK_NAME = ".herdr-replacement.lock"


def scratch_path(*, track: registry.Track) -> Path:
    return Path(track.repo) / "tmp" / "overseer" / track.topic


@contextmanager
def transaction_lock(*, path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def durable_write(*, path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        json.dump(value, handle, sort_keys=True, separators=(",", ":"))
        _ = handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    _ = temporary.replace(path)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def read_transaction(*, path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    return cast(dict[str, object], value)
