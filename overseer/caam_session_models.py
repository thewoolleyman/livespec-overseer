"""Per-session model exception state for caam enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import jsonio
from caam_foreman_override import WANTED_MODELS

__all__: list[str] = [
    "SessionModelExceptions",
    "apply_session_model_exceptions",
]

STATE_KEY: Final = "session-models"
_CLEAR_VALUES: Final = frozenset(("auto", "", "none"))


@dataclass(frozen=True, kw_only=True)
class SessionModelExceptions:
    values: dict[str, str]
    messages: tuple[str, ...]

    def want_for(self, *, session: str) -> str | None:
        return self.values.get(session)

    def summary(self) -> str | None:
        if not self.values:
            return None
        pairs = ", ".join(f"{session}={model}" for session, model in self.values.items())
        return f"exceptions: {pairs}"


def apply_session_model_exceptions(
    *, state: dict[str, object], requested_models: tuple[tuple[str, str], ...], fable_left: bool
) -> SessionModelExceptions:
    exceptions = dict(_stored_exceptions(state=state))
    messages: list[str] = []
    for session, requested_model in requested_models:
        _apply_requested_model(
            exceptions=exceptions,
            session=session,
            requested_model=requested_model,
            messages=messages,
        )
    if exceptions or requested_models or STATE_KEY in state:
        state[STATE_KEY] = exceptions
    for session, model in exceptions.items():
        if model == "fable" and not fable_left:
            messages.append(
                f"models: WARNING {session} pins fable but the active account's Fable "
                "is spent -- that session will be blocked"
            )
    return SessionModelExceptions(values=exceptions, messages=tuple(messages))


def _stored_exceptions(*, state: dict[str, object]) -> dict[str, str]:
    stored = jsonio.as_object(value=state.get(STATE_KEY)) or {}
    return {
        session: model
        for session, model in stored.items()
        if isinstance(model, str) and model in WANTED_MODELS
    }


def _apply_requested_model(
    *,
    exceptions: dict[str, str],
    session: str,
    requested_model: str,
    messages: list[str],
) -> None:
    value = requested_model.strip().lower()
    if not session:
        messages.append(
            f"models: ignoring --session-model={session}={value} (expected session=model)"
        )
        return
    if value in _CLEAR_VALUES:
        _ = exceptions.pop(session, None)
        return
    if value in WANTED_MODELS:
        exceptions[session] = value
        return
    messages.append(
        f"models: ignoring --session-model={session}={value} (expected fable/opus or auto)"
    )
