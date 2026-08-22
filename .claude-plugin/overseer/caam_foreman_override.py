"""Foreman model override state for caam enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

__all__: list[str] = [
    "WANTED_MODELS",
    "ForemanModelChoice",
    "apply_foreman_model_override",
]

WANTED_MODELS: Final = frozenset(("fable", "opus"))
_CLEAR_VALUES: Final = frozenset(("auto", "", "none"))


@dataclass(frozen=True, kw_only=True)
class ForemanModelChoice:
    want_foreman: str
    pinned: bool
    messages: tuple[str, ...]


def apply_foreman_model_override(
    *,
    state: dict[str, object],
    requested_model: str | None,
    default_model: str,
    fable_left: bool,
) -> ForemanModelChoice:
    messages: list[str] = []
    if requested_model is not None:
        _apply_requested_model(
            state=state,
            requested_model=requested_model,
            messages=messages,
        )

    stored = state.get("foreman_model")
    pinned = stored if isinstance(stored, str) and stored in WANTED_MODELS else None
    want_foreman = pinned or default_model
    if pinned == "fable" and not fable_left:
        messages.append(
            "models: WARNING foreman override pins fable but the active account's Fable "
            "is spent -- those sessions will be blocked"
        )
    return ForemanModelChoice(
        want_foreman=want_foreman,
        pinned=pinned is not None,
        messages=tuple(messages),
    )


def _apply_requested_model(
    *,
    state: dict[str, object],
    requested_model: str,
    messages: list[str],
) -> None:
    value = requested_model.strip().lower()
    if value in _CLEAR_VALUES:
        _ = state.pop("foreman_model", None)
        messages.append("models: foreman override cleared -- back to Fable unless spent")
        return
    if value in WANTED_MODELS:
        state["foreman_model"] = value
        messages.append(
            f"models: foreman override set to {value} -- persists until --foreman-model=auto"
        )
        return
    messages.append(f"models: ignoring --foreman-model={value} (expected fable/opus or auto)")
