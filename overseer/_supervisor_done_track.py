"""_supervisor_done_track — which tracks the daemon may not act on, and how they render.

SPECIFICATION v061, spec.md, the terminal declaration: a DONE TRACK is a track holding
a standing ``done`` declaration, or a plan track whose plan directory is archived while
its recorded session still exists. The daemon performs NO act on one —
every observation of it is read-only, exactly as the ``list`` path is — so its state
file, its round record and its pane are all left alone, and it is spent zero model
turns for as long as it stays done.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. The question is asked ONCE per track per tick, in :mod:`_supervisor_tick`, and
BEFORE the evaluation, because the acts the rule forbids are not all inside the
cascade's own ``done`` leg: the self-healing resume retry, the held-delivery release
and the compaction-latch record all run in the evaluation's PROLOGUE, ahead of every
guard. Withholding ``act`` from the whole evaluation is the one place that reaches all
of them at once.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import registry
import signals
from _supervisor_view import RowView, needs_attention

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = ["is_done_track", "quiet_done_row"]


def is_done_track(*, sup: Supervisor, track: registry.Track) -> bool:
    """Whether this track is DONE, and so must be observed read-only this tick.

    Two independent ways in, and the ARCHIVAL one is asked first because it holds
    whatever the state file says: ``sup.archived_live`` is this tick's retention set,
    refreshed by the discovery pass that ran just above the caller, so a plan whose
    directory has gone to ``plan/archive/`` while its recorded session still exists is
    already in it.

    The declaration is read from the track's own canonical state path, exactly as the
    cascade reads it, so the two cannot reach opposite answers about the same file. A
    malformed or absent value is not a ``done`` declaration and does not make an
    unarchived track done.
    """
    if (registry.norm(repo=track.repo), track.topic) in sup.archived_live:
        return True
    state = signals.read_state(repo=track.repo, topic=track.topic)
    return state is not None and state.token == signals.STATE_DONE


def quiet_done_row(*, row: RowView) -> RowView:
    """Project a done track onto the quiet terminal ``done`` status.

    Live gate evidence still outranks ``done`` for REPORTING, so a row whose pane shows
    an open structured picker is left exactly as the cascade classified it: a human is
    being waited on whatever the track declared, and for an archived track that gate is
    the ONLY thing that can make it attention at all. Report-only, though — the caller
    has already withheld ``act``, so surfacing it delivers nothing.

    A NOTE that would otherwise carry the row into ``NEEDS YOU`` is dropped with it.
    That is not cosmetic tidying: an archived plan's state file can hold anything its
    session last wrote — nothing, a stale declaration, or a malformed value — and the
    ratified rule is that such a track is an attention member ONLY through live gate
    evidence. A `BAD state file` note left on the row would make it one through the
    note instead, which is the shape measured on `caam-mixed-plan-capacity`
    (plan research 001): an archived, finished track sitting red in the operator's
    attention block over a value nobody is going to act on.
    """
    if row.picker_open:
        return row
    quiet = dataclasses.replace(row, status=signals.STATE_DONE)
    if not needs_attention(row=quiet):
        return quiet
    return dataclasses.replace(quiet, note=None)
