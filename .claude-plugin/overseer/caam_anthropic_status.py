"""Status-table and advisory output for the caam account-rotation pass."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, cast

from caam_decision import ProfileUsage, UsageRecord, render_table
from caam_foreman_override import apply_foreman_model_override
from caam_rendering import RenderableProfileUsage

__all__: list[str] = [
    "EnforceModels",
    "Flags",
    "LineWriter",
    "StatusContext",
    "unverified_note",
    "write_status",
]

_UNVERIFIED_NOTE = (
    "note: {names} could not be verified live and were not considered. "
    "Revive with: caam activate claude <name>; claude -p ok; caam backup claude <name>"
)
_FABLE_EXHAUSTED = 100.0


class Flags(Protocol):
    @property
    def no_models(self) -> bool: ...

    @property
    def foreman_model(self) -> str | None: ...


class LineWriter(Protocol):
    def __call__(self, line: str) -> None: ...


class StatusContext(Protocol):
    @property
    def flags(self) -> Flags: ...

    @property
    def home(self) -> Path: ...

    @property
    def now(self) -> float: ...

    @property
    def state(self) -> dict[str, object]: ...

    @property
    def state_path(self) -> Path: ...

    @property
    def stdout(self) -> LineWriter: ...


class EnforceModels(Protocol):
    def __call__(
        self,
        *,
        settings_path: Path,
        no_models: bool,
        **model_options: object,
    ) -> list[str]: ...


def write_status(
    *,
    context: StatusContext,
    profiles: tuple[ProfileUsage, ...],
    active_name: str,
    current: UsageRecord,
    enforce_models: EnforceModels,
) -> None:
    now_dt = datetime.fromtimestamp(context.now, tz=timezone.utc)
    rows = cast(tuple[RenderableProfileUsage, ...], profiles)
    lines = render_table(rows=rows, active_name=active_name, now=now_dt).splitlines()
    for line in (
        *lines,
        *model_messages(context=context, active_fable=current.fable, enforce_models=enforce_models),
    ):
        context.stdout(line)
    note = unverified_note(profiles=profiles)
    if note is not None:
        context.stdout(note)


def unverified_note(*, profiles: tuple[ProfileUsage, ...]) -> str | None:
    names = tuple(profile.name for profile in profiles if profile.usage is None)
    return None if not names else _UNVERIFIED_NOTE.format(names=", ".join(names))


def model_messages(
    *, context: StatusContext, active_fable: float | None, enforce_models: EnforceModels
) -> tuple[str, ...]:
    fable_left = active_fable is not None and active_fable < _FABLE_EXHAUSTED
    foreman = apply_foreman_model_override(
        state=context.state,
        requested_model=context.flags.foreman_model,
        default_model="fable" if fable_left else "opus",
        fable_left=fable_left,
    )
    messages = enforce_models(
        settings_path=context.home / ".claude/settings.json",
        no_models=context.flags.no_models,
        home=context.home,
        state_path=context.state_path,
        active_fable=active_fable,
        foreman_model=foreman.want_foreman,
        now=None,
    )
    return (*foreman.messages, *messages)
