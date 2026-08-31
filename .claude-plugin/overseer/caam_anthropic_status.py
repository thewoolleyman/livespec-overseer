"""Status-table and advisory output for the caam account-rotation pass."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, cast

from _caam_pass_span import PassSpan, linked_emitter
from caam_candidate_diagnosis import unverifiable_candidate_names
from caam_decision import ProfileUsage, UsageRecord, render_table
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


class Flags(Protocol):
    @property
    def dry_run(self) -> bool: ...

    @property
    def no_models(self) -> bool: ...

    @property
    def foreman_model(self) -> str | None: ...

    @property
    def session_models(self) -> tuple[tuple[str, str], ...]: ...

    @property
    def protected_accounts(self) -> tuple[tuple[str, str], ...]: ...


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

    # The pass's open span, when the caller is a span-carrying rotation pass. A
    # direct `write_status` caller has none, and enforcement then reports nothing.
    @property
    def span(self) -> PassSpan | None: ...


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
    extra_messages: tuple[str, ...] = (),
) -> None:
    now_dt = datetime.fromtimestamp(context.now, tz=timezone.utc)
    rows = cast(tuple[RenderableProfileUsage, ...], profiles)
    lines = render_table(rows=rows, active_name=active_name, now=now_dt).splitlines()
    for line in (
        *lines,
        *model_messages(context=context, active_fable=current.fable, enforce_models=enforce_models),
        *extra_messages,
    ):
        context.stdout(line)
    note = unverified_note(profiles=profiles, active_name=active_name)
    if note is not None:
        context.stdout(note)


def unverified_note(*, profiles: tuple[ProfileUsage, ...], active_name: str) -> str | None:
    """Name every account excluded for want of a live verification, cached ones too.

    This used to list only rows with NO usage at all -- the fully dark ones -- so a
    table carrying three cached rows told the operator that exactly one account had
    been excluded, while three more were excluded silently with their remembered
    figures still rendered as if they were usable.
    """
    names = unverifiable_candidate_names(profiles=profiles, active_name=active_name)
    return None if not names else _UNVERIFIED_NOTE.format(names=", ".join(names))


def model_messages(
    *, context: StatusContext, active_fable: float | None, enforce_models: EnforceModels
) -> tuple[str, ...]:
    messages = enforce_models(
        settings_path=context.home / ".claude/settings.json",
        no_models=context.flags.no_models,
        home=context.home,
        state=context.state,
        state_path=context.state_path,
        active_fable=active_fable,
        foreman_model=context.flags.foreman_model,
        session_models=context.flags.session_models,
        dry_run=context.flags.dry_run,
        now=None,
        **_span_options(span=context.span),
    )
    return tuple(messages)


def _span_options(*, span: PassSpan | None) -> dict[str, object]:
    """The pass span's two hooks into enforcement, or nothing at all without one.

    `emit_event` is the pass's OWN emitter, wrapped so each pane record hangs
    under the pass span -- deliberately the same object the pass will close on,
    so one pass reads its OTLP configuration once. `note_facts` is the return
    path for the four pass-wide conditions only enforcement can observe.
    """

    if span is None:
        return {}
    return {
        "emit_event": linked_emitter(emit=span.emit, trace=span.trace),
        "note_facts": span.note_facts,
    }
