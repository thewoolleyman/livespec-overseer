"""Model-enforcement orchestration for caam account rotation."""

from __future__ import annotations

import contextlib
import time
from pathlib import Path
from typing import Final, cast

from caam_effort import enforce_effort_floor
from caam_enforcement_options import ModelContext, ModelRun, model_context
from caam_foreman_override import apply_foreman_model_override
from caam_picker import real_picker_tmux
from caam_profile_state import save_state
from caam_sessions import (
    SessionModel,
    discover_session_models,
    enforce_session_models,
)
from claude_sessions import proc_children, proc_environ

__all__: list[str] = [
    "enforce_models",
]

_FABLE_EXHAUSTED: Final = 100.0
_sleep = time.sleep
_ADVISORY_ERRORS: Final = (
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
    KeyError,
    IndexError,
)
_SAVE_ERRORS: Final = (OSError, RuntimeError, TypeError, ValueError)


def enforce_models(
    *,
    settings_path: Path,
    no_models: bool,
    **model_options: object,
) -> list[str]:
    messages = enforce_effort_floor(settings_path=settings_path)
    if no_models:
        return messages
    context = model_context(
        options=model_options,
        real_picker_tmux=real_picker_tmux,
        proc_children=proc_children,
        proc_environ=proc_environ,
        sleep=_sleep,
    )
    if context is None:
        return messages

    try:
        panes = discover_session_models(
            session_names=context.session_names,
            home=context.home,
            pane_pid=context.pane_pid,
            children_of=context.children_of,
            environ_of=context.environ_of,
            model_reader=context.model_reader,
        )
        if context.orchestrated:
            messages.extend(_enforce_orchestrated_models(panes=panes, context=context))
        else:
            messages.extend(
                enforce_session_models(
                    panes=panes,
                    state=context.state,
                    want=cast(str, context.want_model),
                    now=context.run.now,
                    set_model=context.run.set_model,
                    pane_idle=context.run.pane_idle,
                    dry_run=context.run.dry_run,
                )
            )
    except _ADVISORY_ERRORS as exc:
        messages.append(
            f"models: enforcement failed ({type(exc).__name__}: {exc}) -- "
            "table and rotation unaffected"
        )
    with contextlib.suppress(*_SAVE_ERRORS):
        save_state(state=context.state, state_path=context.state_path)
    return messages


def _enforce_orchestrated_models(
    *,
    panes: tuple[SessionModel, ...],
    context: ModelContext,
) -> list[str]:
    fable_left = context.active_fable is not None and context.active_fable < _FABLE_EXHAUSTED
    foreman = apply_foreman_model_override(
        state=context.state,
        requested_model=context.foreman_model,
        default_model="fable" if fable_left else "opus",
        fable_left=fable_left,
    )
    actions = [
        action
        for pane in panes
        for action in _actions_for_pane(
            pane=pane,
            state=context.state,
            fable_left=fable_left,
            want_foreman=foreman.want_foreman,
            run=context.run,
        )
    ]
    balance = "left" if fable_left else "EXHAUSTED"
    suffix = ", ".join(actions) if actions else "nothing to change"
    pinned = " [pinned]" if foreman.pinned else ""
    return [
        *foreman.messages,
        f"models: foremen want {foreman.want_foreman}{pinned} "
        f"(active account Fable {balance}); {suffix}",
    ]


def _actions_for_pane(
    *,
    pane: SessionModel,
    state: dict[str, object],
    fable_left: bool,
    want_foreman: str,
    run: ModelRun,
) -> list[str]:
    want = _wanted_model(session=pane.session, fable_left=fable_left, want_foreman=want_foreman)
    if want is None:
        return []
    try:
        return enforce_session_models(
            panes=(pane,),
            state=state,
            want=want,
            now=run.now,
            set_model=run.set_model,
            pane_idle=run.pane_idle,
            dry_run=run.dry_run,
        )
    except _ADVISORY_ERRORS as exc:
        return [f"{pane.session} SKIPPED({type(exc).__name__})"]


def _wanted_model(*, session: str, fable_left: bool, want_foreman: str) -> str | None:
    if session.endswith("-foreman"):
        return want_foreman
    if not fable_left:
        return "opus"
    return None
