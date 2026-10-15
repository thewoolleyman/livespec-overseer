"""Rendering the account table from the rows a rotation pass already polled."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import cast

from caam_decide_context import DecisionContext
from caam_decision import ProfileUsage
from caam_rendering import RenderableProfileUsage, render_table

__all__: list[str] = ["emit_table", "table_lines"]


def emit_table(
    *, context: DecisionContext, profiles: tuple[ProfileUsage, ...], active_name: str
) -> None:
    """Re-render the table so its CURRENT column names the account now in use.

    Carrier R13. The rows are the ones this pass ALREADY polled, so no request is
    made: re-polling would cost one per switch and would also print figures that
    disagree with the table above for reasons having nothing to do with the move.
    Only the active marker is expected to differ between the two renderings.
    """
    for line in table_lines(context=context, profiles=profiles, active_name=active_name):
        context.stdout(line)


def table_lines(
    *, context: DecisionContext, profiles: tuple[ProfileUsage, ...], active_name: str
) -> tuple[str, ...]:
    now_dt = datetime.fromtimestamp(context.now, tz=timezone.utc)
    rows = cast(tuple[RenderableProfileUsage, ...], profiles)
    return tuple(render_table(rows=rows, active_name=active_name, now=now_dt).splitlines())
