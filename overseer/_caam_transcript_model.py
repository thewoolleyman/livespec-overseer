"""Transcript model reading for caam session model enforcement.

The read scans BACKWARD in bounded steps, up to ``_SCAN_MAX_BYTES``, for the
last assistant ``message.model`` line (work-item overseer-o3t75c.1). A
``/model`` local command writes no such line, so an idle session accumulates a
tail of model-free entries; reading only the final 64 KiB then reported an
unknown model, which never equals the wanted one -- and every re-drive of the
picker appended more model-free lines, making the unknown read
self-perpetuating.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Final

import jsonio

__all__: list[str] = [
    "newest_project_model_for_test",
    "pane_model",
]

_TAIL_BYTES: Final = 65_536
_SCAN_MAX_BYTES: Final = 1_048_576
_SCAN_GROWTH: Final = 4
_MODEL_PREFIXES: Final = {
    "claude-fable": "fable",
    "claude-opus": "opus",
    "claude-sonnet": "sonnet",
    "claude-haiku": "haiku",
}


def pane_model(*, home: Path, session_id: str) -> str | None:
    for transcript in sorted((home / ".claude" / "projects").glob(f"*/{session_id}.jsonl")):
        return _model_from_transcript(path=transcript)
    return None


def newest_project_model_for_test(*, home: Path, project: str) -> str | None:
    """Test-only mirror of the rejected newest-in-project heuristic."""

    transcripts = tuple((home / ".claude" / "projects" / project).glob("*.jsonl"))
    _index, newest = max(
        enumerate(transcripts), key=lambda item: (item[1].stat().st_mtime_ns, item[0])
    )
    return _model_from_transcript(path=newest)


def _model_from_transcript(*, path: Path) -> str | None:
    size = _TAIL_BYTES
    while True:
        raw = _read_tail(path=path, size=size)
        found = _last_model_in(raw=raw)
        if found is not None:
            return _mapped_model(model=found)
        if len(raw) < size or size >= _SCAN_MAX_BYTES:
            return None
        size = min(size * _SCAN_GROWTH, _SCAN_MAX_BYTES)


def _last_model_in(*, raw: bytes) -> str | None:
    found: str | None = None
    for line in raw.decode(errors="replace").splitlines():
        model = _model_from_line(line=line)
        if model is not None:
            found = model
    return found


def _read_tail(*, path: Path, size: int) -> bytes:
    with path.open("rb") as handle:
        _ = handle.seek(0, os.SEEK_END)
        end = handle.tell()
        _ = handle.seek(max(0, end - size))
        return handle.read()


def _model_from_line(*, line: str) -> str | None:
    try:
        parsed: object = json.loads(line)
    except json.JSONDecodeError:
        return None
    body = jsonio.as_object(value=parsed)
    message = jsonio.as_object(value=None if body is None else body.get("message"))
    model = None if message is None else message.get("model")
    return model if isinstance(model, str) else None


def _mapped_model(*, model: str) -> str | None:
    return next(
        (short for prefix, short in _MODEL_PREFIXES.items() if model.startswith(prefix)), None
    )
