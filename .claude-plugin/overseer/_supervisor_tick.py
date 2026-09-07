"""_supervisor_tick — one daemon table/evaluation iteration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import _supervisor_attention
import _supervisor_discovery
import _supervisor_dispatch_quiet
import _supervisor_epic_heal
import _supervisor_mapping_health
import _supervisor_pair
import _supervisor_reexec
import _supervisor_render
from _supervisor_view import RowView, needs_attention

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["run_tick"]


def run_tick(*, sup: Supervisor, act: bool = True) -> list[RowView]:
    """One loop iteration: build rows, evaluate each, render the table + attention block."""
    views: list[RowView] = []
    null_added_at_keys: frozenset[_supervisor_mapping_health.MappingKey] = (
        _supervisor_mapping_health.explicit_null_added_at_keys(store_path=sup.store_path)
        if not act
        else frozenset()
    )
    tracks = sup.build_rows(act=act)
    if act:
        # Heal a derivable-but-null plan epic EAGERLY, before evaluation — persist the
        # anchor-derived epic so no track has to reach the restart-interlock boundary
        # (which a session-gone/idle-and-fine track never does) before its
        # mapping-unusable row is cured (overseer-fdau). Kept OUT of `build_rows`
        # because that discovery pass must stay directory-only and never read a
        # `plan/<topic>/` anchor file; the read-only `list` tick (act=False) never
        # heals, so it too stays plan-file-free. Bounded to one anchor read per null row.
        tracks = _supervisor_epic_heal.heal_derivable_epics(sup=sup, rows=tracks)
    for track in tracks:
        row = sup.evaluate(track=track, act=act)
        if not act:
            row = _supervisor_mapping_health.apply_mapping_health(
                track=track, row=row, null_added_at_keys=null_added_at_keys
            )
        views.append(row)
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
    currency = sup.currency_row()
    if currency is not None:
        views.append(currency)
    dispatch_quiet = _supervisor_dispatch_quiet.apply_dispatch_quiet_with_waiters(rows=views)
    if dispatch_quiet is not None:
        views.append(dispatch_quiet)
    surface_attention = _supervisor_attention.render_surface_attention(sup=sup, act=act)
    _supervisor_render.render_table(sup=sup, rows=views, surface_attention=surface_attention)
    if act:
        _finish_acting_tick(sup=sup, views=views, surface_attention=surface_attention is not None)
    return views


def _finish_acting_tick(
    *, sup: Supervisor, views: list[RowView], surface_attention: bool = False
) -> None:
    """The DAEMON-only tail of an acting tick: badge, stamp, snapshot, then self-replace.

    Split out of :func:`run_tick` so that function stays inside the statement soft
    band; the sequence is unchanged. `list` is advertised read-only, so none of this
    may fire on a read-only tick -- it must not rename the maintainer's window as a
    side effect of printing a table. Re-exec stays LAST so the process image is only
    replaced after this tick's snapshot has been published.
    """
    attention = sum(1 for view in views if needs_attention(row=view))
    if surface_attention:
        _supervisor_render.refresh_window_name(sup=sup, attention=attention, surface_attention=True)
    else:
        _supervisor_render.refresh_window_name(sup=sup, attention=attention)
    sup.tick_generation += 1
    try:
        sup.status_snapshot_writer(sup=sup, rows=views)
    except OSError as exc:
        if not sup.status_snapshot_failed:
            sup.surface(message=f"status snapshot write failed: {exc}")
        sup.status_snapshot_failed = True
    else:
        sup.status_snapshot_failed = False
    _supervisor_reexec.maybe_reexec(sup=sup, rows=views)
