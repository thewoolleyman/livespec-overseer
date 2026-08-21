"""Claude pane session discovery and transcript model reading for caam."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

import claude_sessions
import jsonio
from _seams import PidToIntList, PidToOptionalBytes

__all__: list[str] = [
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
_TRANSCRIPT_TAIL_BYTES: Final = 65_536
_SET_SUPPRESS_DEFAULT_S: Final = "3600"
_MODEL_PREFIXES: Final = {
    "claude-fable": "fable",
    "claude-opus": "opus",
    "claude-sonnet": "sonnet",
    "claude-haiku": "haiku",
}


class PanePid(Protocol):
    def __call__(self, *, session: str) -> int: ...


class PaneCapture(Protocol):
    def __call__(self, *, session: str) -> str: ...


class ModelSetter(Protocol):
    def __call__(self, *, session: str, model: str) -> None: ...


@dataclass(frozen=True, kw_only=True)
class SessionModel:
    session: str
    session_id: str
    model: str | None


def set_suppress_s() -> float:
    return float(os.environ.get("CAAM_ROTATE_SET_SUPPRESS_S", _SET_SUPPRESS_DEFAULT_S))


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
    capture_pane: PaneCapture | None = None,
) -> tuple[SessionModel, ...]:
    del capture_pane
    panes: list[SessionModel] = []
    for session in session_names:
        pid = pane_pid(session=session)
        session_id = _session_id_from_tree(
            root=pid,
            children_of=children_of,
            environ_of=environ_of,
        )
        if session_id is None:
            continue
        panes.append(
            SessionModel(
                session=session,
                session_id=session_id,
                model=pane_model(home=home, session_id=session_id),
            )
        )
    return tuple(panes)


def pane_model(*, home: Path, session_id: str) -> str | None:
    for transcript in sorted((home / ".claude" / "projects").glob(f"*/{session_id}.jsonl")):
        return _model_from_transcript(path=transcript)
    return None


def recently_set(*, state: dict[str, object], session: str, want: str, now: float) -> bool:
    models = jsonio.as_object(value=state.get("models")) or {}
    record = jsonio.as_object(value=models.get(session))
    if record is None or record.get("want") != want:
        return False
    at = jsonio.as_float(value=record.get("at"))
    return at is not None and now - at <= set_suppress_s()


def enforce_session_models(
    *,
    panes: tuple[SessionModel, ...],
    state: dict[str, object],
    want: str,
    now: float | None = None,
    set_model: ModelSetter,
) -> list[str]:
    checked_at = time.time() if now is None else now
    messages: list[str] = []
    for pane in panes:
        if pane.model == want or recently_set(
            state=state, session=pane.session, want=want, now=checked_at
        ):
            continue
        set_model(session=pane.session, model=want)
        _record_model_set(state=state, session=pane.session, want=want, now=checked_at)
        messages.append(f"model: {pane.session} -> {want}")
    return messages


def newest_project_model_for_test(*, home: Path, project: str) -> str | None:
    """Test-only mirror of the rejected newest-in-project heuristic."""

    transcripts = tuple((home / ".claude" / "projects" / project).glob("*.jsonl"))
    newest = max(transcripts, key=lambda path: path.stat().st_mtime_ns)
    return _model_from_transcript(path=newest)


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


def _model_from_transcript(*, path: Path) -> str | None:
    raw = _read_tail(path=path, size=_TRANSCRIPT_TAIL_BYTES)
    found: str | None = None
    for line in raw.decode(errors="replace").splitlines():
        model = _model_from_line(line=line)
        if model is not None:
            found = model
    return None if found is None else _mapped_model(model=found)


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


def _record_model_set(*, state: dict[str, object], session: str, want: str, now: float) -> None:
    models = jsonio.as_object(value=state.get("models")) or {}
    state["models"] = models
    models[session] = {"want": want, "at": now}
