"""Shared return-path handling for the caam account-rotation executable."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

__all__: list[str] = [
    "LineWriter",
    "SaveState",
    "finish",
]


class LineWriter(Protocol):
    def __call__(self, line: str) -> None: ...


class SaveState(Protocol):
    def __call__(self, *, state: dict[str, object], state_path: Path) -> None: ...


def finish(
    *,
    code: int,
    state: dict[str, object],
    state_path: Path,
    save: SaveState,
    stdout: LineWriter,
    lines: tuple[str, ...],
) -> int:
    save(state=state, state_path=state_path)
    for line in lines:
        stdout(line)
    return code
