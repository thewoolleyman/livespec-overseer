"""_supervisor_records — the two per-track value records one tick works with.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. :class:`InjectState` is the in-memory wrap-up bookkeeping the daemon carries
per track between ticks; :class:`Observation` is the seam inside
:meth:`Supervisor.evaluate` between "gather the facts" and "run the precedence
cascade over them".

Both are PUBLIC despite the private module, because pyright-strict's
`reportPrivateUsage` rejects importing an `_`-prefixed name across modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import signals

__all__: list[str] = [
    "ConditionEpisode",
    "InjectState",
    "Observation",
]


@dataclass(kw_only=True)
class ConditionEpisode:
    """In-memory duration for one named observed condition class."""

    since: float | None = None
    last_seen: float | None = None


@dataclass
class InjectState:
    """Per-track wrap-up bookkeeping (in-memory; reset on restart/recovery).

    ``last_ctx`` is the last KNOWN remaining-% (used by
    :meth:`Supervisor._effective_ctx` when a tick reads ctx as unknown — design:
    keep last known, and unknown never triggers a crossing). ``idle_since`` is the epoch
    time the session ENTERED its current continuous-idle episode (None when not cleanly
    idle) — it gates the keep-going nudge behind a minimum idle duration
    (``IDLE_NUDGE_AFTER``) so a session that is only BRIEFLY at the prompt (between turns)
    is never interrupted. Both are in-memory: a daemon restart resets them, which only ever
    DELAYS a nudge (the safe direction). The injection-round timestamp and the set of
    already-notified escalation bands are DURABLE, in the injection-stamp sidecar
    (``registry.read_injection_stamp`` / ``read_notified_bands`` / ``add_notified_band``),
    so a daemon restart never re-spams a band it already sent — they are not in-memory here.
    """

    last_ctx: int | None = None
    last_ctx_seen: float | None = None
    idle_since: float | None = None
    idle_last_seen: float | None = None
    ctx_unreadable_episode: ConditionEpisode = field(default_factory=ConditionEpisode)
    blocked_declaration_mtime: float | None = None
    blocked_entry_age_label: str | None = None
    blocked_alerted_bands: set[int] = field(default_factory=set)
    uncertifiable_ready_mtime: float | None = None
    uncertifiable_ready_entry_age_label: str | None = None
    uncertifiable_ready_alerted_bands: set[int] = field(default_factory=set)


@dataclass(frozen=True, kw_only=True)
class Observation:
    """Everything one tick OBSERVES about a track, before deciding anything.

    :meth:`Supervisor.evaluate` is a two-phase function: gather the facts, then
    run a cascade of guards over them. This record is the seam between the two
    phases — every field is read by the cascade, nothing here decides anything.
    Splitting it out keeps the cascade readable top-to-bottom as one precedence
    order rather than interleaving reads with decisions.

    ``istate`` is deliberately the LIVE ``InjectState`` object out of
    ``Supervisor.inject``, not a copy: the cascade mutates it (recording an
    injection round), and observation already advanced its idle-episode clock.
    """

    capture: str
    busy: bool
    gate: bool
    idle: bool
    is_codex: bool
    runtime: str
    codex_fallback: bool
    claude_status: str | None
    eff_ctx: int | None
    ctx_stale_age: float | None
    stale_ctx: int | None
    injection_stamp: float | None
    istate: InjectState
    declared: signals.TrackState | None
    malformed: bool
    blocked: str | None
    acked: bool
    ready: bool
