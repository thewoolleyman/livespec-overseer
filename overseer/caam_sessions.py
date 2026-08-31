"""Claude pane session discovery for caam, and the façade over model enforcement.

This module owns finding the panes: walking a tmux pane's process tree to its
``CLAUDE_CODE_SESSION_ID``, taking the transcript read for that id, and assembling
the ``SessionModel`` value the rest of caam works from. The transcript read itself
lives in ``_caam_transcript_model``; what enforcement DOES with the result lives in
``_caam_session_enforce``, whose public entry points are re-exported here so
``import caam_sessions`` remains the whole consumer surface.

The pane carries its read's PROVENANCE, not just the model (work-item
overseer-m7qrgp.2): which transcript resolved, and which kind of line attested the
model. Both ride onto the ``caam.enforcement.pane`` span, where they separate the
two very different causes of an unknown read -- a transcript that was never
located, and one that WAS located but whose scanned tail attests nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol, cast

import claude_sessions
from _caam_session_enforce import (
    ModelSetter,
    PaneIdle,
    enforce_session_models,
    recently_set,
    set_suppress_s,
)
from _caam_transcript_model import (
    READ_SOURCE_NONE,
    PaneRead,
    newest_project_model_for_test,
    pane_model,
    pane_read,
)
from _seams import PidToIntList, PidToOptionalBytes

__all__: list[str] = [
    "ModelSetter",
    "PaneCapture",
    "PaneIdle",
    "SessionModel",
    "descendant_pids",
    "discover_session_models",
    "enforce_session_models",
    "newest_project_model_for_test",
    "pane_model",
    "recently_set",
    "set_suppress_s",
]

_SESSION_ENV_PREFIX: Final = "CLAUDE_CODE_SESSION_ID="


class PanePid(Protocol):
    def __call__(self, *, session: str) -> int | None: ...


class PaneCapture(Protocol):
    def __call__(self, *, session: str) -> str: ...


class PaneModelReader(Protocol):
    def __call__(self, *, home: Path, session_id: str) -> str | None: ...


@dataclass(frozen=True, kw_only=True)
class SessionModel:
    """One discovered pane and the model read that was taken for it.

    ``source`` and ``transcript`` default to "no transcript read happened" so a
    hand-built pane -- every test seam, and any caller that already knows the model
    -- states exactly that rather than claiming a provenance it does not have.
    """

    session: str
    session_id: str
    model: str | None
    source: str = READ_SOURCE_NONE
    transcript: str | None = None


def descendant_pids(
    *, root: int, depth: int = 4, children_of: PidToIntList = claude_sessions.proc_children
) -> tuple[int, ...]:
    """Breadth-first process-tree walk, including ``root``."""

    out: list[int] = []
    frontier = [root]
    for _level in range(depth):
        out.extend(frontier)
        frontier = [child for pid in frontier for child in children_of(pid=pid)]
    out.extend(frontier)
    return tuple(out)


def discover_session_models(
    *,
    session_names: tuple[str, ...],
    home: Path,
    pane_pid: PanePid,
    children_of: PidToIntList = claude_sessions.proc_children,
    environ_of: PidToOptionalBytes = claude_sessions.proc_environ,
    **discovery_options: object,
) -> tuple[SessionModel, ...]:
    _ = discovery_options.get("capture_pane")
    model_reader = _pane_model_option(options=discovery_options)
    panes: list[SessionModel] = []
    for session in session_names:
        pid = pane_pid(session=session)
        if pid is None:
            continue
        session_id = _session_id_from_tree(
            root=pid,
            children_of=children_of,
            environ_of=environ_of,
        )
        if session_id is None:
            continue
        read = _read_for(home=home, session_id=session_id, model_reader=model_reader)
        panes.append(
            SessionModel(
                session=session,
                session_id=session_id,
                model=read.model,
                source=read.source,
                transcript=read.transcript,
            )
        )
    return tuple(panes)


def _read_for(*, home: Path, session_id: str, model_reader: PaneModelReader | None) -> PaneRead:
    """The pane's read, plus the provenance the span reports it with.

    The transcript is resolved either way, so an OVERRIDDEN read still names the file
    the pass would have consulted. Its source, however, only carries through when the
    override AGREES with what that file attests: no transcript line stands behind a
    model some other reader supplied, and claiming one would put a fabricated
    provenance on the span.
    """

    read = pane_read(home=home, session_id=session_id)
    if model_reader is None:
        return read
    overridden = model_reader(home=home, session_id=session_id)
    return PaneRead(
        model=overridden,
        source=read.source if overridden == read.model else READ_SOURCE_NONE,
        transcript=read.transcript,
    )


def _session_id_from_tree(
    *, root: int, children_of: PidToIntList, environ_of: PidToOptionalBytes
) -> str | None:
    for pid in descendant_pids(root=root, children_of=children_of):
        session_id = _session_id_from_environ(environ=environ_of(pid=pid))
        if session_id is not None:
            return session_id
    return None


def _session_id_from_environ(*, environ: bytes | None) -> str | None:
    if not environ:
        return None
    for entry in environ.decode(errors="replace").split("\0"):
        if entry.startswith(_SESSION_ENV_PREFIX):
            return entry.removeprefix(_SESSION_ENV_PREFIX) or None
    return None


def _pane_model_option(*, options: dict[str, object]) -> PaneModelReader | None:
    value = options.get("model_reader")
    return cast(PaneModelReader, value) if callable(value) else None
