"""_supervisor_view — the outward projection of a track: row, colour, attention.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. This module owns what the OPERATOR sees — the :class:`RowView` record one
track renders to, the per-status row tint, the elision that keeps the Status column
from being blown up by a long session-authored note, the annotated `tmux` cell, and
the `NEEDS YOU` membership test.

It holds no judgment: :meth:`Supervisor.evaluate` decides a track's status, and this
module only projects it. `_ANSI_GREEN` / `_ANSI_YELLOW` / `_ANSI_RED` /
`_STATUS_COLOR` stay private because only :func:`row_color`, in this module, reads
them; `ANSI_RESET` is public because the table writer reads it across the module
boundary, where pyright-strict's `reportPrivateUsage` rejects an `_`-prefixed name.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__: list[str] = [
    "ANSI_RESET",
    "ATTENTION_STATUSES",
    "MAX_NOTE_IN_TABLE",
    "MAX_REASON_IN_ALERT",
    "RESUME_PENDING_NOTE",
    "RowView",
    "elide",
    "needs_attention",
    "row_color",
    "tmux_cell",
]

# The statuses that mean "a human must go look at this track". They are the membership
# test for the `NEEDS YOU` block the daemon renders under its table, and for the tmux
# window-name badge — the two surfaces that answer "what needs attention?".
#
# `unassigned` is deliberately NOT here: a discovered plan with no session is startable,
# not stuck, and there are dozens of them — including them would bury the handful of rows
# that genuinely want the operator, which is the exact failure this block exists to fix.
# `session-gone` IS attention: a plan we have seen running is no longer in any tmux,
# and the operator decides whether to restart or unassign it. `not-claude` is gone.
ATTENTION_STATUSES = (
    "blocked:human",
    "codex-unindexed",
    "ctx-stale",
    "danger",
    "foreman-heartbeat-stale",
    "ready-uncertifiable",
    "restart-never-worked",
    "session-gone",
    "shell-prolonged",
    "winddown-starved",
)

# The row note a track carries while its POST-RESPAWN resume line has not yet SUBMITTED
# (R1, 2026-07-18). The daemon self-heals — it re-sends Enter every tick (never a
# re-respawn) until the box clears — but until it lands the operator should SEE the track
# is mid-restart and stranded, and a human may need to press Enter if the retry cannot
# clear it. Matched by `needs_attention` so the row stays in `NEEDS YOU` (and the alert
# stays edge-triggered, not re-armed) until the resume actually submits.
RESUME_PENDING_NOTE = "resume not submitted — daemon retrying Enter"

# Live-table row color (TTY-only; see `Supervisor.render`). The operator scans the
# table by hue: each row is tinted by its STATUS so the handful that want a human
# stand out from the background of `unassigned` plans. Color is a whole-LINE
# affordance — the ANSI codes wrap the already-padded row, never a cell, so column
# alignment (widths computed on plain-text `len`) is preserved. Emitted ONLY to a
# TTY (`render` gates on `out.isatty()`), so piped `list` output and the
# beside-tests' `StringIO` stay plain text.
#
#   green  = actively working (working / winding-down / restarting / settling)
#   yellow = idle, waiting on a human (`blocked:human`), or low on context
#            (`warned` / `danger`)
#   red    = broken: the session is gone (`session-gone` — the only red status;
#            `not-claude` was deleted)
#   default (uncolored — terminal white/gray) = `unassigned`, and any unmapped status
ANSI_RESET = "\x1b[0m"
_ANSI_GREEN = "\x1b[32m"
_ANSI_YELLOW = "\x1b[33m"
_ANSI_RED = "\x1b[31m"
_STATUS_COLOR = {
    "working": _ANSI_GREEN,
    "winding-down": _ANSI_GREEN,
    "restarting": _ANSI_GREEN,
    "settling": _ANSI_GREEN,
    "idle": _ANSI_YELLOW,
    "idle-with-context-left": _ANSI_YELLOW,
    "warned": _ANSI_YELLOW,
    "danger": _ANSI_YELLOW,
    "blocked:human": _ANSI_YELLOW,
    "codex-unindexed": _ANSI_YELLOW,
    "ctx-stale": _ANSI_YELLOW,
    "foreman-heartbeat-stale": _ANSI_YELLOW,
    "ready-uncertifiable": _ANSI_YELLOW,
    "restart-never-worked": _ANSI_YELLOW,
    "session-gone": _ANSI_RED,
    "shell-prolonged": _ANSI_YELLOW,
    "winddown-starved": _ANSI_YELLOW,
}


def row_color(*, status: str) -> str:
    """The ANSI SGR prefix a row with STATUS is tinted with, or ``""`` for the
    terminal default (``unassigned`` and any unmapped status)."""
    return _STATUS_COLOR.get(status, "")


# The Status cell carries a session-authored NOTE (a `blocked:` reason, or the
# live-outside-tmux detail) that can be arbitrarily long and multi-line. Rendered raw it
# blew up the whole Status column (the column is sized to its widest cell) and broke row
# alignment (maintainer 2026-07-16, after a 705-byte `blocked:` completion summary). So
# the note is flattened to one line and elided in the TABLE; a longer, still-bounded
# preview goes into the `NEEDS YOU` alert (whose full detail the operator reads in the
# tracked pane the alert points at — so a preview is enough and a 705-byte dump is not).
MAX_NOTE_IN_TABLE = 48
MAX_REASON_IN_ALERT = 160


def elide(*, text: str, limit: int) -> str:
    """``text`` flattened to a single line and truncated to ``limit`` chars with a
    trailing ellipsis (the result is never longer than ``limit``).

    ``" ".join(text.split())`` collapses every whitespace run — including newlines, which
    would otherwise split a table row across lines — into single spaces.
    """
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    return flat[: limit - 1].rstrip() + "…"


# --------------------------------------------------------------------------- #
# View + per-track internal state.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, kw_only=True)
class RowView:
    """One rendered table row: the outward projection of a track this tick.

    ``runtime`` is the harness driving the track — ``"claude"`` or ``"codex"`` —
    carried so the table's ``tmux`` column can annotate the session name
    (``livespec (claude)`` / ``livespec1 (codex)``) and the operator can tell at a
    glance which runtime a track is. It is set exactly for a row with a LIVE MANAGED
    pane (``evaluate`` derives it from ``is_codex`` and sets it alongside
    ``tmux=session``); the no-managed-pane rows (``unassigned`` / ``session-gone`` /
    ``live-outside-tmux``) carry ``tmux=None`` and leave it ``None`` — those cells
    render a bare ``—`` with no ``(...)`` (there is no live session, and for the first
    two no runtime either).
    """

    topic: str
    repo: str
    tmux: str | None
    ctx: int | None
    status: str
    note: str | None = None
    runtime: str | None = None
    progress_now: bool = False
    human_wait: bool = False
    round_open: bool = False
    acked: bool = False


def needs_attention(*, row: RowView) -> bool:
    """True if ROW is a track a human must go look at (the ``NEEDS YOU`` membership test).

    A malformed state file is matched on the NOTE rather than the status, because it does
    not have a status of its own: ``evaluate`` reports it by hanging a ``BAD state file``
    note on whatever status the track otherwise has. It is fail-closed (treated as no
    declaration) and needs a human, so it belongs in the block.
    """
    if row.status in ATTENTION_STATUSES:
        return True
    if row.note and row.note.startswith("BAD state file"):
        return True
    # A stranded post-respawn resume (R1) is also a NEEDS-YOU row: the daemon keeps
    # retrying the Enter, but the operator should see it — and keeping it here keeps the
    # `alert` edge-triggered (not re-armed) so it fires once, not every tick.
    return bool(row.note and row.note.startswith(RESUME_PENDING_NOTE))


def tmux_cell(*, row: RowView) -> str:
    """The ``tmux`` column value: the session name annotated with its RUNTIME.

    A row with a live managed pane renders ``<tmux> (<runtime>)`` — ``livespec (claude)``
    / ``livespec1 (codex)`` — so the operator can tell at a glance which harness a track
    is; a no-managed-pane row (``tmux=None``: ``unassigned`` / ``session-gone`` /
    ``live-outside-tmux``) renders the bare ``—`` with no ``(...)``. The annotation is
    part of the CELL, so the column width in :meth:`Supervisor.render` MUST be computed
    from this string, not the bare name, or the column misaligns.

    Single-sourced here so the table (:meth:`Supervisor.render`) and the ``NEEDS YOU``
    block (:meth:`Supervisor._attention_lines`) — the operator's handover surface, where
    knowing the runtime before jumping into a Claude-vs-Codex pane has the same value —
    format the tmux cell identically and cannot drift. The jump command itself still uses
    the bare ``row.tmux`` (``tmux switch-client -t <session>``); only the DISPLAYED cell
    is annotated.
    """
    if row.tmux is None:
        return "—"
    if row.runtime is None:
        return row.tmux
    return f"{row.tmux} ({row.runtime})"
