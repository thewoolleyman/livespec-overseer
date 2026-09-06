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

import registry
import signals

__all__: list[str] = [
    "CTX_SOURCE_LIVE",
    "CTX_SOURCE_RETAINED",
    "CTX_SOURCE_UNREADABLE",
    "UNREADABLE_CTX_READING",
    "ConditionEpisode",
    "CtxReading",
    "InjectState",
    "Observation",
    "PairStallState",
    "WaitTargetCacheEntry",
]


@dataclass(kw_only=True)
class ConditionEpisode:
    """In-memory duration for one named observed condition class."""

    since: float | None = None
    last_seen: float | None = None


@dataclass(kw_only=True)
class PairStallState:
    """In-memory ladder state for one worker/supervisor pair."""

    since: float | None = None
    last_seen: float | None = None
    nudged_this_episode: bool = False
    last_nudged_at: float | None = None
    consecutive_nudged_episodes: int = 0
    unstalled_since: float | None = None


@dataclass(frozen=True, kw_only=True)
class WaitTargetCacheEntry:
    """One per-tick wait-target re-verification result."""

    checked_at: float
    status: str
    note: str | None


# --------------------------------------------------------------------------- #
# Context-headroom readings and their provenance (`overseer-62mgxr`).
# --------------------------------------------------------------------------- #

# HOW a reported headroom was obtained. `live` is the statusline the pane is
# rendering right now. `retained` is the last reading this daemon actually took for
# the track, carried forward WITH ITS AGE because the pane is no longer rendering
# one — the shape an open picker produces, its overlay displacing the statusline out
# of the capture. `unreadable` is the honest absence: no reading was ever taken, so
# there is nothing to carry and nothing is invented.
CTX_SOURCE_LIVE = "live"
CTX_SOURCE_RETAINED = "retained"
CTX_SOURCE_UNREADABLE = "unreadable"


@dataclass(frozen=True, kw_only=True)
class CtxReading:
    """A headroom reading together with the provenance that makes it judgeable.

    ``value`` alone is not reportable. A stale headroom presented as current is worse
    than none — an operator reading `42%` cannot tell "the pane says 42%" from "the
    pane said 42% four hours ago and has said nothing since", and those are opposite
    operational situations. So a retained value ALWAYS travels with ``source`` and
    with ``age_seconds``, the age of the observation it came from.

    ``age_seconds`` is set EXACTLY for a retained reading; a live one and an absent
    one both carry None, for opposite reasons — there is no age to state, and there
    is no value to age. Surfaces may therefore treat the presence of an age as the
    retained marker.
    """

    value: int | None
    source: str
    age_seconds: float | None


# The reading for a track this daemon has nothing to say about. Frozen, so one shared
# instance is safe as a field default — and the default is deliberately this one: a
# construction that forgets to supply a reading reports "we do not know" rather than a
# number nobody observed, which is the direction this whole record exists to protect.
UNREADABLE_CTX_READING = CtxReading(value=None, source=CTX_SOURCE_UNREADABLE, age_seconds=None)


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

    The stall-watch daemon id below shares that in-memory contract. It cannot observe a
    production daemon bounce today because the current process id is immutable and this
    record is discarded across a restart. If this record becomes durable, re-audit
    ``_supervisor_pane_still``'s bounce re-key branch and ``watch-target-gone`` status
    before landing the persistence change.

    Guard phrase: if this record becomes durable, re-audit the bounce branch.
    """

    last_ctx: int | None = None
    last_ctx_seen: float | None = None
    last_ctx_changed_at: float | None = None
    idle_since: float | None = None
    idle_last_seen: float | None = None
    ctx_unreadable_episode: ConditionEpisode = field(default_factory=ConditionEpisode)
    winddown_starved_episode: ConditionEpisode = field(default_factory=ConditionEpisode)
    escalation_exhausted_episode: ConditionEpisode = field(default_factory=ConditionEpisode)
    settling_episode: ConditionEpisode = field(default_factory=ConditionEpisode)
    shell_episode: ConditionEpisode = field(default_factory=ConditionEpisode)
    restart_never_worked_episode: ConditionEpisode = field(default_factory=ConditionEpisode)
    # A `ready` declaration held by a standing statusline-mismatch veto must not
    # expire at the max age with only per-tick log lines to show for it: this flag
    # marks that the current ready declaration is (or was) veto-held so expiry is
    # skipped until the declaration is consumed by a restart or retracted. Reset the
    # moment no ready declaration is present. See `_supervisor_state.expire_aged_ready`.
    statusline_veto_holding: bool = False
    blocked_human_stall_since: float | None = None
    blocked_human_stall_capture: str | None = None
    picker_stall_nudged: bool = False
    picker_stall_nudge_echo_capture: str | None = None
    blocked_declaration_mtime: float | None = None
    blocked_entry_age_label: str | None = None
    blocked_alerted_bands: set[int] = field(default_factory=set)
    uncertifiable_ready_mtime: float | None = None
    uncertifiable_ready_entry_age_label: str | None = None
    uncertifiable_ready_alerted_bands: set[int] = field(default_factory=set)
    uncertifiable_ready_notice_mtime: float | None = None
    stall_watch_daemon_instance_id: str | None = None
    stall_watch_pane: str | None = None
    stall_watch_capture_hash: str | None = None
    stall_watch_capture_since: float | None = None
    stall_watch_due_observations: int = 0
    wait_target_cache: dict[str, WaitTargetCacheEntry] = field(default_factory=dict)
    wait_target_relayed_keys: set[str] = field(default_factory=set)


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
    current_ctx: int | None
    eff_ctx: int | None
    # The OPERATOR-facing projection of the same headroom knowledge. It is deliberately
    # NOT `eff_ctx`: the cascade decides on `eff_ctx`, which drops a reading older than
    # `CTX_STALE_AFTER` so a stale number can never cross a threshold, while this one
    # carries the reading however old and SAYS how old. See `_supervisor_ctx_reading`.
    ctx_reading: CtxReading = UNREADABLE_CTX_READING
    ctx_changed: bool = False
    ctx_stale_age: float | None
    stale_ctx: int | None
    injection_stamp: float | None
    round_record: registry.RoundRecord
    session_identity: str | None
    ready_uncertifiable_reason: str | None
    istate: InjectState
    observed_at: float
    declared: signals.TrackState | None
    malformed: bool
    blocked: str | None
    acked: bool
    ready: bool
