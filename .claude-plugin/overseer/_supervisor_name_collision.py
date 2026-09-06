"""_supervisor_name_collision — an ABSENT session is not a SQUATTED tmux name.

A private collaborator of :mod:`supervisor`; see that module's header for the whole
split. It answers exactly one question, at the point a track is about to be reported as
having no session at all: **is this topic's tmux name FREE, or is it held by a pane
working in some OTHER repo?**

WHY THE TWO MUST NOT SHARE A ROW (`overseer-5p6d6g`, measured 2026-08-21T23:10:23Z). The
daemon resolves a topic to a session by NAME **and** repo cwd, so a live tmux session
named exactly like the topic but sitting in a different repo is correctly not this
track's session — and the row collapsed to a plain ``session-gone``. That row was
accurate and unreadable: nothing on it separated "this topic has no session" from "this
topic's name is taken by something else", and the two point at OPPOSITE remedies. The
honest reading suggests STARTING a session; the misreading suggests RESTARTING a live
foreign process.

The measured instance: topic ``caam-anthropic-loop`` tracked for
``/data/projects/livespec-overseer``, while a live tmux session of exactly that name ran
the maintainer's quota-rotation watcher in ``/data/projects/vps-info`` — the very thing
the plan thread of that name was reproducing, which is why the two names matched at all.
A seat read the row as "our session, drifted cwd" and asked that foreign session to wind
down and declare ``ready`` so it could be "restarted correctly seated in this repo".
Both halves were destructive: the restart would have broken a session whose project
skill resolves only from its own project, and the declaration would have written this
topic's state file on behalf of a session that does not own it — corrupting the one file
the cardinal rule depends on. The session refused. The next one may not.

Plan topics here are frequently NAMED after the external thing they reproduce or
supervise, so the collision is structural rather than a one-off. The ambiguity is
therefore resolved ON THE ROW, and the row says what to do about the holder: nothing.

**This module never ACTS.** It reads a pane's cwd and returns a status. The identity gate
(:func:`_supervisor_observe.pane_is_managed`) is untouched and still rejects that pane for
every capture, injection, paste and respawn — what changes is only what the operator is
TOLD, exactly as the ``live-outside-tmux`` and ``live-name-mismatch`` softeners beside it.

**Matching is by EXACT session name, and that is load-bearing.** A prefix or substring
match would sweep in a near-miss neighbour — ``caam-anthropic-loop-legacy`` is precisely
what the host held once the measured collision was resolved by renaming the foreign
session out of the way — and report a squat that does not exist.
:meth:`tmuxio.TmuxIO.session_exists` is exact membership in ``list-sessions`` rather than
the prefix-matching ``has-session`` (adversarial-review blocker B1), so the exactness is
INHERITED here rather than re-implemented, and it stays correct only for as long as that
does.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import registry
import signals
from _supervisor_view import RowView

if TYPE_CHECKING:
    from _supervisor_core import Supervisor

__all__: list[str] = [
    "NAME_COLLISION_STATUS",
    "foreign_repo_pane_path",
    "name_collision_row",
]

# The row status. It is NOT red: `session-gone` remains the only red status, and this is
# not lost work — it is a name that needs a human to disentangle. Registered in
# `_supervisor_view.ATTENTION_STATUSES` so the row reaches the `NEEDS YOU` block, because
# nothing else will surface it: the track has no pane to alert about.
NAME_COLLISION_STATUS = "name-collision"


def foreign_repo_pane_path(*, sup: Supervisor, repo: str, session: str) -> str | None:
    """The cwd of the pane holding tmux session ``session``, when it is OUTSIDE ``repo``.

    ``None`` means "no collision", and it covers three different ways of not being one:
    the name is free (no session of that exact name), the session exists but resolves to
    no pane, or the holder is working inside this track's OWN repo. The last is an
    ordinary no-managed-pane case — our session exited to a bare shell, say — and reading
    it as a squat would report the track's own dead pane as a stranger.
    """
    if not sup.tmux.session_exists(session=session):
        return None
    target = sup.tmux.pane_id(session=session)
    if target is None:
        return None
    cwd = sup.tmux.pane_current_path(session=target)
    if cwd is None or signals.path_in_repo(pane_current_path=cwd, repo=repo):
        return None
    return cwd


def name_collision_row(*, sup: Supervisor, track: registry.Track, session: str) -> RowView | None:
    """The row for a track whose tmux NAME is held by a pane in a different repo, or None.

    ``tmux=None`` like every other no-managed-pane row: the cell means *the tmux session
    HOLDING this track*, and no session holds it — the name is a stranger's. The holder's
    cwd goes in the NOTE instead, because that is the fact that tells the two cases apart,
    and the note ends by naming the remedy that must NOT be taken. The operator's real
    options are to rename this plan's session, or to start it under a free name; both are
    decisions about OUR track, and neither touches the pane.
    """
    cwd = foreign_repo_pane_path(sup=sup, repo=track.repo, session=session)
    if cwd is None:
        return None
    return RowView(
        topic=track.topic,
        repo=track.repo,
        tmux=None,
        ctx=None,
        status=NAME_COLLISION_STATUS,
        note=(
            f"tmux name {session!r} is held by a pane in {cwd}, outside this track's repo — "
            f"this topic has NO session here; do not restart or rename that pane"
        ),
    )
