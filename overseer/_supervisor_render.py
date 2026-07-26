"""_supervisor_render — the operator's live table and the NEEDS YOU block.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. This module owns the two SURFACES the daemon paints each tick — the
``Status · Topic · tmux · Ctx% · Repo`` table, and the ``NEEDS YOU`` block under it —
plus the tmux window-name badge, which is the only overseer surface visible without
looking at the overseer window.

Free functions taking the ``Supervisor`` as a parameter, per the split's shape: a class
cannot span modules and this repo bans inheritance, so the daemon's method groups move
out as collaborators rather than as mixins. `Supervisor` is imported under
``TYPE_CHECKING`` only — the annotation resolves for pyright-strict while no runtime
import cycle exists.

:func:`attention_lines` takes NO supervisor: it is a pure function of the rows, and
saying so in the signature is the point. :func:`render_table` needs only ``sup.out``,
and :func:`refresh_window_name` needs ``own_pane`` / ``last_window_name`` / ``tmux``.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

import registry
from _supervisor_config import WINDOW_NAME, iso_now
from _supervisor_view import (
    ANSI_RESET,
    MAX_NOTE_IN_TABLE,
    MAX_REASON_IN_ALERT,
    RowView,
    elide,
    needs_attention,
    row_color,
    tmux_cell,
)
from version import APP_VERSION

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "attention_lines",
    "refresh_window_name",
    "render_table",
]


def render_table(sup: Supervisor, rows: Iterable[RowView]) -> None:
    """Clear the screen and print the live ``Status · Topic · tmux · Ctx% · Repo`` table.

    Re-rendered from live captures every tick, and stamped with the current
    wall-clock time, so a ``/clear``-orphaned pane can never freeze on a
    stale "all idle" snapshot (the second historical failure mode). Status leads
    (maintainer 2026-07-15): it is the column the operator scans first.

    Each data row is tinted by its status (``row_color``) so the operator can
    scan the list by hue — green working, yellow idle/waiting, red broken. The
    color wraps the WHOLE padded line (never a cell), so alignment is untouched,
    and is emitted ONLY to a TTY (``out.isatty()``): piped ``list`` output and the
    beside-tests' ``StringIO`` stay plain. The header + separator stay uncolored.
    """
    rows = list(rows)
    lines: list[str] = []
    lines.append(f"overseer — {iso_now()} — {len(rows)} track(s) - {APP_VERSION}")
    header = ("Status", "Topic", "tmux", "Ctx%", "Repo")
    table: list[tuple[str, ...]] = [header]
    for row in rows:
        # Elide the session-authored note so an over-long / multi-line value cannot
        # blow up the Status column width or break the row (the full note still
        # reaches the NEEDS YOU block below).
        note = elide(row.note, MAX_NOTE_IN_TABLE) if row.note else None
        table.append(
            (
                row.status if not note else f"{row.status} ({note})",
                row.topic,
                # The tmux cell is the session name annotated with its runtime
                # (`livespec (claude)`); the column width is computed below from THIS
                # already-annotated string (the `max(len(...))` over `table`), so the
                # column stays aligned — never widen it from the bare name.
                tmux_cell(row),
                "—" if row.ctx is None else f"{row.ctx}%",
                registry.repo_slug(row.repo),
            )
        )
    widths = [max(len(r[i]) for r in table) for i in range(len(header))]
    isatty = getattr(sup.out, "isatty", None)
    use_color = bool(isatty) and isatty()
    for i, cells in enumerate(table):
        line = "  ".join(cell.ljust(widths[j]) for j, cell in enumerate(cells))
        if i == 0:
            lines.append(line)
            lines.append("  ".join("-" * widths[j] for j in range(len(header))))
            continue
        # table[i] for i >= 1 is the projection of rows[i - 1]; tint by its raw
        # status (not the note-decorated cell text).
        color = row_color(rows[i - 1].status) if use_color else ""
        lines.append(f"{color}{line}{ANSI_RESET}" if color else line)
    lines.extend(attention_lines(rows))
    # Clear scrollback + screen + home, then the table.
    _ = sup.out.write("\x1b[3J\x1b[2J\x1b[H" + "\n".join(lines) + "\n")
    sup.out.flush()


def attention_lines(rows: list[RowView]) -> list[str]:
    """The ``NEEDS YOU`` block: the rows a human must act on, and where to go.

    THIS is the answer to "what needs attention?", and it lives here — in the daemon's
    re-rendered table — for two reasons that the bottom pane cannot satisfy:

    - it inherits the tick's refresh, so a track the operator resolves DISAPPEARS from
      it on the next render (it can never go stale, which is the whole bug: an LLM
      pane prints text ONCE and that text then ages silently); and
    - it costs no tokens, so it can refresh forever.

    The table alone was not enough: dozens of `unassigned` rows buried the two that
    actually wanted the operator. This filters to exactly those, and carries the same
    jump command `alert` does, so the block is a sufficient handover on its own.

    Each row's coordinates are LABELED (`topic: … | tmux: … | repo: …`) so the operator
    never has to guess which unlabeled token is which — a bare `autonomous-mode
    (livespec)` said WHAT but the tmux session (WHERE to go) had to be inferred from the
    jump line (maintainer 2026-07-14).
    """
    attention = [row for row in rows if needs_attention(row)]
    lines = [""]
    if not attention:
        lines.append("NEEDS YOU: nothing — every tracked session is healthy.")
        return lines
    lines.append(f"NEEDS YOU ({len(attention)}):")
    for row in attention:
        # Elide the note here too: a session can write an arbitrarily long `blocked:`
        # reason, and the full text lives in the pane this line points at.
        detail = f" — {elide(row.note, MAX_REASON_IN_ALERT)}" if row.note else ""
        # Annotate the tmux coordinate with the runtime the SAME way the table does
        # (`tmux_cell`), so the operator knows whether they are jumping into a Claude
        # or a Codex pane before they do. The jump command itself stays the bare
        # session name (`tmux switch-client -t` takes no runtime).
        coords = (
            f"topic: {row.topic} | tmux: {tmux_cell(row)} "
            f"| repo: {registry.repo_slug(row.repo)}"
        )
        lines.append(f"  ! {coords} — {row.status}{detail}")
        if row.tmux:
            lines.append(f"      jump: tmux switch-client -t {row.tmux}")
    return lines


def refresh_window_name(sup: Supervisor, attention: int) -> None:
    """Badge the attention count onto the tmux WINDOW name (``overseer`` → ``overseer(2!)``).

    The only overseer surface visible WITHOUT looking at the overseer window: tmux
    renders the window name in the status bar of whatever session the operator is
    currently attached to. So a track that wants them is noticed while they are heads-
    down in a different session — no pane switch, no polling, no tokens.

    Only written when the count CHANGES, and a no-op when the daemon is not in tmux
    (``own_pane`` unset).
    """
    pane = sup.own_pane
    if not pane:
        return
    name = f"{WINDOW_NAME}({attention}!)" if attention else WINDOW_NAME
    if name == sup.last_window_name:
        return
    if sup.tmux.rename_window(pane=pane, name=name):
        sup.last_window_name = name
