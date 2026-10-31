"""Out-of-band state-file vocabulary, parsing, and restart certification."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path

__all__: list[str] = [
    "STATE_BLOCKED",
    "STATE_BLOCKED_VOIDED",
    "STATE_DONE",
    "STATE_DONE_VOIDED",
    "STATE_IDLE_NUDGE_CLEARED",
    "STATE_IDLE_WITH_CONTEXT_LEFT",
    "STATE_PATH_MISMATCH",
    "STATE_READY",
    "STATE_READY_EXPIRED",
    "STATE_RESTARTED",
    "STATE_TOKENS",
    "STATE_WINDING_DOWN",
    "TrackState",
    "marker_dir",
    "read_state",
    "ready_valid",
    "rejected_state_path",
    "rejected_value",
    "rejected_value_notice",
    "state_path",
    "valid_session_token",
    "valid_token",
]


def marker_dir(*, repo: str, topic: str) -> Path:
    """``<repo>/tmp/overseer/<topic>/`` — the overseer's per-track TEMP dir.

    The markers live under the repo's ``tmp/`` (gitignored, maintainer-owned
    scratch), NOT under ``plan/``: the overseer NEVER touches files inside a
    session's ``plan/<topic>/`` tree — that is the session's own workflow. The
    daemon validates each watched repo's ``tmp/overseer/`` is gitignored at
    startup (else it refuses to start).
    """
    return Path(repo) / "tmp" / "overseer" / topic


# The values of the SINGLE indicator file. One file with a VALUE — never a set of
# separate presence-markers: two files (`.overseer-ready` + `.overseer-blocked`)
# carried a built-in ambiguity, because nothing stopped BOTH existing and their
# precedence was incidental rather than designed (maintainer 2026-07-14).
#
# `STATE_TOKENS` are the four the SESSION declares (used verbatim in the session-facing
# wrap-up + malformed-token messages). `STATE_IDLE_WITH_CONTEXT_LEFT` is the ONE token the
# DAEMON writes itself — the "I nudged this idle-with-context-left session to keep going
# this episode" marker (single-prompt edge-trigger). It is kept OUT of `STATE_TOKENS` so
# the session-facing text still lists only the four a session should write, but
# `valid_token` accepts it so the daemon's own marker is never surfaced as malformed.
STATE_READY = "ready"
STATE_BLOCKED = "blocked"
STATE_WINDING_DOWN = "winding-down"
STATE_DONE = "done"
STATE_IDLE_WITH_CONTEXT_LEFT = "idle-with-context-left"
STATE_IDLE_NUDGE_CLEARED = "idle-nudge-cleared"
STATE_BLOCKED_VOIDED = "blocked-voided"
STATE_DONE_VOIDED = "done-voided"
STATE_READY_EXPIRED = "ready-expired"
STATE_RESTARTED = "restarted"
STATE_TOKENS = (STATE_READY, STATE_BLOCKED, STATE_WINDING_DOWN, STATE_DONE)
_DAEMON_TOKENS = (
    STATE_IDLE_WITH_CONTEXT_LEFT,
    STATE_IDLE_NUDGE_CLEARED,
    STATE_BLOCKED_VOIDED,
    STATE_DONE_VOIDED,
    STATE_READY_EXPIRED,
    STATE_RESTARTED,
)
STATE_PATH_MISMATCH = "state-path-mismatch"


def state_path(*, repo: str, topic: str) -> Path:
    """``<repo>/tmp/overseer/<topic>/.overseer-state`` — the ONE indicator file."""
    return marker_dir(repo=repo, topic=topic) / ".overseer-state"


def rejected_state_path(*, repo: str, topic: str) -> Path:
    """The malformed-state evidence file beside the canonical declaration path."""
    return marker_dir(repo=repo, topic=topic) / ".overseer-state.rejected"


def rejected_value(*, repo: str, topic: str) -> str | None:
    """Return the safe, bounded first non-empty line of standing rejection evidence."""
    path = rejected_state_path(repo=repo, topic=topic)
    try:
        if not path.is_file() or path.is_symlink():
            return None
        raw = path.read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None
    line = next((candidate for candidate in raw.split("\n") if candidate.strip()), "")
    return "".join(char for char in line if unicodedata.category(char) != "Cc")[:120]


def rejected_value_notice(*, repo: str, topic: str) -> str:
    """The one-line recovery instruction owed while rejection evidence stands."""
    value = rejected_value(repo=repo, topic=topic)
    if value is None:
        return ""
    return (
        f"RECOVERY: rejected state value: {value!r}. Write one of winding-down, ready, "
        "blocked: <one-line reason>, or done[: <one-line summary>].\n\n"
    )


def _canonical_state_path_matches(*, path: Path, repo: str, topic: str) -> bool:
    """Fail closed when the state dir or state file is a symlink escape.

    The repo root itself is canonicalized before appending the fixed tmp path, so a
    symlinked checkout still passes. The per-entity state directory and file must then
    resolve to exactly that canonical location; a symlinked topic dir or state file does
    not.
    """
    import signals as signals_facade

    try:
        expected = (
            signals_facade.Path(repo).resolve() / "tmp" / "overseer" / topic / ".overseer-state"
        )
        actual = path.resolve()
    except OSError:
        return False
    return actual == expected


@dataclass(frozen=True, kw_only=True)
class TrackState:
    """A tracked session's self-declared state — parsed from the one indicator file.

    ``token`` is the raw lowercased first word (may be INVALID — use
    :func:`valid_token` before trusting it, so a typo'd value is surfaced as
    malformed rather than silently ignored). ``detail`` is the optional free text
    after a ``:`` (e.g. the one-line reason on ``blocked``). ``mtime`` powers the
    this-round freshness check.
    """

    token: str
    detail: str
    mtime: float


def valid_token(*, token: str) -> bool:
    """True iff ``token`` is a recognized state — a session-declared one
    (:data:`STATE_TOKENS`) OR one of the daemon-written inert state markers.
    Only genuinely unrecognized (typo'd) tokens are surfaced as malformed."""
    return token in STATE_TOKENS or token in _DAEMON_TOKENS


def valid_session_token(*, token: str) -> bool:
    """True iff ``token`` is one of the states a tracked session may declare."""
    return token in STATE_TOKENS


def read_state(*, repo: str, topic: str) -> TrackState | None:
    """Parse ``.overseer-state``; None when absent or unreadable (fail-closed).

    Format — the first non-empty line is ``<token>`` or ``<token>: <detail>``::

        ready
        blocked: waiting on the schema call
        winding-down
        done

    A file write cannot be forged by prompt-echo, cannot scroll off, and cannot
    line-wrap, so all the pane-text blockers dissolve here. The token is returned
    verbatim (lowercased) even when unknown, so the daemon can SURFACE a malformed
    value instead of silently treating it as "no state".
    """
    import signals as signals_facade

    path = signals_facade.state_path(repo=repo, topic=topic)
    try:
        if not path.is_file():
            return None
        if not _canonical_state_path_matches(path=path, repo=repo, topic=topic):
            return TrackState(
                token=STATE_PATH_MISMATCH, detail=str(path), mtime=path.stat().st_mtime
            )
        raw = path.read_text(encoding="utf-8")
        mtime = path.stat().st_mtime
    # ValueError covers the UnicodeDecodeError a non-UTF-8 indicator raises — a
    # ValueError subclass, so an OSError-only handler let it propagate.
    except (OSError, ValueError):
        return None
    line = next((ln.strip() for ln in raw.splitlines() if ln.strip()), "")
    token, _, detail = line.partition(":")
    return TrackState(token=token.strip().lower(), detail=detail.strip(), mtime=mtime)


def ready_valid(
    *,
    repo: str,
    topic: str,
    certification_floor: float | None = None,
    malformed_round_reason: str | None = None,
    round_session_identity: str | None = None,
    live_session_identity: str | None = None,
) -> bool:
    """The restart authorization — the ONLY thing that may restart a session.

    True only when ALL hold:

    1. a certification floor exists for this round (``certification_floor`` is not
       None) and the round record is well-formed,
    2. the state file declares exactly ``ready``, AND
    3. its mtime is strictly newer than ``certification_floor`` (this round, and
       newer than any expiry recorded within it),
    4. the identity live at the pane matches the round-open identity.

    The daemon NEVER infers readiness. A session that is merely idle — however long,
    however low on context — is NOT ready: "idle + settled" is not "safe to kill" (a
    session can be idle while a background build runs, while a sub-agent works, or
    while it waits on a human in another pane). Only the session knows, so only the
    session may say so. Any absent/unreadable/other-valued file → False (fail-closed).
    """
    if (
        certification_floor is None
        or malformed_round_reason is not None
        or round_session_identity is None
        or live_session_identity is None
        or live_session_identity != round_session_identity
    ):
        return False
    state = read_state(repo=repo, topic=topic)
    if state is None or state.token != STATE_READY:
        return False
    return state.mtime > certification_floor
