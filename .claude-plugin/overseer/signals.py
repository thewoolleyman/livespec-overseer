"""signals.py — pure pane-text parsing + filesystem-marker certification.

Stdlib-only, host-only (see ``registry.py`` header). **No subprocess calls
here.** Every pane function takes a captured-text STRING and returns a value,
so it is unit-testable with no tmux — the actual ``tmux capture-pane`` +
``tmux display-message`` subprocesses belong to the daemon (the next build).

The load-bearing correctness fact (see design.md, adversarial review): a pane's
text stream cannot carry a trustworthy "the session asserts X now" signal —
prompt-echo, model quotation, scroll, and line-wrap all corrupt it. So the
session's self-declared *state* is out-of-band on the filesystem (the ONE
``.overseer-state`` file: ``ready`` / ``blocked`` / ``winding-down``), and pane text is
trusted ONLY for the busy / idle / gate signals, which are not echo-forgeable
in a harmful direction (a false "busy" merely suppresses action — the safe
direction).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from _signals_context import parse_ctx_remaining, strip_ansi
from _signals_delivery import queued_cross_session_delivery_sender
from _signals_pane_identity import pane_is_claude, pane_is_codex, pane_is_shell, path_in_repo
from _signals_topics import (
    is_foreman_topic,
    is_grooming_topic,
    reserved_worker_suffix,
    supervisor_entity_topic,
    supervisor_topic,
    topic_reserved_for_supervisor,
    topic_supervised_worker,
)

__all__: list[str] = [
    "STATE_BLOCKED",
    "STATE_BLOCKED_VOIDED",
    "STATE_IDLE_NUDGE_CLEARED",
    "STATE_IDLE_WITH_CONTEXT_LEFT",
    "STATE_READY",
    "STATE_READY_EXPIRED",
    "STATE_RESTARTED",
    "STATE_TOKENS",
    "STATE_WINDING_DOWN",
    "TrackState",
    "codex_prompt_present",
    "input_box_ready",
    "input_box_text",
    "is_busy",
    "is_codex_idle_input",
    "is_foreman_topic",
    "is_grooming_topic",
    "is_idle_input",
    "is_structured_gate",
    "marker_dir",
    "pane_is_claude",
    "pane_is_codex",
    "pane_is_shell",
    "parse_ctx_remaining",
    "path_in_repo",
    "queued_cross_session_delivery_sender",
    "read_state",
    "ready_valid",
    "reserved_worker_suffix",
    "state_path",
    "strip_ansi",
    "supervisor_entity_topic",
    "supervisor_topic",
    "topic_reserved_for_supervisor",
    "topic_supervised_worker",
    "valid_session_token",
    "valid_token",
]


# --------------------------------------------------------------------------- #
# Busy / structured-gate / idle-input detection (see design.md, signal sources).
# --------------------------------------------------------------------------- #

# `Waiting for N background…` where N is a number.
_WAITING_RE = re.compile(r"Waiting for \d+ background", re.IGNORECASE)
# Active-generation markers (verified live 2026-07-13). The live TUI busy
# indicator is a spinner line such as
#   ``✻ Galloping… (running stop hooks… 1/3 · 24s · ↓ 1.4k tokens)``
# — NOT the string ``esc to interrupt``. These CONTENT signals fire only during
# active generation and NOT on the lingering completed-turn summary
# ``✻ Brewed for 25s`` (no parenthetical, no token counter, and `for Ns` rather
# than the `· Ns ·` dot-delimited elapsed form). Glyph-independent, so a
# rotating spinner glyph can't break it.
_BUSY_ACTIVE_RE = re.compile(
    r"esc to interrupt"  # kept: older/other layouts may still show it
    r"|[↓↑]\s*[\d.]+\s*k?\s*tokens"  # streaming token counter (active only)
    r"|·\s*\d+\s*s\s*[·)]"  # `· 24s ·` / `· 24s)` dot-delimited elapsed
    r"|\(\s*running\b",  # `(running … hook…` phase
    re.IGNORECASE,
)


def is_busy(*, capture_text: str) -> bool:
    """True if the pane is actively working.

    Fires on the live active-generation spinner (`_BUSY_ACTIVE_RE`) or a
    `Waiting for N background` line. A liberal (over-firing) busy detector is the
    SAFE direction: a false busy merely suppresses an injection/restart; a missed
    busy is the dangerous one. The lingering completed-turn summary
    (`✻ Brewed for 25s`) is deliberately NOT treated as busy.
    """
    text = strip_ansi(text=capture_text)
    if _WAITING_RE.search(text):
        return True
    return bool(_BUSY_ACTIVE_RE.search(text))


# The permission-prompt / picker cursor: a `❯` (Claude) or `›` (Codex) immediately
# before a numbered option (`❯ 1.` / `› 1.`), present in the Claude permission dialog,
# the AskUserQuestion picker, AND Codex's approval / directory-trust picker (verified
# live 2026-07-17: `› 1. Yes, continue` / `  2. No, quit`). BOTH glyphs are load-bearing
# — a Codex track is now a full citizen that gets the wrap-up pasted in, so a Codex
# picker MUST suppress injection or the paste would type into the `1/2` chooser.
# Best-effort; documented markers.
_GATE_CURSOR_RE = re.compile(r"[❯›]\s*\d+\.")


def is_structured_gate(*, capture_text: str) -> bool:
    """True if the pane shows a structured permission-prompt / picker gate.

    Best-effort. Keyed on two low-false-positive markers: a ``❯ N.`` numbered
    cursor option, or the literal permission question ``Do you want to
    proceed`` (case-insensitive). Used to SUPPRESS injection — never keystroke
    into a gate (adversarial-review blocker #6).
    """
    text = strip_ansi(text=capture_text)
    if _GATE_CURSOR_RE.search(text):
        return True
    return "do you want to proceed" in text.lower()


# The live idle input box is an EMPTY `❯` prompt line sandwiched between two
# horizontal rule lines (`────…`), with the statusline + footer hint below it
# (verified live 2026-07-13 — NOT a `╭─╮` rounded box with `? for shortcuts`).
# We detect that structural shape: it is stable across idle and busy and is
# independent of the footer-hint wording and the spinner glyph.
#
# The border MAY carry an embedded title. `claude -n <topic>` renders the session
# name INTO the top border. Claude Code 2.1.235 rendered that as
# `─── mytopic ──`; 2.1.237/2.1.238 render `─── mytopic ─` (measured live
# 2026-08-20). So the top border is NOT a pure rule; a pure-rule-only match
# would make EVERY session
# the daemon itself launches (all of `start` / `--recover` / post-restart, which
# always pass `-n <topic>`) read as never-idle → never injected/restarted again →
# run to autocompact, the exact failure the overseer exists to prevent (adversarial
# code review 2026-07-13, blocker B2). So a border is: starts with ≥3 rule chars
# AND ends with ≥1 rule char (a pure rule satisfies this too). That is tight
# enough that ordinary wrapped prose / tool output — which does not both start and
# end with box-drawing rule chars — is not mistaken for a border.
_BORDER_RE = re.compile(r"^[─—━]{3,}.*[─—━]{1,}$")


def _is_border(*, line: str) -> bool:
    """True if ``line`` is a box border: a pure rule OR a rule with an embedded title."""
    return _BORDER_RE.match(line) is not None


def _is_empty_prompt(*, line: str) -> bool:
    """True if ``line`` is the empty idle prompt: the `❯` glyph with nothing after."""
    return line.startswith("❯") and not line[1:].strip()


def _input_box_present(*, text: str) -> bool:
    """True if an EMPTY `❯` prompt sits between two box-border lines.

    Scans the non-empty lines and requires an empty `❯` with a border line
    immediately before and after it. The border above MAY carry the `-n <topic>`
    title (`─── mytopic ──` on Claude Code 2.1.235, `─── mytopic ─` on 2.1.237);
    the border below is a pure rule. The empty-prompt requirement means a box
    that already holds typed/pasted input is NOT treated as idle (the daemon
    must never inject over existing input). A numbered-option
    gate (`❯ 1.`) is not empty and not border-bracketed, so it is excluded here
    (and by :func:`is_structured_gate`).
    """
    ne = [stripped for raw in text.splitlines() if (stripped := strip_ansi(text=raw).strip())]
    for i, line in enumerate(ne):
        if not _is_empty_prompt(line=line):
            continue
        above = i >= 1 and _is_border(line=ne[i - 1])
        below = i + 1 < len(ne) and _is_border(line=ne[i + 1])
        if above and below:
            return True
    return False


def is_idle_input(*, capture_text: str) -> bool:
    """True only for a VERIFIED normal, EMPTY input state.

    An empty `❯` prompt box (positive structural marker) is present AND the pane
    is not busy AND not a structured gate. "Not busy" alone is NOT idle-input
    (see design.md, signal sources) — a blank / frozen / booting pane has no
    input box and is therefore not idle.
    """
    if is_busy(capture_text=capture_text):
        return False
    if is_structured_gate(capture_text=capture_text):
        return False
    return _input_box_present(text=capture_text)


def input_box_ready(*, capture_text: str) -> bool:
    """True if the EMPTY `❯` input box is present (regardless of busy/gate).

    Unlike :func:`is_idle_input`, this does NOT require not-busy — it is the
    "the prompt cleared" signal the daemon uses to confirm a pasted prompt
    actually SUBMITTED (after submit the box empties; while a fresh session is
    still drawing its welcome screen the box holds the un-submitted paste, so
    this stays False until an Enter lands).
    """
    return _input_box_present(text=capture_text)


def input_box_text(*, capture_text: str) -> str | None:
    """Return the Claude composer text when a non-empty ``❯`` box is visible."""
    ne = [
        stripped for raw in capture_text.splitlines() if (stripped := strip_ansi(text=raw).strip())
    ]
    for i, line in enumerate(ne):
        if not line.startswith("❯") or not line[1:].strip():
            continue
        above = i >= 1 and _is_border(line=ne[i - 1])
        below = i + 1 < len(ne) and _is_border(line=ne[i + 1])
        if above and below:
            return line[1:].lstrip()
    return None


# The Codex TUI renders a DIFFERENT idle shape from Claude's `❯`-between-rules box: a
# `›` input line sitting above its statusline (`model · cwd · Context N% left · <name>`),
# with a grey ROTATING placeholder when the box is empty — indistinguishable from typed
# text in an ANSI-stripped capture. So Codex idle detection is STRUCTURAL (a `›` prompt +
# a Codex statusline, not busy, not a picker), never Claude's cleared-`❯` check, and a
# Codex submit is confirmed by the pane going BUSY, not by an emptied box (see
# supervisor `_submit_prompt`). Verified live 2026-07-17 (codex-cli 0.144.5).
_CODEX_STATUSLINE_RE = re.compile(r"Context\s+\d+%\s+left")


def codex_prompt_present(*, capture_text: str) -> bool:
    """True if the pane is a live Codex TUI sitting at its input prompt.

    Structural + glyph-anchored: a ``›`` input line AND a Codex statusline
    (``… · Context N% left · …``) among the visible rows, independent of the rotating
    placeholder wording. It is present whether the box is empty OR holds text (the
    placeholder problem above), so it asserts only "a Codex TUI is here"; idle-ness adds
    not-busy + not-gate (:func:`is_codex_idle_input`).
    """
    text = strip_ansi(text=capture_text)
    if not _CODEX_STATUSLINE_RE.search(text):
        return False
    return any(line.lstrip().startswith("›") for line in text.splitlines())


def is_codex_idle_input(*, capture_text: str) -> bool:
    """The Codex analogue of :func:`is_idle_input`: a Codex prompt that is neither busy
    nor a structured gate.

    STRUCTURAL, never the coarse "not busy" — so a Codex approval / directory-trust
    picker (``› 1.``, caught by :func:`is_structured_gate`) or a booting / blank pane is
    NOT read as idle and can never be keystroked into. This matters because a Codex track
    is now a full citizen: an over-loose idle read would paste the wrap-up into a Codex
    gate.
    """
    if is_busy(capture_text=capture_text):
        return False
    if is_structured_gate(capture_text=capture_text):
        return False
    return codex_prompt_present(capture_text=capture_text)


# --------------------------------------------------------------------------- #
# Out-of-band marker certification (see design.md, the certification protocol,
# blockers #1,#3,#4). These read the filesystem but NEVER a subprocess.
# --------------------------------------------------------------------------- #


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
# `STATE_TOKENS` are the three the SESSION declares (used verbatim in the session-facing
# wrap-up + malformed-token messages). `STATE_IDLE_WITH_CONTEXT_LEFT` is the ONE token the
# DAEMON writes itself — the "I nudged this idle-with-context-left session to keep going
# this episode" marker (single-prompt edge-trigger). It is kept OUT of `STATE_TOKENS` so
# the session-facing text still lists only the three a session should write, but
# `valid_token` accepts it so the daemon's own marker is never surfaced as malformed.
STATE_READY = "ready"
STATE_BLOCKED = "blocked"
STATE_WINDING_DOWN = "winding-down"
STATE_IDLE_WITH_CONTEXT_LEFT = "idle-with-context-left"
STATE_IDLE_NUDGE_CLEARED = "idle-nudge-cleared"
STATE_BLOCKED_VOIDED = "blocked-voided"
STATE_READY_EXPIRED = "ready-expired"
STATE_RESTARTED = "restarted"
STATE_TOKENS = (STATE_READY, STATE_BLOCKED, STATE_WINDING_DOWN)
_DAEMON_TOKENS = (
    STATE_IDLE_WITH_CONTEXT_LEFT,
    STATE_IDLE_NUDGE_CLEARED,
    STATE_BLOCKED_VOIDED,
    STATE_READY_EXPIRED,
    STATE_RESTARTED,
)
STATE_PATH_MISMATCH = "state-path-mismatch"


def state_path(*, repo: str, topic: str) -> Path:
    """``<repo>/tmp/overseer/<topic>/.overseer-state`` — the ONE indicator file."""
    return marker_dir(repo=repo, topic=topic) / ".overseer-state"


def _canonical_state_path_matches(*, path: Path, repo: str, topic: str) -> bool:
    """Fail closed when the state dir or state file is a symlink escape.

    The repo root itself is canonicalized before appending the fixed tmp path, so a
    symlinked checkout still passes. The per-entity state directory and file must then
    resolve to exactly that canonical location; a symlinked topic dir or state file does
    not.
    """
    try:
        expected = Path(repo).resolve() / "tmp" / "overseer" / topic / ".overseer-state"
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

    A file write cannot be forged by prompt-echo, cannot scroll off, and cannot
    line-wrap, so all the pane-text blockers dissolve here. The token is returned
    verbatim (lowercased) even when unknown, so the daemon can SURFACE a malformed
    value instead of silently treating it as "no state".
    """
    path = state_path(repo=repo, topic=topic)
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
