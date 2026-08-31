"""Model-enforcement orchestration for caam account rotation."""

from __future__ import annotations

import contextlib
import time
from pathlib import Path
from typing import Final, cast

from caam_effort import enforce_effort_floor
from caam_enforcement_options import model_context
from caam_enforcement_orchestrated import enforce_orchestrated_models, fable_left
from caam_picker import real_picker_tmux
from caam_profile_state import load_state, save_state
from caam_session_models import apply_session_model_exceptions
from caam_sessions import discover_session_models, enforce_session_models
from claude_sessions import proc_children, proc_environ

__all__: list[str] = [
    "enforce_models",
]

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
        _persist_session_model_requests(model_options=model_options)
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
            messages.extend(enforce_orchestrated_models(panes=panes, context=context))
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
                    emit_event=context.run.emit_event,
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


def _persist_session_model_requests(*, model_options: dict[str, object]) -> None:
    requested = model_options.get("session_models")
    if not isinstance(requested, tuple):
        return
    state_path = model_options.get("state_path")
    if not isinstance(state_path, Path):
        return
    state = model_options.get("state")
    current_state = (
        cast(dict[str, object], state)
        if isinstance(state, dict)
        else load_state(state_path=state_path)
    )
    active_fable = model_options.get("active_fable")
    _ = apply_session_model_exceptions(
        state=current_state,
        requested_models=cast(tuple[tuple[str, str], ...], requested),
        fable_left=fable_left(
            active_fable=active_fable if isinstance(active_fable, float) else None
        ),
    )
    with contextlib.suppress(*_SAVE_ERRORS):
        save_state(state=current_state, state_path=state_path)
