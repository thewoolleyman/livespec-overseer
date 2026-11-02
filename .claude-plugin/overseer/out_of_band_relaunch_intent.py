"""Durable start-intent records for sanctioned operator relaunches."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Protocol

import registry

__all__: list[str] = ["finish_intent", "record_start_intent"]

_ACTION = "sanctioned-out-of-band-relaunch"
_INTENT_NAME = ".out-of-band-relaunch-intent.json"


class _IntentRequest(Protocol):
    @property
    def invoker(self) -> str: ...

    @property
    def target(self) -> str: ...


def _intent_path(*, track: registry.Track) -> Path:
    return Path(track.repo) / "tmp" / "overseer" / track.topic / _INTENT_NAME


def _intent_value(
    *, track: registry.Track, request: _IntentRequest, outcome: str | None
) -> dict[str, object]:
    return {
        "action": _ACTION,
        "invoker": request.invoker,
        "outcome": outcome,
        "target": request.target,
        "track": f"{track.repo}::{track.topic}",
    }


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


def record_start_intent(*, track: registry.Track, request: _IntentRequest) -> Path:
    """Persist an attempted relaunch before its launch command is submitted."""
    path = _intent_path(track=track)
    _durable_json(path=path, value=_intent_value(track=track, request=request, outcome=None))
    return path


def finish_intent(
    *, path: Path, track: registry.Track, request: _IntentRequest, outcome: str
) -> None:
    """Amend the already-recorded intent with the final terminal outcome."""
    _durable_json(path=path, value=_intent_value(track=track, request=request, outcome=outcome))
