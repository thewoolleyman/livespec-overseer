"""_supervisor_config — the daemon's tuning constants and its two shared helpers.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. This module is the LEAF of the supervisor group — it imports nothing from its
siblings — and holds the numbers the supervision loop is tuned by (poll bounds, the
settle and submit windows, the marker grace, the ack/nudge staleness windows), the
start-up gitignore probe, and the two tiny helpers every phase shares
(:func:`track_key`, :func:`iso_now`).

Its members are PUBLIC even though the module is private, because pyright-strict's
`reportPrivateUsage` rejects importing an `_`-prefixed name across modules — the same
shape the `_registry_*` collaborators use. `_GIT_TIMEOUT_SECONDS` is the exception and
stays private: only :func:`default_gitignore_check`, in this module, reads it.

`default_gitignore_check` lives HERE, beside the timeout it is bounded by, and that
placement is load-bearing rather than tidy. It reads `_GIT_TIMEOUT_SECONDS` as a bare
module global, so a test that redirects it must patch THIS module. The general rule,
paid for during the registry split: a reader that moves out of a constant's module
must import from the module that DEFINES the constant, never through the `supervisor`
facade — a facade re-export can be monkeypatched successfully while the real reader
keeps its own binding, leaving the test green and the production default live.
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone

__all__: list[str] = [
    "ACK_STALE_AFTER",
    "BLOCKED_AGE_ALERT_BANDS",
    "CLAUDE_BUSY_STATUSES",
    "CONDITION_CONTINUITY_GAP",
    "CTX_STALE_AFTER",
    "DANGER_CTX_REMAINING",
    "ESCALATION_EXHAUSTED_AFTER",
    "IDLE_NUDGE_AFTER",
    "LOOP_INTERVAL_SECONDS",
    "MARKER_VOID_GRACE",
    "PAIR_STALL_AFTER",
    "PANE_STILL_AFTER",
    "PICKER_STALL_AFTER",
    "POST_RESPAWN_NEVER_WORKED_AFTER",
    "READY_ARM_MAX_AGE",
    "RESTART_POLL_INTERVAL",
    "RESTART_POLL_MAX",
    "SETTLE_DELAY",
    "SETTLING_STUCK_AFTER",
    "SHELL_PROLONGED_AFTER",
    "SUBMIT_MAX_ENTERS",
    "SUBMIT_POLL",
    "SUPERVISION_CONDITIONS",
    "SUPERVISOR_STATE_STALE_AFTER",
    "WINDDOWN_STARVED_AFTER",
    "WINDOW_NAME",
    "default_gitignore_check",
    "iso_now",
    "track_key",
]

# ~10s fast loop (design). Configurable via the daemon CLI ``--interval``.
LOOP_INTERVAL_SECONDS = 10
# Wall-clock ceiling on the one `git` call this module makes. A liveness floor, not
# a latency budget: `git check-ignore` is a local index read that returns in
# milliseconds, so exceeding this means git is not answering at all.
_GIT_TIMEOUT_SECONDS = 10.0

# The "danger" line, expressed in REMAINING-context percent: ~20% left ≈ 80% used.
# At/below this with no `ready` declaration, the daemon SURFACES the track to the
# human — loudly, with its tmux coordinates — and does NOTHING ELSE. It NEVER kills
# a session that has not declared itself ready (maintainer 2026-07-14: "NEVER
# forcibly restart a session that is not ready; it MUST drop the indicator file for
# action"). A timer cannot know whether a session is safe to kill: "idle + settled"
# is not "at a safe stopping point" — a session can be idle while a background build
# runs, while a sub-agent works, or while it waits on a human in another pane. Only
# the session knows, so only the session may authorize the restart.
DANGER_CTX_REMAINING = 20

# Claude's registry `status` values (`~/.claude/sessions/<pid>.json`) that mean the session
# is doing work — the AUTHORITATIVE busy signal for an adopted Claude session. `busy` =
# actively generating / running an in-process sub-agent; `shell` = at the prompt with a live
# `Bash(run_in_background)` command (Claude's own background-work signal). `idle` / `waiting`
# are NOT here (at a prompt, nothing running / waiting for the human).
CLAUDE_BUSY_STATUSES = frozenset({"busy", "shell"})

# The tmux window name the daemon owns; it badges an attention count onto it
# (`overseer` → `overseer(2!)`).
WINDOW_NAME = "overseer"


# Bounded wait for a respawned pane to become a live Claude TUI before pasting
# the resume line (poll #{pane_current_command} → node/claude; never scrape ❯).
RESTART_POLL_MAX = 30
RESTART_POLL_INTERVAL = 0.5

# Delay between the two captures of the settled-check. The live Claude TUI shows
# NO persistent busy spinner while streaming tokens (verified 2026-07-13), so a
# single capture cannot tell active streaming from idle. Before acting on an
# apparently-idle track, the daemon captures twice this far apart; if the pane
# changed, it is actively working and is skipped (treated as `working`).
SETTLE_DELAY = 0.6

# Submit verification: a single Enter after a bracketed paste can be DROPPED by a
# freshly-respawned session still drawing its welcome screen (verified live
# 2026-07-13), leaving the resume line un-submitted. `_submit_prompt` re-sends
# Enter up to this many times, polling `SUBMIT_POLL` between, until the input box
# clears. Extra Enters on an empty prompt are harmless no-ops.
SUBMIT_MAX_ENTERS = 8
SUBMIT_POLL = 0.5

# Grace window before a stale `blocked:` declaration is voided on a generating
# observation. The declaring turn's tail may keep the pane busy briefly after the file
# write, so a young declaration survives; an older one is incompatible with observed
# generation and is cleared.
MARKER_VOID_GRACE = 120.0

# A `ready` declaration arms the restart until the first verified settled-idle
# observation. It is NOT voided by intervening narration or generation; the restart-time
# settle/busy gates already prevent killing mid-work. This bounded age is the only stale
# ready limit: when exceeded, the declaration is surfaced loudly and no restart occurs.
READY_ARM_MAX_AGE = 1800.0

# How long a `winding-down` acknowledgement may sit before the daemon SURFACES it as
# "acknowledged but not finishing". The ACK buys patience — while it is fresh the
# daemon stops re-warning, so it never keystrokes into a session that is actively
# wrapping up. But an ACK must not become an infinite stall: past this window the
# daemon resumes escalating and reports the track. It STILL never acts on it — the
# escalation is louder words, never a kill.
ACK_STALE_AFTER = 900.0

# Minimum CONTINUOUS idle duration before the keep-going ("idle-with-context-left") nudge
# may fire. The nudge pastes + submits text into the session, so firing it on a session that
# is only BRIEFLY at the prompt (between turns, or the human is mid-thought) INTERRUPTS
# active work — the maintainer-reported failure (2026-07-18: "too aggressive, TOO SOON …
# interrupting active sessions"). A session must sit cleanly idle (empty prompt, not busy,
# above its wind-down threshold) for at least this long before it is nudged. In-memory
# (`InjectState.idle_since`), so a daemon restart resets the clock — which only DELAYS a
# nudge, the safe direction.
IDLE_NUDGE_AFTER = 3600.0  # 1 hour
PAIR_STALL_AFTER = 7200.0  # 2 hours
PANE_STILL_AFTER = 30 * 60.0

# Continuity window for observed in-memory condition episodes. The design rule is
# formulaic: at least twice the loop's worst-case full-load tick, re-derived when
# entity count changes materially. Until measured derivation lands, the ruled interim
# value is 900s; the too-small direction suppresses detection entirely.
CONDITION_CONTINUITY_GAP = 900.0

# Bounded post-respawn floor for reporting a fresh session that never began work.
POST_RESPAWN_NEVER_WORKED_AFTER = 60.0

# A last-known remaining-context value stops satisfying ctx gates after this long
# without a fresh parse. The row still reports the stale knowledge so losing sight of
# a low-context track is visible.
CTX_STALE_AFTER = 3600.0

# Report-only liveness floors. Wind-down starvation shares the ratified 2h
# background-shell floor; above-threshold shell-only shielding uses the ruled 8h floor.
WINDDOWN_STARVED_AFTER = 2 * 3600.0
SHELL_PROLONGED_AFTER = 8 * 3600.0
ESCALATION_EXHAUSTED_AFTER = 10 * 60.0
PICKER_STALL_AFTER = 30 * 60.0
SETTLING_STUCK_AFTER = 10 * 60.0
SUPERVISOR_STATE_STALE_AFTER = 30 * 60.0

# Standing blocked declarations escalate once at each crossed age band. Further daily
# bands are derived from the same 24h cadence in the evaluator.
BLOCKED_AGE_ALERT_BANDS = (4 * 3600.0, 24 * 3600.0)


def default_gitignore_check(*, repo: str) -> bool:
    """True iff ``<repo>/tmp/overseer/`` is gitignored in ``repo``.

    Bounded by ``_GIT_TIMEOUT_SECONDS``: this runs on the START-UP path, so an
    unbounded hang here wedges the daemon before any tick, and a restart would
    re-enter the same hang. A timeout resolves to the same fail-soft ``False`` as a
    spawn error.

    ``git -C <repo> check-ignore -q tmp/overseer`` exits 0 when the path is
    ignored, 1 when it is not, 128 on error — so only a 0 means "ignored". The
    daemon refuses to start unless every watched repo passes, because the overseer
    writes its markers there and must never dirty a tracked tree. Fail-soft to
    False (treated as "not ignored" → refuse) on any spawn error.
    """
    try:
        completed = subprocess.run(  # noqa: S603 — fixed argv, no shell
            ["git", "-C", repo, "check-ignore", "-q", "tmp/overseer"],  # noqa: S607 — PATH git
            capture_output=True,
            check=False,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    # TimeoutExpired subclasses SubprocessError, so neither OSError nor ValueError
    # catches it. It resolves to the SAME fail-soft False as a spawn error — an
    # unanswerable check has not proven the path is ignored, so the daemon refuses
    # to start rather than risking a write into a tracked tree.
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0


def track_key(*, repo: str, topic: str) -> tuple[str, str]:
    """The normalized (repo, topic) in-memory state key (mirrors registry joins)."""
    return (os.path.normpath(repo), topic)


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


SUPERVISION_CONDITIONS = frozenset(
    {
        "supervision-offer",
        "supervision-capture-offer",
        "supervisor-missing",
        "pair-stalled",
    }
)
