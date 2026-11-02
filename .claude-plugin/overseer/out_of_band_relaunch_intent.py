"""Durable start-intent records for the attended relaunch surface."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Protocol

import registry

__all__: list[str] = ["finish_intent", "start_intent"]

_ACTION = "sanctioned-out-of-band-relaunch"
_INTENT_NAME = ".out-of-band-relaunch-intent.json"


class RelaunchRequest(Protocol):
    """The request fields that belong in an immutable start-intent record."""

    @property
    def invoker(self) -> str: ...

    @property
    def target(self) -> str: ...


def _intent_path(*, track: registry.Track) -> Path:
    return Path(track.repo) / "tmp" / "overseer" / track.topic / _INTENT_NAME


def _durable_json(*, path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        json.dump(value, handle, sort_keys=True, separators=(",", ":"))
        _ = handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    _ = temporary.replace(path)
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _intent_value(
    *,
    error: str | None = None,
    outcome: str | None,
    request: RelaunchRequest,
    track: registry.Track,
) -> dict[str, object]:
    value: dict[str, object] = {
        "action": _ACTION,
        "invoker": request.invoker,
        "outcome": outcome,
        "target": request.target,
        "track": f"{track.repo}::{track.topic}",
    }
    if error is not None:
        value["error"] = error
    return value


def start_intent(*, request: RelaunchRequest, track: registry.Track) -> Path:
    """Durably record an authorized launch intent before its terminal input."""
    path = _intent_path(track=track)
    _durable_json(
        path=path,
        value=_intent_value(
            outcome=None,
            request=request,
            track=track,
        ),
    )
    return path


def finish_intent(
    *,
    error: str | None = None,
    outcome: str,
    path: Path,
    request: RelaunchRequest,
    track: registry.Track,
) -> None:
    """Atomically replace a recorded intent with its terminal outcome."""
    _durable_json(
        path=path,
        value=_intent_value(
            error=error,
            outcome=outcome,
            request=request,
            track=track,
        ),
    )
