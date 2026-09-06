"""Scenario coverage for the daemon's render ORDER: attention block first, table last.

The daemon repaints the whole pane from the home position every tick, so whatever it
writes FIRST is what a pane too short to hold the render loses off the top. The
``Status · Topic · tmux · Ctx% · Repo`` table is the surface the operator scans, and it
used to print above a ``NEEDS YOU`` block that grows with every track wanting attention
— so the table was the thing that scrolled away. Printing the block first makes the
table the LAST thing written, and therefore the thing a short pane keeps.
"""

from __future__ import annotations

from overseer import supervisor
from overseer.test_supervisor_builders import make_supervisor, render_of
from overseer.test_supervisor_fakes import FakeTmux

__all__: list[str] = []

# The render opens with a clear sequence glued onto its first line; the table's own
# first line is `overseer — <iso> — N track(s) - <version>`.
CLEAR_SEQUENCE = "\x1b[3J\x1b[2J\x1b[H"
TABLE_STAMP = "overseer — "


def stamp_index(*, lines: list[str]) -> int:
    """The index of the table's stamp line, found by its prefix rather than by position."""
    return next(
        i for i, ln in enumerate(lines) if ln.removeprefix(CLEAR_SEQUENCE).startswith(TABLE_STAMP)
    )


def test_the_attention_block_prints_above_the_status_table(*, tmp_path):
    """A track wanting the operator puts a NEEDS YOU block above the table, never below."""
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    view = supervisor.RowView(topic="stuck", repo="/r", tmux="s", ctx=9, status="danger")

    lines = render_of(sup=sup, views=[view]).splitlines()

    needs_you = next(i for i, ln in enumerate(lines) if "NEEDS YOU" in ln)
    assert needs_you < stamp_index(lines=lines)


def test_the_empty_attention_block_prints_above_the_status_table(*, tmp_path):
    """The `NEEDS YOU: nothing` block takes the same position — the order is not
    conditional on there being anything to report, so the table's place is stable."""
    sup = make_supervisor(tmp_path=tmp_path, fake=FakeTmux())
    view = supervisor.RowView(topic="fine", repo="/r", tmux="s", ctx=90, status="working")

    lines = render_of(sup=sup, views=[view]).splitlines()

    assert next(i for i, ln in enumerate(lines) if "NEEDS YOU: nothing" in ln) < stamp_index(
        lines=lines
    )
