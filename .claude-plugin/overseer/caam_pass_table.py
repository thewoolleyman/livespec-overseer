"""The account table a rotation pass renders, and the re-render a switch earns.

Moved out of `caam_anthropic_pass` whole, callers and all: rendering rows is a
concern of its own, and the pass module it left is named for orchestrating one
pass rather than for drawing it. The two entry points take the figures they
render -- the rows, the account to mark current, and the pass clock -- rather than
the pass context, so this module can be read without the pass and the pass
without it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import cast

from caam_anthropic_finish import LineWriter
from caam_decision import ProfileUsage
from caam_rendering import RenderableProfileUsage, render_table

__all__: list[str] = [
    "emit_pass_table",
    "pass_table_lines",
]


def emit_pass_table(
    *,
    stdout: LineWriter,
    profiles: tuple[ProfileUsage, ...],
    active_name: str,
    now: float,
) -> None:
    """Re-render the table so its CURRENT column names the account now in use.

    Carrier R13. The rows are the ones this pass ALREADY polled, so no request is
    made: re-polling would cost one per switch and would also print figures that
    disagree with the table above for reasons having nothing to do with the move.
    Only the active marker is expected to differ between the two renderings.
    """
    for line in pass_table_lines(profiles=profiles, active_name=active_name, now=now):
        stdout(line)


def pass_table_lines(
    *, profiles: tuple[ProfileUsage, ...], active_name: str, now: float
) -> tuple[str, ...]:
    now_dt = datetime.fromtimestamp(now, tz=timezone.utc)
    rows = cast(tuple[RenderableProfileUsage, ...], profiles)
    return tuple(render_table(rows=rows, active_name=active_name, now=now_dt).splitlines())
