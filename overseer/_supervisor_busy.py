"""Busy branch of the supervisor decision cascade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import _supervisor_attention
import _supervisor_liveness
import _supervisor_nudge
import _supervisor_state
import registry
import signals

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["BusyDecision", "BusyRequest", "busy"]


@dataclass(frozen=True, kw_only=True)
class BusyDecision:
    note: str | None
    ready: bool
    blocked: str | None
    blocked_age: float | None
    blocked_age_label: str | None


@dataclass(frozen=True, kw_only=True)
class BusyRequest:
    sup: Supervisor
    track: registry.Track
    capture: str
    claude_status: str | None
    codex_fallback: bool
    generating: bool
    malformed: bool
    note: str | None
    ready: bool
    blocked: str | None
    act: bool


def busy(*, request: BusyRequest) -> BusyDecision:
    note = request.note
    ready = request.ready
    blocked = request.blocked
    blocked_age: float | None = None
    blocked_age_label: str | None = None
    if request.act:
        # A GENERATING session is not waiting on a human, so a `blocked:` it has
        # outlived is provably dead — retire it before the note is derived, or the
        # dead reason rides this row (it is the note default) and later fires a
        # false `blocked:human`. Busy via a BACKGROUND SHELL alone does NOT qualify:
        # that session is at its prompt and may genuinely still be waiting.
        blocked = _supervisor_state.void_stale_blocked(
            sup=request.sup,
            track=request.track,
            blocked=blocked,
            generating=request.generating,
        )
        declared = signals.read_state(repo=request.track.repo, topic=request.track.topic)
        blocked_age = _supervisor_liveness.blocked_age(sup=request.sup, declared=declared)
        blocked_age_label = _supervisor_liveness.age_label_or_none(seconds=blocked_age)
        if not request.malformed:
            note = _supervisor_liveness.blocked_note(
                blocked=blocked, blocked_age_label=blocked_age_label
            )
    # When the PANE itself looks idle, the row note explains WHY it is `working`,
    # or the operator would read the idle-looking pane and distrust the status.
    if not signals.is_busy(capture_text=request.capture):
        if request.claude_status == "shell" or request.codex_fallback:
            note = _supervisor_liveness.append_note(
                note=note if request.malformed else None,
                extra=_supervisor_attention.shell_evidence_note(),
            )
        # Provably always True where it stands: reaching here needs `busy` True
        # with `is_busy(capture)` False and the `shell`/codex-fallback arm above
        # already excluded, which leaves `claude_busy` as the only disjunct that
        # can be carrying `busy` — and `CLAUDE_BUSY_STATUSES` holds exactly
        # {"busy", "shell"}. So the else-exit is dead and branch coverage can
        # never close it.
        #
        # KEPT as an `elif` rather than demoted to `else` precisely because that
        # proof depends on the CURRENT contents of `CLAUDE_BUSY_STATUSES`, which
        # exists to be extended. Add a third status and `else` would silently
        # label it "sub-agent (Claude busy)" — wrong; the `elif` correctly leaves
        # the note unset. The dead arc is the cost of that safety, so it is
        # annotated rather than removed.
        elif request.claude_status == "busy":  # pragma: no branch
            note = _supervisor_liveness.append_note(
                note=note if request.malformed else None,
                extra="sub-agent (Claude busy)",
            )
    if request.act:
        # Void the certification ONLY if it is past the grace — a young
        # marker is the certifying turn's own busy tail and must survive
        # (RB1); an old one means the session resumed work after certifying.
        ready = _supervisor_state.void_if_stale(
            sup=request.sup,
            track=request.track,
            ready=ready,
            resumed_work=request.generating,
        )
        # The session took a turn — clear any idle-with-context-left nudge marker
        # so the NEXT idle-with-context episode re-nudges (re-arm on non-idle).
        _supervisor_nudge.clear_idle_nudge_state(sup=request.sup, track=request.track)
    return BusyDecision(
        note=note,
        ready=ready,
        blocked=blocked,
        blocked_age=blocked_age,
        blocked_age_label=blocked_age_label,
    )
