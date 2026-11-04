"""Generic callbacks the runtime-specific relaunch arms compose."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from _supervisor_launch import SubmitResult

__all__: list[str] = ["RelaunchActions"]


@dataclass(frozen=True, kw_only=True)
class RelaunchActions:
    """The generic entrypoint operations a runtime-specific arm orders."""

    finish_intent: Callable[..., None]
    resume_for_track: Callable[..., str | None]
    submit_prompt_result: Callable[..., SubmitResult]
    rebind: Callable[..., bool]
