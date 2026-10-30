"""Busy-session wrap-up delivery: when a busy pane may still receive the wind-down.

Maintainer ruling 2026-10-15, ratified in SPECIFICATION v058 (spec.md, contracts.md and
constraints.md: the supervision round, the wrap-up injection, acting safety). The
idle-only delivery rule was WRONG: a session that never idles — a
running turn, sub-agents, monitors, background shells — could never be wound down and
therefore never restarted. Winding down, including stopping its own background work
before declaring ``ready``, is the SESSION's responsibility, so the daemon's only
obligation at the pane is not to type over INPUT: the wrap-up and its expiry-notice
tail are delivered into a busy pane whose input is POSITIVELY EMPTY and unchanged
across the settle captures.

What still suppresses the paste is evidence about the INPUT, never about busyness:
typed text, an open picker or structured gate, a runtime-reported human wait, a
standing declaration, ambiguous identity. The restart interlock is untouched — a
``ready`` still restarts only under its own no-busy gates — so nothing here can kill a
working session.

Codex is the asymmetric arm. Its empty composer shows a grey rotating placeholder that
an ANSI-stripped capture cannot tell from typed text; the structural idle-input shape is
the positive evidence for an IDLE Codex session, but a BUSY Codex session presents no
such evidence, so the paste is withheld and the reason surfaced (fail-closed).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_compaction
import _supervisor_liveness_time
import signals
from _supervisor_config import SETTLE_DELAY

if TYPE_CHECKING:
    import registry
    from _supervisor_core import Supervisor
    from _supervisor_records import Observation

__all__: list[str] = [
    "CODEX_BUSY_WITHHELD_CONDITION",
    "CODEX_BUSY_WITHHELD_NOTE",
    "codex_busy_withheld",
    "deliverable_while_busy",
    "input_empty",
    "input_settled",
    "obs_input_empty",
    "surface_codex_withheld",
    "wind_down_or_notice_owed",
]

CODEX_BUSY_WITHHELD_CONDITION = "codex-busy-wrapup-withheld"
CODEX_BUSY_WITHHELD_NOTE = "wrap-up withheld: busy Codex composer cannot be proven empty"

# Declarations that hold the paste whatever the pane shows: the paste predicate never
# keystrokes over a standing `ready`, `blocked:` or `done`.
_HOLDING_TOKENS = frozenset({signals.STATE_READY, signals.STATE_BLOCKED, signals.STATE_DONE})


def input_empty(*, capture: str, is_codex: bool) -> bool:
    """Positive evidence that the pane's INPUT is empty, independent of busyness.

    Claude: an available ``❯`` box between its borders (empty, or holding only the
    ANSI-proven generated placeholder) and no structured gate — the same box
    :func:`signals.input_box_ready` reads to confirm a submit, which renders whether or
    not a turn is running. Codex: only its structural idle-input shape, which cannot
    hold while it is generating — so a busy Codex session is never positively empty.
    """
    if is_codex:
        return signals.is_codex_idle_input(capture_text=capture)
    return signals.input_box_ready(capture_text=capture) and not signals.is_structured_gate(
        capture_text=capture
    )


def obs_input_empty(*, obs: Observation) -> bool:
    """:func:`input_empty` for an observation, derived from its own capture."""
    return input_empty(capture=obs.capture, is_codex=obs.is_codex)


def _expiry_notice_due(*, obs: Observation) -> bool:
    record = obs.round_record
    return (
        record.at is not None
        and record.expired_at is not None
        and record.malformed_reason is None
        and not record.expiry_notice_sent
    )


def wind_down_or_notice_owed(*, obs: Observation, threshold: int) -> bool:
    """Whether this track owes a wrap-up or its round's expiry notice right now."""
    return _supervisor_compaction.wind_down_owed(
        compaction=obs.compaction, eff_ctx=obs.eff_ctx, threshold=threshold
    ) or (obs.eff_ctx is not None and _expiry_notice_due(obs=obs))


def _input_guards_pass(*, obs: Observation) -> bool:
    declared = obs.declared
    return (
        obs_input_empty(obs=obs)
        and not obs.gate
        and obs.claude_status != "waiting"
        and (declared is None or declared.token not in _HOLDING_TOKENS)
    )


def deliverable_while_busy(*, obs: Observation, threshold: int) -> bool:
    """True when a BUSY pane may still receive the owed wrap-up or expiry notice.

    Busy evidence is exactly what this ignores; every input-protecting guard is kept.
    A pane can look idle while the runtime reports it busy (a Claude sub-agent renders
    no spinner), so busyness is read from ``obs.busy``, never from the capture alone.
    """
    return (
        obs.busy
        and wind_down_or_notice_owed(obs=obs, threshold=threshold)
        and _input_guards_pass(obs=obs)
    )


def codex_busy_withheld(*, obs: Observation, threshold: int) -> bool:
    """A busy Codex track that owes the wind-down but cannot prove an empty composer."""
    return (
        obs.is_codex
        and obs.busy
        and not obs_input_empty(obs=obs)
        and not obs.gate
        and wind_down_or_notice_owed(obs=obs, threshold=threshold)
    )


def input_settled(*, sup: Supervisor, target: str, is_codex: bool) -> bool:
    """The busy-delivery settle: the INPUT region, not the whole pane, is unchanged.

    A generating pane changes on every capture, so the whole-pane settle of
    :func:`_supervisor_launch.pane_settled` could never pass for it. What the paste must
    not race is the input: two captures ``SETTLE_DELAY`` apart must BOTH show a
    positively empty input. An empty input is one fixed shape, so two empty readings
    are the same input region.
    """
    first = sup.tmux.capture_pane(session=target)
    sup.sleep(SETTLE_DELAY)
    second = sup.tmux.capture_pane(session=target)
    return input_empty(capture=first, is_codex=is_codex) and input_empty(
        capture=second, is_codex=is_codex
    )


def surface_codex_withheld(
    *,
    sup: Supervisor,
    track: registry.Track,
    session: str,
    pane: str,
    note: str | None,
    act: bool,
) -> str | None:
    """Name the withheld Codex wrap-up on the row and, when acting, alert it once.

    The alert is edge-triggered on :data:`CODEX_BUSY_WITHHELD_CONDITION`, which the
    caller registers as active, so it fires once per episode rather than per tick.
    """
    if act:
        sup.alert(
            repo=track.repo,
            topic=track.topic,
            session=session,
            pane=pane,
            message=CODEX_BUSY_WITHHELD_NOTE,
            condition=CODEX_BUSY_WITHHELD_CONDITION,
        )
    return _supervisor_liveness_time.append_note(note=note, extra=CODEX_BUSY_WITHHELD_NOTE)
