"""_supervisor_tick — one daemon table/evaluation iteration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_discovery
import _supervisor_foreman
import _supervisor_grooming
import _supervisor_pair
import _supervisor_render
from _supervisor_view import RowView, needs_attention

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["run_tick"]


def run_tick(*, sup: Supervisor, act: bool = True) -> list[RowView]:
    """One loop iteration: build rows, evaluate each, render the table + attention block."""
    views: list[RowView] = []
    for track in sup.build_rows(act=act):
        views.append(sup.evaluate(track=track, act=act))
        supervisor_view = _supervisor_pair.evaluate_supervisor_pair(sup=sup, track=track, act=act)
        if supervisor_view is not None:
            views.append(supervisor_view)
            _supervisor_pair.evaluate_pair_stall(
                sup=sup,
                track=track,
                worker_view=views[-2],
                supervisor_view=supervisor_view,
                act=act,
            )
    views.extend(_supervisor_discovery.unindexed_codex_rows(sup=sup))
    repos = _supervisor_discovery.resolve_watch(sup=sup)
    views.extend(_supervisor_foreman.foreman_rows(sup=sup, repos=repos, act=act))
    views.extend(_supervisor_grooming.grooming_rows(sup=sup, repos=repos, act=act))
    currency = sup.currency_row()
    if currency is not None:
        views.append(currency)
    sup.render(rows=views)
    # Only the DAEMON badges the window. `list` is advertised read-only, so it must
    # not rename the maintainer's window as a side effect of printing a table.
    if act:
        _supervisor_render.refresh_window_name(
            sup=sup, attention=sum(1 for view in views if needs_attention(row=view))
        )
        sup.tick_generation += 1
        try:
            sup.status_snapshot_writer(sup=sup, rows=views)
        except OSError as exc:
            if not sup.status_snapshot_failed:
                sup.surface(message=f"status snapshot write failed: {exc}")
            sup.status_snapshot_failed = True
        else:
            sup.status_snapshot_failed = False
    return views
