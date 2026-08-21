"""Model-enforcement orchestration for caam account rotation."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Final, cast

from _seams import PidToIntList, PidToOptionalBytes
from caam_effort import enforce_effort_floor
from caam_profile_state import load_state, save_state
from caam_sessions import (
    ModelSetter,
    PanePid,
    SessionModel,
    discover_session_models,
    enforce_session_models,
)

__all__: list[str] = [
    "enforce_models",
]

_FABLE_EXHAUSTED: Final = 100.0
_ADVISORY_ERRORS: Final = (
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
    KeyError,
    IndexError,
)


def enforce_models(
    *,
    settings_path: Path,
    no_models: bool,
    **model_options: object,
) -> list[str]:
    messages = enforce_effort_floor(settings_path=settings_path)
    if no_models:
        return messages
    home = _path_option(options=model_options, key="home")
    state_path = _path_option(options=model_options, key="state_path")
    session_names = _session_names_option(options=model_options)
    want_model = _string_option(options=model_options, key="want_model")
    active_fable = _active_fable_option(options=model_options)
    now = _float_option(options=model_options, key="now")
    pane_pid = _pane_pid_option(options=model_options)
    children_of = _children_option(options=model_options)
    environ_of = _environ_option(options=model_options)
    set_model = _setter_option(options=model_options)
    if (
        home is None
        or state_path is None
        or (want_model is None and "active_fable" not in model_options)
        or pane_pid is None
        or children_of is None
        or environ_of is None
        or set_model is None
    ):
        return messages

    state = load_state(state_path=state_path)
    try:
        panes = discover_session_models(
            session_names=session_names,
            home=home,
            pane_pid=pane_pid,
            children_of=children_of,
            environ_of=environ_of,
        )
        if "active_fable" in model_options:
            messages.append(
                _enforce_orchestrated_models(
                    panes=panes,
                    state=state,
                    active_fable=active_fable,
                    now=now,
                    set_model=set_model,
                )
            )
        else:
            messages.extend(
                enforce_session_models(
                    panes=panes,
                    state=state,
                    want=cast(str, want_model),
                    now=now,
                    set_model=set_model,
                )
            )
    except _ADVISORY_ERRORS as exc:
        messages.append(
            f"models: enforcement failed ({type(exc).__name__}: {exc}) -- "
            "table and rotation unaffected"
        )
    finally:
        with contextlib.suppress(OSError):
            save_state(state=state, state_path=state_path)
    return messages


def _path_option(*, options: dict[str, object], key: str) -> Path | None:
    value = options.get(key)
    return value if isinstance(value, Path) else None


def _string_option(*, options: dict[str, object], key: str) -> str | None:
    value = options.get(key)
    return value if isinstance(value, str) else None


def _active_fable_option(*, options: dict[str, object]) -> float | None:
    value = options.get("active_fable")
    if isinstance(value, float):
        return value
    return None


def _float_option(*, options: dict[str, object], key: str) -> float | None:
    value = options.get(key)
    return value if isinstance(value, float) else None


def _session_names_option(*, options: dict[str, object]) -> tuple[str, ...]:
    value = options.get("session_names")
    if not isinstance(value, tuple):
        return ()
    items = cast(tuple[object, ...], value)
    return tuple(item for item in items if isinstance(item, str))


def _pane_pid_option(*, options: dict[str, object]) -> PanePid | None:
    value = options.get("pane_pid")
    return cast(PanePid, value) if callable(value) else None


def _children_option(*, options: dict[str, object]) -> PidToIntList | None:
    value = options.get("children_of")
    return cast(PidToIntList, value) if callable(value) else None


def _environ_option(*, options: dict[str, object]) -> PidToOptionalBytes | None:
    value = options.get("environ_of")
    return cast(PidToOptionalBytes, value) if callable(value) else None


def _setter_option(*, options: dict[str, object]) -> ModelSetter | None:
    value = options.get("set_model")
    return cast(ModelSetter, value) if callable(value) else None


def _enforce_orchestrated_models(
    *,
    panes: tuple[SessionModel, ...],
    state: dict[str, object],
    active_fable: float | None,
    now: float | None,
    set_model: ModelSetter,
) -> str:
    fable_left = active_fable is not None and active_fable < _FABLE_EXHAUSTED
    want_foreman = "fable" if fable_left else "opus"
    actions = [
        action
        for pane in panes
        for action in _actions_for_pane(
            pane=pane,
            state=state,
            fable_left=fable_left,
            want_foreman=want_foreman,
            now=now,
            set_model=set_model,
        )
    ]
    balance = "left" if fable_left else "EXHAUSTED"
    suffix = ", ".join(actions) if actions else "nothing to change"
    return f"models: foremen want {want_foreman} (active account Fable {balance}); {suffix}"


def _actions_for_pane(
    *,
    pane: SessionModel,
    state: dict[str, object],
    fable_left: bool,
    want_foreman: str,
    now: float | None,
    set_model: ModelSetter,
) -> list[str]:
    want = _wanted_model(session=pane.session, fable_left=fable_left, want_foreman=want_foreman)
    if want is None:
        return []
    try:
        return enforce_session_models(
            panes=(pane,),
            state=state,
            want=want,
            now=now,
            set_model=set_model,
        )
    except _ADVISORY_ERRORS as exc:
        return [f"{pane.session} SKIPPED({type(exc).__name__})"]


def _wanted_model(*, session: str, fable_left: bool, want_foreman: str) -> str | None:
    if session.endswith("-foreman"):
        return want_foreman
    if not fable_left:
        return "opus"
    return None
