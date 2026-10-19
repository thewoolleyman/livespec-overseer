"""_supervisor_done_track — which tracks the daemon may not act on.

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

import registry
import signals

__all__: list[str] = ["is_done_track"]


def is_done_track(*, track: registry.Track) -> bool:
    """Whether this track is DONE, and so must be observed read-only this tick.

    The declaration is read from the track's own canonical state path, exactly as the
    cascade reads it, so the two cannot reach opposite answers about the same file. A
    malformed or absent value is not a ``done`` declaration and does not make a track
    done.
    """
    state = signals.read_state(repo=track.repo, topic=track.topic)
    return state is not None and state.token == signals.STATE_DONE
