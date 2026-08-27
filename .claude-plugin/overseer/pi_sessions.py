"""Live Pi active-session identity — the Pi twin of :mod:`codex_sessions`.

Pi keeps no pid-keyed registry, and it holds no rollout fd open, so neither the
Claude registry join nor the Codex ``/proc``-plus-rollout join transfers. What it
does have is a SUPPORTED identity carrier at exactly the boundary the shared
foreman skill uses: a command run by Pi's LLM-callable ``bash`` tool receives
``PI_SESSION_ID`` and ``PI_SESSION_FILE`` resolved from the CURRENT session
manager, alongside the inherited process markers ``AI_AGENT=pi`` and
``PI_CODING_AGENT=true``. The injection DELETES any inherited values before
writing the current ones, so a nested Pi cannot present a stale parent session;
and the user-entered ``!`` / ``!!`` path deliberately injects nothing, so a
command typed there fails this reader closed. Measured against
``@earendil-works/pi-coding-agent`` 0.84.3; see
``plan/foreman-codex-pi-runtime-support/research/002-pi-shell-session-environment.md``.

**The join, and why it is exact rather than a heuristic.** Four independent facts
must agree before any identity is produced::

    AI_AGENT + PI_CODING_AGENT  -->  the caller IS a Pi tool invocation
    PI_SESSION_FILE             -->  the CURRENT session's JSONL file
    its `session` header        -->  id (must equal PI_SESSION_ID) + THE REPO
    its latest `session_info`   -->  name             == THE PLAN TOPIC

The header binds the id to a repository and the environment binds the invocation
to that id, so neither a tmux name nor a pane read is ever consulted. Whether the
name is the canonical foreman name, and whether the cwd is the governed
repository, stay the ENTRY GATE's questions — this module supplies evidence and
holds no policy, exactly as ``codex_sessions`` does.

**Secrets caution — this module NEVER reads a session's transcript.** A Pi
session file interleaves identity metadata with the whole conversation: messages,
tool results, compaction summaries. Only two record shapes are decoded at all,
and a line is classified from a BOUNDED RAW PREFIX before any decode, so a
transcript-bearing record is skipped without being decoded, retained, logged or
returned. An over-long line is DRAINED rather than read whole, so a large
transcript record is never held in memory either. Keep it that way: a widened
classifier turns a transcript into an identity source.

Fail-closed throughout. Every refusal returns the empty list, which is the same
shape :func:`codex_sessions.read_live_codex_sessions` returns for "no evidence",
so the foreman entry gate consumes Pi through its existing code path rather than
growing a Pi branch that could drift.

Stdlib-only, like every module in this folder. The environment and the JSON
decode are both injected, so the beside-tests run with no Pi process, no Pi
installation, and no real session file.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TextIO

import jsonio

__all__: list[str] = [
    "AI_AGENT_ENV",
    "MAX_CLASSIFIED_PREFIX_CHARS",
    "MAX_METADATA_LINE_CHARS",
    "MAX_SCANNED_RECORDS",
    "PI_AGENT",
    "PI_CODING_AGENT_ENV",
    "PI_CODING_AGENT_TRUE",
    "PI_SESSION_FILE_ENV",
    "PI_SESSION_ID_ENV",
    "SESSION_HEADER_TYPE",
    "SESSION_INFO_TYPE",
    "MetadataLineParse",
    "PiSession",
    "metadata_record_type",
    "read_live_pi_sessions",
]

# The two inherited process markers. They identify the INVOKING TOOL PATH rather
# than the machine: Pi's built-in `bash`/`powershell` tools carry them, and the
# `!` / `!!` shell path a user types by hand does not.
AI_AGENT_ENV = "AI_AGENT"
PI_AGENT = "pi"
PI_CODING_AGENT_ENV = "PI_CODING_AGENT"
PI_CODING_AGENT_TRUE = "true"

# The two per-invocation session variables, re-resolved from the current session
# manager on every tool call.
PI_SESSION_ID_ENV = "PI_SESSION_ID"
PI_SESSION_FILE_ENV = "PI_SESSION_FILE"

# The only two record shapes this module will decode. Both are metadata-only in
# Pi's session format; every other shape carries transcript content.
SESSION_HEADER_TYPE = "session"
SESSION_INFO_TYPE = "session_info"
_METADATA_TYPES: frozenset[str] = frozenset({SESSION_HEADER_TYPE, SESSION_INFO_TYPE})

# Bounds on the streaming read. A metadata record is small; these are generous
# for one and far below any transcript record worth worrying about.
MAX_METADATA_LINE_CHARS = 8192
MAX_CLASSIFIED_PREFIX_CHARS = 256
MAX_SCANNED_RECORDS = 50000

# Matches the FIRST `"type": "<value>"` in a bounded prefix, whatever the value.
# Capturing ANY value and testing it against `_METADATA_TYPES` afterwards is what
# makes the classifier honest: an alternation over the two metadata names alone
# would happily skip past a transcript record's own `"type": "message"` and match
# the words `"type": "session"` occurring later inside its CONTENT.
_TYPE_RE = re.compile(r'"type"\s*:\s*"([^"\\]*)"')


class MetadataLineParse(Protocol):
    """Decode ONE already-classified metadata line into a JSON-object result.

    Injected so a test can prove WHICH lines are decoded, which is the property
    the transcript-safety rule above actually rests on — a returned identity
    shows what came out, never what was read on the way.
    """

    def __call__(self, *, line: str) -> jsonio.JsonObjectParse: ...


@dataclass(frozen=True, kw_only=True)
class PiSession:
    """One live, NAMED Pi session, joined to its plan topic and repository.

    Mirrors :class:`codex_sessions.CodexSession` where the two runtimes agree, so
    the foreman entry gate's ``name`` + ``cwd`` identity shape is satisfied
    without a Pi-specific accessor. There is no ``pid`` twin: the evidence is the
    CALLER's own environment rather than a scan of other processes, so the only
    process involved is this one.
    """

    session_id: str
    name: str
    cwd: str


def metadata_record_type(*, line: str) -> str:
    """Which metadata record shape a RAW line declares — ``""`` when none.

    The classifier, and the whole of the no-transcript-decoding guarantee's first
    half: it reads at most ``MAX_CLASSIFIED_PREFIX_CHARS`` characters of the raw
    line and never calls a JSON decoder, so a message, tool-result or compaction
    record is refused before its contents are parsed. ``""`` is the refusal and
    covers every non-metadata shape, including ones Pi has not shipped yet.

    ⚠️ RESIDUAL, stated rather than smoothed over, because it is narrower than it
    first looks. A token quoted inside a STRING value cannot match: JSON escapes
    those quotes, so ``\\"type\\": \\"session\\"`` is not the characters this
    pattern looks for. A NESTED OBJECT can — a record carrying
    ``{"content": {"type": "session"}, "type": "message"}`` classifies as a header
    here. :func:`_metadata_record` closes that by re-checking the DECODED
    record's own top-level ``type``, so such a line is dropped rather than
    believed; the residual is only that it was decoded.
    """
    match = _TYPE_RE.search(line[:MAX_CLASSIFIED_PREFIX_CHARS])
    if match is None:
        return ""
    kind = match.group(1)
    return kind if kind in _METADATA_TYPES else ""


def read_live_pi_sessions(
    *,
    env: Mapping[str, str] | None = None,
    parse: MetadataLineParse = jsonio.parse_object_line,
    max_line_chars: int = MAX_METADATA_LINE_CHARS,
    max_records: int = MAX_SCANNED_RECORDS,
) -> list[PiSession]:
    """The ONE live Pi session that issued this command, or ``[]``.

    A list rather than a scalar because that is the shape the foreman entry gate
    already consumes for both other runtimes; it holds at most one element,
    because the evidence is the caller's own environment and a process has one.

    Every one of these refuses, and each returns ``[]`` rather than raising: the
    process markers absent (``!`` / ``!!``, or a plain shell), no-session mode or
    an unset ``PI_SESSION_FILE``, a missing or non-regular or undecodable file,
    metadata that is malformed or over-long, a header whose id is not the
    environment's id, a header with no cwd, and a latest ``session_info`` whose
    name is absent or empty.
    """
    environ = os.environ if env is None else env
    if environ.get(AI_AGENT_ENV) != PI_AGENT:
        return []
    if environ.get(PI_CODING_AGENT_ENV) != PI_CODING_AGENT_TRUE:
        return []
    session_id = environ.get(PI_SESSION_ID_ENV, "")
    session_file = environ.get(PI_SESSION_FILE_ENV, "")
    if not session_id or not session_file:
        return []
    records = _read_metadata_records(
        path=Path(session_file),
        parse=parse,
        max_line_chars=max_line_chars,
        max_records=max_records,
    )
    header_id, cwd = _header_identity(records=records)
    name = _latest_session_name(records=records)
    if header_id != session_id or not cwd or not name:
        return []
    return [PiSession(session_id=session_id, name=name, cwd=cwd)]


def _read_metadata_records(
    *, path: Path, parse: MetadataLineParse, max_line_chars: int, max_records: int
) -> list[tuple[str, dict[str, object]]]:
    """Every metadata record in ``path``, in file order — ``[]`` on any refusal.

    Bounded on three axes, which together are the second half of the
    no-transcript-retention guarantee: at most ``max_records`` lines are
    considered at all; no more than ``max_line_chars`` characters of any one line
    are ever held; and a line that exceeds that is DRAINED by
    :func:`_drain_line` instead of being read whole.

    Fail-soft: a missing or non-regular path, an unreadable one, and a non-UTF-8
    file all yield ``[]`` — the ``ValueError`` leg covers the
    ``UnicodeDecodeError`` a binary file raises, which is not an ``OSError``.
    """
    records: list[tuple[str, dict[str, object]]] = []
    try:
        if not path.is_file():
            return []
        with path.open(encoding="utf-8") as handle:
            for _scanned in range(max_records):
                line = handle.readline(max_line_chars + 1)
                if not line:
                    break
                if len(line) > max_line_chars:
                    _drain_line(handle=handle, max_line_chars=max_line_chars)
                    continue
                record = _metadata_record(line=line, parse=parse)
                if record is not None:
                    records.append(record)
    except (OSError, ValueError):
        return []
    return records


def _drain_line(*, handle: TextIO, max_line_chars: int) -> None:
    """Discard the remainder of an over-long line, ``max_line_chars`` at a time.

    Skipping the line by reading it whole would defeat the bound it violated, so
    the tail is consumed in bounded chunks and none of it is retained. Returns at
    the line's newline, or at end of file when the last line has none.
    """
    while True:
        chunk = handle.readline(max_line_chars)
        if not chunk or chunk.endswith("\n"):
            return


def _metadata_record(
    *, line: str, parse: MetadataLineParse
) -> tuple[str, dict[str, object]] | None:
    """``(kind, record)`` for a metadata line, or None when it is not one.

    The decoded record's OWN top-level ``type`` must confirm the raw
    classification. That closes the residual named on
    :func:`metadata_record_type`: a line admitted because its content quoted the
    token is dropped here rather than being treated as an identity source.
    """
    kind = metadata_record_type(line=line)
    if not kind:
        return None
    parsed = parse(line=line)
    if jsonio.is_parse_failure(result=parsed):
        return None
    record = parsed.unwrap()
    if record is None or record.get("type") != kind:
        return None
    return (kind, record)


def _header_identity(*, records: Sequence[tuple[str, dict[str, object]]]) -> tuple[str, str]:
    """``(id, cwd)`` from the FIRST ``session`` header — ``("", "")`` when absent.

    The first header is the one Pi's format guarantees is metadata-only and
    writes at session creation. A later one is deliberately not allowed to
    redefine the session's identity.
    """
    for kind, record in records:
        if kind == SESSION_HEADER_TYPE:
            return (_text(record=record, key="id"), _text(record=record, key="cwd"))
    return ("", "")


def _latest_session_name(*, records: Sequence[tuple[str, dict[str, object]]]) -> str:
    """The LATEST ``session_info`` name — ``""`` when no such record carries one.

    Last-writer-wins, INCLUDING an explicitly empty name: a cleared display name
    is not the canonical foreman name, and reaching back to an earlier record
    would resurrect a name the session no longer has. A ``session_info`` that
    carries no ``name`` key at all leaves the previous value standing, so an
    entry written for some other field does not silently un-name a live seat.
    """
    name = ""
    for kind, record in records:
        if kind == SESSION_INFO_TYPE and "name" in record:
            name = _text(record=record, key="name")
    return name


def _text(*, record: dict[str, object], key: str) -> str:
    """One string field of an already-decoded record — ``""`` when absent or not a str."""
    value = record.get(key)
    return value if isinstance(value, str) else ""
