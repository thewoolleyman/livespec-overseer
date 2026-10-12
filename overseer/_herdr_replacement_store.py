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
_MALFORMED_RECORD = "malformed durable Herdr replacement record"

_PHASES = frozenset(
    {
        "before-stop",
        "signal-attempted",
        "stopped-awaiting-shell",
        "launch-attempted",
        "rename-attempted",
        "successor-observed",
        "resume-attempted",
        "completed",
    }
)


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


def _positive_int(*, value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _number(*, value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _nonempty_text(*, value: object) -> bool:
    return isinstance(value, str) and bool(value)


def _mapping(*, value: object, field: str) -> dict[str, object]:
    del field
    if not isinstance(value, dict):
        raise TypeError(_MALFORMED_RECORD)
    return cast(dict[str, object], value)


def _process_record(*, value: object, field: str, complete_image: bool) -> None:
    record = _mapping(value=value, field=field)
    required = {"pid", "starttime", "process_group"}
    if complete_image:
        required.update({"executable", "argv", "session_id"})
    if not required.issubset(record):
        raise ValueError(_MALFORMED_RECORD)
    if not _positive_int(value=record["pid"]) or not _positive_int(value=record["process_group"]):
        raise ValueError(_MALFORMED_RECORD)
    if not _nonempty_text(value=record["starttime"]):
        raise ValueError(_MALFORMED_RECORD)
    if not complete_image:
        return
    argv = record["argv"]
    if (
        not _nonempty_text(value=record["executable"])
        or not isinstance(argv, list)
        or not argv
        or any(not isinstance(item, str) for item in cast(list[object], argv))
        or not _positive_int(value=record["session_id"])
    ):
        raise ValueError(_MALFORMED_RECORD)


def _validate_transaction(*, value: object) -> dict[str, object]:
    transaction = _mapping(value=value, field="record")
    required = {
        "version",
        "phase",
        "target",
        "server",
        "runtime",
        "predecessor",
        "shell",
        "round",
        "launch",
    }
    if not required.issubset(transaction):
        raise ValueError(_MALFORMED_RECORD)
    if transaction["version"] != 1 or isinstance(transaction["version"], bool):
        raise ValueError(_MALFORMED_RECORD)
    if transaction["phase"] not in _PHASES:
        raise ValueError(_MALFORMED_RECORD)
    if not _nonempty_text(value=transaction["target"]):
        raise ValueError(_MALFORMED_RECORD)
    if transaction["runtime"] not in {"claude", "codex"}:
        raise ValueError(_MALFORMED_RECORD)

    server = _mapping(value=transaction["server"], field="server")
    if not {"socket_path", "pid", "starttime", "pane_id"}.issubset(server) or not all(
        (
            _nonempty_text(value=server.get("socket_path")),
            _positive_int(value=server.get("pid")),
            _nonempty_text(value=server.get("starttime")),
            _nonempty_text(value=server.get("pane_id")),
        )
    ):
        raise ValueError(_MALFORMED_RECORD)

    _process_record(value=transaction["predecessor"], field="predecessor", complete_image=False)
    _process_record(value=transaction["shell"], field="shell", complete_image=True)

    round_record = _mapping(value=transaction["round"], field="round")
    if not {"ready_mtime", "round_at", "session_identity"}.issubset(round_record) or not all(
        (
            _number(value=round_record.get("ready_mtime")),
            _number(value=round_record.get("round_at")),
            _nonempty_text(value=round_record.get("session_identity")),
        )
    ):
        raise ValueError(_MALFORMED_RECORD)

    launch = _mapping(value=transaction["launch"], field="launch")
    environment = launch.get("env")
    if (
        not {"command", "cwd", "env"}.issubset(launch)
        or not _nonempty_text(value=launch.get("command"))
        or not _nonempty_text(value=launch.get("cwd"))
        or not isinstance(environment, dict)
        or any(
            item is not None and not isinstance(item, str)
            for item in cast(dict[str, object], environment).values()
        )
    ):
        raise ValueError(_MALFORMED_RECORD)
    return transaction


def read_transaction(*, path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    return _validate_transaction(value=value)
