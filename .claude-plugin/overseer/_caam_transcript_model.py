"""Transcript model reading for caam session model enforcement.

The read scans BACKWARD in bounded steps, up to ``_SCAN_MAX_BYTES``, for the
last line that ATTESTS a model (work-item overseer-o3t75c.1). Two kinds of line
do: an assistant entry's ``message.model``, and the answer a ``/model`` local
command writes back ("Set model to Fable 5", "Kept model as Fable 5").

Reading only the first kind is what made the spam self-perpetuating
(overseer-o3t75c.2). An idle session accumulates a tail of ``/model``
invocation entries, which carry no ``message.model``; once they push the last
assistant entry past the scan bound the read is unknown, unknown never equals
the wanted model, so enforcement drives the picker -- which appends yet more of
them. Reading the ANSWER inverts that: the drive's own footprint states the
model the pane is on, so the pass after a drive reads the wanted model and
suppresses itself. The suppression is then a property of the pane's transcript
rather than of a memo that has to survive to the next pass -- which the live
memos measurably did not.
"""

from __future__ import annotations

import json
import os
import re
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
_PREFIX_BY_FAMILY: Final = {family: prefix for prefix, family in _MODEL_PREFIXES.items()}
_LOCAL_STDOUT_RE: Final = re.compile(r"<local-command-stdout>(.*?)</local-command-stdout>")
_MODEL_ANSWER_RE: Final = re.compile(r"(?:set model to|kept model as)\s+(.+)", re.IGNORECASE)


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
    """The model id one transcript line attests, or None if it attests none."""

    assistant = _assistant_model(line=line)
    return _answered_model(line=line) if assistant is None else assistant


def _assistant_model(*, line: str) -> str | None:
    try:
        parsed: object = json.loads(line)
    except json.JSONDecodeError:
        return None
    body = jsonio.as_object(value=parsed)
    message = jsonio.as_object(value=None if body is None else body.get("message"))
    model = None if message is None else message.get("model")
    return model if isinstance(model, str) else None


def _answered_model(*, line: str) -> str | None:
    """The model id a ``/model`` local-command answer on ``line`` names.

    Matched against the RAW line rather than the parsed message content: the
    answer's own characters need no JSON escaping, so one pattern reads it
    whichever shape the content takes (a bare string, or a list of blocks).
    Requiring the full ``<local-command-stdout>`` wrapper AND the answer phrase
    keeps a transcript that merely QUOTES such an answer from being read as one.
    """

    for stdout in _LOCAL_STDOUT_RE.finditer(line):
        answer = _MODEL_ANSWER_RE.search(stdout.group(1))
        if answer is None:
            continue
        label = answer.group(1).lower()
        family = next((name for name in _MODEL_PREFIXES.values() if name in label), None)
        if family is not None:
            return _PREFIX_BY_FAMILY[family]
    return None


def _mapped_model(*, model: str) -> str | None:
    return next(
        (short for prefix, short in _MODEL_PREFIXES.items() if model.startswith(prefix)), None
    )
