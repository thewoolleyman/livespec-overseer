"""Claude pane session discovery and model enforcement for caam.

The transcript read itself lives in ``_caam_transcript_model``; this module
owns what enforcement DOES with it. One rule keeps enforcement from re-driving
a pane that is already on the wanted model (work-item overseer-o3t75c.1): an
unknown (``None``) read is NOT evidence of a mismatch. It authorises ONE
verifying drive per session and wanted model -- remembered under the
``models_unknown`` state key, independently of the time-boxed ``models`` memo --
and never re-authorises one while the read stays unknown. Settling the pane is
left to the actuator, which dismisses the picker without switching when the
model is already correct (``caam_picker.PICKER_ALREADY_SET``). A later KNOWN
mismatch acts as usual and re-arms the verify.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol, cast

import claude_sessions
import jsonio
from _caam_transcript_model import newest_project_model_for_test, pane_model
from _seams import PidToIntList, PidToOptionalBytes

__all__: list[str] = [
    "PaneCapture",
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
_SET_SUPPRESS_DEFAULT_S: Final = "3600"


class PanePid(Protocol):
    def __call__(self, *, session: str) -> int | None: ...


class PaneCapture(Protocol):
    def __call__(self, *, session: str) -> str: ...


class PaneModelReader(Protocol):
    def __call__(self, *, home: Path, session_id: str) -> str | None: ...


class PaneIdle(Protocol):
    def __call__(self, *, session: str) -> bool: ...


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
    **discovery_options: object,
) -> tuple[SessionModel, ...]:
    _ = discovery_options.get("capture_pane")
    model_reader = _pane_model_option(options=discovery_options)
    read_model = pane_model if model_reader is None else model_reader
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
        panes.append(
            SessionModel(
                session=session,
                session_id=session_id,
                model=read_model(home=home, session_id=session_id),
            )
        )
    return tuple(panes)


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
    **model_options: object,
) -> list[str]:
    checked_at = time.time() if now is None else now
    pane_idle = _pane_idle_option(options=model_options)
    dry_run = _bool_option(options=model_options, key="dry_run")
    messages: list[str] = []
    for pane in panes:
        if pane.model == want or recently_set(
            state=state, session=pane.session, want=want, now=checked_at
        ):
            continue
        unknown = pane.model is None
        if unknown and _unknown_verified(state=state, session=pane.session, want=want):
            continue
        model = pane.model or "unknown"
        if pane_idle is not None and not pane_idle(session=pane.session):
            messages.append(f"{pane.session} busy({model}->{want})")
            continue
        if dry_run:
            messages.append(f"{pane.session} would {model}->{want}")
            continue
        set_model(session=pane.session, model=want)
        _record_model_set(state=state, session=pane.session, want=want, now=checked_at)
        _record_unknown_read(state=state, session=pane.session, want=want, unknown=unknown)
        messages.append(f"{pane.session} {model}->{want}")
    return messages


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


def _record_model_set(*, state: dict[str, object], session: str, want: str, now: float) -> None:
    models = jsonio.as_object(value=state.get("models")) or {}
    state["models"] = models
    models[session] = {"want": want, "at": now}


def _unknown_verified(*, state: dict[str, object], session: str, want: str) -> bool:
    verified = jsonio.as_object(value=state.get("models_unknown")) or {}
    return verified.get(session) == want


def _record_unknown_read(
    *, state: dict[str, object], session: str, want: str, unknown: bool
) -> None:
    verified = jsonio.as_object(value=state.get("models_unknown")) or {}
    state["models_unknown"] = verified
    if unknown:
        verified[session] = want
        return
    _ = verified.pop(session, None)


def _pane_idle_option(*, options: dict[str, object]) -> PaneIdle | None:
    value = options.get("pane_idle")
    return cast(PaneIdle, value) if callable(value) else None


def _pane_model_option(*, options: dict[str, object]) -> PaneModelReader | None:
    value = options.get("model_reader")
    return cast(PaneModelReader, value) if callable(value) else None


def _bool_option(*, options: dict[str, object], key: str) -> bool:
    value = options.get(key)
    return value if isinstance(value, bool) else False
