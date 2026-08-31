"""Option parsing and production seams for caam model enforcement."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

import _caam_span_seam
from _caam_pane_decision import PaneEventEmitter
from _caam_pass_span import PassFactsSink
from _seams import PidToIntList, PidToOptionalBytes
from caam_picker import Sleep, drive_model_picker, pane_is_idle
from caam_profile_state import load_state
from caam_sessions import ModelSetter, PaneIdle, PaneModelReader, PanePid

_SESSION_MODEL_PARTS = 2

__all__: list[str] = [
    "EnforcementTmux",
    "ModelContext",
    "ModelRun",
    "model_context",
]


class EnforcementTmux(Protocol):
    def capture_pane(self, *, session: str) -> str: ...

    def send_keys(self, *, session: str, keys: str) -> bool: ...

    def send_literal_keys(self, *, session: str, text: str) -> bool: ...

    def list_sessions(self) -> list[str]: ...

    def pane_pid(self, *, session: str) -> int | None: ...


@dataclass(frozen=True, kw_only=True)
class ModelRun:
    now: float | None
    set_model: ModelSetter
    pane_idle: PaneIdle
    dry_run: bool
    emit_event: PaneEventEmitter


@dataclass(frozen=True, kw_only=True)
class ModelContext:
    home: Path
    state_path: Path
    session_names: tuple[str, ...]
    want_model: str | None
    active_fable: float | None
    foreman_model: str | None
    session_models: tuple[tuple[str, str], ...]
    orchestrated: bool
    pane_pid: PanePid
    children_of: PidToIntList
    environ_of: PidToOptionalBytes
    model_reader: PaneModelReader | None
    state: dict[str, object]
    run: ModelRun
    # Absent for every caller that is not a span-carrying rotation pass, which is
    # every direct `enforce_models` caller and every test that wants no telemetry.
    note_facts: PassFactsSink | None


def model_context(
    *,
    options: dict[str, object],
    real_picker_tmux: Callable[[], EnforcementTmux],
    proc_children: PidToIntList,
    proc_environ: PidToOptionalBytes,
    sleep: Sleep = time.sleep,
) -> ModelContext | None:
    home = _path_option(options=options, key="home")
    state_path = _path_option(options=options, key="state_path")
    want_model = _string_option(options=options, key="want_model")
    orchestrated = "active_fable" in options
    if home is None or state_path is None or (want_model is None and not orchestrated):
        return None

    tmux = real_picker_tmux()
    pane_idle = _pane_idle_option(options=options)
    set_model = _setter_option(options=options)
    if set_model is None:
        pane_idle = _production_pane_idle(tmux=tmux) if pane_idle is None else pane_idle
        set_model = _production_set_model(tmux=tmux, sleep=sleep)
    return ModelContext(
        home=home,
        state_path=state_path,
        session_names=_session_names(options=options, tmux=tmux),
        want_model=want_model,
        active_fable=_active_fable_option(options=options),
        foreman_model=_string_option(options=options, key="foreman_model"),
        session_models=_session_models_setting(options=options),
        orchestrated=orchestrated,
        pane_pid=_pane_pid_option(options=options) or tmux.pane_pid,
        children_of=_children_option(options=options) or proc_children,
        environ_of=_environ_option(options=options) or proc_environ,
        model_reader=_pane_model_option(options=options),
        state=_loaded_state(options=options, state_path=state_path),
        note_facts=_note_facts_option(options=options),
        run=ModelRun(
            now=_float_option(options=options, key="now"),
            set_model=set_model,
            pane_idle=pane_idle or _always_idle,
            dry_run=_bool_option(options=options, key="dry_run"),
            # Resolved ONCE per context so every pane in a pass ships through the
            # same configuration, and so an unconfigured host pays for reading the
            # environment once rather than per pane.
            emit_event=_emitter_option(options=options) or _caam_span_seam.emitter_from_env(),
        ),
    )


def _session_names(*, options: dict[str, object], tmux: EnforcementTmux) -> tuple[str, ...]:
    names = _session_names_option(options=options)
    return names if names else tuple(tmux.list_sessions())


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


def _bool_option(*, options: dict[str, object], key: str) -> bool:
    value = options.get(key)
    return value if isinstance(value, bool) else False


def _state_option(*, options: dict[str, object]) -> dict[str, object] | None:
    value = options.get("state")
    return cast(dict[str, object], value) if isinstance(value, dict) else None


def _loaded_state(*, options: dict[str, object], state_path: Path) -> dict[str, object]:
    state = _state_option(options=options)
    return load_state(state_path=state_path) if state is None else state


def _session_names_option(*, options: dict[str, object]) -> tuple[str, ...]:
    value = options.get("session_names")
    if not isinstance(value, tuple):
        return ()
    items = cast(tuple[object, ...], value)
    return tuple(item for item in items if isinstance(item, str))


def _session_models_setting(*, options: dict[str, object]) -> tuple[tuple[str, str], ...]:
    value = options.get("session_models")
    if not isinstance(value, tuple):
        return ()
    items = cast(tuple[object, ...], value)
    parsed: list[tuple[str, str]] = []
    for item in items:
        if not isinstance(item, tuple):
            continue
        parts = cast(tuple[object, ...], item)
        if len(parts) != _SESSION_MODEL_PARTS:
            continue
        session, model = parts
        if isinstance(session, str) and isinstance(model, str):
            parsed.append((session, model))
    return tuple(parsed)


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


def _pane_idle_option(*, options: dict[str, object]) -> PaneIdle | None:
    value = options.get("pane_idle")
    return cast(PaneIdle, value) if callable(value) else None


def _emitter_option(*, options: dict[str, object]) -> PaneEventEmitter | None:
    value = options.get("emit_event")
    return cast(PaneEventEmitter, value) if callable(value) else None


def _note_facts_option(*, options: dict[str, object]) -> PassFactsSink | None:
    value = options.get("note_facts")
    return cast(PassFactsSink, value) if callable(value) else None


def _pane_model_option(*, options: dict[str, object]) -> PaneModelReader | None:
    value = options.get("pane_model")
    return cast(PaneModelReader, value) if callable(value) else None


def _production_pane_idle(*, tmux: EnforcementTmux) -> PaneIdle:
    def idle(*, session: str) -> bool:
        return pane_is_idle(screen=tmux.capture_pane(session=session))

    return idle


def _production_set_model(*, tmux: EnforcementTmux, sleep: Sleep) -> ModelSetter:
    def set_model(*, session: str, model: str) -> str:
        # The picker's own verdict is the answer -- `already-set` in particular, which
        # is the actuator catching a mis-read upstream and is exactly what the decision
        # span needs to distinguish from a real switch.
        return drive_model_picker(
            tmux=tmux,
            session=session,
            want=model,
            sleep=sleep,
            check_idle=False,
        )

    return set_model


def _always_idle(*, session: str) -> bool:
    del session
    return True
